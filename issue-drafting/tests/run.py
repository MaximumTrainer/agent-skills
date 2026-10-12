"""Eval runner for issue-drafting.

Dispatches on `case.kind` so adding case classes doesn't touch the
dispatcher. Each handler returns (passed: bool, detail: str).

Usage:
    python evals/run.py              # run every case in suite.yaml
    python evals/run.py <case_id>    # run a single case
    PROMOTE=1 python evals/run.py <case_id>
        # for snapshot cases: overwrite the snapshot with current output.
        # Use after hand-reviewing the first run.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "tests" / "suite.yaml"
TMP = ROOT / "tests" / "_tmp"


def build_cmd(
    *,
    review: str,
    profile: str,
    slug_prefix: str,
    out_dir: Path,
    slugs: Path | None = None,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "issue_drafting.cli",
        "--review",
        str(ROOT / review),
        "--profile",
        profile,
        "--slug-prefix",
        slug_prefix,
        "--out",
        str(out_dir),
    ]
    if slugs is not None:
        cmd += ["--slugs", str(slugs)]
    return cmd


def _run_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "scripts")}
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _list_files(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.is_file())


def check_snapshot(case: dict, result, out_dir: Path) -> tuple[bool, str]:
    expected = ROOT / case["expect"]["snapshot_dir"]
    expected_code = case["expect"].get("exit_code", 0)

    if result.returncode != expected_code:
        return (
            False,
            f"exit code {result.returncode} != expected {expected_code}\n"
            f"stderr:\n{result.stderr}",
        )

    if os.environ.get("PROMOTE") == "1":
        if expected.exists():
            import shutil

            shutil.rmtree(expected)
        import shutil

        shutil.copytree(out_dir, expected)
        return (True, f"PROMOTED snapshot to {expected.relative_to(ROOT)}")

    if not expected.exists():
        return (
            False,
            f"no snapshot at {expected.relative_to(ROOT)}; "
            f"rerun with PROMOTE=1 after hand-reviewing {out_dir}",
        )

    got_files = {p.relative_to(out_dir): p for p in _list_files(out_dir)}
    exp_files = {p.relative_to(expected): p for p in _list_files(expected)}

    missing = sorted(set(exp_files) - set(got_files))
    extra = sorted(set(got_files) - set(exp_files))
    if missing or extra:
        return (
            False,
            f"file set differs\n  missing: {missing}\n  extra:   {extra}",
        )

    diffs = []
    for rel in sorted(exp_files):
        got_text = got_files[rel].read_text()
        exp_text = exp_files[rel].read_text()
        if got_text != exp_text:
            d = difflib.unified_diff(
                exp_text.splitlines(keepends=True),
                got_text.splitlines(keepends=True),
                fromfile=f"expected/{rel}",
                tofile=f"got/{rel}",
            )
            diffs.append("".join(d))
    if diffs:
        return (False, "snapshot mismatch:\n" + "\n".join(diffs))

    return (True, f"snapshot ok ({len(exp_files)} files)")


def check_lint(case: dict, result, out_dir: Path) -> tuple[bool, str]:
    if result.returncode != 0:
        return (False, f"CLI exited {result.returncode}\nstderr:\n{result.stderr}")

    required = case["expect"]["every_draft_has_sections"]
    forbid_empty = case["expect"].get("no_section_body_empty", False)

    drafts = _list_files(out_dir)
    if not drafts:
        return (False, f"no drafts emitted into {out_dir}")

    failures: list[str] = []
    for draft in drafts:
        text = draft.read_text()
        for section in required:
            if section not in text:
                failures.append(f"{draft.name}: missing section {section!r}")
        if forbid_empty:
            for section in required:
                body = _section_body(text, section, required)
                if not body.strip():
                    failures.append(f"{draft.name}: empty body under {section!r}")

    if failures:
        return (False, "lint failures:\n  " + "\n  ".join(failures))
    return (True, f"lint ok ({len(drafts)} drafts)")


def _section_body(text: str, section: str, all_sections: list[str]) -> str:
    """Return the body between `section` and the next section heading, or EOF."""
    start = text.find(section)
    if start < 0:
        return ""
    start += len(section)
    # Earliest subsequent section heading, if any.
    rest = text[start:]
    next_offsets = [rest.find("\n" + s) for s in all_sections if rest.find("\n" + s) >= 0]
    end = min(next_offsets) if next_offsets else len(rest)
    return rest[:end]


def _parse_frontmatter(text: str) -> dict:
    """Extract the YAML frontmatter block (between the first two '---' lines)."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _fnmatch_any(label: str, patterns: list[str]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatchcase(label, p) for p in patterns)


