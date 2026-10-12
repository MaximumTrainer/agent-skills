"""The filer.

Files a folder of drafts to GitHub in dependency order, writes issue
numbers back into each draft's frontmatter so the operation is
idempotent, then runs a second pass to resolve `blocked_by` / `blocks`
cross-refs by appending `Blocks: #N` / `Blocked by: #N` lines to the
body.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .drafts import Draft, load_drafts
from .gh import GhError, auth_status, create_issue, edit_issue_body, list_labels
from .order import topo_order


class LabelMismatch(Exception):
    pass


@dataclass
class FilerResult:
    created: list[tuple[str, int]]
    skipped: list[str]
    cross_refs: list[tuple[str, int]]


def _write_issue_number(draft: Draft, number: int) -> None:
    text = draft.path.read_text()
    lines = text.splitlines(keepends=True)
    # Insert `issue: N` just after the opening '---'.
    assert lines[0].rstrip() == "---"
    try:
        end = next(i for i, l in enumerate(lines[1:], start=1) if l.rstrip() == "---")
    except StopIteration:
        raise RuntimeError(f"no closing --- in {draft.path}")
    insertion = f"issue: {number}\n"
    new_lines = lines[:end] + [insertion] + lines[end:]
    draft.path.write_text("".join(new_lines))
    draft.issue = number


def _append_cross_refs(draft: Draft, blocks_nums: list[int], blocked_by_nums: list[int]) -> None:
    if not blocks_nums and not blocked_by_nums:
        return
    text = draft.path.read_text()
    extra = []
    if blocks_nums:
        extra.append("Blocks: " + ", ".join(f"#{n}" for n in blocks_nums))
    if blocked_by_nums:
        extra.append("Blocked by: " + ", ".join(f"#{n}" for n in blocked_by_nums))
    stamped = text.rstrip() + "\n\n" + "\n".join(extra) + "\n"
    draft.path.write_text(stamped)


def preflight(drafts: list[Draft], repo: str, allowed_labels: set[str]) -> None:
    """Validate against live repo state. Raises LabelMismatch on any gap."""
    missing: list[str] = []
    for d in drafts:
        for lab in d.labels:
            if lab not in allowed_labels:
                missing.append(f"{d.slug}: {lab}")
    if missing:
        raise LabelMismatch(
            "labels not present on " + repo + ":\n  " + "\n  ".join(missing)
        )


def file_all(
    drafts_dir: Path, repo: str, *, strict_labels: bool = True
) -> FilerResult:
    drafts = load_drafts(drafts_dir)
    auth_status()

    if strict_labels:
        live_labels = set(list_labels(repo))
        if live_labels:  # empty set = unknown; skip the check
            preflight(drafts, repo, live_labels)

    ordered = topo_order(drafts)

    created: list[tuple[str, int]] = []
    skipped: list[str] = []
    for d in ordered:
        if d.filed:
            skipped.append(d.slug)
            continue
        try:
            num = create_issue(
                repo=repo,
                title=d.title,
                body=d.body,
                labels=d.labels,
                milestone=d.milestone,
            )
        except GhError:
            # Write-back only on success; let the caller see the error
            # and know to re-run (idempotent on prior successes).
            raise
        _write_issue_number(d, num)
        created.append((d.slug, num))

    # Second pass: resolve cross-refs now that every slug has a number.
    slug_to_num = {d.slug: d.issue for d in load_drafts(drafts_dir) if d.issue}
    cross_refs: list[tuple[str, int]] = []
    for d in load_drafts(drafts_dir):
        if d.issue is None:
            continue
        blocks_nums = [slug_to_num[s] for s in d.blocks if s in slug_to_num]
        blocked_by_nums = [slug_to_num[s] for s in d.blocked_by if s in slug_to_num]
        if blocks_nums or blocked_by_nums:
            new_body = d.body
            extras = []
            if blocks_nums:
                extras.append("Blocks: " + ", ".join(f"#{n}" for n in blocks_nums))
            if blocked_by_nums:
                extras.append("Blocked by: " + ", ".join(f"#{n}" for n in blocked_by_nums))
            new_body = new_body.rstrip() + "\n\n" + "\n".join(extras) + "\n"
            edit_issue_body(repo=repo, number=d.issue, body=new_body)
            cross_refs.append((d.slug, d.issue))

    return FilerResult(created=created, skipped=skipped, cross_refs=cross_refs)
