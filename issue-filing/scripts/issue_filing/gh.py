"""Thin shell over `gh` CLI invocations.

Isolated so the eval suite's mock-shim swaps the whole surface by
putting a fake `gh` on PATH. The filer never shells out to anything
but these functions.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class GhError(Exception):
    pass


def auth_status() -> None:
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if r.returncode != 0:
        raise GhError(f"gh auth failed: {r.stderr.strip() or r.stdout.strip()}")


def list_labels(repo: str, limit: int = 500) -> list[str]:
    r = subprocess.run(
        ["gh", "label", "list", "--repo", repo, "--limit", str(limit)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise GhError(f"gh label list failed: {r.stderr.strip()}")
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


_ISSUE_URL_RE = re.compile(r"/issues/(\d+)\b")


def create_issue(
    *, repo: str, title: str, body: str, labels: list[str], milestone: str | None
) -> int:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(body)
        body_file = f.name
    try:
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body-file",
            body_file,
        ]
        for lab in labels:
            cmd += ["--label", lab]
        if milestone:
            cmd += ["--milestone", milestone]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise GhError(f"gh issue create failed: {r.stderr.strip()}")
        m = _ISSUE_URL_RE.search(r.stdout)
        if not m:
            raise GhError(f"gh issue create: no issue URL in output: {r.stdout!r}")
        return int(m.group(1))
    finally:
        Path(body_file).unlink(missing_ok=True)


def edit_issue_body(*, repo: str, number: int, body: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(body)
        body_file = f.name
    try:
        r = subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--body-file",
                body_file,
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise GhError(f"gh issue edit failed: {r.stderr.strip()}")
    finally:
        Path(body_file).unlink(missing_ok=True)
