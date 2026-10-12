"""Eval runner for issue-filing.

Runs the filer CLI under a PATH-shimmed mock `gh`. Each case class
has its own handler. The mock's call log is the primary observation.

Usage:
    python evals/run.py                   # run every case
    python evals/run.py <case_id>         # run one
    PROMOTE=1 python evals/run.py <id>    # for snapshot: overwrite the log
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "tests" / "suite.yaml"
TMP = ROOT / "tests" / "_tmp"
MOCK_GH_DIR = ROOT / "tests" / "fixtures" / "mock_gh"


def _mock_env(case_tmp: Path, extras: dict | None = None) -> dict:
    log_path = case_tmp / "gh-calls.jsonl"
    state_path = case_tmp / "gh-state.json"
    create_count = case_tmp / "gh-create-count.json"
    env = {
        **os.environ,
        "PATH": f"{MOCK_GH_DIR}:{os.environ.get('PATH', '')}",
        "GH_MOCK_LOG": str(log_path),
        "GH_MOCK_STATE": str(state_path),
        "GH_MOCK_CREATE_COUNT": str(create_count),
        "GH_MOCK_NEXT_ISSUE": "329",  # mirrors VirtualRow after #328
        "PYTHONPATH": str(ROOT / "scripts"),
    }
    if extras:
        env.update({k: str(v) for k, v in extras.items()})
    return env


def _stage_drafts(case_tmp: Path, drafts_rel: str) -> Path:
    """Copy the fixture drafts into case_tmp so the filer can mutate them
    without corrupting the fixture."""
    src = ROOT / drafts_rel
    dst = case_tmp / "drafts"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def _run_filer(case_tmp: Path, inp: dict, env_extras: dict | None = None):
    drafts_dir = _stage_drafts(case_tmp, inp["drafts"])
    cmd = [
        sys.executable,
        "-m",
        "issue_filing.cli",
        "--drafts",
        str(drafts_dir),
        "--repo",
        inp["repo"],
    ]
    if inp.get("no_label_check"):
        cmd.append("--no-label-check")
    env = _mock_env(case_tmp, env_extras)
    if inp.get("labels_fixture"):
        env["GH_MOCK_LABELS"] = str(ROOT / inp["labels_fixture"])
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _normalise_log(raw: str) -> str:
    """Strip timestamps so snapshots stay stable."""
    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        entry.pop("ts", None)
        out.append(json.dumps(entry, sort_keys=True))
    return "\n".join(out) + ("\n" if out else "")


def check_snapshot(case: dict, result, case_tmp: Path) -> tuple[bool, str]:
    want_code = case["expect"].get("exit_code", 0)
    if result.returncode != want_code:
        return (
            False,
            f"exit {result.returncode} != {want_code}\nstderr:\n{result.stderr}",
        )
    log_path = case_tmp / "gh-calls.jsonl"
    got = _normalise_log(log_path.read_text() if log_path.exists() else "")
    snap_path = ROOT / case["expect"]["log_snapshot"]
    if os.environ.get("PROMOTE") == "1":
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(got)
        return (True, f"PROMOTED {snap_path.relative_to(ROOT)}")
    if not snap_path.exists():
        return (
            False,
            f"no snapshot at {snap_path.relative_to(ROOT)}; rerun with PROMOTE=1",
        )
    want = snap_path.read_text()
    if want != got:
        diff = "".join(
            difflib.unified_diff(
                want.splitlines(keepends=True),
                got.splitlines(keepends=True),
                fromfile="expected",
                tofile="got",
            )
        )
        return (False, f"log mismatch:\n{diff}")
    return (True, f"snapshot ok ({len(got.splitlines())} log entries)")


def _read_log(case_tmp: Path) -> list[dict]:
    log_path = case_tmp / "gh-calls.jsonl"
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]


def _create_calls(log: list[dict]) -> list[dict]:
    return [e for e in log if e.get("cmd") == "issue-create"]


def _edit_calls(log: list[dict]) -> list[dict]:
    return [e for e in log if e.get("cmd") == "issue-edit"]


def check_ordering(case: dict, _r, case_tmp: Path) -> tuple[bool, str]:
    r = _run_filer(case_tmp, case["input"])
    if r.returncode != 0:
        return (False, f"filer exited {r.returncode}\nstderr:\n{r.stderr}")
    log = _read_log(case_tmp)
    creates = _create_calls(log)
    edits = _edit_calls(log)
    exp = case["expect"]

    want_titles = exp["create_order_by_title"]
    got_titles = [c["title"] for c in creates]
    if got_titles != want_titles:
        return (
            False,
            f"create order:\n  got:  {got_titles}\n  want: {want_titles}",
        )

    if exp.get("edits_follow_creates") and edits:
        last_create_pos = max(i for i, e in enumerate(log) if e.get("cmd") == "issue-create")
        first_edit_pos = min(i for i, e in enumerate(log) if e.get("cmd") == "issue-edit")
        if first_edit_pos < last_create_pos:
            return (False, "an edit happened before all creates finished")

    return (True, f"ordering ok ({len(creates)} creates, {len(edits)} edits)")


def check_idempotence(case: dict, _r, case_tmp: Path) -> tuple[bool, str]:
    inp = case["input"]
    exp = case["expect"]

    # Run 1 — fresh drafts copy, fresh mock state.
    r1_tmp = case_tmp / "run1"
    r1_tmp.mkdir(parents=True)
    r1 = _run_filer(r1_tmp, inp)
    if r1.returncode != 0:
        return (False, f"run 1 failed:\n{r1.stderr}")
    log1 = _read_log(r1_tmp)
    creates_1 = _create_calls(log1)
    if len(creates_1) < exp["run1_creates_at_least"]:
        return (
            False,
            f"run 1 created {len(creates_1)}, expected ≥{exp['run1_creates_at_least']}",
        )

    # Run 2 — reuse run 1's drafts (now carrying `issue:` numbers).
    r2_tmp = case_tmp / "run2"
    r2_tmp.mkdir(parents=True)

    # The drafts are now mutated inside run1/drafts. Point run 2 at them
    # directly, without copying from the fixture.
    inp2 = dict(inp)
    # Hand-stage: copy the already-mutated drafts into run2's drafts dir.
    staged = r2_tmp / "drafts"
    shutil.copytree(r1_tmp / "drafts", staged)

    # Build the filer invocation manually to point at `staged`.
    cmd = [
        sys.executable,
        "-m",
        "issue_filing.cli",
        "--drafts",
        str(staged),
        "--repo",
        inp["repo"],
    ]
    env = _mock_env(r2_tmp, {"GH_MOCK_NEXT_ISSUE": "500"})
    if inp.get("labels_fixture"):
        env["GH_MOCK_LABELS"] = str(ROOT / inp["labels_fixture"])
    r2 = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r2.returncode != 0:
        return (False, f"run 2 failed:\n{r2.stderr}")
    log2 = _read_log(r2_tmp)
    creates_2 = _create_calls(log2)
    if len(creates_2) != exp["run2_creates"]:
        return (
            False,
            f"run 2 created {len(creates_2)}, expected {exp['run2_creates']}; "
            f"titles: {[c['title'] for c in creates_2]}",
        )
    return (True, f"idempotent ({len(creates_1)} created, 0 on rerun)")


def check_negative(case: dict, _r, case_tmp: Path) -> tuple[bool, str]:
    r = _run_filer(case_tmp, case["input"])
    exp = case["expect"]
    if r.returncode != exp["exit_code"]:
        return (
            False,
            f"exit {r.returncode} != {exp['exit_code']}\nstderr:\n{r.stderr}",
        )
    needle = exp.get("stderr_contains")
    if needle and needle not in r.stderr:
        return (False, f"stderr missing {needle!r}; got:\n{r.stderr}")
    if exp.get("no_create_calls"):
        log = _read_log(case_tmp)
        creates = _create_calls(log)
        if creates:
            return (False, f"{len(creates)} create calls made, expected 0")
    return (True, "negative case rejected as required")


def check_recovery(case: dict, _r, case_tmp: Path) -> tuple[bool, str]:
    inp = case["input"]
    exp = case["expect"]

    # Run 1: fail-after injected.
    r1_tmp = case_tmp / "run1"
    r1_tmp.mkdir(parents=True)
    r1 = _run_filer(
        r1_tmp,
        inp,
        env_extras={"GH_MOCK_FAIL_AFTER": inp["fail_after"]},
    )
    if r1.returncode != exp["run1_exit_code"]:
        return (
            False,
            f"run 1 exit {r1.returncode} != {exp['run1_exit_code']}; stderr:\n{r1.stderr}",
        )
    log1 = _read_log(r1_tmp)
    creates_1 = _create_calls(log1)
    successful_1 = [c for c in creates_1 if c.get("ok")]
    if len(successful_1) < exp["run1_creates_at_least"]:
        return (
            False,
            f"run 1: only {len(successful_1)} successful creates, "
            f"expected ≥{exp['run1_creates_at_least']}",
        )

    # Run 2: no fail-after. Carries forward run 1's partially-written drafts.
    r2_tmp = case_tmp / "run2"
    r2_tmp.mkdir(parents=True)
    staged = r2_tmp / "drafts"
    shutil.copytree(r1_tmp / "drafts", staged)
    cmd = [
        sys.executable,
        "-m",
        "issue_filing.cli",
        "--drafts",
        str(staged),
        "--repo",
        inp["repo"],
    ]
    env = _mock_env(r2_tmp, {"GH_MOCK_NEXT_ISSUE": "500"})
    if inp.get("labels_fixture"):
        env["GH_MOCK_LABELS"] = str(ROOT / inp["labels_fixture"])
    r2 = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r2.returncode != exp["run2_exit_code"]:
        return (False, f"run 2 exit {r2.returncode}; stderr:\n{r2.stderr}")

    log2 = _read_log(r2_tmp)
    creates_2 = [c for c in _create_calls(log2) if c.get("ok")]
    total = len(successful_1) + len(creates_2)
    if total != exp["total_creates_across_runs"]:
        return (
            False,
            f"total successful creates = {total}, "
            f"expected {exp['total_creates_across_runs']}",
        )

    if exp.get("no_duplicate_titles"):
        all_titles = [c["title"] for c in successful_1] + [c["title"] for c in creates_2]
        if len(all_titles) != len(set(all_titles)):
            dups = [t for t in all_titles if all_titles.count(t) > 1]
            return (False, f"duplicate create titles across runs: {sorted(set(dups))}")

    return (True, f"recovered: {len(successful_1)} + {len(creates_2)} = {total}")


def check_transformation(case: dict, _r, case_tmp: Path) -> tuple[bool, str]:
    r = _run_filer(case_tmp, case["input"])
    if r.returncode != 0:
        return (False, f"filer exited {r.returncode}\n{r.stderr}")
    log = _read_log(case_tmp)
    exp = case["expect"]
    edits = _edit_calls(log)
    creates = _create_calls(log)
    if len(edits) < exp.get("edit_calls_at_least", 0):
        return (
            False,
            f"{len(edits)} edit calls, expected ≥{exp.get('edit_calls_at_least')}",
        )

    # Pair each edit's issue number back to its original title via the create log.
    issue_to_title = {str(c["returned_number"]): c["title"] for c in creates if c.get("ok")}
    failures: list[str] = []
    for title, needle in exp.get("edit_body_contains_for_title", {}).items():
        matched = False
        for e in edits:
            if issue_to_title.get(str(e.get("issue"))) == title:
                if needle in (e.get("body") or ""):
                    matched = True
                    break
        if not matched:
            failures.append(f"{title!r}: no edit with body containing {needle!r}")
    if failures:
        return (False, "transformation failures:\n  " + "\n  ".join(failures))
    return (True, f"transformations ok ({len(edits)} edits)")


HANDLERS = {
    "snapshot": check_snapshot,
    "ordering": check_ordering,
    "idempotence": check_idempotence,
    "negative": check_negative,
    "recovery": check_recovery,
    "transformation": check_transformation,
}


def run_case(case: dict) -> tuple[bool, str]:
    case_tmp = TMP / case["id"]
    if case_tmp.exists():
        shutil.rmtree(case_tmp)
    case_tmp.mkdir(parents=True)

    handler = HANDLERS.get(case["kind"])
    if handler is None:
        return (False, f"no handler for kind={case['kind']}")

    # snapshot cases: the dispatcher drives the single filer run.
    # Everything else: the handler drives its own run(s).
    if case["kind"] == "snapshot":
        r = _run_filer(case_tmp, case["input"])
        return handler(case, r, case_tmp)
    return handler(case, None, case_tmp)


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
