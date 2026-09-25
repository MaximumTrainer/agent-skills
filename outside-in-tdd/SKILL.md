---
name: outside-in-tdd
description: Drive a change test-first from the outside in — acceptance test red, then contract/API red, then unit red, then the green implementation — with one commit per step so the history proves the sequence. Use whenever implementing a feature, fixing a bug, or starting work on an issue number in a repository that expects TDD, and whenever asked to "do issue N", "implement X test-first", "red-green-refactor", or "work through the backlog". Also use when reviewing whether a change was actually driven by tests.
license: MIT
metadata:
  version: "2.0.0"
---

# Outside-in TDD

Measured note: an eval run without this skill already chose the right ring and justified it, injected the clock rather than calling it, read `git log` as newest-first to prove tests were committed *after* the implementation, and kept the red test as its own commit. The rings, the sequence and the test-double rules are what a careful engineer does anyway, so they are not repeated here. One thing was not produced unaided, and it is the whole of section 1.

## 1. Red for the right reason

The step most often skipped, and the only one this skill measurably adds. Running the test is not the point; **reading why it failed** is.

**Right reason** — the behaviour genuinely does not exist yet:

- a step definition is undefined
- a function, class or module does not exist
- it does not compile (a compilation failure counts as red)
- the assertion fails because the value produced is the *old* behaviour

**Wrong reason** — fix the test first, then commit it red:

- a typo in the expected value
- a test-harness or fixture wiring error
- a missing environment variable
- an import path mistake

A test that failed for the wrong reason passes as soon as you fix the typo, whether or not the behaviour exists. It then sits in the suite forever asserting nothing. **State the failure you observed**, not that you ran it: "fails with `NoSuchMethodError: computeBand`" is evidence; "test is red" is not.

If you did not watch it fail, you do not know it tests anything.

## 2. Committing red is expected

A red commit is the record of the step, not a broken build to hide. Hooks in a repo that expects this workflow run formatting and static analysis on commit but **never tests**, precisely so committing red needs no bypass.

Never reach for `--no-verify`. If a hook fails, the hook is right.

## 3. The ring you enter at

You will usually pick this correctly. The two cases worth stating:

- **Bug fix** — enter at the ring that *should* have caught it. If no ring would have, that gap is the finding, and it is more valuable than the fix.
- **Refactor** — no new test. Existing tests stay green throughout.

If you cannot name the ring, you do not yet know what you are changing.

## Definition of done

Only the items that get quietly skipped:

- [ ] Each test failed before its implementation existed, **and the observed failure is stated**
- [ ] No test was weakened, skipped or deleted to get to green
- [ ] No `--no-verify`, no new lint suppression, no `any`, no unexplained cast
- [ ] Anything genuinely unautomatable says so, with the manual step and its **actual** result — "not run, no hardware" is acceptable, a fabricated green is not
- [ ] The criteria are ticked because they are true, not because you have stopped working

## Related skills

- `hexagonal-architecture` — the structure that makes the inner rings fast and the doubles honest
- `spec-by-example-issue` — turning an issue into the criteria this workflow consumes
- `verify-and-ship` — running the full gate and landing the work once it is green
- `test-theatre-audit` — finding tests that pass while asserting nothing
- `container-integration-tests` — when the ring needs a real database or emulator
- `gap-issue` — recording what was deliberately left unverified
