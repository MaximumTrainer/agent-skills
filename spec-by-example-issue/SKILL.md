---
name: spec-by-example-issue
description: Turn a thin issue, idea or ticket into an implementable specification — numbered requirements, Given/When/Then acceptance criteria that are executable as written, and an outside-in test plan naming the files to create. Use when asked to elaborate, flesh out, specify or add acceptance criteria to an issue, when writing a user story, when picking the next piece of work off a backlog, or when an issue is a placeholder title with no body. Requires probing the real API and codebase first — the grounding is what makes the spec worth having.
license: MIT
metadata:
  version: "1.0.0"
---

# Specify an issue by example

A specification is worth having only if it is *grounded* and *executable*. Grounded means every claim in it was checked against the real codebase and the real external API, not inferred from the issue title. Executable means each acceptance criterion can be transliterated into a test without a further decision.

Most of the value is in the probing, before any writing. An ungrounded spec is a guess with formatting, and it is worse than the placeholder issue it replaced because it looks authoritative.

## 1. Probe before writing

Do not write a requirement you have not checked. Spend the first pass finding out what is actually true.

**In the codebase:**

```bash
gh issue view <number>                  # the placeholder, and any discussion
gh issue list --state all --search "<keyword>"   # has this been specified or rejected before?
```

- Which module owns this behaviour, and which layer does the change belong in?
- What already exists that this must compose with, or contradicts?
- Is this in the deliberate-decisions register — a choice that looks like a bug and is not? See `deliberate-decisions`. Do not specify away a decision someone made on purpose.

**Against the external API or data source**, where one is involved:

- What does the real payload look like, including the fields the docs do not mention? See `live-api-probe`.
- What does it do at the edges — empty, null, out of range, rate-limited, newest-first versus oldest-first?
- What are the units, and the precision the source can actually measure?

**With the user**, where a decision is genuinely theirs: the threshold value, the tie-break, what should happen in a case the data does not cover. Ask these before writing, not in the spec as an open question.

Record what you found. A spec that says "`/wellness` returns oldest-first, unlike `/activities`" is doing real work; a spec that says "fetch the wellness data" is not.

## 2. Write the requirements

Numbered, atomic, testable, and about observable behaviour — not implementation.

```markdown
## Requirements

R1. The dashboard reads the athlete's most recent HRV from the newest wellness
    row at or before today, ignoring future-dated rows.
R2. A future-dated wellness row is treated as a forecast and never as a
    measurement, including when it is the only row present.
R3. Where no wellness row exists at or before today, the dashboard shows
    "no data" and not a zero.
```

Each requirement must be:

- **Atomic** — one behaviour. If it contains "and", consider splitting it.
- **Observable** — phrased in terms of what a caller or user can see. "Uses a repository" is not a requirement; "returns 409 when the name is already taken" is.
- **Falsifiable** — you can say what would prove it wrong.
- **Free of solution** — no class names, no library choices, no table names. Those belong in the test plan.

State the **non-goals** explicitly. A spec without a boundary invites scope creep, and the reviewer cannot tell whether an omission was deliberate.

## 3. Write acceptance criteria as examples

One or more concrete examples per requirement, with real values. The examples are the specification; the prose is commentary.

```gherkin
Scenario: future-dated wellness rows are forecasts, not measurements
  Given the athlete has a wellness row for 2026-03-10 with HRV 61
    And the athlete has a wellness row for 2026-03-14 with HRV 78
    And today is 2026-03-11
  When the dashboard state is derived
  Then the reported HRV is 61
   And the reported HRV date is 2026-03-10
```

Rules that make the difference between a criterion and a wish:

- **Real values, not placeholders.** `HRV 61` on `2026-03-10`, not "some HRV on some date". A criterion with placeholders defers exactly the decision it was written to settle.
- **A fixed reference date.** "today is 2026-03-11", never "today". A criterion that depends on the real calendar becomes a test that fails on Tuesdays.
- **One `When`.** Two actions means two scenarios.
- **Assert on one thing plus its provenance.** The value and where it came from, so a test cannot pass on a coincidence.
- **Include the unhappy examples**: empty, null, malformed, unauthorised, rate-limited, boundary-exact. Where the path is security-sensitive, a negative example is mandatory, not optional.
- **Boundaries are separate examples.** If the band is `0 to −20`, write examples at `0`, at `−20`, and just outside each — that is where the drift between code and copy shows up. See `single-source-constants`.

If a criterion cannot be written as an example with real values, the requirement is not yet understood. Go back to step 1.

### When a criterion is not automatable

Say so in the criterion itself, and give the manual step and what a pass looks like:

```markdown
AC7. (manual — no chip available in CI) With a real FxChip in range, crossing
     the start gate produces one Garmin lap within 1.0 s of the chip's own
     split. Record the observed delta in the PR.
```

An honest manual step is fine. A criterion silently left unverifiable is not. See `gap-issue`.

## 4. Write the outside-in test plan

This is what turns a spec into work someone can start. Name the ring, the file and the test for each criterion, working from the outside in — see `outside-in-tdd`.

```markdown
## Outside-in plan

1. RED acceptance — `test/acceptance/dashboard-hrv.feature`
   Scenario above, plus the no-data case (R3).
2. RED contract — `tests/application/dashboard-sync.test.ts`
   "reads HRV from the newest non-future row" (R1, R2).
3. RED unit — `tests/domain/wellness.test.ts`
   `selectCurrentWellness` with future rows, empty input, single future row.
4. Fixture — add `withProjectedFutureRows` to `tests/fixtures/intervals-api.ts`
   and list the trait in the header comment.
5. GREEN — `src/domain/wellness.ts`, called from `buildDashboardState`.
6. Docs — add the trait row to the README's API quirks table.
```

Name the fixture work explicitly. A criterion that needs a new fixture trait and does not say so is where estimates go wrong.

## 5. Sizing, and splitting

If the plan has more than roughly five criteria or touches more than one bounded area, split it. Prefer a vertical slice that delivers observable behaviour end to end over a horizontal one that delivers a layer — a slice can be shipped and judged; a layer cannot.

State dependencies as issue references (`blocked by #12`), not as prose.

## 6. Post it

```bash
gh issue edit <number> --body-file spec.md
```

Keep the issue as the single source of truth for the work. If a criterion turns out to be wrong or untestable during implementation, **edit the issue body** and say in the PR what you changed and why — do not quietly implement something different from what the issue says. See `outside-in-tdd`.

## Definition of ready

An issue is ready to start when:

- [ ] Requirements are numbered, atomic, observable and solution-free
- [ ] Non-goals are stated
- [ ] Every requirement has at least one example with real values and a fixed reference date
- [ ] Unhappy and boundary examples are present; negative examples exist for sensitive paths
- [ ] Every claim about the codebase or an external API was checked, not assumed
- [ ] Any manual criterion says it is manual and states the pass condition
- [ ] The outside-in plan names the ring, file and test for each criterion
- [ ] New fixture traits are called out
- [ ] Dependencies are issue references
- [ ] Nothing in it contradicts the deliberate-decisions register

## Related skills

- `outside-in-tdd` — implementing the plan this produces
- `live-api-probe` — grounding the spec in what the real API does
- `gap-issue` — filing what a piece of work deliberately left unverified
- `deliberate-decisions` — checking a "bug" is not a decision before specifying it away
- `single-source-constants` — where a threshold named in a criterion should live
- `engineering-white-paper` — the longer-form write-up of a practice like this one
