#!/usr/bin/env python3
"""
Tests for tools/build_catalogue.py and skill-exchange/scripts/skills.py.

The network is stubbed by replacing skills.fetch with a reader over a fake
catalogue on disk, so the real pull/status/diff/contribute code paths run.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import io
import os
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalogue_tool = load(REPO / "tools" / "build_catalogue.py", "build_catalogue")
skills = load(REPO / "skill-exchange" / "scripts" / "skills.py", "skills")


SKILL_MD = """---
name: {name}
description: {desc}
license: MIT
metadata:
  version: "{version}"
---

# {name}

Body text - with an em-dash and a "curly quote".
"""


class TestFrontmatter(unittest.TestCase):
    def test_reads_nested_metadata_version(self):
        fm = catalogue_tool.frontmatter(SKILL_MD.format(name="a", desc="d", version="1.2.3"))
        self.assertEqual(fm["name"], "a")
        self.assertEqual(fm["metadata.version"], "1.2.3")
        self.assertEqual(fm["license"], "MIT")

    def test_missing_frontmatter(self):
        self.assertEqual(catalogue_tool.frontmatter("# heading\n"), {})


class TestCatalogueOfThisRepo(unittest.TestCase):
    """The committed catalogue.json must match the SKILL.md files."""

    def test_catalogue_is_not_stale(self):
        built = catalogue_tool.serialise(catalogue_tool.build())
        current = (REPO / "catalogue.json").read_text(encoding="utf-8")
        self.assertEqual(
            built, current,
            "catalogue.json is out of date - run python3 tools/build_catalogue.py",
        )

    def test_catalogue_is_deterministic(self):
        self.assertEqual(
            catalogue_tool.serialise(catalogue_tool.build()),
            catalogue_tool.serialise(catalogue_tool.build()),
        )

    def test_contains_no_timestamp_or_sha(self):
        # a non-deterministic field would make the drift check fail every run
        text = (REPO / "catalogue.json").read_text(encoding="utf-8")
        for banned in ("generated", "timestamp", "sha", "date"):
            self.assertNotIn(f'"{banned}"', text.lower())

    def test_every_skill_has_name_version_description(self):
        data = json.loads((REPO / "catalogue.json").read_text(encoding="utf-8"))
        self.assertGreater(len(data["skills"]), 0)
        for s in data["skills"]:
            self.assertTrue(s["name"], s)
            self.assertRegex(s["version"], r"^\d+\.\d+\.\d+$")
            self.assertGreater(len(s["description"]), 40, s["name"])
            self.assertIn("SKILL.md", s["files"])

    def test_skill_exchange_is_in_the_catalogue(self):
        data = json.loads((REPO / "catalogue.json").read_text(encoding="utf-8"))
        entry = next(s for s in data["skills"] if s["name"] == "skill-exchange")
        self.assertIn("scripts/skills.py", entry["files"])


class ExchangeHarness(unittest.TestCase):
    """A fake upstream catalogue plus a fake consuming repo."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="exchange-"))
        self.upstream = {}
        self.consumer = self.dir / "consumer"
        (self.consumer / ".claude" / "skills").mkdir(parents=True)
        self._real_fetch = skills.fetch
        skills.fetch = self.fake_fetch

    def tearDown(self):
        skills.fetch = self._real_fetch
        shutil.rmtree(self.dir, ignore_errors=True)

    def fake_fetch(self, *args):
        # signature: fetch(source, ref, path)
        path = args[-1]
        if path not in self.upstream:
            raise SystemExit(f"error: fake 404 for {path}")
        return self.upstream[path]

    def publish(self, name, version="1.0.0", extra=None):
        self.upstream[f"{name}/SKILL.md"] = SKILL_MD.format(
            name=name, desc="A catalogue skill used in tests, long enough to be real.", version=version
        )
        files = ["SKILL.md"]
        for relative, content in (extra or {}).items():
            self.upstream[f"{name}/{relative}"] = content
            files.append(relative)
        entries = []
        if "catalogue.json" in self.upstream:
            entries = json.loads(self.upstream["catalogue.json"])["skills"]
            entries = [e for e in entries if e["name"] != name]
        entries.append({
            "name": name, "directory": name, "version": version,
            "license": "MIT", "description": "A catalogue skill used in tests.",
            "files": files,
        })
        self.upstream["catalogue.json"] = json.dumps(
            {"source": "Test/catalogue", "schema": 1,
             "skills": sorted(entries, key=lambda e: e["name"])}
        )

    def run_cli(self, *argv):
        buffer = io.StringIO()
        full = ["--skills-dir", str(self.consumer / ".claude" / "skills"), *argv]
        with redirect_stdout(buffer):
            code = skills.main(full)
        return code, buffer.getvalue()

    def skill_path(self, name, relative="SKILL.md"):
        return self.consumer / ".claude" / "skills" / name / relative

    def manifest(self):
        p = self.consumer / ".claude" / "skills" / skills.MANIFEST_NAME
        return json.loads(p.read_text(encoding="utf-8"))


