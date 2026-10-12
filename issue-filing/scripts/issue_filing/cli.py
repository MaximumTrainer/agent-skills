"""issue-filing CLI.

Usage:
    python -m issue_filing.cli --drafts drafts/ --repo MaximumTrainer/virtualrow

Exit codes:
    0  success
    2  bad arguments, auth failure, or preflight label mismatch
    3  gh failure mid-run (idempotent: a rerun will skip already-filed drafts)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .filer import LabelMismatch, file_all
from .gh import GhError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="issue-filing")
    ap.add_argument("--drafts", required=True, type=Path)
    ap.add_argument("--repo", required=True)
    ap.add_argument(
        "--no-label-check",
        action="store_true",
        help="Skip the preflight label check (useful during setup).",
    )
    args = ap.parse_args(argv)

    try:
        result = file_all(args.drafts, args.repo, strict_labels=not args.no_label_check)
    except LabelMismatch as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except GhError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    print(f"created {len(result.created)}, skipped {len(result.skipped)}, "
          f"cross-refs {len(result.cross_refs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
