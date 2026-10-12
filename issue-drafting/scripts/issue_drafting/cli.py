"""issue-drafting CLI.

Minimum surface to drive case #1 to green:

    python -m issue_drafting.cli \
        --review fixtures/reviews/mini-kg-review.md \
        --profile sdlc-knowledge-graph \
        --slug-prefix KGR \
        --out drafts/

Exit codes:
    0  success
    2  unknown repo profile, bad arguments, or render-time label error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import parser as review_parser
from . import profiles as profiles_module
from . import render as render_module
from . import slugs as slugs_module

ROOT = Path(__file__).resolve().parents[2]
PROFILES_PATH = ROOT / "references" / "repo-profiles.yaml"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="issue-drafting")
    ap.add_argument("--review", required=True, type=Path)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--slug-prefix", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--slugs",
        type=Path,
        default=None,
        help="Sidecar JSON mapping title-hash → slug, so reruns keep slugs stable.",
    )
    args = ap.parse_args(argv)

    try:
        profile = profiles_module.load(PROFILES_PATH, args.profile)
    except profiles_module.UnknownRepo as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    gaps = review_parser.parse_review(args.review.read_text())
    if not gaps:
        print(f"error: no `## Gap:` headings found in {args.review}", file=sys.stderr)
        return 2

    existing = slugs_module.load(args.slugs)
    assigned = slugs_module.assign(
        titles=[g.title for g in gaps],
        slug_prefix=args.slug_prefix,
        existing=existing,
    )

    try:
        render_module.render(
            gaps=gaps,
            profile=profile,
            slug_prefix=args.slug_prefix,
            out_dir=args.out,
            slug_for_title=assigned,
        )
    except profiles_module.UnknownLabel as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.slugs is not None:
        new_map = slugs_module.updated_sidecar(
            [g.title for g in gaps], assigned, existing
        )
        slugs_module.save(args.slugs, new_map)

    return 0


if __name__ == "__main__":
    sys.exit(main())
