---
name: ci-failure-triage
description: Find out why a remote build is red, reproduce the real failure locally, and land the fix. Use when asked "is the build broken", "check remote main is green", "fix main", "why did CI fail", or before starting new work on a repository whose default branch may be red. Covers locating the failing run and job, extracting the actual error out of a long log, telling an infrastructure failure apart from a code failure, and the flaky-versus-real decision.
license: MIT
metadata:
  version: "1.0.0"
---

# Getting a red build green again

A red default branch blocks everyone and gets less trustworthy the longer it stays red, because the next failure hides behind the first. Fix it before starting new work.

The discipline here is to **read the actual failure before forming a theory**. Most wasted time in CI triage comes from guessing at a cause from the job name and fixing something that was not broken.

## 1. Find the run

```bash
gh run list --branch main --limit 5 --json databaseId,workflowName,status,conclusion,headSha,displayTitle,createdAt
```

Check every workflow, not just the one called CI. A green test workflow beside a red publish or deploy workflow is not green.

Note the `headSha`. If the failure is not on the newest commit, someone may have already fixed it — check whether a later run passed before investigating.

## 2. Read the real failure

```bash
gh run view <id>                 # which jobs failed
gh run view <id> --log-failed    # only the failing steps' output
```

`--log-failed` is the important one; a full log is tens of thousands of lines and the failure is rarely where you would scroll to. If you must search a full log:

```bash
gh run view <id> --log | grep -nE 'FAIL|FAILED|Error:|error:|Caused by|Exception|AssertionError|✕|✗' | head -40
```

Then read **around** the first real hit, not just the hit — the assertion message and the diff usually sit a few lines below, and the `Caused by` chain sits below that. The last line of a stack trace is almost never the cause; the deepest `Caused by` usually is.

Download artefacts when the job produced reports, screenshots or traces:

```bash
gh run download <id> -D /tmp/ci-artefacts
```

A Playwright trace or a failing-test HTML report answers in seconds what log-reading takes twenty minutes to guess at.

## 3. Classify it before fixing it

The fix is completely different depending on which of these it is. Decide explicitly.

| Class | How it looks | What to do |
|---|---|---|
| **Real code failure** | An assertion failed with a plausible diff; compilation error; type error | Reproduce locally, fix the code |
| **Environment / infrastructure** | "Could not find a valid Docker environment"; registry 5xx; runner out of disk; network timeout pulling a dependency; expired token or secret | Do not touch the code. Re-run, or fix the workflow/credential |
| **Non-determinism** | Passes on re-run with no change; timing or ordering dependent; timezone or locale dependent | Fix the test's determinism — see below. Do not just re-run |
| **Drift check** | A generated file, docs page, lockfile or OpenAPI document disagrees with its source | Regenerate and commit — see `docs-drift-guard` |
| **Someone else's commit** | Failure is unrelated to your change and predates it | Say so, and fix or escalate rather than stacking on top |

**A Docker or Testcontainers failure looks like a wall of failing tests but is not a code failure.** Read the `Caused by` before believing that thirty tests broke.

**Environment-shaped failures that are really code:** a test that only fails on the CI runner's timezone, locale, filesystem case-sensitivity or CPU count is a real defect in the test, not an infrastructure problem. The runner is allowed to be different from your laptop.

## 4. Reproduce locally

Match the CI environment on whatever dimension the failure implicates, then run only the failing test first.

```bash
# same commit as the failing run
git fetch && git checkout <headSha>

# the specific failing test
./gradlew test --tests "com.example.FlowServiceTest"
npx vitest run path/to/file.test.ts -t "the failing case"

# under the dimension CI used
TZ=Pacific/Chatham npm test -- --run
LANG=de_DE.UTF-8 ./gradlew test
```

For a suspected ordering or pollution problem, run the suite in a different order and run the single test alone:

```bash
npx vitest run --sequence.shuffle
npx vitest run path/to/file.test.ts        # passes alone but fails in the suite => shared state
```

If you cannot reproduce it locally, do not guess a fix. Add the diagnostic that will tell you next time — log the value, upload the artefact, print the resolved timezone — and say plainly that the cause is not yet identified.

## 5. Flaky or real?

"It passed on re-run" is not a diagnosis. A test that passes 90% of the time is failing 10% of the time, and it will fail on someone else's unrelated change and cost them an hour.

```bash
# does it actually flake?
for i in $(seq 1 20); do npx vitest run path/to/file.test.ts -t "case" >/dev/null 2>&1 || echo "fail $i"; done
```

The usual causes, in order of how often they turn out to be it:

- **Real time.** `Date.now()`, `System.currentTimeMillis()`, a sleep used as a synchronisation primitive, a test asserting on "today". Inject a clock.
- **Shared mutable state** between tests — a module-level cache, a reassembly buffer, a singleton, a database row left behind. Reset in setup, or make it an instance.
- **Ordering assumptions** over a set, map, or a query with no `ORDER BY`.
- **A race against something asynchronous** — waiting a fixed 200ms instead of waiting for the condition.
- **Timezone, locale or DST**, especially around date boundaries.
- **Network or a real external service** in what should be a unit test. See `live-api-probe` for where real calls belong.

Fix the cause. Do not add a retry, do not extend the timeout, and do not mark it skipped — a quarantined test is a test nobody will ever unquarantine. See `test-theatre-audit`.

## 6. Land the fix

Fix forward on a branch and land it through the normal gate — do not push a "quick fix" straight to the default branch, because a wrong quick fix on a red branch makes the next diagnosis harder. Run the gate locally first; see `verify-and-ship`.

Where the failure was a real defect that no test would have caught, add the test that would have caught it, in the ring that should have caught it. That is the part that stops the same failure recurring.

Reverting is the right answer when the breaking change is large, the cause is not understood, and the branch needs to be green now:

```bash
git revert <sha>
```

Say that it is a revert and that the underlying work still needs doing — file it.

## Reporting

State: which workflow and run was red, which job and step failed, the actual error, which class of failure it was, whether you reproduced it locally, and what the fix was. If you could not reproduce it, say so rather than presenting a speculative fix as a diagnosis.

## Related skills

- `verify-and-ship` — running the gate before pushing so this happens less
- `test-theatre-audit` — tests that pass while asserting nothing, and quarantined tests
- `docs-drift-guard` — the drift class of failure
- `container-integration-tests` — Docker-dependent suites and their start guards
