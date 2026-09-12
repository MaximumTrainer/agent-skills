#!/usr/bin/env python3
"""
Tests for tools/bump_skill_versions.py.

Unit tests cover the pure logic. The integration tests build a throwaway git
repository, install the real hook into it, and make real commits — which is the
only way to prove the staged version actually lands in the commit rather than in
a dirty index afterwards.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "bump_skill_versions.py"
HOOK = REPO / ".githooks" / "pre-commit"


def load_module():
    spec = importlib.util.spec_from_file_location("bump_skill_versions", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bsv = load_module()


# The em-dash and the other non-ASCII characters here are load-bearing. Real
# SKILL.md files are full of them, and an ASCII-only fixture hid a decoding bug
# that silently disabled every version bump: subprocess text=True decodes with
# the locale codec (cp1252 on default Windows Python), so `git show` blew up in a
# reader thread, HEAD content came back empty, and every edited skill looked new.
SKILL_TEMPLATE = """---
name: {name}
description: A test skill used by the version-bump tests — long enough to look real.
license: MIT
metadata:
  version: "{version}"
---

# {name}

{body} — with an em-dash, a “curly quote”, ≥ and °C.
"""


class TestBump(unittest.TestCase):
    def test_patch(self):
        self.assertEqual(bsv.bump("1.0.0", "patch"), "1.0.1")
        self.assertEqual(bsv.bump("1.2.9", "patch"), "1.2.10")

    def test_minor_resets_patch(self):
        self.assertEqual(bsv.bump("1.2.9", "minor"), "1.3.0")

    def test_major_resets_minor_and_patch(self):
        self.assertEqual(bsv.bump("2.7.3", "major"), "3.0.0")

    def test_rejects_non_semver(self):
        for bad in ("1.0", "v1.0.0", "1.0.0-rc1", "latest", ""):
            with self.assertRaises(ValueError):
                bsv.bump(bad, "patch")


class TestFindVersion(unittest.TestCase):
    def test_finds_quoted_version(self):
        text = SKILL_TEMPLATE.format(name="a", version="1.2.3", body="x")
        version, line = bsv.find_version(text)
        self.assertEqual(version, "1.2.3")
        self.assertTrue(text.split("\n")[line].strip().startswith("version:"))

    def test_finds_unquoted_version(self):
        text = "---\nname: a\nmetadata:\n  version: 2.0.1\n---\n\n# a\n"
        self.assertEqual(bsv.find_version(text)[0], "2.0.1")

    def test_ignores_version_outside_metadata(self):
        text = "---\nname: a\nversion: 9.9.9\n---\n\n# a\n"
        self.assertEqual(bsv.find_version(text), (None, None))

    def test_ignores_version_after_metadata_block_ends(self):
        text = "---\nname: a\nmetadata:\n  author: x\nlicense: MIT\nversion: 9.9.9\n---\n\n# a\n"
        self.assertEqual(bsv.find_version(text), (None, None))

    def test_no_frontmatter(self):
        self.assertEqual(bsv.find_version("# just a heading\n"), (None, None))

    def test_body_mention_not_matched(self):
        text = SKILL_TEMPLATE.format(name="a", version="1.0.0", body="  version: 5.5.5")
        self.assertEqual(bsv.find_version(text)[0], "1.0.0")


class TestReplaceVersion(unittest.TestCase):
    def test_preserves_quoting_and_indent(self):
        text = SKILL_TEMPLATE.format(name="a", version="1.0.0", body="x")
        _, line = bsv.find_version(text)
        out = bsv.replace_version(text, line, "1.0.1")
        self.assertIn('  version: "1.0.1"', out)
        self.assertEqual(bsv.find_version(out)[0], "1.0.1")

    def test_preserves_absence_of_quotes(self):
        text = "---\nname: a\nmetadata:\n  version: 1.0.0\n---\n\n# a\n"
        _, line = bsv.find_version(text)
        self.assertIn("  version: 1.0.1", bsv.replace_version(text, line, "1.0.1"))

    def test_changes_nothing_else(self):
        text = SKILL_TEMPLATE.format(name="a", version="1.0.0", body="body line")
        _, line = bsv.find_version(text)
        out = bsv.replace_version(text, line, "1.0.1")
        self.assertEqual(len(text.split("\n")), len(out.split("\n")))
        self.assertIn("body line", out)


class TestTouchedSkills(unittest.TestCase):
    skills = ["alpha", "beta"]

    def test_matches_skill_md(self):
        self.assertEqual(bsv.touched_skills(["alpha/SKILL.md"], self.skills), ["alpha"])

    def test_matches_nested_file(self):
        self.assertEqual(bsv.touched_skills(["beta/references/x.md"], self.skills), ["beta"])

    def test_ignores_non_skill_paths(self):
        self.assertEqual(bsv.touched_skills(["README.md", "tools/x.py", ".githooks/pre-commit"], self.skills), [])

    def test_deduplicates_and_sorts(self):
        paths = ["beta/SKILL.md", "beta/scripts/s.sh", "alpha/SKILL.md"]
        self.assertEqual(bsv.touched_skills(paths, self.skills), ["alpha", "beta"])


class HookHarness(unittest.TestCase):
    """Builds a real git repo with the real tool and hook installed."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="skillhook-"))
        self.git("init", "-q", ".")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        (self.dir / "tools").mkdir()
        (self.dir / ".githooks").mkdir()
        shutil.copy(TOOL, self.dir / "tools" / "bump_skill_versions.py")
        shutil.copy(HOOK, self.dir / ".githooks" / "pre-commit")
        os.chmod(self.dir / ".githooks" / "pre-commit", 0o755)
        self.git("config", "core.hooksPath", ".githooks")
        # start on main regardless of the machine's init.defaultBranch
        self.git("checkout", "-q", "-B", "main")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args, env=None):
        full = dict(os.environ)
        full.pop("SKILL_BUMP", None)
        if env:
            full.update(env)
        # encoding pinned for the same reason as in the tool: text=True would
        # decode git output with the locale codec and choke on the non-ASCII
        # characters in the fixture.
        result = subprocess.run(
            ["git", *args],
            cwd=self.dir,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=full,
        )
        return result

    def write_skill(self, name, version="1.0.0", body="original body"):
        d = self.dir / name
        d.mkdir(exist_ok=True)
        (d / "SKILL.md").write_text(
            SKILL_TEMPLATE.format(name=name, version=version, body=body), encoding="utf-8"
        )

    def committed_version(self, name):
        out = self.git("show", f"HEAD:{name}/SKILL.md").stdout
        return bsv.find_version(out.replace("\r\n", "\n"))[0]

    def worktree_version(self, name):
        text = (self.dir / name / "SKILL.md").read_text(encoding="utf-8")
        return bsv.find_version(text.replace("\r\n", "\n"))[0]

    def dirty(self):
        return self.git("status", "--porcelain").stdout.strip()

    def commit_all(self, message, env=None):
        self.git("add", "-A")
        return self.git("commit", "-m", message, env=env)


