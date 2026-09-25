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


def stage(ws, name, expectations, discriminating):
    d = Path(ws) / name
    for cfg in ("with_skill", "without_skill"):
        (d / cfg).mkdir(parents=True)
    (d / "with_skill" / "eval.json").write_text(json.dumps({
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
