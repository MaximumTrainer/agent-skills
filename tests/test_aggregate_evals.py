"""Tests for tools/aggregate_evals.py judge merging.

Two judges exist because one judge decided several published results by a
whisker. The behaviour that matters is that a split is *visible* - averaged into
a half and listed as contested - rather than resolved silently by whichever
grading file happened to sort last.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import aggregate_evals  # noqa: E402


def grading(*pairs):
    exps = [{"text": t, "passed": p} for t, p in pairs]
    ok = sum(1 for e in exps if e["passed"])
    return {"expectations": exps,
            "summary": {"passed": ok, "failed": len(exps) - ok,
                        "total": len(exps), "pass_rate": ok / len(exps) if exps else 0.0}}


def stage(ws, name, cfg, gradings):
    d = Path(ws) / name / cfg
    d.mkdir(parents=True)
    for i, g in enumerate(gradings, 1):
        suffix = "" if i == 1 else f".{i}"
        (d / f"grading{suffix}.json").write_text(json.dumps(g), encoding="utf-8")
    return d


class MergeJudges(unittest.TestCase):
    def test_single_judge_is_unchanged(self):
        m = aggregate_evals.merge_judges([grading(("a", True), ("b", False))])
        self.assertEqual(m["pass_rate"], 0.5)
        self.assertEqual(m["contested"], [])
        self.assertEqual(m["judges"], 1)

    def test_agreeing_judges_agree(self):
        g = grading(("a", True), ("b", False))
        m = aggregate_evals.merge_judges([g, g])
        self.assertEqual(m["pass_rate"], 0.5)
        self.assertEqual(m["contested"], [])
        self.assertEqual(m["judges"], 2)

    def test_split_scores_a_half_and_is_reported(self):
        """The whole point: a disagreement must not be resolved silently."""
        m = aggregate_evals.merge_judges([grading(("a", True)), grading(("a", False))])
        self.assertEqual(m["pass_rate"], 0.5)
        self.assertEqual(m["contested"], ["a"])

    def test_order_of_judges_does_not_change_the_result(self):
        a, b = grading(("x", True), ("y", False)), grading(("x", False), ("y", False))
        self.assertEqual(aggregate_evals.merge_judges([a, b])["pass_rate"],
                         aggregate_evals.merge_judges([b, a])["pass_rate"])

    def test_three_judges_take_the_mean(self):
        m = aggregate_evals.merge_judges(
            [grading(("a", True)), grading(("a", True)), grading(("a", False))])
        self.assertAlmostEqual(m["pass_rate"], 0.6667, places=3)
        self.assertEqual(m["contested"], ["a"])


class LoadRuns(unittest.TestCase):
    def test_picks_up_every_grading_file_in_an_arm(self):
        with TemporaryDirectory() as ws:
            stage(ws, "s-1", "with_skill", [grading(("a", True)), grading(("a", False))])
            stage(ws, "s-1", "without_skill", [grading(("a", False))])
            runs = aggregate_evals.load_runs(Path(ws))
            with_run = next(r for r in runs if r["configuration"] == "with_skill")
            self.assertEqual(with_run["judges"], 2)
            self.assertEqual(with_run["contested"], ["a"])

    def test_arm_with_no_grading_is_omitted_not_zeroed(self):
        """A missing arm once counted as a zero and turned +17% into +0%."""
        with TemporaryDirectory() as ws:
            stage(ws, "s-1", "with_skill", [grading(("a", True))])
            (Path(ws) / "s-1" / "without_skill").mkdir(parents=True)
            runs = aggregate_evals.load_runs(Path(ws))
            self.assertEqual([r["configuration"] for r in runs], ["with_skill"])


class NonDiscriminating(unittest.TestCase):
    def test_flags_only_outright_passes_in_both_arms(self):
        with TemporaryDirectory() as ws:
            stage(ws, "s-1", "with_skill", [grading(("a", True), ("b", True))])
            stage(ws, "s-1", "without_skill", [grading(("a", True), ("b", False))])
            runs = aggregate_evals.load_runs(Path(ws))
            self.assertEqual(aggregate_evals.non_discriminating(runs), [("s-1", "a")])

    def test_a_contested_expectation_is_not_called_non_discriminating(self):
        """A half-pass means the judges split, which is a different problem."""
        with TemporaryDirectory() as ws:
            stage(ws, "s-1", "with_skill", [grading(("a", True)), grading(("a", False))])
            stage(ws, "s-1", "without_skill", [grading(("a", True))])
            runs = aggregate_evals.load_runs(Path(ws))
            self.assertEqual(aggregate_evals.non_discriminating(runs), [])


if __name__ == "__main__":
    unittest.main()
