"""Topological ordering of drafts by blocked_by.

A draft with `blocked_by: [X]` must be filed after X's draft is filed,
because the body-level cross-ref needs X's issue number. Cycles are
treated as an authoring error — reported, not resolved.
"""

from __future__ import annotations

from .drafts import Draft


class CycleError(Exception):
    pass


def topo_order(drafts: list[Draft]) -> list[Draft]:
    by_slug = {d.slug: d for d in drafts}
    order: list[Draft] = []
    seen: set[str] = set()
    temp: set[str] = set()

    def visit(slug: str) -> None:
        if slug in seen:
            return
        if slug in temp:
            raise CycleError(f"cycle involves {slug!r}")
        temp.add(slug)
        d = by_slug.get(slug)
        if d is not None:
            for dep in d.blocked_by:
                if dep in by_slug:
                    visit(dep)
            order.append(d)
        temp.discard(slug)
        seen.add(slug)

    for d in drafts:
        visit(d.slug)
    return order
