"""Tests for tools/make_judge_keys.py.

The property that matters is that the key is actually blind: over many evals,
with_skill must land in arm_A roughly half the time. A key that always put the
skill arm in the same slot would let a judge learn the position and would
reintroduce exactly the bias this replaced.
"""

import json
import random
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import make_judge_keys  # noqa: E402
import stage_eval  # noqa: E402


def stage(ws, name, expectations, discriminating):
    """Mirror stage_eval: responses in the run dir, the answer key in .keys/.

    The key is deliberately NOT under the run directory. It sat there once, a
    runner read it, and that run answered against the expectations it was about
    to be graded on."""
    d = Path(ws) / name
    for cfg in ("with_skill", "without_skill"):
        (d / cfg).mkdir(parents=True)
    keys = Path(ws) / ".keys"
    keys.mkdir(exist_ok=True)
    (keys / f"{name}.json").write_text(json.dumps({
        "id": 1, "prompt": "p",
        "expectations": expectations,
        "discriminating": discriminating,
    }), encoding="utf-8")
    return d


class JudgeKeys(unittest.TestCase):
    def test_key_holds_only_discriminating_expectations(self):
        with TemporaryDirectory() as ws:
            d = stage(ws, "s-1", ["a", "b", "c", "d"], [1, 3])
            make_judge_keys.write_keys(ws)
            key = json.loads((d / "JUDGE.json").read_text(encoding="utf-8"))
            self.assertEqual(key["expectations"], ["b", "d"])

    def test_arms_are_the_two_configs(self):
        with TemporaryDirectory() as ws:
            d = stage(ws, "s-1", ["a"], [0])
            make_judge_keys.write_keys(ws)
            key = json.loads((d / "JUDGE.json").read_text(encoding="utf-8"))
            self.assertEqual({key["arm_A"], key["arm_B"]},
                             {"with_skill", "without_skill"})

    def test_assignment_is_blind_not_fixed(self):
        """with_skill must not always be arm_A, or the blinding is decorative."""
        with TemporaryDirectory() as ws:
            for i in range(60):
                stage(ws, f"s-{i}", ["a"], [0])
            make_judge_keys.write_keys(ws, rng=random.Random(0))
            a_is_with = sum(
                json.loads((Path(ws) / f"s-{i}" / "JUDGE.json").read_text(encoding="utf-8"))["arm_A"] == "with_skill"
                for i in range(60))
            self.assertTrue(10 < a_is_with < 50, f"arm_A was with_skill {a_is_with}/60 times")

    def test_eval_with_no_discriminating_marks_is_skipped(self):
        """Nothing to compare, so no key - it would waste a judge."""
        with TemporaryDirectory() as ws:
            d = stage(ws, "s-1", ["a"], [])
            self.assertEqual(make_judge_keys.write_keys(ws), [])
            self.assertFalse((d / "JUDGE.json").exists())

    def test_only_filter_selects_by_skill_not_eval_id(self):
        with TemporaryDirectory() as ws:
            stage(ws, "alpha-1", ["a"], [0])
            stage(ws, "alpha-2", ["a"], [0])
            stage(ws, "beta-1", ["a"], [0])
            self.assertEqual(make_judge_keys.write_keys(ws, only={"alpha"}),
                             ["alpha-1", "alpha-2"])

    def test_non_ascii_expectations_survive(self):
        with TemporaryDirectory() as ws:
            d = stage(ws, "s-1", ["red - for the right reason — not a typo"], [0])
            make_judge_keys.write_keys(ws)
            key = json.loads((d / "JUDGE.json").read_text(encoding="utf-8"))
            self.assertIn("—", key["expectations"][0])


if __name__ == "__main__":
    unittest.main()


class JudgePrompt(unittest.TestCase):
    def test_second_judge_writes_a_different_file(self):
        """Both judges writing grading.json would leave one verdict, silently."""
        one = make_judge_keys.judge_prompt("/w/s-1", 1)
        two = make_judge_keys.judge_prompt("/w/s-1", 2)
        self.assertIn("grading.json", one)
        self.assertIn("grading.2.json", two)

    def test_prompt_forbids_reading_the_skill(self):
        """A judge that reads the skill knows which arm is which."""
        p = make_judge_keys.judge_prompt("/w/s-1")
        self.assertIn("Do not read the skill under test", p)

    def test_prompt_carries_the_honesty_rule(self):
        """The outside-in-tdd reversal: an honest 'not run' must not be marked
        wrong just because the expectation is phrased as reporting a result."""
        p = make_judge_keys.judge_prompt("/w/s-1")
        self.assertIn("honestly saying", p)
        self.assertIn("Never credit a claimed verification", p)

    def test_prompt_names_the_run_directory(self):
        self.assertIn("/w/s-1", make_judge_keys.judge_prompt("/w/s-1"))


class KeyIsOutOfReach(unittest.TestCase):
    """Regression for a real contamination: the answer key used to be written
    into the run directory as eval.json, one level up from the sandbox. A
    runner read it and said so in its own report."""

    def test_stage_eval_writes_no_key_inside_the_run_directory(self):
        with TemporaryDirectory() as ws:
            run_dir, _ = stage_eval.stage("gap-issue", 1, "with_skill", ws)
            leaked = [p.name for p in run_dir.rglob("*")
                      if p.is_file() and p.suffix == ".json" and "sandbox" not in p.parts]
            self.assertEqual(leaked, [], f"answer key reachable from the run dir: {leaked}")

    def test_the_key_exists_where_the_judge_looks_for_it(self):
        with TemporaryDirectory() as ws:
            stage_eval.stage("gap-issue", 1, "with_skill", ws)
            key = Path(ws) / ".keys" / "gap-issue-1.json"
            self.assertTrue(key.is_file())
            self.assertIn("expectations", json.loads(key.read_text(encoding="utf-8")))
