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
    <workspace>/<skill>-<eval id>/{with_skill,without_skill}/grading*.json

More than one grading file per arm means more than one judge graded it. That is
the default now: a single judge decided several results here by a whisker, and
in three cases said so unprompted. Where judges disagree on an expectation the
run is still counted - at the mean of their rates - but the disagreement is
printed, because a contested expectation is a badly written expectation and the
list is what needs fixing, not the arithmetic.

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


def merge_judges(gradings):
    """One run's verdict from one or more judges, plus what they disagreed on."""
    per_expectation = {}
    order = []
    for data in gradings:
        for e in data.get("expectations", []):
            text = e["text"]
            if text not in per_expectation:
                per_expectation[text] = []
                order.append(text)
            per_expectation[text].append(bool(e["passed"]))

    expectations, contested = [], []
    for text in order:
        votes = per_expectation[text]
        if len(set(votes)) > 1:
            contested.append(text)
        # Mean of the votes, so two judges splitting scores a half rather than
        # letting whichever ran last decide it.
        expectations.append({"text": text, "passed": sum(votes) / len(votes)})

    total = len(expectations)
    passed = sum(e["passed"] for e in expectations)
    return {
        "expectations": expectations,
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "contested": contested,
        "judges": len(gradings),
    }


def load_runs(workspace):
    runs = []
    for eval_dir in sorted(p for p in workspace.iterdir() if p.is_dir()):
        for config in CONFIGS:
            gradings = [json.loads(f.read_text(encoding="utf-8"))
                        for f in sorted((eval_dir / config).glob("grading*.json"))]
            if not gradings:
                continue
            merged = merge_judges(gradings)
            runs.append({
                "eval_name": eval_dir.name,
                "configuration": config,
                "pass_rate": merged["pass_rate"],
                "passed": merged["passed"],
                "total": merged["total"],
                "expectations": merged["expectations"],
                "contested": merged["contested"],
                "judges": merged["judges"],
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
            # Both arms cleared it outright. A half-pass means the judges split,
            # which is a different problem and reported separately.
            if e["passed"] == 1 and base.get(e["text"]) == 1:
                flagged.append((name, e["text"]))
    return flagged


def by_skill(runs):
    """Mean delta per skill. This is the unit that decays, not the eval."""
    pairs = {}
    for r in runs:
        pairs.setdefault(r["eval_name"], {})[r["configuration"]] = r
    per = {}
    for name, pair in pairs.items():
        if set(pair) != set(CONFIGS):
            continue
        skill = name.rsplit("-", 1)[0]
        per.setdefault(skill, []).append(
            pair["with_skill"]["pass_rate"] - pair["without_skill"]["pass_rate"])
    return {s: {"delta": round(sum(v) / len(v), 4), "evals": len(v)}
            for s, v in sorted(per.items())}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("--json", dest="out", default=None)
    parser.add_argument("--model", default=None,
                        help="model id that produced these runs. Recorded in the "
                             "benchmark, because a delta without one cannot be "
                             "compared to anything later.")
    args = parser.parse_args(argv)

    # Expectation text can contain emoji (severity tags, for one). On a cp1252
    # console the notes print dies before benchmark.json is ever written, so the
    # run looks like it produced nothing. Same class of bug as the git decode
    # one; pin the streams.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

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
        ws = f"{w['passed']:g}/{w['total']} {w['pass_rate']:.0%}" if w else "-"
        bs = f"{b['passed']:g}/{b['total']} {b['pass_rate']:.0%}" if b else "-"
        d = f"{(w['pass_rate'] - b['pass_rate']):+.0%}" if w and b else "-"
        print(f"{name:<{width}}  {ws:>12}  {bs:>12}  {d:>7}")

    print()
    print(f"with skill    : {summary['with_skill']['mean']:.1%} "
          f"(sd {summary['with_skill']['stddev']:.2f}, n={len(by_config['with_skill'])})")
    print(f"without skill : {summary['without_skill']['mean']:.1%} "
          f"(sd {summary['without_skill']['stddev']:.2f}, n={len(by_config['without_skill'])})")
    print(f"delta         : {delta:+.1%}")

    per = by_skill(runs)
    if len(per) > 1:
        print()
        for skill, v in sorted(per.items(), key=lambda kv: -kv[1]["delta"]):
            print(f"  {skill:<30} {v['delta']:+.0%}  ({v['evals']} evals)")

    single = sorted({r["eval_name"] for r in runs if r["judges"] < 2})
    if single:
        print(f"\nsingle-judge runs ({len(single)}) - no second opinion, treat the delta as soft:")
        for name in single[:15]:
            print(f"  {name}")
        if len(single) > 15:
            print(f"  ... and {len(single) - 15} more")

    contested = [(r["eval_name"], r["configuration"], text)
                 for r in runs for text in r["contested"]]
    if contested:
        print(f"\ncontested expectations ({len(contested)}) - judges disagreed, so the wording is unclear:")
        for name, cfg, text in contested[:15]:
            print(f"  {name} [{cfg}]: {text[:88]}")
        if len(contested) > 15:
            print(f"  ... and {len(contested) - 15} more")

    flagged = non_discriminating(runs)
    if flagged:
        print(f"\nnon-discriminating expectations ({len(flagged)}) - passed with AND without the skill:")
        for name, text in flagged[:25]:
            print(f"  {name}: {text[:96]}")
        if len(flagged) > 25:
            print(f"  ... and {len(flagged) - 25} more")

    if args.out:
        payload = {
            "metadata": {"workspace": workspace.name, "model": args.model,
                         "evals_run": sorted(by_eval)},
            "by_skill": by_skill(runs),
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
            "contested": [f"{name} [{cfg}]: {text}" for name, cfg, text in contested],
            "single_judge": single,
        }
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
