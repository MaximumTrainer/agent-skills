#!/usr/bin/env python3
"""
Aggregate eval grading results across every skill into one benchmark.

Reads grading.json from each run directory in the workspace and reports the
with-skill versus baseline pass rate per eval and overall.

The number that matters is the delta, not the with-skill pass rate. A skill
whose evals pass just as well without it has evals that measure the model, not
the skill - so this also flags non-discriminating expectations, which pass in
both configurations and therefore tell you nothing.

Layout expected:
    <workspace>/<skill>-<eval id>/{with_skill,without_skill}/grading.json

Stdlib only.

Usage:
    python3 tools/aggregate_evals.py <workspace>
    python3 tools/aggregate_evals.py <workspace> --json benchmark.json
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

CONFIGS = ("with_skill", "without_skill")


def load_runs(workspace):
    runs = []
    for eval_dir in sorted(p for p in workspace.iterdir() if p.is_dir()):
        for config in CONFIGS:
            grading = eval_dir / config / "grading.json"
            if not grading.is_file():
                continue
            data = json.loads(grading.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            runs.append({
                "eval_name": eval_dir.name,
                "configuration": config,
                "pass_rate": summary.get("pass_rate", 0.0),
                "passed": summary.get("passed", 0),
                "total": summary.get("total", 0),
                "expectations": data.get("expectations", []),
            })
    return runs


def stats(values):
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": round(statistics.fmean(values), 4),
        "stddev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def non_discriminating(runs):
    """Expectations that passed in both configurations for the same eval."""
    by_eval = {}
    for r in runs:
        by_eval.setdefault(r["eval_name"], {})[r["configuration"]] = r
    flagged = []
    for name, pair in sorted(by_eval.items()):
        if set(pair) != set(CONFIGS):
            continue
        base = {e["text"]: e["passed"] for e in pair["without_skill"]["expectations"]}
        for e in pair["with_skill"]["expectations"]:
            if e["passed"] and base.get(e["text"]) is True:
                flagged.append((name, e["text"]))
    return flagged


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("--json", dest="out", default=None)
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        sys.exit(f"no such workspace: {workspace}")

    runs = load_runs(workspace)
    if not runs:
        sys.exit(f"no grading.json found under {workspace}")

    by_config = {c: [r["pass_rate"] for r in runs if r["configuration"] == c] for c in CONFIGS}
    summary = {c: stats(v) for c, v in by_config.items()}
    delta = summary["with_skill"]["mean"] - summary["without_skill"]["mean"]

    by_eval = {}
    for r in runs:
        by_eval.setdefault(r["eval_name"], {})[r["configuration"]] = r

    width = max(len(n) for n in by_eval)
    print(f"{'eval':<{width}}  {'with':>12}  {'without':>12}  {'delta':>7}")
    print("-" * (width + 38))
    for name in sorted(by_eval):
        pair = by_eval[name]
        w = pair.get("with_skill")
        b = pair.get("without_skill")
        ws = f"{w['passed']}/{w['total']} {w['pass_rate']:.0%}" if w else "-"
        bs = f"{b['passed']}/{b['total']} {b['pass_rate']:.0%}" if b else "-"
        d = f"{(w['pass_rate'] - b['pass_rate']):+.0%}" if w and b else "-"
        print(f"{name:<{width}}  {ws:>12}  {bs:>12}  {d:>7}")

    print()
    print(f"with skill    : {summary['with_skill']['mean']:.1%} "
          f"(sd {summary['with_skill']['stddev']:.2f}, n={len(by_config['with_skill'])})")
    print(f"without skill : {summary['without_skill']['mean']:.1%} "
          f"(sd {summary['without_skill']['stddev']:.2f}, n={len(by_config['without_skill'])})")
    print(f"delta         : {delta:+.1%}")

    flagged = non_discriminating(runs)
    if flagged:
        print(f"\nnon-discriminating expectations ({len(flagged)}) - passed with AND without the skill:")
        for name, text in flagged[:25]:
            print(f"  {name}: {text[:96]}")
        if len(flagged) > 25:
            print(f"  ... and {len(flagged) - 25} more")

    if args.out:
        payload = {
            "metadata": {"workspace": str(workspace), "evals_run": sorted(by_eval)},
            "runs": [
                {"eval_name": r["eval_name"], "configuration": r["configuration"], "run_number": 1,
                 "result": {"pass_rate": r["pass_rate"], "passed": r["passed"], "total": r["total"]},
                 "expectations": r["expectations"]}
                for r in runs
            ],
            "run_summary": {
                "with_skill": {"pass_rate": summary["with_skill"]},
                "without_skill": {"pass_rate": summary["without_skill"]},
                "delta": {"pass_rate": f"{delta:+.4f}"},
            },
            "notes": [f"{name}: {text}" for name, text in flagged],
        }
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