def check_property(case: dict, result, out_dir: Path) -> tuple[bool, str]:
    if result.returncode != 0:
        return (False, f"CLI exited {result.returncode}\nstderr:\n{result.stderr}")

    exp = case["expect"]
    forbid = exp.get("no_labels_matching", [])
    all_in_profile = exp.get("all_labels_in_profile", False)

    profile_name = case["input"]["profile"]
    profile_data = yaml.safe_load(
        (ROOT / "references" / "repo-profiles.yaml").read_text()
    )[profile_name]
    allowed: set[str] = set()
    for ns_labels in profile_data["scheme"].values():
        allowed.update(ns_labels)

    failures: list[str] = []
    drafts = _list_files(out_dir)
    for draft in drafts:
        fm = _parse_frontmatter(draft.read_text())
        for label in fm.get("labels", []):
            if _fnmatch_any(label, forbid):
                failures.append(f"{draft.name}: forbidden label {label!r}")
            if all_in_profile and label not in allowed:
                failures.append(
                    f"{draft.name}: label {label!r} not in profile {profile_name!r}"
                )
    if failures:
        return (False, "property failures:\n  " + "\n  ".join(failures))
    return (True, f"property ok ({len(drafts)} drafts)")


def check_structural(case: dict, result, out_dir: Path) -> tuple[bool, str]:
    import fnmatch

    if result.returncode != 0:
        return (False, f"CLI exited {result.returncode}\nstderr:\n{result.stderr}")

    specs = case["expect"]["files"]
    all_files = _list_files(out_dir)
    failures: list[str] = []

    for spec in specs:
        pattern = spec["glob"]
        matches = [p for p in all_files if fnmatch.fnmatchcase(p.name, pattern)]
        if "count" in spec and len(matches) != spec["count"]:
            failures.append(
                f"glob {pattern!r}: expected count {spec['count']}, got {len(matches)}"
            )
        if "count_at_least" in spec and len(matches) < spec["count_at_least"]:
            failures.append(
                f"glob {pattern!r}: expected ≥{spec['count_at_least']}, got {len(matches)}"
            )
        fm_rules = spec.get("frontmatter", {})
        for match in matches:
            fm = _parse_frontmatter(match.read_text())
            labels = fm.get("labels") or []
            for required in fm_rules.get("labels_includes", []):
                if required not in labels:
                    failures.append(f"{match.name}: missing label {required!r}")
            for forbid in fm_rules.get("labels_excludes", []):
                if forbid in labels:
                    failures.append(f"{match.name}: forbidden label {forbid!r}")
            if "parent" in fm_rules:
                want = fm_rules["parent"]
                got = fm.get("parent")
                if want is None and got is not None:
                    failures.append(f"{match.name}: parent={got!r}, expected null")
                if want is not None and got != want:
                    failures.append(f"{match.name}: parent={got!r}, expected {want!r}")
            if "parent_matches" in fm_rules:
                pat = fm_rules["parent_matches"]
                got = fm.get("parent") or ""
                if not fnmatch.fnmatchcase(got, pat):
                    failures.append(
                        f"{match.name}: parent={got!r} doesn't match glob {pat!r}"
                    )

    if failures:
        return (False, "structural failures:\n  " + "\n  ".join(failures))
    return (True, f"structural ok ({len(all_files)} files, {len(specs)} specs)")


