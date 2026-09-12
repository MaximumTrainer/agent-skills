#!/usr/bin/env python3
"""
Validate the skill and package it as a .skill (zip) file.

Only runtime files are packaged; tests, evals, CI config and tooling stay in
the repo. Stdlib only.

Usage:
    python3 tools/package_skill.py            # validate + write dist/minimal-docker.skill
    python3 tools/package_skill.py OUT_DIR    # write to OUT_DIR
    python3 tools/package_skill.py --check    # validate only
"""

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "minimal-docker"

# Everything shipped inside the .skill. Anything not listed is left out.
INCLUDE = ["SKILL.md", "README.md", "LICENSE", "references", "scripts", "assets"]
EXCLUDE_PARTS = {"__pycache__", ".DS_Store"}
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("SKILL.md has no YAML frontmatter")
    fields = {}
    for line in m.group(1).splitlines():
        top = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if top:
            fields[top.group(1)] = top.group(2).strip().strip('"')
    return fields


def validate():
    errors = []
    skill_md = ROOT / "SKILL.md"
    if not skill_md.is_file():
        return ["SKILL.md not found"]
    try:
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
    except ValueError as e:
        return [str(e)]

    unexpected = set(fm) - ALLOWED_KEYS
    if unexpected:
        errors.append(f"unexpected frontmatter keys: {sorted(unexpected)}")
    name = fm.get("name", "")
    if name != SKILL_NAME:
        errors.append(f"name must be '{SKILL_NAME}', got '{name}'")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("name must be kebab-case and at most 64 characters")
    desc = fm.get("description", "")
    if not desc:
        errors.append("description is missing")
    elif len(desc) > 1024:
        errors.append(f"description is {len(desc)} chars (max 1024)")
    elif "<" in desc or ">" in desc:
        errors.append("description cannot contain angle brackets")

    body = skill_md.read_text(encoding="utf-8")
    if len(body.splitlines()) > 500:
        errors.append("SKILL.md is over 500 lines; move detail into references/")

    # Every file SKILL.md points at must exist.
    for ref in sorted(set(re.findall(r"`((?:references|scripts|assets)/[\w./-]+)`", body))):
        if not (ROOT / ref).exists():
            errors.append(f"SKILL.md references missing file: {ref}")

    # Only one SKILL.md may be packaged.
    extra = [p for p in iter_files() if p.name == "SKILL.md" and p != skill_md]
    if extra:
        errors.append(f"extra SKILL.md files would be packaged: {extra}")
    return errors


def iter_files():
    for entry in INCLUDE:
        path = ROOT / entry
        if path.is_file():
            yield path
        elif path.is_dir():
            for p in sorted(path.rglob("*")):
                if p.is_file() and not (set(p.parts) & EXCLUDE_PARTS) and p.suffix != ".pyc":
                    yield p


def package(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{SKILL_NAME}.skill"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in iter_files():
            arc = Path(SKILL_NAME) / p.relative_to(ROOT)
            info = zipfile.ZipInfo.from_file(p, arc)
            info.date_time = (2026, 1, 1, 0, 0, 0)  # stable timestamps -> reproducible zip
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, p.read_bytes())
            print(f"  + {arc}")
    return target


def main():
    args = sys.argv[1:]
    errors = validate()
    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("Skill is valid.")
    if "--check" in args:
        return
    out = Path(args[0]) if args else ROOT / "dist"
    print(f"\nPackaging {SKILL_NAME}:")
    target = package(out)
    print(f"\nWrote {target}")


if __name__ == "__main__":
    main()
