#!/usr/bin/env python3
"""
Bump the metadata.version of every skill that has staged changes.

Intended to run from the pre-commit hook (see .githooks/pre-commit), which is
the only hook whose `git add` reliably lands in the commit being created -
prepare-commit-msg and commit-msg both stage into the *next* commit and leave a
dirty index.

Semantics:
  - A skill is any top-level directory containing a SKILL.md.
  - A skill is "touched" when the commit stages any file inside its directory.
  - A touched skill's patch version is bumped, and SKILL.md is re-staged.
  - A skill whose version was already changed in this commit is left alone, so a
    manual bump and `git commit --amend` are both respected.
  - A skill whose only staged change is the version line is left alone, so the
    hook cannot bump itself in a loop.
  - A brand-new skill keeps the version it declares; first commit is not a bump.

Stdlib only.

Usage:
    python3 tools/bump_skill_versions.py --staged                 # hook mode
    python3 tools/bump_skill_versions.py --staged --dry-run       # report only
    python3 tools/bump_skill_versions.py --staged --only-on-branch main
    python3 tools/bump_skill_versions.py --all --level minor      # bump everything
    python3 tools/bump_skill_versions.py --check                  # validate, no writes

Bump level comes from --level, or the SKILL_BUMP environment variable:
    SKILL_BUMP=minor git commit -m "feat: add a new section"
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ("patch", "minor", "major")
VERSION_RE = re.compile(r"^(?P<indent>\s+)version:\s*(?P<quote>\"?)(?P<version>[^\"\s]+)(?P=quote)\s*$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


# --- git helpers -------------------------------------------------------------


def git(*args, check=True):
    """
    Run a git command in the repo root and return stdout, or None on failure.

    encoding is pinned to UTF-8 deliberately. `text=True` alone decodes with the
    locale codec, which is cp1252 on a default Windows Python - and SKILL.md
    files contain em-dashes, so `git show` output raised UnicodeDecodeError in a
    reader thread. stdout then came back empty and every edited skill looked
    like a new one, so nothing was bumped and nothing reported an error.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        if check:
            raise RuntimeError(f"git {' '.join(args)} failed: {(result.stderr or '').strip()}")
        return None
    return result.stdout


def current_branch():
    out = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return out.strip() if out else None


def has_head():
    return git("rev-parse", "--verify", "HEAD", check=False) is not None


def staged_paths():
    """Paths added, copied, modified or renamed in the index."""
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [line.strip() for line in out.splitlines() if line.strip()]


def head_text(relpath):
    """
    File content at HEAD, or None when the file genuinely is not in HEAD.

    Existence is tested separately from reading so that a read failure cannot
    masquerade as "this is a new skill" - that ambiguity is what let a decoding
    bug silently disable every bump.
    """
    if not has_head():
        return None
    if git("cat-file", "-e", f"HEAD:{relpath}", check=False) is None:
        return None
    text = git("show", f"HEAD:{relpath}", check=False)
    if text is None:
        raise RuntimeError(f"{relpath} is in HEAD but could not be read")
    return text


# --- skill discovery and version handling ------------------------------------


def discover_skills():
    """Top-level directories containing a SKILL.md, by directory name."""
    return sorted(p.parent.name for p in ROOT.glob("*/SKILL.md"))


def read_preserving_newlines(path):
    """Return (text_with_lf, newline) so the file can be written back unchanged."""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def write_preserving_newlines(path, text, newline):
    data = text.replace("\n", newline) if newline != "\n" else text
    path.write_bytes(data.encode("utf-8"))


