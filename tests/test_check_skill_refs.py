"""Tests for tools/check_skill_refs.py.

The point of these is that the check BITES. A reference checker that never
fires is indistinguishable from no checker, and that is exactly the state the
catalogue was in when two skills shipped pointing at a directory that was never
copied across with them.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_skill_refs  # noqa: E402


def make_skill(root, name, body, files=()):
    d = Path(root) / name
    (d / "").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: x\n---\n\n{body}\n", encoding="utf-8")
    for f in files:
        p = d / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    return d


class ReferenceCheck(unittest.TestCase):
    def test_resolving_payload_reference_passes(self):
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "See `references/rules/a.md`.",
                           ["references/rules/a.md"])
            self.assertEqual(check_skill_refs.check_skill(d), [])

    def test_missing_payload_file_is_an_error(self):
        """The exact defect: an index entry whose file is not there."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "See `references/rules/gone.md`.",
                           ["references/rules/a.md"])
            errors = check_skill_refs.check_skill(d)
            self.assertEqual(len(errors), 1)
            self.assertIn("references/rules/gone.md", errors[0])

    def test_renamed_file_is_an_error(self):
        """r3f-best-practices listed state-zustand-selectors; the file was
        perf-zustand-selectors. Both names are plausible, so only a check
        catches it."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "`references/rules/state-zustand-selectors.md`",
                           ["references/rules/perf-zustand-selectors.md"])
            self.assertEqual(len(check_skill_refs.check_skill(d)), 1)

    def test_reader_repo_paths_are_not_flagged(self):
        """The false-positive class that killed the wider rule. A skill saying
        'put it in docs/adr/' means the reader's repo, not its own payload."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s",
                           "Record it under `docs/adr/0001.md` and wire "
                           "`.github/workflows/ci.yml`. Name it `scripts/__probe.py`.")
            self.assertEqual(check_skill_refs.check_skill(d), [])

    def test_absent_payload_dir_means_the_path_is_the_readers(self):
        """scripts/ is a payload dir NAME, but this skill has no scripts/, so
        the mention is instruction to the reader, not a broken pointer."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "Write `scripts/__probe.py`, run it, delete it.")
            self.assertEqual(check_skill_refs.check_skill(d), [])

    def test_present_payload_dir_makes_the_path_binding(self):
        """Same path, but now the skill HAS scripts/ - so it is a real pointer
        and must resolve."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "Run `scripts/__probe.py`.", ["scripts/other.py"])
            self.assertEqual(len(check_skill_refs.check_skill(d)), 1)

    def test_urls_are_not_paths(self):
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s",
                           "See https://example.com/references/x.md and "
                           "`gcr.io/distroless/static-debian12`.",
                           ["references/a.md"])
            self.assertEqual(check_skill_refs.check_skill(d), [])

    def test_non_ascii_body_does_not_break_the_read(self):
        """SKILL.md files contain em-dashes. Reading without an explicit
        encoding decodes with the locale codec and raises on cp1252 - the bug
        class that has now bitten this repo four times."""
        with TemporaryDirectory() as tmp:
            d = make_skill(tmp, "s", "A rule — see `references/a.md` — applies.",
                           ["references/a.md"])
            self.assertEqual(check_skill_refs.check_skill(d), [])


if __name__ == "__main__":
    unittest.main()
