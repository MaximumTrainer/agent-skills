#!/usr/bin/env python3
"""
Validate that every skill has evals, and that those evals are worth having.

Presence is the easy half. The half that matters is whether an expectation
actually discriminates: an expectation any competent model would satisfy without
the skill tells you nothing about the skill. This checks the mechanical
properties that correlate with a useful eval and leaves judgement to review.

Stdlib only.

Usage:
    python3 tools/check_evals.py            # validate every skill
    python3 tools/check_evals.py --stats     # also print a per-skill summary
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MIN_EVALS = 2
MIN_EXPECTATIONS = 3
MIN_PROMPT_CHARS = 40
MAX_EXPECTATION_CHARS = 220

# An expectation phrased this loosely cannot be graded consistently.
VAGUE = re.compile(
    r"\b(appropriate(ly)?|correct(ly)?|properly|good|reasonable|sensible|as expected"
    r"|works?\s+(well|fine)|handles?\s+it|makes sense)\b",
    re.I,
)


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e


def check_skill(name, errors, warnings, stats, n_discriminating=None):
    n_discriminating = n_discriminating if n_discriminating is not None else [0]
    path = ROOT / name / "evals" / "evals.json"
    if not path.is_file():
        errors.append(f"{name}: no evals/evals.json")
        return

    try:
        data = load(path)
    except ValueError as e:
        errors.append(f"{name}: {e}")
        return

    if data.get("skill_name") != name:
        errors.append(f"{name}: skill_name is '{data.get('skill_name')}', expected '{name}'")

    evals = data.get("evals")
    if not isinstance(evals, list) or not evals:
        errors.append(f"{name}: evals must be a non-empty list")
        return
    if len(evals) < MIN_EVALS:
        errors.append(f"{name}: only {len(evals)} eval(s), want at least {MIN_EVALS}")

    seen_ids, seen_prompts = set(), set()
    n_expect = 0

    for ev in evals:
        eid = ev.get("id")
        label = f"{name}#{eid}"

        if not isinstance(eid, int):
            errors.append(f"{label}: id must be an integer")
        elif eid in seen_ids:
            errors.append(f"{label}: duplicate id")
        else:
            seen_ids.add(eid)

        for field in ("prompt", "expected_output"):
            if not isinstance(ev.get(field), str) or not ev[field].strip():
                errors.append(f"{label}: {field} is missing or empty")

        prompt = ev.get("prompt", "")
        if isinstance(prompt, str):
            if len(prompt) < MIN_PROMPT_CHARS:
                errors.append(f"{label}: prompt is too short to be realistic ({len(prompt)} chars)")
            if prompt.strip().lower() in seen_prompts:
                errors.append(f"{label}: duplicate prompt")
            seen_prompts.add(prompt.strip().lower())

        if not isinstance(ev.get("files"), list):
            errors.append(f"{label}: files must be a list (use [] when there are none)")
        else:
            for f in ev["files"]:
                if not (ROOT / name / f).is_file() and not (ROOT / f).is_file():
                    errors.append(f"{label}: referenced file not found: {f}")

        expectations = ev.get("expectations")
        if not isinstance(expectations, list) or len(expectations) < MIN_EXPECTATIONS:
            errors.append(
                f"{label}: needs at least {MIN_EXPECTATIONS} expectations, "
                f"got {len(expectations) if isinstance(expectations, list) else 'none'}"
            )
            continue

        n_expect += len(expectations)
        if len(set(e.strip().lower() for e in expectations)) != len(expectations):
            errors.append(f"{label}: duplicate expectations")

        # At least one expectation must be one the skill alone should produce.
        # Without this, an eval can pass entirely on things the model already
        # does, which measures the model rather than the skill. The pilot found
        # 28 of 37 expectations passing in both arms, which is what this stops.
        fixture = ev.get("fixture")
        if fixture is not None:
            if not isinstance(fixture, str) or not fixture:
                errors.append(f"{label}: fixture must be a non-empty string")
            elif not (ROOT / "eval-fixtures" / fixture).is_dir():
                errors.append(f"{label}: fixture {fixture!r} is not in eval-fixtures/")

        marks = ev.get("discriminating")
        if not isinstance(marks, list) or not marks:
            errors.append(
                f"{label}: no discriminating expectations. Mark the index of at least one "
                f"expectation the skill alone should produce, as \"discriminating\": [i]"
            )
        else:
            if len(set(marks)) != len(marks):
                errors.append(f"{label}: duplicate entries in discriminating")
            for i in marks:
                if not isinstance(i, int) or not 0 <= i < len(expectations):
                    errors.append(
                        f"{label}: discriminating index {i!r} is out of range "
                        f"(0..{len(expectations) - 1})"
                    )
            if len(marks) == len(expectations):
                warnings.append(
                    f"{label}: every expectation is marked discriminating, which is "
                    f"unlikely - the mark loses meaning if it is not selective"
                )
            n_discriminating[0] += len(marks)

        for text in expectations:
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{label}: empty expectation")
                continue
            if len(text) > MAX_EXPECTATION_CHARS:
                warnings.append(f"{label}: expectation is very long, may be hard to grade: {text[:60]}...")
            # Strip quoted fragments first: an expectation that quotes a vague
            # word from the prompt ("identifies that 'appropriate' is not
            # verifiable") is precise about something imprecise, not vague.
            unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", "", text)
            if VAGUE.search(unquoted):
                warnings.append(f"{label}: vague wording, hard to grade objectively: {text[:80]}")

    stats.append((name, len(evals), n_expect))


def main(argv):
    skills = sorted(p.parent.name for p in ROOT.glob("*/SKILL.md"))
    errors, warnings, stats = [], [], []
    n_discriminating = [0]

    for name in skills:
        check_skill(name, errors, warnings, stats, n_discriminating)

    if "--stats" in argv:
        print(f"{'skill':<32} {'evals':>6} {'expectations':>13}")
        for name, n, x in stats:
            print(f"{name:<32} {n:>6} {x:>13}")
        print()

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)

    total_e = sum(s[1] for s in stats)
    total_x = sum(s[2] for s in stats)
    print(
        f"{len(skills)} skill(s), {total_e} eval(s), {total_x} expectation(s) "
        f"({n_discriminating[0]} discriminating); "
        f"{len(errors)} error(s), {len(warnings)} warning(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