def frontmatter_bounds(text):
    """(start, end) character offsets of the frontmatter body, or None."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.start(1), m.end(1)) if m else None


def find_version(text):
    """
    Locate metadata.version inside the frontmatter.

    Returns (version_string, line_index) or (None, None). Only a `version:`
    indented under a `metadata:` key counts, so a top-level `version:` elsewhere
    is not mistaken for it.
    """
    bounds = frontmatter_bounds(text)
    if not bounds:
        return None, None
    start, end = bounds
    lines = text[start:end].split("\n")
    offset = text[:start].count("\n")
    in_metadata = False
    for i, line in enumerate(lines):
        if re.match(r"^metadata:\s*$", line):
            in_metadata = True
            continue
        if in_metadata:
            m = VERSION_RE.match(line)
            if m:
                return m.group("version"), offset + i
            # a new unindented key ends the metadata block
            if line and not line[0].isspace():
                in_metadata = False
    return None, None


def bump(version, level):
    m = SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"'{version}' is not a MAJOR.MINOR.PATCH version")
    major, minor, patch = (int(g) for g in m.groups())
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def replace_version(text, line_index, new_version):
    lines = text.split("\n")
    m = VERSION_RE.match(lines[line_index])
    if not m:
        raise ValueError(f"line {line_index + 1} is not a version line")
    quote = m.group("quote")
    lines[line_index] = f"{m.group('indent')}version: {quote}{new_version}{quote}"
    return "\n".join(lines)


# --- modes -------------------------------------------------------------------


def run_check():
    """Every skill must carry a valid semver metadata.version."""
    errors = []
    skills = discover_skills()
    if not skills:
        errors.append("no skills found (expected */SKILL.md)")
    for name in skills:
        path = ROOT / name / "SKILL.md"
        text, _ = read_preserving_newlines(path)
        if not frontmatter_bounds(text):
            errors.append(f"{name}: SKILL.md has no YAML frontmatter")
            continue
        version, _ = find_version(text)
        if version is None:
            errors.append(f"{name}: no metadata.version in frontmatter")
        elif not SEMVER_RE.match(version):
            errors.append(f"{name}: version '{version}' is not MAJOR.MINOR.PATCH")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    print(f"checked {len(skills)} skill(s); {len(errors)} problem(s)")
    return 1 if errors else 0


def touched_skills(paths, skills):
    """Skill names whose directory contains at least one of the given paths."""
    known = set(skills)
    touched = set()
    for p in paths:
        top = p.split("/", 1)[0]
        if top in known:
            touched.add(top)
    return sorted(touched)


def only_version_changed(name, relpath):
    """True when the staged diff for SKILL.md touches nothing but the version line."""
    diff = git("diff", "--cached", "--unified=0", "--", relpath, check=False) or ""
    changed = [
        line
        for line in diff.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith(("+++", "---"))
    ]
    if not changed:
        return False
    return all(re.match(r"^[+-]\s+version:", line) for line in changed)


def run_staged(level, dry_run, only_on_branch):
    branch = current_branch()
    if only_on_branch and branch != only_on_branch:
        where = f"branch '{branch}'" if branch else "a detached HEAD"
        print(f"skill-version: on {where}, not '{only_on_branch}' - no version bump")
        return 0

    skills = discover_skills()
    paths = staged_paths()
    targets = touched_skills(paths, skills)
    if not targets:
        return 0

    bumped, skipped = [], []
    for name in targets:
        relpath = f"{name}/SKILL.md"
        path = ROOT / name / "SKILL.md"
        if not path.is_file():
            continue

        text, newline = read_preserving_newlines(path)
        version, line_index = find_version(text)
        if version is None:
            skipped.append((name, "no metadata.version"))
            continue

        previous = head_text(relpath)
        if previous is None:
            skipped.append((name, f"new skill, keeping {version}"))
            continue

        head_version, _ = find_version(previous.replace("\r\n", "\n"))
        if head_version is not None and head_version != version:
            skipped.append((name, f"already {head_version} -> {version} in this commit"))
            continue

        if only_version_changed(name, relpath):
            skipped.append((name, "only the version line changed"))
            continue

        try:
            new_version = bump(version, level)
        except ValueError as e:
            skipped.append((name, str(e)))
            continue

        if not dry_run:
            write_preserving_newlines(path, replace_version(text, line_index, new_version), newline)
            git("add", "--", relpath)
        bumped.append((name, version, new_version))

    verb = "would bump" if dry_run else "bumped"
    for name, old, new in bumped:
        print(f"skill-version: {verb} {name} {old} -> {new} ({level})")
    for name, reason in skipped:
        print(f"skill-version: skipped {name} ({reason})")
    return 0


def run_all(level, dry_run):
    for name in discover_skills():
        path = ROOT / name / "SKILL.md"
        text, newline = read_preserving_newlines(path)
        version, line_index = find_version(text)
        if version is None:
            print(f"skill-version: skipped {name} (no metadata.version)")
            continue
        try:
            new_version = bump(version, level)
        except ValueError as e:
            print(f"skill-version: skipped {name} ({e})")
            continue
        if not dry_run:
            write_preserving_newlines(path, replace_version(text, line_index, new_version), newline)
        print(f"skill-version: {'would bump' if dry_run else 'bumped'} {name} {version} -> {new_version}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="bump skills with staged changes (hook mode)")
    mode.add_argument("--all", action="store_true", help="bump every skill")
    mode.add_argument("--check", action="store_true", help="validate versions, write nothing")
    parser.add_argument("--level", choices=LEVELS, default=None, help="bump level (default: patch, or $SKILL_BUMP)")
    parser.add_argument("--dry-run", action="store_true", help="report without writing or staging")
    parser.add_argument("--only-on-branch", metavar="NAME", default=None, help="do nothing unless on this branch")
    args = parser.parse_args(argv)

    if args.check:
        return run_check()

    level = args.level or os.environ.get("SKILL_BUMP", "patch").strip().lower()
    if level not in LEVELS:
        print(f"error: bump level must be one of {', '.join(LEVELS)}, got '{level}'", file=sys.stderr)
        return 2

    if args.all:
        return run_all(level, args.dry_run)
    return run_staged(level, args.dry_run, args.only_on_branch)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        # Never block a commit because of a tooling failure.
        print(f"skill-version: {e}", file=sys.stderr)
        sys.exit(0)
