"""Load drafts from a folder, preserving dependency metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Draft:
    path: Path
    slug: str
    title: str
    repo: str
    labels: list[str] = field(default_factory=list)
    milestone: str | None = None
    blocks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    parent: str | None = None
    body: str = ""
    issue: int | None = None  # filled in after filing

    @property
    def filed(self) -> bool:
        return self.issue is not None


def _split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            fm = yaml.safe_load("".join(lines[1:i])) or {}
            body = "".join(lines[i + 1 :]).lstrip("\n")
            return fm, body
    return {}, text


def load_drafts(folder: Path) -> list[Draft]:
    drafts: list[Draft] = []
    for path in sorted(folder.iterdir()):
        if path.suffix != ".md":
            continue
        text = path.read_text()
        fm, body = _split_frontmatter(text)
        drafts.append(
            Draft(
                path=path,
                slug=fm.get("slug", path.stem),
                title=fm.get("title", path.stem),
                repo=fm.get("repo", ""),
                labels=list(fm.get("labels") or []),
                milestone=fm.get("milestone"),
                blocks=list(fm.get("blocks") or []),
                blocked_by=list(fm.get("blocked_by") or []),
                parent=fm.get("parent"),
                body=body,
                issue=fm.get("issue"),
            )
        )
    return drafts
