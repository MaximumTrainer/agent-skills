"""Review parser.

Splits a review markdown doc on `## Gap:` headings. Each gap becomes
one Gap record: title, body (prose), and the hints line
(`Area: X. Size: Y. Type: Z.`) parsed into a dict.

Kept deliberately dumb: no NLP, no inference. The review author writes
hints the parser knows how to read, and the renderer fills the five
sections from the body + hints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


GAP_RE = re.compile(r"^## Gap:\s*(.+?)\s*$", re.MULTILINE)
SLICES_RE = re.compile(r"^### Slices\s*$", re.MULTILINE)
# e.g. "- AUTH-1: Signed-principal plumbing (Size: M)"
SLICE_LINE_RE = re.compile(
    r"^-\s*(?P<key>[A-Z]+-\d+)\s*:\s*(?P<title>.+?)\s*\(Size:\s*(?P<size>S|M|L)\)\s*$",
    re.MULTILINE,
)

# "Area: ontology. Size: M. Type: feature." → {area: ontology, size: M, type: feature}
HINT_RE = re.compile(r"([A-Za-z]+)\s*:\s*([A-Za-z0-9_-]+)")


@dataclass
class Slice:
    key: str          # e.g. "AUTH-1"
    title: str        # e.g. "Signed-principal plumbing on read path, deny-by-default"
    size: str         # "S" | "M" | "L"


@dataclass
class Gap:
    title: str
    body: str
    hints: dict[str, str] = field(default_factory=dict)
    slices: list[Slice] = field(default_factory=list)


def parse_review(text: str) -> list[Gap]:
    # Split on `## Gap:` so each chunk starts after a heading.
    parts = GAP_RE.split(text)
    # parts = [preamble, title1, body1, title2, body2, ...]
    gaps: list[Gap] = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body_raw = parts[i + 1].strip()
        body_without_slices, slices = _split_slices(body_raw)
        body, hints = _split_hints(body_without_slices)
        gaps.append(Gap(title=title, body=body, hints=hints, slices=slices))
    return gaps


def _split_slices(body: str) -> tuple[str, list[Slice]]:
    """Pull a `### Slices` subsection out and parse its bullets."""
    m = SLICES_RE.search(body)
    if not m:
        return body, []
    before = body[: m.start()].rstrip()
    after = body[m.end():]
    slices = [
        Slice(key=sm.group("key"), title=sm.group("title"), size=sm.group("size"))
        for sm in SLICE_LINE_RE.finditer(after)
    ]
    return before, slices


def _split_hints(body: str) -> tuple[str, dict[str, str]]:
    """Pull the hints line out of a gap body.

    The hints line is the last non-empty line containing `Key: value`
    pairs separated by '. '. Everything above it is the prose body.
    """
    lines = body.splitlines()
    # Find the last non-empty line.
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip():
            last = lines[idx].strip()
            found = dict(HINT_RE.findall(last))
            # Heuristic: it's a hints line iff it carries ≥2 Key:Value pairs
            # and no sentence structure beyond them.
            if len(found) >= 2 and _looks_like_hints_line(last):
                prose = "\n".join(lines[:idx]).strip()
                return prose, {k.lower(): v for k, v in found.items()}
            break
    return body, {}


def _looks_like_hints_line(line: str) -> bool:
    # Allow "Area: X. Size: Y. Type: Z." style; reject prose that happens
    # to contain a colon.
    stripped = line.rstrip(".")
    chunks = [c.strip() for c in stripped.split(".") if c.strip()]
    return all(":" in c and len(c.split()) <= 3 for c in chunks)
