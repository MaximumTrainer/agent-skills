#!/usr/bin/env python3
"""
Generate catalogue.json from the skills in this repository.

catalogue.json is what a seeded repo fetches to discover what is available here,
in one request rather than one per skill. It is derived from the SKILL.md files,
never hand-edited, and CI fails if it drifts from them.

Deliberately contains no timestamp, no commit SHA and no version of its own:
anything non-deterministic would make the drift check fail on every run. See the
docs-drift-guard skill.

Stdlib only.

Usage:
    python3 tools/build_catalogue.py           # write catalogue.json
    python3 tools/build_catalogue.py --check    # fail if it is out of date
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue.json"
SOURCE_REPO = "MaximumTrainer/agent-skills"

# Directories inside a skill that are part of the skill and get vendored with it.
PAYLOAD_DIRS = ("references", "scripts", "assets")
SKIP_PARTS = {"__pycache__", ".DS_Store"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    fields = {}
    key = None
    for line in m.group(1).split("\n"):
        top = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if top:
            key = top.group(1)
            fields[key] = top.group(2).strip().strip('"')
        elif key and line.startswith(" "):
            nested = re.match(r"^\s+([A-Za-z][\w-]*):\s*(.*)$", line)
            if nested:
                fields[f"{key}.{nested.group(1)}"] = nested.group(2).strip().strip('"')
    return fields


def skill_files(directory):
    """SKILL.md plus README and any payload directories, as repo-relative paths."""
    files = ["SKILL.md"]
    if (directory / "README.md").is_file():
        files.append("README.md")
    for sub in PAYLOAD_DIRS:
        base = directory / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not set(path.parts) & SKIP_PARTS:
                files.append(path.relative_to(directory).as_posix())
    return files


def build():
    skills = []
    for skill_md in sorted(ROOT.glob("*/SKILL.md")):
        directory = skill_md.parent
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
        name = fm.get("name") or directory.name
        skills.append(
            {
                "name": name,
                "directory": directory.name,
                "version": fm.get("metadata.version", "0.0.0"),
                "license": fm.get("license", ""),
                "description": fm.get("description", ""),
                "files": skill_files(directory),
            }
        )
    return {
        "source": SOURCE_REPO,
        "schema": 1,
        "skills": skills,
    }


def serialise(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv):
    check = "--check" in argv
    data = serialise(build())

    if check:
        if not CATALOGUE.is_file():
            print("error: catalogue.json is missing; run tools/build_catalogue.py", file=sys.stderr)
            return 1
        current = CATALOGUE.read_text(encoding="utf-8")
        if current != data:
            print(
                "error: catalogue.json is out of date with the SKILL.md files.\n"
                "       run: python3 tools/build_catalogue.py",
                file=sys.stderr,
            )
            return 1
        print(f"catalogue.json is up to date ({len(json.loads(current)['skills'])} skills)")
        return 0

    CATALOGUE.write_text(data, encoding="utf-8")
    print(f"wrote {CATALOGUE.relative_to(ROOT)} ({len(json.loads(data)['skills'])} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
