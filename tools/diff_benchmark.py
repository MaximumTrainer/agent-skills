#!/usr/bin/env python3
"""
Diff two benchmarks and name the skills whose measured lift has moved.

A skill's value decays and nothing else here detects it. `three-best-practices`
almost certainly did lift when it was written; it measures zero now because the
model improved, not because the skill got worse. Nothing in the repository
would have told you that - the frontmatter was valid, the evals passed, CI was
green, and the SKILL.md was accurate. It had simply stopped being needed.

So a benchmark is committed per model version and diffed on the next one. The
output is a worklist, not a score:

  DECAYED   lift has fallen to roughly nothing. Shrink the skill to whatever
            the model still does not do, or reduce it to a stub. This is the
            expected end state for a skill that taught a fact rather than an
            ordering, because facts arrive in the weights eventually.
  IMPROVED  lift has risen. Usually the skill was edited; occasionally the
            model regressed. Worth knowing which.
  NEW/GONE  the eval set changed between the two runs, so the pair is not a
            comparison. Reported separately rather than silently skipped.

A shift smaller than --threshold is not reported. Two judges and a handful of
evals per skill do not resolve five points, and treating noise as decay is how
a good skill gets deleted.

Stdlib only.

Usage:
    python3 tools/diff_benchmark.py OLD.json NEW.json
    python3 tools/diff_benchmark.py OLD.json NEW.json --threshold 0.15
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 0.10
# Below this, a skill is doing nothing the model does not already do.
DEAD = 0.05


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    per = data.get("by_skill")
    if per is None:
        raise SystemExit(
            f"{path} has no by_skill block - it predates --model and cannot be "
            f"compared. Re-run aggregate_evals.py against its workspace.")
    return data.get("metadata", {}), per


def compare(old, new, threshold=DEFAULT_THRESHOLD):
    """Returns (moved, appeared, vanished). moved is (skill, was, now, verdict)."""
    moved = []
    for skill in sorted(set(old) & set(new)):
        was, now = old[skill]["delta"], new[skill]["delta"]
        shift = now - was
        if abs(shift) < threshold:
            continue
        if now <= DEAD < was:
            verdict = "DECAYED"
        elif shift < 0:
            verdict = "WEAKER"
        else:
            verdict = "IMPROVED"
        moved.append((skill, was, now, verdict))
    # Sort worst first: a decayed skill is the thing you act on.
    moved.sort(key=lambda m: m[2] - m[1])
    return moved, sorted(set(new) - set(old)), sorted(set(old) - set(new))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    old_meta, old = load(args.old)
    new_meta, new = load(args.new)

    print(f"old: {old_meta.get('model') or '(model not recorded)'}  "
          f"[{len(old)} skills]")
    print(f"new: {new_meta.get('model') or '(model not recorded)'}  "
          f"[{len(new)} skills]")
    print()

    moved, appeared, vanished = compare(old, new, args.threshold)

    if moved:
        width = max(len(s) for s, *_ in moved)
        for skill, was, now, verdict in moved:
            print(f"{verdict:<9} {skill:<{width}}  {was:+.0%} -> {now:+.0%}")
    else:
        print(f"no skill moved by {args.threshold:.0%} or more")

    if appeared:
        print(f"\nnot in the old benchmark ({len(appeared)}): {', '.join(appeared)}")
    if vanished:
        print(f"\nnot in the new benchmark ({len(vanished)}): {', '.join(vanished)}")

    decayed = [m for m in moved if m[3] == "DECAYED"]
    if decayed:
        print(f"\n{len(decayed)} skill(s) decayed to nothing. Shrink each to what the "
              f"model still does not do, or reduce it to a stub - on this evidence, "
              f"not on a hunch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
