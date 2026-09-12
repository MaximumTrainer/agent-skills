---
name: test-theatre-audit
description: Find tests that pass while exercising nothing — env-gated early returns, assertions inside loops over empty collections, swallowed fixture failures, container suites with no start guard, mocks asserting on themselves, snapshots of wrong output. Use when asked to audit test coverage, check whether a suite actually runs, verify tests are not silently skipping, investigate why a bug shipped past a green build, or review a suspiciously fast or suspiciously green suite. Coverage percentages do not detect any of these.
license: MIT
metadata:
  version: "1.0.0"
---

# Find tests that pass while testing nothing

A failing test is cheap. A test that passes without exercising anything is expensive, because it buys confidence that was never earned — and it buys it silently, at exactly the moment someone decides not to look any closer.

This class of defect has shipped repeatedly in real projects here:

- Five cloud-storage tests passed while their emulator had never started. Only a "did the emulator actually start" guard caught it.
- Three of four database profilers had never run against a database: their tests were gated behind credentials nobody had configured, so the suite was green and empty.
- An integration suite looped over a collection and asserted per element — so it passed even when the collection was empty, which it always was.

Note what they have in common: **the build was green the whole time, and coverage did not flag any of them.** A gated test that returns early still shows as executed. Coverage measures lines reached, not assertions made.

## The patterns to hunt

### 1. Gated early return with no report

The whole suite disappears when a variable is unset, and nothing says so.

```csharp
if (string.IsNullOrWhiteSpace(connectionString)) return;   // silent
```

```bash
rg -n 'is null\) return;|IsNullOrWhiteSpace\(.*\)\) return;' -g '**/*Test*.cs'
rg -n 'if \(!?process\.env\.[A-Z_]+\) return' -g '**/*.test.ts'
rg -n '@(Disabled|Ignore|EnabledIf)|assumeTrue\(' -g '**/*Test*.java'
rg -n 'pytest.mark.skipif|pytest.skip\(' -g '**/test_*.py'
rg -n '\.(skip|todo)\(|xit\(|xdescribe\(' -g '**/*.test.*'
```

A conditional skip is legitimate. A conditional skip that does not **report** is not: the run must be able to tell you which suites were exercised and which were not.

### 2. Assertions inside a loop with no non-empty check

`for (const x of items) expect(x).toBe(...)` passes vacuously when `items` is empty — and it is usually empty for a reason you would want to know about.

```bash
rg -n -A6 'foreach \(.*in .*\)\s*$' -g '**/*Test*.cs'
rg -n -A6 'for \(const \w+ of ' -g '**/*.test.ts'
```

Look for a missing `Should().NotBeEmpty()` / `expect(items).toHaveLength(n)` / `assertThat(items).isNotEmpty()` **before** the loop. Assert the count first, then the contents.

### 3. Swallowed fixture failure

`catch { }` around setup turns "the fixture is broken" into "every test skipped", which is indistinguishable from "the dependency is unavailable" — two facts that need different responses.

```bash
rg -n -A3 'catch \(Exception|catch \{|except Exception:\s*$|catch \{\s*\}' -g '**/*Test*' -g '**/*test*'
```

Store the exception on the fixture and surface it through a guard, rather than letting it vanish.

### 4. A self-skipping suite with no start guard

If every test in a class self-skips on a null connection, **one** test must fail when the fixture should have started and did not:

```csharp
[Fact]
public void EmulatorStartedWhenDockerIsAvailable()
{
    output.WriteLine(fixture.Report());      // says what ran and what did not
    if (!fixture.DockerAvailable) return;    // no Docker at all is a real skip

    fixture.ConnectionString.Should().NotBeNull(
        "the emulator must start when Docker is available; it failed with: {0}", fixture.Failure);
}
```

Two things make this honest: the guard **fails** when the fixture should have worked and did not, carrying the underlying exception; and the report distinguishes *exercised* / *failed* / *not run* — and within "not run", distinguishes "not asked for" from "asked for and broken". Printing the first when the second is true is the bug. See `container-integration-tests`.

### 5. A wait strategy that cannot match