class TestHookIntegration(HookHarness):
    def test_new_skill_keeps_declared_version(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.assertEqual(self.committed_version("alpha"), "1.0.0")
        self.assertEqual(self.dirty(), "")

    def test_edit_bumps_patch_and_lands_in_the_commit(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.write_skill("alpha", "1.0.0", body="edited body")
        self.commit_all("edit alpha")
        # the crucial assertion: the bump is in the commit, not left staged
        self.assertEqual(self.committed_version("alpha"), "1.0.1")
        self.assertEqual(self.worktree_version("alpha"), "1.0.1")
        self.assertEqual(self.dirty(), "")

    def test_only_touched_skills_bump(self):
        self.write_skill("alpha", "1.0.0")
        self.write_skill("beta", "1.0.0")
        self.commit_all("add both")
        self.write_skill("alpha", "1.0.0", body="edited")
        self.commit_all("edit alpha only")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")
        self.assertEqual(self.committed_version("beta"), "1.0.0")

    def test_nested_file_change_bumps_the_skill(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        refs = self.dir / "alpha" / "references"
        refs.mkdir()
        (refs / "extra.md").write_text("notes\n", encoding="utf-8")
        self.commit_all("add a reference file")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")

    def test_skill_bump_env_selects_minor(self):
        self.write_skill("alpha", "1.4.7")
        self.commit_all("add alpha")
        self.write_skill("alpha", "1.4.7", body="edited")
        self.commit_all("feature", env={"SKILL_BUMP": "minor"})
        self.assertEqual(self.committed_version("alpha"), "1.5.0")

    def test_manual_bump_is_respected(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.write_skill("alpha", "2.0.0", body="rewritten")
        self.commit_all("manual major bump")
        self.assertEqual(self.committed_version("alpha"), "2.0.0")

    def test_version_only_change_does_not_rebump(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        path = self.dir / "alpha" / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        _, line = bsv.find_version(text)
        path.write_text(bsv.replace_version(text, line, "1.0.5"), encoding="utf-8")
        self.commit_all("set version explicitly")
        self.assertEqual(self.committed_version("alpha"), "1.0.5")

    def test_amend_bumps_again_documented_limitation(self):
        """
        git does not tell pre-commit that a commit is an --amend: there is no
        env var, and COMMIT_EDITMSG still holds the *previous* message at that
        point. Amending a commit that already bumped therefore bumps again.
        This test pins that behaviour so it stays documented rather than
        surprising; use SKILL_VERSION_SKIP=1 to amend without bumping.
        """
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.write_skill("alpha", "1.0.0", body="edited")
        self.commit_all("edit")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")
        self.write_skill("alpha", "1.0.1", body="edited again")
        self.git("add", "-A")
        self.git("commit", "--amend", "-m", "edit, amended")
        self.assertEqual(self.committed_version("alpha"), "1.0.2")

    def test_amend_with_skip_env_keeps_the_version(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.write_skill("alpha", "1.0.0", body="edited")
        self.commit_all("edit")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")
        self.write_skill("alpha", "1.0.1", body="edited again")
        self.git("add", "-A")
        self.git("commit", "--amend", "-m", "edit, amended", env={"SKILL_VERSION_SKIP": "1"})
        self.assertEqual(self.committed_version("alpha"), "1.0.1")

    def test_other_branch_is_not_versioned(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.git("checkout", "-q", "-b", "feature")
        self.write_skill("alpha", "1.0.0", body="edited on a branch")
        self.commit_all("edit on feature")
        self.assertEqual(self.committed_version("alpha"), "1.0.0")
        self.assertEqual(self.dirty(), "")

    def test_configured_branch_is_honoured(self):
        self.git("config", "skills.versionBranch", "release")
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.git("checkout", "-q", "-b", "release")
        self.write_skill("alpha", "1.0.0", body="edited on release")
        self.commit_all("edit on release")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")

    def test_empty_branch_config_versions_everywhere(self):
        self.git("config", "skills.versionBranch", "")
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.git("checkout", "-q", "-b", "anything")
        self.write_skill("alpha", "1.0.0", body="edited")
        self.commit_all("edit anywhere")
        self.assertEqual(self.committed_version("alpha"), "1.0.1")

    def test_no_verify_skips_the_hook(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        self.write_skill("alpha", "1.0.0", body="edited")
        self.git("add", "-A")
        self.git("commit", "--no-verify", "-m", "edit without hooks")
        self.assertEqual(self.committed_version("alpha"), "1.0.0")

    def test_non_skill_change_bumps_nothing(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        (self.dir / "README.md").write_text("docs\n", encoding="utf-8")
        self.commit_all("docs only")
        self.assertEqual(self.committed_version("alpha"), "1.0.0")
        self.assertEqual(self.dirty(), "")

    def test_crlf_file_keeps_crlf(self):
        self.write_skill("alpha", "1.0.0")
        self.commit_all("add alpha")
        path = self.dir / "alpha" / "SKILL.md"
        raw = path.read_text(encoding="utf-8").replace("original body", "edited body")
        path.write_bytes(raw.replace("\n", "\r\n").encode("utf-8"))
        self.commit_all("edit with crlf")
        self.assertEqual(self.worktree_version("alpha"), "1.0.1")
        self.assertIn(b"\r\n", path.read_bytes())


class TestCheckMode(HookHarness):
    def run_check(self):
        return subprocess.run(
            ["python", str(self.dir / "tools" / "bump_skill_versions.py"), "--check"],
            cwd=self.dir,
            capture_output=True,
            text=True,
        )

    def test_passes_on_valid_skills(self):
        self.write_skill("alpha", "1.0.0")
        self.write_skill("beta", "2.3.4")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checked 2 skill(s); 0 problem(s)", result.stdout)

    def test_fails_on_missing_version(self):
        d = self.dir / "broken"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: broken\n---\n\n# broken\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no metadata.version", result.stderr)

    def test_fails_on_non_semver(self):
        self.write_skill("alpha", "1.0")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not MAJOR.MINOR.PATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
