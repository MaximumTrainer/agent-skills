#!/usr/bin/env python3
"""
Stage one eval run, and print the exact prompt to give the runner.

Exists because of a measurement failure: a baseline run wandered the working
directory, read container-integration-tests/SKILL.md, and answered using the
very skill it was supposed to be blind to. That comparison was void and we only
caught it because the runner mentioned it. A baseline that quietly reads a skill
off disk produces a delta of zero and looks like a finding.

So a baseline runs in a scratch directory outside the repository, with no skill
present and no path back to one. The with-skill arm gets the skill copied in,
and nothing else from the catalogue - so it cannot lean on a neighbouring skill
either.

Stdlib only.

Usage:
    python3 tools/stage_eval.py SKILL EVAL_ID --config with_skill   --workspace DIR
    python3 tools/stage_eval.py SKILL EVAL_ID --config without_skill --workspace DIR
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIRS = ("references", "scripts", "assets")


def load_eval(skill, eval_id):
    path = ROOT / skill / "evals" / "evals.json"
    if not path.is_file():
        sys.exit(f"no evals for {skill}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for ev in data["evals"]:
        if ev["id"] == eval_id:
            return ev
    sys.exit(f"{skill} has no eval {eval_id}")


def stage(skill, eval_id, config, workspace):
    ev = load_eval(skill, eval_id)
    run_dir = Path(workspace) / f"{skill}-{eval_id}" / config
    sandbox = run_dir / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    if config == "with_skill":
        # Only this skill. Not the catalogue, not its siblings, not the tooling.
        target = sandbox / skill
        target.mkdir()
        shutil.copy(ROOT / skill / "SKILL.md", target / "SKILL.md")
        for sub in PAYLOAD_DIRS:
            src = ROOT / skill / sub
            if src.is_dir():
                shutil.copytree(src, target / sub)
        skill_path = (target / "SKILL.md").resolve()
    else:
        skill_path = None

    (run_dir / "eval.json").write_text(
        json.dumps({"skill": skill, "eval_id": eval_id, "config": config,
                    "prompt": ev["prompt"], "expectations": ev["expectations"],
                    "discriminating": ev.get("discriminating", [])},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    response = (run_dir / "response.md").resolve()
    lines = []
    if skill_path:
        lines.append(f"Skill evaluation. FIRST read the skill at {skill_path} and follow its guidance.")
        lines.append("")
    lines += [
        "Work only inside this directory:",
        f"  {sandbox.resolve()}",
        "Do not read files outside it, and do not search other directories for",
        "guidance, conventions or skills. Answer from the task and what is here.",
        "",
        "USER TASK:",
        f'"{ev["prompt"]}"',
        "",
        "Answer as if replying to a real user. Do not ask clarifying questions -",
        "make reasonable assumptions and proceed.",
        "",
        f"SAVE YOUR COMPLETE RESPONSE to: {response}",
        "Final message: just confirm the file was written.",
    ]
    return run_dir, "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("skill")
    parser.add_argument("eval_id", type=int)
    parser.add_argument("--config", choices=("with_skill", "without_skill"), required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)

    run_dir, prompt = stage(args.skill, args.eval_id, args.config, args.workspace)
    print(f"# staged {args.skill}#{args.eval_id} [{args.config}] -> {run_dir}")
    print("# ---- prompt below ----")
    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