A log-line readiness wait against an image that logs to a file waits forever, and the timeout is then caught by pattern 3 and presented as a skip. Readiness should be a real client call.

### 6. Mocks asserting on themselves

The test configures a mock to return a value and then asserts the value came back. Nothing under test was exercised.

```bash
rg -n -B4 'verify\(|toHaveBeenCalledWith|Verify\(' -g '**/*test*' | head -40
```

The smell: a test whose only assertions are `verify(...)` calls against doubles, with no assertion on a returned value or observable state. Testing that your code calls a collaborator in a particular way tests your current implementation, not the behaviour — and it will fail on every refactor while catching no defects. Prefer asserting on the outcome, with an in-memory implementation of the port. See `hexagonal-architecture`.

### 7. Assertion-free tests

A test with no assertion at all passes as long as nothing throws. Sometimes intentional (a smoke test); usually an accident, or an assertion deleted to get to green.

```bash
# test bodies containing no expect/assert/should at all
rg -n --multiline --multiline-dotall 'it\((.|\n)*?\n  \}\)' -g '**/*.test.ts' | rg -v 'expect|assert'
rg -c 'void .*Test\(\)' -g '**/*Test*.cs'   # then compare against the Assert/Should count per file
```

Compare per file: the number of test methods against the number of assertions. A file with twelve tests and four assertions is worth reading.

### 8. Snapshots that record the bug

An approved snapshot or golden file records whatever the code produced on the day it was approved. If the code was wrong then, the snapshot now defends the defect, and the test fails the day someone fixes it.

Check: was the snapshot ever reviewed, or bulk-accepted with `-u`? A snapshot diff in a PR that nobody commented on is a snapshot nobody read.

### 9. Tests that assert the wrong layer

An end-to-end test that stubs the thing it was written to exercise. A "contract" test that asserts against a hand-written fixture rather than the provider's real shape. See `api-quirk-fixtures` — a fixture that encodes the same wrong assumption as the code cannot fail.

### 10. Time and order dependence that happens to pass

A test that passes only because of the machine's timezone, the current date, or the order the runner happened to choose. It is not testing theatre yet, but it is a green that means nothing.

```bash
npx vitest run --sequence.shuffle
TZ=Pacific/Chatham npm test -- --run
```

See `ci-failure-triage`.

## Cheap global checks

Before hunting patterns, get the shape of the suite:

```bash
# does the count of executed tests match the count of defined tests?
npx vitest run --reporter=verbose 2>&1 | tail -20
./gradlew test && find . -name 'TEST-*.xml' | xargs grep -ho 'tests="[0-9]*"\|skipped="[0-9]*"'

# how long does the "integration" suite take? a container suite finishing in 40ms never started one
```

Two numbers worth reading together: **skipped count** and **duration**. A suite that claims to test a database and runs in under a second did not reach a database.

## Reporting

For each finding, give the file and line, which pattern it is, and what it would take to make the test real.

Rank by **how much false confidence it buys**, not by how easy it is to fix. A security or data-boundary assertion that never runs is worse than a formatting one. A test that guards an invariant named in the docs is worse than an incidental one.

Then choose per finding:

- **Make it real** — add the non-empty assertion, the start guard, the reporting. Almost always the right answer.
- **Delete it** — a test that iterates an always-empty list, or asserts only on its own mocks, is worse than nothing: it occupies the space where a real test would be noticed as missing. Deleting it is an improvement, and the coverage drop is information.
- **File a gap issue** — where a test cannot be made real without credentials or hardware you do not have. Say so, rather than deleting a test that only needs an environment. See `gap-issue`.

Do not fix a finding by weakening it further, and do not report a suite as passing when this audit found it vacuous. The audit result *is* the finding.

## Related skills

- `container-integration-tests` — start guards, reporting fixtures, real readiness checks
- `api-quirk-fixtures` — fixtures that encode the code's own wrong assumptions
- `gap-issue` — recording a test that cannot be made real here
- `outside-in-tdd` — watching a test fail first, which prevents most of this
- `ci-failure-triage` — the flaky-versus-real decision
