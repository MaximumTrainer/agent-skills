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

It also prints the judge prompt, so the rubric is versioned here rather than
retyped per run. Retyping is how a rubric drifts between the runs you are
comparing.

Usage:
    python3 tools/make_judge_keys.py <workspace> [SKILL ...]
    python3 tools/make_judge_keys.py <workspace> --prompts        # one per line
"""

import json
import random
import sys
from pathlib import Path

CONFIGS = ("with_skill", "without_skill")

JUDGE_PROMPT = """Grade two candidate answers against a fixed expectation list. You do not know which answer came from which condition, and it does not matter.

Working directory: `{run_dir}`

1. Read `JUDGE.json`. Its `expectations` array is what you grade against. `arm_A` and `arm_B` are subdirectory names.
2. Read `<arm_A>/response.md` (answer A) and `<arm_B>/response.md` (answer B), in FULL.
3. For each expectation, decide independently for A and for B whether that answer satisfies it.

Grading rules - these matter more than anything:
- Judge SUBSTANCE, not wording. Different words conveying the same thing PASS. Never require a specific phrase.
- It passes if a competent reader would come away knowing the thing. It need not be the headline.
- Do not reward length. A short answer that says it passes; a long one that never does fails.
- Where an expectation says "first" or "most severe", check actual ordering/emphasis.
- An expectation that rewards reporting a result is satisfied by honestly saying the check was not run. Never credit a claimed verification that could not have happened here.
- Be willing to pass both or fail both. There is no expected split.

4. Write `<arm_A>/{filename}` and `<arm_B>/{filename}`, each exactly:
{{"expectations": [{{"text": "<expectation verbatim>", "passed": true, "evidence": "<short quote or why it fails>"}}], "summary": {{"passed": N, "failed": M, "total": T, "pass_rate": 0.0}}}}

pass_rate = passed/total to 4 dp. UTF-8 encoding. Overwrite any existing file at that name.

Read no other file. Do not read the skill under test, and do not look at the agent-skills repository.
Final message: one line, `A <n>/<total> vs B <n>/<total>`."""


def judge_prompt(run_dir, judge=1):
    """The prompt for one judge on one eval. Judge N writes grading[.N].json."""
    filename = "grading.json" if judge == 1 else f"grading.{judge}.json"
    return JUDGE_PROMPT.format(run_dir=run_dir, filename=filename)


def write_keys(workspace, only=(), rng=None):
    """Write JUDGE.json for each eval dir; returns the names written."""
    rng = rng or random.Random()
    written = []
    for d in sorted(p for p in Path(workspace).iterdir() if p.is_dir()):
        skill = d.name.rsplit("-", 1)[0]
        if only and skill not in only:
            continue
        src = Path(workspace) / ".keys" / f"{d.name}.json"
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
    rest = [a for a in argv[1:] if not a.startswith("--")]
    written = write_keys(workspace, only=set(rest))

    if "--prompts" in argv:
        for name in written:
            for judge in (1, 2):
                print(judge_prompt((workspace / name).resolve(), judge))
                print("=" * 8)
        return 0

    for name in written:
        print(f"  {name}")
    print(f"wrote {len(written)} judge key(s); "
          f"--prompts emits the judge prompt for each (2 judges per eval)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
