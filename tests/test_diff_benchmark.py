"""Tests for tools/diff_benchmark.py.

This tool exists to catch the one failure mode nothing else here catches: a
skill that is still accurate, still passing, still green, and no longer needed
because the model caught up. The tests pin the two judgements that matter -
what counts as decayed, and what counts as noise.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import diff_benchmark  # noqa: E402


def bench(**skills):
    return {s: {"delta": d, "evals": 3} for s, d in skills.items()}


class Compare(unittest.TestCase):
    def test_lift_falling_to_nothing_is_decay(self):
        moved, _, _ = diff_benchmark.compare(bench(a=0.67), bench(a=0.0))
        self.assertEqual(moved, [("a", 0.67, 0.0, "DECAYED")])

    def test_a_skill_that_never_lifted_is_not_decayed(self):
        """It cannot decay from zero. Reporting it would bury the real ones."""
        moved, _, _ = diff_benchmark.compare(bench(a=0.02), bench(a=0.0))
        self.assertEqual(moved, [])

    def test_a_large_drop_that_stops_short_of_zero_is_weaker_not_decayed(self):
        moved, _, _ = diff_benchmark.compare(bench(a=0.67), bench(a=0.33))
        self.assertEqual(moved[0][3], "WEAKER")

    def test_rising_lift_is_reported_as_improved(self):
        moved, _, _ = diff_benchmark.compare(bench(a=0.1), bench(a=0.5))
        self.assertEqual(moved[0][3], "IMPROVED")

    def test_noise_below_the_threshold_is_not_decay(self):
        """Two judges over three evals do not resolve five points. Treating
        that as decay is how a good skill gets deleted."""
        moved, _, _ = diff_benchmark.compare(bench(a=0.35), bench(a=0.30))
        self.assertEqual(moved, [])

    def test_threshold_is_configurable(self):
        self.assertEqual(diff_benchmark.compare(bench(a=0.35), bench(a=0.30), 0.01)[0][0][3],
                         "WEAKER")

    def test_worst_movement_sorts_first(self):
        moved, _, _ = diff_benchmark.compare(
            bench(up=0.1, down=0.8), bench(up=0.6, down=0.0))
        self.assertEqual([m[0] for m in moved], ["down", "up"])

    def test_changed_eval_set_is_reported_not_silently_skipped(self):
        moved, appeared, vanished = diff_benchmark.compare(bench(a=0.5), bench(b=0.5))
        self.assertEqual(moved, [])
        self.assertEqual((appeared, vanished), (["b"], ["a"]))


class Load(unittest.TestCase):
    def test_a_benchmark_without_by_skill_is_refused_not_guessed(self):
        """Older benchmarks predate the per-skill rollup. Comparing against one
        would invent numbers."""
        with TemporaryDirectory() as d:
            p = Path(d) / "old.json"
            p.write_text(json.dumps({"metadata": {}, "runs": []}), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                diff_benchmark.load(p)
            self.assertIn("predates", str(cm.exception))

    def test_model_is_read_from_metadata(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "b.json"
            p.write_text(json.dumps({"metadata": {"model": "m-1"},
                                     "by_skill": bench(a=0.5)}), encoding="utf-8")
            meta, per = diff_benchmark.load(p)
            self.assertEqual(meta["model"], "m-1")
            self.assertEqual(per["a"]["delta"], 0.5)


if __name__ == "__main__":
    unittest.main()
