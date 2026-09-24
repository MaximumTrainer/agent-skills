---
name: code-review
description: Perform a structured code review of a diff, PR, or set of files, evaluating test coverage, test correctness, security, and whether the code reads as fluent, human-readable, domain-oriented language rather than mechanical implementation detail. Use this skill whenever the user asks to "review this code," "review my PR," "check this diff," or shares a code change and asks for feedback, even if they don't name these four areas explicitly — they are the default lens for any review. Also use it when asked to write review comments, assess "is this ready to merge," or audit test suites for gaps.
license: MIT
metadata:
  version: "1.0.0"
---

# Code Review

A structured review process built around four pillars, applied in order. Each pillar has its own failure modes and its own checklist — don't skip to "looks good" without walking all four.

## How to run a review

1. **Scope the change.** Identify what files changed, what the change is trying to do (read the PR description / commit message / ticket if available), and what's *not* in scope. Don't review unrelated pre-existing code unless it's directly touched or directly relevant to the change's correctness.
2. **Walk the four pillars below, in order.** Coverage and correctness of tests first (they're your safety net for judging everything else), then security, then readability/domain fit.
3. **Produce output in the format in "Output format" below.** Don't just narrate — give the user something they can act on.

---

## Pillar 1: Test Coverage

The question isn't "are there tests" — it's "if this logic broke, would a test fail?"

Check:
- **New/changed behavior has a corresponding new/changed test.** A behavior change with no test diff is a red flag by default.
- **Branches, not just lines.** Every `if`/`else`, early return, exception path, and loop boundary (empty, one item, many) should have a test on each side. Line coverage percentage is not the metric — branch/path coverage is.
- **Boundary and edge cases**: empty input, null/None/nil, zero, negative numbers, max values, duplicate entries, unicode/encoding edge cases where relevant.
- **Error paths**: what happens when a dependency fails, a network call times out, a file is missing, permissions are denied. These are usually under-tested relative to the happy path.
- **Integration seams**: if the change touches a boundary (API contract, DB schema, serialization format), is there a test that would catch a breaking change on that seam, not just a unit test of the internal logic?
- **Deletions**: if tests were removed, is that justified by removed functionality, or is it coverage quietly regressing?

Flag as a gap, don't just note it as a *suggestion* — a merge with no test for new logic should be called out clearly, not softened into "you might consider maybe adding a test."

## Pillar 2: Test Correctness

A test that exists can still be worthless or actively misleading. Check each test for:

- **Does it actually test the thing it claims to?** Look for tests that exercise a code path but assert something trivial (e.g., asserting a function didn't throw, without checking the return value) — these pass even when the logic is wrong.
- **Would it fail if the logic were wrong?** Mentally mutate the implementation (flip a condition, off-by-one an index, swap two variables) and ask if the test would catch it. If not, the test is decorative.
- **Over-mocking.** If everything the function touches is mocked, the test may just be asserting "the mocks were called," not that the real behavior is correct. Mocks should stand in for things outside the unit under test, not for the logic being tested.
- **Test isolation.** Shared mutable state between tests, reliance on execution order, or tests that only pass when run as a full suite (not individually) are bugs in the test suite itself.
- **Flakiness risk**: timing assumptions (`sleep`, race conditions), reliance on real network/clock/filesystem, unseeded randomness.
- **Assertion quality**: asserting on exact values/structures where reasonable, not just "no exception" or "result is not null." Weak assertions are a common way coverage numbers look good while correctness confidence stays low.
- **Test names describe behavior, not implementation** — a test named after what it verifies (`rejects_negative_quantity`) survives refactors; one named after internals (`test_helper_function_3`) doesn't and signals the author wasn't thinking about behavior.

## Pillar 3: Security

Review for the change's actual attack surface — don't run a generic checklist against code that has no external input. Prioritize:

- **Input validation & trust boundaries**: is untrusted input (user input, external API responses, file contents, query params, headers) validated/sanitized before use, especially before it reaches a query, shell command, file path, template, or deserializer?
- **Injection**: SQL/NoSQL, command injection, path traversal, template injection, log injection (unsanitized input written to logs an attacker could use for forgery).
- **AuthN/AuthZ**: does this change introduce or touch an endpoint/action that needs an authorization check? Is the check at the right layer (server-side, not just hidden in the UI)? Watch for IDOR — resource IDs taken from the client without verifying the caller owns/can access that resource.
- **Secrets**: no hardcoded credentials, API keys, or tokens; secrets not logged; secrets not sent to error trackers or client-side code.
- **Data exposure**: API/error responses don't leak more than the caller needs (stack traces, internal IDs, other users' data); PII handled per whatever standard the codebase already follows.
- **Dependency changes**: new dependencies from a change diff — are they from a trustworthy source, pinned, and is the added surface area justified by the feature?
- **Crypto/randomness misuse**: non-cryptographic RNG used for tokens/secrets, weak or homegrown hashing for passwords, missing TLS verification.
- **Unsafe deserialization** of untrusted data (pickle, unsafe YAML load, etc.).

Rate each finding by exploitability and blast radius, not just presence — a theoretical issue in dead code is not the same severity as unsanitized input on a public endpoint. Use the severity scale in "Output format."

## Pillar 4: Fluent, Human-Readable, Domain-Oriented Code

The test here is: **does the code read like the problem, or like the machine?** Good code lets a domain expert who doesn't code well follow the logic; code that only a compiler-brain can follow has failed this pillar even if it's correct and fast.

Check:
- **Names come from the domain, not the implementation.** `overdueInvoices`, not `filteredList2`. `calculateShippingCost`, not `doCalc`. A function/variable name should answer "what is this, in the language of the business/problem" — not "what data structure holds it."
- **The main flow reads top-to-bottom as a narrative.** A reader should be able to read the primary function and get the gist of *what* happens without diving into every helper — implementation detail is pushed down into well-named helpers, not inlined into the main path.
- **No unexplained magic.** Magic numbers/strings, non-obvious flags (`process(data, true, false, 2)`), and clever one-liners that need a comment to decode are all signs the code is optimizing for the writer, not the reader. Prefer a named constant or a more explicit call over a comment explaining a cryptic one.
- **Abstractions match the domain's real shape.** Watch for both under-abstraction (the same domain concept reimplemented in three places with copy-paste drift) and over-abstraction (a generic framework/interface built for one caller, adding indirection with no payoff).
- **Comments explain *why*, not *what*.** A comment restating what the next line does is noise; a comment is earning its place when it explains a non-obvious constraint, a business rule, or a trade-off that isn't visible in the code itself.
- **Consistency with the surrounding codebase's idioms** — a locally "more elegant" pattern that fights the codebase's existing conventions usually costs more in reader confusion than it gains.

This pillar is more judgment-based than the others — call out concrete examples (name/line) rather than vague "improve readability" comments, and prefer suggesting the specific rename/restructure over just flagging the smell.

---

## Output format

Structure the review as:

1. **One-paragraph summary** — what the change does, and a one-line verdict (ready to merge / needs changes / needs discussion).
2. **Findings grouped by pillar** (Coverage, Test Correctness, Security, Readability), each finding tagged with a severity:
   - 🔴 **Blocking** — should not merge as-is (missing test for risky logic, real security hole, test that doesn't actually verify behavior)
   - 🟡 **Should fix** — meaningfully improves quality/safety, not merge-blocking
   - 🟢 **Nit / optional** — style or polish, purely a suggestion
3. **Each finding** includes: file/line (or function name if line numbers aren't available), what's wrong, and — where reasonably possible — a concrete suggested fix (a rewritten line, a test skeleton, a rename), not just a description of the problem.
4. Skip a pillar's section entirely if there is nothing to flag for it — don't pad the review with "no issues found" filler for every pillar on every file.

Keep the tone direct and specific. Praise genuinely good instances of any pillar briefly (e.g., a well-named function, a test that clearly would catch a real regression) rather than only listing problems — but don't let praise dilute or hedge a blocking finding.

## Related skills

- `test-theatre-audit` — when the review turns up tests that pass while asserting nothing
- `outside-in-tdd` — checking whether the change was genuinely driven by a failing test
- `hexagonal-architecture` — the layer violations worth flagging in a review
- `gap-issue` — recording what a review could not verify
- `verify-and-ship` — landing the change once the review is addressed
