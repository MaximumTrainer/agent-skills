---
name: gap-issue
description: Record what a piece of work deliberately left unverified or unbuilt, as a precise GitHub issue, so the gap is tracked rather than forgotten. Use when closing work with an acceptance criterion unmet, when something is wired but untested, when hardware or a live account was unavailable, when asked to "create issues for anything incomplete" or "what's left", and when reconciling a backlog against what has actually shipped. The alternative to a gap issue is a silent false green.
license: MIT
metadata:
  version: "1.0.1"
---

# File the gap instead of hiding it

Work ends in one of three states, and only two of them are honest:

1. **Done** — every criterion is a passing test, or a manual step with its result recorded.
2. **Done with a tracked gap** — something is deliberately unverified, and there is an issue saying exactly what.
3. **Reported done** — the checkbox is ticked and nobody knows what was not checked.

The third is the one that costs, because it converts a known unknown into an unknown unknown. A gap issue is cheap; discovering the gap in production is not.

A gap is not a failure to be apologised for. Hardware you do not have, an account you cannot access, a vendor behaviour you cannot reproduce, a criterion the issue got wrong — these are legitimate. Going quiet about them is not.

## When to file one

At the point you would otherwise call the work done, anything a reader of the
closed issue would reasonably have assumed was verified, and was not.

Not a gap: a hypothetical improvement, a refactor you would like, "add more
tests". Those are wishes. The test is whether closing without saying so would
mislead someone.

## What a gap issue must contain

Precision is the whole value. "Needs more testing" is not trackable and will be closed unread in six months.

```markdown
### What is unverified

`MeshyMeshAdapter.generate()` is wired into the composition root and covered by
unit tests against a mocked `httpx` client. It has never been run against the
real Meshy API.

### Why it was left

`MESHY_API_KEY` is not available in CI, and the integration suite is gated on
that variable being present, so it reported "skipped" rather than failing.
Closed #77 on the strength of the mocked tests only.

### What we do not know

- Whether the real response shape matches `MeshyResponse` — the schema was
  written from the published documentation, not from a captured payload.
- Whether the 30 s sandbox timeout is enough for a real generation call.
- What the API returns on quota exhaustion; the code assumes a 429 with a
  `Retry-After` header.

### What would close this

1. Capture one real response and add it as a fixture, with the traits listed
   (see `api-quirk-fixtures`).
2. Run `pytest -m integration` with a real key, and paste the result.
3. Assert the quota-exhaustion path against the captured shape.

### Blast radius if the assumption is wrong

AI mesh generation fails at runtime for every user; the rest of the CAD loop is
unaffected. No data loss, no silent wrong output.

Origin: #77 (closed 2026-09-12). Referenced from README quirks table.
```

The five headings are the point: **what**, **why**, **what we do not know**,
**what would close it**, **blast radius**. Each answers a question the future
reader would otherwise have to reconstruct.

**Blast radius is the one most often left out, and the one that sets priority.**
Size it honestly. "Silently produces wrong numbers on the dashboard" and "the feature errors visibly" are different priorities, and only you know which it is right now.

## Filing it

```bash
gh issue create \
  --title "Unverified: Meshy adapter has never run against the real API" \
  --body-file gap.md \
  --label "gap,needs-verification"
```

Then **link it from both directions**:

- Reference the gap issue in the PR body and in the closing comment of the original issue: "Closing #77; the unverified Meshy path is tracked in #91."
- Reference the origin issue inside the gap issue.

A gap issue nobody can find from the work that created it is a gap issue that does not exist. Title it so it is findable: start with `Unverified:`, `Untested:` or `Gap:` and name the component, not the symptom.

## Reconciling a backlog

When asked what is left, or to close what has shipped, work from evidence rather than from memory. Both directions matter.

**Close what is proven shipped.** An issue may be closed when its acceptance criteria are demonstrably met *and* a CI run on the default branch that includes the work concluded success. Not when the code was merged — when the build that contains it passed. See `verify-and-ship`.

```bash
gh run list --branch main --limit 1 --json conclusion,headSha
gh issue close <n> --comment "Criteria met; verified green on main in run <url>."
```

Quote the evidence in the closing comment: the run URL, and which test covers which criterion. A closing comment that says "done" teaches the next reader nothing.

**File what is missing.** For each open issue, and each criterion inside it, decide: met and verified, met but unverified (gap issue), or not met (leave open, and update the body if the criteria have changed). Do not leave an issue open with three of five criteria silently met — split it, so what remains is what remains.

Ask before bulk-closing. Closing someone's issue is not reversible in their attention, even though it is reversible in GitHub.

## The reporting rule

Whatever the gap, say it in plain language in the PR and in your summary to the user, in the same breath as the success:

> Implemented and green: 6 of 7 criteria, full suite passing. AC7 (real-chip
> timing) not verified — no hardware available; tracked in #91.

Never: a ticked box, an unqualified "all tests pass", or a summary that omits the one thing that was not checked. "Not run — no chip available" is an acceptable line. A fabricated green is not, and it is the one thing that makes every other report you write untrustworthy.

## Related skills

- `outside-in-tdd` — the definition of done a gap issue is the honest exception to
- `spec-by-example-issue` — writing criteria that make gaps visible instead of arguable
- `test-theatre-audit` — finding the gaps nobody filed, in suites that pass vacuously
- `verify-and-ship` — the green run that licenses a close
- `deliberate-decisions` — for a choice that is settled, as opposed to a gap that is open
