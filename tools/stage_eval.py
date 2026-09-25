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

That isolation went too far. Staging an EMPTY directory also removed the task,
and eight skills measured +0% under it. A skill that changes an ordering - read
the issue before writing code, check the existing fixtures before inventing one,
diff the aggregate script against the workflow - cannot bite when there is
nothing to read: both arms answer from the prompt alone and converge on the same
essay. So an eval may name a `fixture`, a small real repository copied into the
sandbox identically for both arms. Fixtures live in eval-fixtures/ and carry the
properties being measured: a drifted constant, a test that asserts nothing, a
`verify` script that omits what CI runs.

An eval with no `fixture` runs bare, deliberately: a prompt that carries its
subject inline, or that is pure authoring, gains nothing from scenery.

The answer key lives in <workspace>/.keys/, NOT in the run directory. It used to
sit one level up from the sandbox, beside response.md, and a runner read it and
said so in its own report - so that run was answering against the expectations
it was about to be graded on. The prompt told it to stay in the sandbox and it
did not. Putting the key out of reach is the fix; asking more firmly is not.

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
FIXTURE_ROOT = ROOT / "eval-fixtures"


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

    fixture = ev.get("fixture")
    if fixture:
        src = FIXTURE_ROOT / fixture
        if not src.is_dir():
            sys.exit(f"{skill}#{eval_id} names fixture {fixture!r}, which does not exist")
        # Identical in both arms. If the arms ever differ by anything but the
        # skill, the delta stops meaning what it says.
        shutil.copytree(src, sandbox / fixture)

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

    # Out of the runner's reach. See the note in the module docstring.
    keys = Path(workspace) / ".keys"
    keys.mkdir(parents=True, exist_ok=True)
    (keys / f"{skill}-{eval_id}.json").write_text(
        json.dumps({"skill": skill, "eval_id": eval_id,
                    "prompt": ev["prompt"], "expectations": ev["expectations"],
                    "discriminating": ev.get("discriminating", []),
                    "fixture": fixture},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    response = (run_dir / "response.md").resolve()
    lines = []
    if skill_path:
        lines.append(f"Skill evaluation. FIRST read the skill at {skill_path} and follow its guidance.")
        lines.append("")
    if fixture:
        lines += [
            f"The repository you are working in is at {(sandbox / fixture).resolve()}.",
            "Read it before answering. It is the codebase the user is talking about.",
            "",
        ]
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
    prompt = "\n".join(lines)
    # Write the prompt to disk so a runner can be pointed at it rather than
    # having it pasted in, which keeps every run identical.
    (run_dir / "PROMPT.txt").write_text(prompt + "\n", encoding="utf-8")
    return run_dir, prompt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", nargs="?")
    parser.add_argument("eval_id", nargs="?", type=int)
    parser.add_argument("--config", choices=("with_skill", "without_skill"))
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--all-for", nargs="+", metavar="SKILL",
                        help="stage every eval of these skills, both configs")
    args = parser.parse_args(argv)

    if args.all_for:
        staged = 0
        for skill in args.all_for:
            data = json.loads((ROOT / skill / "evals" / "evals.json").read_text(encoding="utf-8"))
            for ev in data["evals"]:
                for config in ("with_skill", "without_skill"):
                    run_dir, _ = stage(skill, ev["id"], config, args.workspace)
                    print(f"{run_dir / 'PROMPT.txt'}")
                    staged += 1
        print(f"# staged {staged} run(s)", file=sys.stderr)
        return 0

    if not (args.skill and args.eval_id and args.config):
        parser.error("give SKILL EVAL_ID --config, or --all-for SKILL...")
    run_dir, prompt = stage(args.skill, args.eval_id, args.config, args.workspace)
    print(f"# staged {args.skill}#{args.eval_id} [{args.config}] -> {run_dir}")
    print("# ---- prompt below ----")
    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
