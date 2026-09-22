#!/usr/bin/env python3
"""
Tests for tools/check_evals.py, plus repo-wide assertions about the evals.

The repo-wide tests are the ones that matter day to day: they fail when a skill
is added without evals, or when an eval file drifts out of the schema.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load(REPO / "tools" / "check_evals.py", "check_evals")


def skills():
    return sorted(p.parent.name for p in REPO.glob("*/SKILL.md"))


def evals_for(name):
    return json.loads((REPO / name / "evals" / "evals.json").read_text(encoding="utf-8"))


class TestEverySkillHasEvals(unittest.TestCase):
    def test_evals_file_exists(self):
        missing = [s for s in skills() if not (REPO / s / "evals" / "evals.json").is_file()]
        self.assertEqual(missing, [], f"skills without evals/evals.json: {missing}")

    def test_repo_passes_its_own_checker(self):
        errors, warnings, stats = [], [], []
        for name in skills():
            checker.check_skill(name, errors, warnings, stats)
        self.assertEqual(errors, [], f"eval validation errors: {errors}")
        self.assertEqual(warnings, [], f"eval validation warnings: {warnings}")


class TestEvalSchema(unittest.TestCase):
    def test_shape_matches_the_canonical_schema(self):
        for name in skills():
            data = evals_for(name)
            with self.subTest(skill=name):
                self.assertEqual(data["skill_name"], name)
                self.assertGreaterEqual(len(data["evals"]), 2)
                for ev in data["evals"]:
                    self.assertEqual(
                        set(ev) , {"id", "prompt", "expected_output", "files", "expectations"},
                        f"{name}#{ev.get('id')} has unexpected or missing fields",
                    )
                    self.assertIsInstance(ev["id"], int)
                    self.assertIsInstance(ev["files"], list)
                    self.assertGreaterEqual(len(ev["expectations"]), 3)

    def test_ids_are_unique_and_sequential(self):
        for name in skills():
            ids = [e["id"] for e in evals_for(name)["evals"]]
            with self.subTest(skill=name):
                self.assertEqual(ids, list(range(1, len(ids) + 1)))

    def test_prompts_read_like_a_real_user(self):
        # A prompt that just restates the skill name tests triggering, not behaviour.
        for name in skills():
            for ev in evals_for(name)["evals"]:
                with self.subTest(skill=name, eval=ev["id"]):
                    self.assertGreaterEqual(len(ev["prompt"]), 40)
                    self.assertNotEqual(ev["prompt"].strip().lower(), name.replace("-", " "))

    def test_referenced_files_exist(self):
        for name in skills():
            for ev in evals_for(name)["evals"]:
                for f in ev["files"]:
                    with self.subTest(skill=name, file=f):
                        self.assertTrue(
                            (REPO / name / f).is_file() or (REPO / f).is_file(),
                            f"{name}#{ev['id']} references missing file {f}",
                        )


class TestCheckerCatchesProblems(unittest.TestCase):
    """The checker has to actually fail on bad input, or it is decoration."""

    def setUp(self):
        self.errors, self.warnings, self.stats = [], [], []

    def write(self, tmp, name, payload):
        d = tmp / name / "evals"
        d.mkdir(parents=True)
        (tmp / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        (d / "evals.json").write_text(json.dumps(payload), encoding="utf-8")

    def check(self, tmp, name):
        original = checker.ROOT
        try:
            checker.ROOT = tmp
            checker.check_skill(name, self.errors, self.warnings, self.stats)
        finally:
            checker.ROOT = original

    def good_eval(self, **over):
        eid = over.get("id", 1)
        ev = {
            "id": 1,
            # vary by id: the checker rejects duplicate prompts, correctly
            "prompt": f"A realistic user prompt, number {eid}, comfortably long enough to pass the length floor.",
            "expected_output": "Something happens.",
            "files": [],
            "expectations": ["The response does A", "The response does B", "The response does C"],
        }
        ev.update(over)
        return ev

    def test_missing_file_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "skillx").mkdir()
            self.check(tmp, "skillx")
        self.assertTrue(any("no evals/evals.json" in e for e in self.errors))

    def test_mismatched_skill_name_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self.write(tmp, "skillx", {"skill_name": "wrong", "evals": [self.good_eval(), self.good_eval(id=2)]})
            self.check(tmp, "skillx")
        self.assertTrue(any("skill_name" in e for e in self.errors))

    def test_too_few_expectations_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            bad = self.good_eval(expectations=["only one"])
            self.write(tmp, "skillx", {"skill_name": "skillx", "evals": [bad, self.good_eval(id=2)]})
            self.check(tmp, "skillx")
        self.assertTrue(any("expectations" in e for e in self.errors))

    def test_short_prompt_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            bad = self.good_eval(prompt="do it")
            self.write(tmp, "skillx", {"skill_name": "skillx", "evals": [bad, self.good_eval(id=2)]})
            self.check(tmp, "skillx")
        self.assertTrue(any("too short" in e for e in self.errors))

    def test_duplicate_ids_are_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self.write(tmp, "skillx", {"skill_name": "skillx", "evals": [self.good_eval(), self.good_eval()]})
            self.check(tmp, "skillx")
        self.assertTrue(any("duplicate id" in e for e in self.errors))

    def test_vague_expectation_is_a_warning(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            bad = self.good_eval(expectations=[
                "The response handles it appropriately", "The response does B", "The response does C"])
            self.write(tmp, "skillx", {"skill_name": "skillx", "evals": [bad, self.good_eval(id=2)]})
            self.check(tmp, "skillx")
        self.assertTrue(any("vague wording" in w for w in self.warnings))
        self.assertEqual(self.errors, [])

    def test_quoted_vague_word_is_not_flagged(self):
        # quoting a vague word from the prompt is precise about something imprecise
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            ok = self.good_eval(expectations=[
                "The response identifies that 'appropriate' is not verifiable",
                "The response does B", "The response does C"])
            self.write(tmp, "skillx", {"skill_name": "skillx", "evals": [ok, self.good_eval(id=2)]})
            self.check(tmp, "skillx")
        self.assertEqual(self.warnings, [])
        self.assertEqual(self.errors, [])

    def test_invalid_json_is_an_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = tmp / "skillx" / "evals"
            d.mkdir(parents=True)
            (tmp / "skillx" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            (d / "evals.json").write_text("{not json", encoding="utf-8")
            self.check(tmp, "skillx")
        self.assertTrue(any("invalid JSON" in e for e in self.errors))


if __name__ == "__main__":
    unittest.main()
