"""Persistent slug assignment.

Problem: naive `{prefix}-{idx}` numbering renumbers everything the
moment a gap is added or reordered in the source review. If any of
those gaps are already filed as GitHub issues, the slug drift breaks
the link.

Solution: a JSON sidecar that maps a stable key (hash of the title) to
the slug assigned on first sight. Rerun with the same sidecar → every
title that was there before keeps its slug; new titles get fresh ones
after the max currently in use.

The sidecar is small and human-readable. It lives next to the review
or in a chosen path via --slugs. Missing file → empty map, as if we're
starting fresh.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def _key(title: str) -> str:
    # Normalise whitespace + case so cosmetic edits don't trigger a new slug.
    norm = re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def load(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text())


def save(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")


def assign(
    titles: list[str], slug_prefix: str, existing: dict[str, str]
) -> dict[str, str]:
    """Return title → slug for every title, reusing existing entries."""
    out: dict[str, str] = {}
    used_nums: set[int] = set()
    for slug in existing.values():
        if slug.startswith(slug_prefix + "-"):
            tail = slug[len(slug_prefix) + 1 :]
            if tail.isdigit():
                used_nums.add(int(tail))

    next_num = max(used_nums) + 1 if used_nums else 1

    for title in titles:
        key = _key(title)
        if key in existing:
            out[title] = existing[key]
            continue
        slug = f"{slug_prefix}-{next_num:02d}"
        used_nums.add(next_num)
        next_num += 1
        out[title] = slug
    return out


def updated_sidecar(
    titles: list[str], assigned: dict[str, str], existing: dict[str, str]
) -> dict[str, str]:
    """Return the new sidecar: existing kept intact, new titles added by key."""
    out = dict(existing)
    for title in titles:
        out[_key(title)] = assigned[title]
    return out
