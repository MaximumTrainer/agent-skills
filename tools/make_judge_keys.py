#!/usr/bin/env python3
"""
Write a blinded grading key for every staged eval run in a workspace.

Grading by regex was the instrument's weakest joint. It produced at least two
wrong answers that changed a reported result: `code-review` scored -50% because
the pattern was narrower than the response, and `verify-and-ship` scored +33%
on a pattern the baseline also satisfied in different words. Re-grading the same
15 runs with blind judges moved two skills by more than 30 points in opposite
directions, so the error was not a consistent bias that cancels out.

This writes JUDGE.json next to each run pair:

    {"expectations": [...only the discriminating ones...],
     "arm_A": "without_skill", "arm_B": "with_skill"}

The arm assignment is shuffled per eval, so a judge reading only JUDGE.json and
the two response.md files cannot tell which arm is which. Hand one judge one
eval directory, have it write grading.json into each arm, then run
aggregate_evals.py as usual.

Grading rules that matter, and why (all three were learned by getting them
wrong):

- Judge substance, not wording, or you measure vocabulary overlap with whoever
  wrote the expectation.
- Be willing to pass both or fail both. A judge told a skill is under test will
  find a difference.
- Check what the expectation actually rewards. One expectation here rewarded
  asserting an observed test failure; in a sandbox with no repo, the honest
  answer was "not run", so the skill that taught honesty scored zero and the
  arm that fabricated a result scored one.

Stdlib only.

Usage:
    python3 tools/make_judge_keys.py <workspace> [SKILL ...]
"""

import json
import random
import sys
from pathlib import Path

CONFIGS = ("with_skill", "without_skill")


def write_keys(workspace, only=(), rng=None):
    """Write JUDGE.json for each eval dir; returns the names written."""
    rng = rng or random.Random()
    written = []
    for d in sorted(p for p in Path(workspace).iterdir() if p.is_dir()):
        skill = d.name.rsplit("-", 1)[0]
        if only and skill not in only:
            continue
        src = d / "with_skill" / "eval.json"
        if not src.is_file():
            continue
        ev = json.loads(src.read_text(encoding="utf-8"))
        disc = ev.get("discriminating") or []
        if not disc:
            continue
        order = list(CONFIGS)
        rng.shuffle(order)
        (d / "JUDGE.json").write_text(json.dumps({
            "expectations": [ev["expectations"][i] for i in disc],
            "arm_A": order[0],
            "arm_B": order[1],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(d.name)
    return written


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not argv:
        sys.exit("usage: make_judge_keys.py <workspace> [SKILL ...]")
    workspace = Path(argv[0])
    if not workspace.is_dir():
        sys.exit(f"no such workspace: {workspace}")
    written = write_keys(workspace, only=set(argv[1:]))
    for name in written:
        print(f"  {name}")
    print(f"wrote {len(written)} judge key(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