class TestPull(ExchangeHarness):
    def test_pull_writes_skill_and_manifest(self):
        self.publish("alpha", "1.0.0")
        code, out = self.run_cli("pull", "alpha")
        self.assertEqual(code, 0)
        self.assertIn("added alpha 1.0.0", out)
        self.assertIn("# alpha", self.skill_path("alpha").read_text(encoding="utf-8"))
        record = self.manifest()["skills"]["alpha"]
        self.assertEqual(record["version"], "1.0.0")
        self.assertIn("SKILL.md", record["files"])

    def test_pull_brings_payload_files(self):
        self.publish("beta", "1.0.0", extra={"scripts/run.sh": "#!/bin/sh\necho hi\n",
                                             "references/notes.md": "notes\n"})
        self.run_cli("pull", "beta")
        self.assertTrue(self.skill_path("beta", "scripts/run.sh").is_file())
        self.assertTrue(self.skill_path("beta", "references/notes.md").is_file())

    def test_pull_unknown_skill_fails_clearly(self):
        self.publish("alpha")
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli("pull", "nope")
        self.assertIn("no skill named 'nope'", str(ctx.exception))

    def test_pull_refuses_over_local_modification(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.skill_path("alpha").write_text("locally rewritten\n", encoding="utf-8")
        code, out = self.run_cli("pull", "alpha")
        self.assertEqual(code, 0)
        self.assertIn("locally modified", out)
        self.assertEqual(self.skill_path("alpha").read_text(encoding="utf-8"), "locally rewritten\n")

    def test_force_overwrites_local_modification(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.skill_path("alpha").write_text("locally rewritten\n", encoding="utf-8")
        self.run_cli("pull", "alpha", "--force")
        self.assertIn("# alpha", self.skill_path("alpha").read_text(encoding="utf-8"))

    def test_pull_updates_to_new_version(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.publish("alpha", "1.1.0")
        code, out = self.run_cli("pull", "alpha")
        self.assertIn("updated alpha 1.1.0", out)
        self.assertEqual(self.manifest()["skills"]["alpha"]["version"], "1.1.0")


class TestStatus(ExchangeHarness):
    def test_current(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        _, out = self.run_cli("status")
        self.assertIn("CURRENT", out)

    def test_outdated_when_upstream_moves(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.publish("alpha", "2.0.0")
        _, out = self.run_cli("status")
        self.assertIn("OUTDATED", out)
        self.assertIn("upstream is 2.0.0", out)

    def test_modified_when_edited_locally(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.skill_path("alpha").write_text("edited\n", encoding="utf-8")
        _, out = self.run_cli("status")
        self.assertIn("MODIFIED", out)

    def test_diverged_when_both(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.skill_path("alpha").write_text("edited\n", encoding="utf-8")
        self.publish("alpha", "2.0.0")
        _, out = self.run_cli("status")
        self.assertIn("DIVERGED", out)

    def test_missing_when_deleted_on_disk(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.skill_path("alpha").unlink()
        _, out = self.run_cli("status")
        self.assertIn("MISSING", out)

    def test_removed_when_gone_from_catalogue(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        self.upstream["catalogue.json"] = json.dumps(
            {"source": "Test/catalogue", "schema": 1, "skills": []}
        )
        _, out = self.run_cli("status")
        self.assertIn("REMOVED", out)

    def test_empty_manifest_is_not_an_error(self):
        self.publish("alpha")
        code, out = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("no vendored skills", out)


class TestClassify(unittest.TestCase):
    def test_all_states(self):
        self.assertEqual(skills.classify("clean", "1.0.0", "1.0.0")[0], "CURRENT")
        self.assertEqual(skills.classify("clean", "1.1.0", "1.0.0")[0], "OUTDATED")
        self.assertEqual(skills.classify("modified", "1.0.0", "1.0.0")[0], "MODIFIED")
        self.assertEqual(skills.classify("modified", "1.1.0", "1.0.0")[0], "DIVERGED")
        self.assertEqual(skills.classify("missing", "1.0.0", "1.0.0")[0], "MISSING")


class TestDiffAndContribute(ExchangeHarness):
    def test_diff_reports_identical(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        _, out = self.run_cli("diff", "alpha")
        self.assertIn("identical", out)

    def test_diff_shows_local_change(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        text = self.skill_path("alpha").read_text(encoding="utf-8")
        self.skill_path("alpha").write_text(text + "\nAn added local line.\n", encoding="utf-8")
        _, out = self.run_cli("diff", "alpha")
        self.assertIn("+An added local line.", out)

    def test_contribute_without_changes(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        _, out = self.run_cli("contribute", "alpha")
        self.assertIn("nothing to contribute", out)

    def test_contribute_writes_patch_and_instructions(self):
        self.publish("alpha", "1.0.0")
        self.run_cli("pull", "alpha")
        text = self.skill_path("alpha").read_text(encoding="utf-8")
        # exactly one added line, so the reported count is unambiguous
        self.skill_path("alpha").write_text(text + "A general improvement.\n", encoding="utf-8")
        cwd = Path.cwd()
        try:
            os.chdir(self.dir)
            _, out = self.run_cli("contribute", "alpha")
        finally:
            os.chdir(cwd)
        self.assertIn("+1 -0 lines", out)
        self.assertIn("git checkout -b improve/alpha", out)
        self.assertIn("build_catalogue.py", out)
        patch = self.dir / "alpha.patch"
        self.assertTrue(patch.is_file())
        self.assertIn("+A general improvement.", patch.read_text(encoding="utf-8"))


class TestList(ExchangeHarness):
    def test_list_shows_skills(self):
        self.publish("alpha", "1.0.0")
        self.publish("beta", "2.0.0")
        _, out = self.run_cli("list")
        self.assertIn("alpha", out)
        self.assertIn("beta", out)
        self.assertIn("2 skill(s)", out)

    def test_search_filters(self):
        self.publish("alpha")
        self.publish("beta")
        _, out = self.run_cli("list", "--search", "alph")
        self.assertIn("alpha", out)
        self.assertNotIn("  beta ", out)

    def test_search_with_no_match(self):
        self.publish("alpha")
        _, out = self.run_cli("list", "--search", "zzzz")
        self.assertIn("nothing in the catalogue matches", out)


if __name__ == "__main__":
    unittest.main()
