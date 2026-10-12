"""Render parsed gaps to the five-section issue-draft markdown.

The template is in assets/templates/issue.md.j2. This module is the
one place that decides how a Gap + Profile become a draft file:

- labels: resolved via Profile, plus the profile's defaults
- slug: `{slug_prefix}-{nn}` using the per-run slug_prefix
- the five sections are filled from the gap body + hints in a
  deliberately plain way; the convention lives in references/
  convention.md and the snapshot pins the exact rendered form.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .parser import Gap, Slice
from .profiles import Profile

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "assets" / "templates"


@dataclass
class Draft:
    slug: str
    filename: str
    body: str


def _slugify(title: str) -> str:
    out = []
    for ch in title.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:60]


def _labels_for(gap: Gap, profile: Profile) -> list[str]:
    labels: list[str] = []
    hints = gap.hints
    # The hint namespaces the convention knows about, in a fixed order.
    for ns in ("area", "size", "type", "priority", "module"):
        if ns in hints:
            labels.append(profile.resolve(ns, hints[ns]))
    # Flat-label repos: 'tag' hint is dropped straight into 'flat'.
    if "tag" in hints:
        labels.append(profile.resolve("flat", hints["tag"]))
    for d in profile.defaults:
        if d not in labels:
            labels.append(d)
    return labels


def _sections(gap: Gap) -> dict[str, object]:
    """Fill the five sections from the gap. Deliberately mechanical:
    the review author writes the Context sentence, the convention
    does the rest. Snapshot pins the exact output.
    """
    context = gap.body
    scope = (
        f"In scope: addressing the gap stated above. "
        f"Out of scope: adjacent concerns not called out in the review."
    )
    # One FR per sentence in the body, as a starting point. Humans edit
    # the drafts before filing; the generator just gives a scaffold.
    sentences = [s.strip() for s in gap.body.replace("\n", " ").split(". ") if s.strip()]
    frs = [s.rstrip(".") for s in sentences]
    gherkin = (
        "```gherkin\n"
        f"Scenario: {gap.title}\n"
        "  Given the system is in its current state\n"
        f"  When the change implied by \"{gap.title}\" is applied\n"
        "  Then the behaviour described in the Context is observable\n"
        "```"
    )
    tdd = (
        "- Acceptance test first, driven by the Gherkin above.\n"
        "- Unit tests follow, one per functional requirement.\n"
        "- Integration test last, exercising the end-to-end path."
    )
    return dict(context=context, scope=scope, frs=frs, gherkin=gherkin, tdd=tdd)


def _render_one(
    tpl, *, slug, title, repo, labels, parent, sections
) -> str:
    return tpl.render(
        slug=slug,
        title=title,
        repo=repo,
        labels=labels,
        parent=parent,
        **sections,
    )


def _render_parent_and_children(
    tpl, gap: Gap, profile: Profile, slug_prefix: str
) -> list[tuple[str, str]]:
    """XL case: emit a parent carrying the full scope, plus one child per slice.

    Returns a list of (filename, body) pairs.
    """
    parent_slug = f"{slug_prefix}-parent"
    parent_labels = _labels_for(gap, profile)  # keeps size:XL
    parent_body = _render_one(
        tpl,
        slug=parent_slug,
        title=gap.title,
        repo=profile.repo,
        labels=parent_labels,
        parent=None,
        sections=_sections(gap),
    )
    out: list[tuple[str, str]] = [
        (f"{parent_slug}-{_slugify(gap.title)}.md", parent_body)
    ]
    for sl in gap.slices:
        child_slug = f"{slug_prefix}-child-{sl.key.lower()}"
        child_labels = [
            profile.resolve("size", sl.size),
            *(
                profile.resolve(ns, gap.hints[ns])
                for ns in ("area", "type", "module")
                if ns in gap.hints and ns != "size"
            ),
            *(d for d in profile.defaults),
        ]
        child_gap = Gap(title=f"{sl.key}: {sl.title}", body=sl.title, hints={})
        child_body = _render_one(
            tpl,
            slug=child_slug,
            title=child_gap.title,
            repo=profile.repo,
            labels=child_labels,
            parent=parent_slug,
            sections=_sections(child_gap),
        )
        out.append((f"{child_slug}-{_slugify(sl.title)}.md", child_body))
    return out


def render(
    gaps: list[Gap],
    profile: Profile,
    slug_prefix: str,
    out_dir: Path,
    slug_for_title: dict[str, str] | None = None,
) -> list[Draft]:
    """Render drafts.

    slug_for_title: title → slug mapping from the slugs sidecar. When None,
    slugs fall back to positional {prefix}-{nn}. Passed explicitly to make
    the mapping testable without going through disk.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    tpl = env.get_template("issue.md.j2")
    out_dir.mkdir(parents=True, exist_ok=True)
    drafts: list[Draft] = []
    slug_for_title = slug_for_title or {}
    for idx, gap in enumerate(gaps, start=1):
        is_xl = gap.hints.get("size") == "XL"
        if is_xl and gap.slices:
            pairs = _render_parent_and_children(tpl, gap, profile, slug_prefix)
            for filename, body in pairs:
                (out_dir / filename).write_text(body)
                slug = filename.split("-")[0] + "-" + filename.split("-")[1]
                drafts.append(Draft(slug=slug, filename=filename, body=body))
            continue
        if is_xl and not gap.slices:
            raise ValueError(
                f"size:XL gap {gap.title!r} has no `### Slices` subsection; "
                f"XL candidates must be pre-split into independently shippable children"
            )
        slug = slug_for_title.get(gap.title) or f"{slug_prefix}-{idx:02d}"
        labels = _labels_for(gap, profile)
        body = _render_one(
            tpl,
            slug=slug,
            title=gap.title,
            repo=profile.repo,
            labels=labels,
            parent=None,
            sections=_sections(gap),
        )
        filename = f"{slug}-{_slugify(gap.title)}.md"
        (out_dir / filename).write_text(body)
        drafts.append(Draft(slug=slug, filename=filename, body=body))
    return drafts
