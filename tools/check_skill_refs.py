#!/usr/bin/env python3
"""
Fail when a SKILL.md points at a payload file that is not there.

Two consolidated skills shipped for weeks as an index of rule ids pointing at a
`rules/` directory that was never copied across with them. Nothing detected it -
the frontmatter was valid, the evals passed, and CI was green. An agent reading
the skill got a list of filenames and no files. That is the defect class this
catches.

One rule, deliberately narrow: a path under a payload directory the skill
actually HAS (references/, scripts/, assets/) must resolve. That catches a
rename, a deletion, or an id that never matched its filename - which is the
whole of the defect above once the payload is in place.

A wider rule was tried and removed. Flagging any `<dir>/<file>` whose directory
is absent produced 26 findings and one true positive: skills legitimately write
`docs/adr/`, `core/port/outbound/` and `.github/workflows/` meaning paths in the
READER's repository, and nothing in the text distinguishes those from a pointer
to the skill's own payload. A check that cries wolf 25 times out of 26 gets
switched off, so it does not exist.

Stdlib only.

Usage:
    python3 tools/check_skill_refs.py          # whole catalogue
    python3 tools/check_skill_refs.py SKILL    # one skill
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIRS = ("references", "scripts", "assets")

# A repo-relative path with at least one directory component and a file
# extension, or a bare directory path. Matched inside backticks and bare in a
# fenced-off reference list, which is how both index skills wrote theirs.
REF = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]*)")


def find_refs(text):
    """Candidate repo-relative paths mentioned in a SKILL.md."""
    # Strip fenced code that is clearly a shell/source sample rather than a
    # reference list: a line with a command in it is not a pointer to a file.
    refs = set()
    for m in REF.finditer(text):
        ref = m.group(1)
        if ref.startswith(("http", "//", "~")) or "://" in ref:
            continue
        refs.add(ref)
    return refs


def check_skill(skill_dir):
    """Errors for one skill directory."""
    errors = []
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    present = {d for d in PAYLOAD_DIRS if (skill_dir / d).is_dir()}

    for ref in sorted(find_refs(text)):
        head = ref.split("/", 1)[0]
        if head in present and not (skill_dir / ref).exists():
            errors.append(f"{skill_dir.name}: SKILL.md references {ref}, which does not exist")

    return errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if argv:
        skills = [ROOT / a for a in argv]
    else:
        skills = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))

    errors = []
    for s in skills:
        errors.extend(check_skill(s))

    for e in errors:
        print(f"error: {e}")
    print(f"{len(skills)} skill(s); {len(errors)} dangling reference(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