def check_idempotence(case: dict, _result, out_dir: Path) -> tuple[bool, str]:
    """Two CLI runs with different review orderings but a shared slugs sidecar.

    After both runs, every title present in both reviews must carry the same
    slug in both outputs. The sidecar is written by run 1 and read by run 2.
    """
    inp = case["input"]
    run1_dir = out_dir / "run1"
    run2_dir = out_dir / "run2"
    sidecar = out_dir / "slugs.json"

    for i, (review, run_dir) in enumerate(
        [(inp["first_review"], run1_dir), (inp["second_review"], run2_dir)], start=1
    ):
        cmd = build_cmd(
            review=review,
            profile=inp["profile"],
            slug_prefix=inp["slug_prefix"],
            out_dir=run_dir,
            slugs=sidecar,
        )
        r = _run_cli(cmd)
        if r.returncode != 0:
            return (False, f"run {i} failed:\n{r.stderr}")

    titles_1 = _title_to_slug(run1_dir)
    titles_2 = _title_to_slug(run2_dir)

    common = set(titles_1) & set(titles_2)
    if not common:
        return (False, "no titles in common between the two runs")

    mismatches = [
        f"{title!r}: run1={titles_1[title]!r}, run2={titles_2[title]!r}"
        for title in sorted(common)
        if titles_1[title] != titles_2[title]
    ]
    if mismatches:
        return (False, "slug drift between runs:\n  " + "\n  ".join(mismatches))
    return (True, f"idempotent across {len(common)} shared titles")


def _title_to_slug(d: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in _list_files(d):
        fm = _parse_frontmatter(f.read_text())
        if "title" in fm and "slug" in fm:
            out[fm["title"]] = fm["slug"]
    return out


def check_negative(case: dict, result, out_dir: Path) -> tuple[bool, str]:
    exp = case["expect"]
    want_code = exp["exit_code"]
    if result.returncode != want_code:
        return (
            False,
            f"exit code {result.returncode} != expected {want_code}; "
            f"stderr:\n{result.stderr}",
        )
    needle = exp.get("stderr_contains")
    if needle and needle not in result.stderr:
        return (False, f"stderr missing {needle!r}; stderr was:\n{result.stderr}")
    if exp.get("no_files_written") and _list_files(out_dir):
        return (
            False,
            f"files were written to {out_dir}, expected none:\n"
            f"{[p.name for p in _list_files(out_dir)]}",
        )
    return (True, "negative case rejected as required")


HANDLERS = {
    "snapshot": check_snapshot,
    "lint": check_lint,
    "property": check_property,
    "structural": check_structural,
    "idempotence": check_idempotence,
    "negative": check_negative,
}


def run_case(case: dict) -> tuple[bool, str]:
    out = TMP / case["id"]
    if out.exists():
        import shutil

        shutil.rmtree(out)
    out.mkdir(parents=True)

    handler = HANDLERS.get(case["kind"])
    if handler is None:
        return (False, f"no handler for kind={case['kind']}")

    # idempotence runs the CLI itself; the other kinds get one pre-run.
    if case["kind"] == "idempotence":
        return handler(case, None, out)

    inp = case["input"]
    cmd = build_cmd(
        review=inp["review"],
        profile=inp["profile"],
        slug_prefix=inp["slug_prefix"],
        out_dir=out,
    )
    r = _run_cli(cmd)
    return handler(case, r, out)


def main(argv: list[str]) -> int:
    suite = yaml.safe_load(SUITE.read_text())
    only = argv[1] if len(argv) > 1 else None
    cases = suite["cases"]
    if only:
        cases = [c for c in cases if c["id"] == only]
        if not cases:
            print(f"no case {only!r}", file=sys.stderr)
            return 2

    fails = 0
    for case in cases:
        ok, detail = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}: {detail}")
        if not ok:
            fails += 1
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
