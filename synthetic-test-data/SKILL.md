---
name: synthetic-test-data
description: Build test data that reproduces the shape, ordering and value ranges of real data while inventing every identity, and prove no real value leaked. Use when creating fixtures or seed data, when tempted to copy a production record or payload into a test, when masking or anonymising a dataset, when a fixture needs to look realistic, and when reviewing whether test data or a captured capture contains personal data. Covers what makes data identifying, referential integrity across a synthetic dataset, planted canary secrets, and why masking is not anonymisation.
license: MIT
metadata:
  version: "1.0.0"
---

# Synthetic test data

Test data must reproduce the **shape, ordering, distribution and value ranges** of real data, and invent everything that identifies a person. Those two requirements pull against each other, and resolving the tension badly is how production data ends up in a repository.

The default that is always wrong: copying a production record and changing the name. Names are rarely what identifies someone.

## What makes data identifying

Direct identifiers are the easy part. The ones that leak are the indirect ones.

**Direct** — obviously remove: name, email, phone, address, account id, device id, IP, national/insurance number, payment details, photo, free-text notes.

**Indirect / quasi-identifiers** — these re-identify in combination, and are routinely left in "anonymised" fixtures:

- Date of birth, or an exact age
- A postcode, GPS trace, or any location precise enough to be a home
- A timestamp precise to the second, especially a sequence of them
- An unusual value: a very high or very low measurement, a rare configuration, a long-tail category
- A combination that is unique in the population even though each field is not — the classic result is that a handful of quasi-identifiers uniquely identify most people in a dataset
- Free text of any kind. Notes fields contain names, and nothing generic will find them all
- Referential structure — the same synthetic id appearing in two files links them back together

**Not personal data but must not ship anyway**: real credentials, tokens, internal hostnames, customer names in a B2B dataset, and anything under a confidentiality agreement. Where a specification was shared in confidence, implement it and do not reproduce it — keep byte tables and protocol layouts out of public fixtures and public issues.

## Reproduce the shape, invent the identity

Decide, field by field, which of these a field is:

| Field kind | What to do |
|---|---|
| Identifying | Invent. A stable synthetic value, obviously fake to a human |
| Structural (type, nullability, ordering, envelope) | Reproduce exactly |
| Distributional (range, precision, units, skew) | Reproduce the range and shape; invent the values |
| Semantic-edge (the surprising cases) | Reproduce deliberately, and list them — see `api-quirk-fixtures` |
| Free text | Invent from a fixed lorem set. Never carry through |

Make invented identities **obviously synthetic to a human, and stable across the suite**:

```ts
export const FIXTURE_ATHLETE = {
  id: 'i90210',                     // recognisably fake, not a real id shape in use
  name: 'Masters Test Sprinter',
  dob: '1974-01-01',                // synthetic, deliberately a round date
  email: 'sprinter@example.invalid' // reserved TLD — cannot route anywhere
};
```

Use reserved values that cannot collide with anything real: `example.com` / `example.invalid` for domains, `555-0100`–`555-0199` for US phone numbers, `192.0.2.0/24` and `2001:db8::/32` for IPs, `4111 1111 1111 1111` for a card number. These are reserved precisely so that a leak into a live system fails safely.

Avoid a plausible-but-real value. A randomly generated email at a real domain belongs to somebody, and a generated postcode is a real postcode.

## Determinism

A fixture that changes between runs produces a suite that fails on Tuesdays, and a suite that fails on Tuesdays gets ignored.

- **A fixed reference date**, exported: `export const FIXTURE_NOW = new Date('2026-03-11T09:00:00Z')`. Derive every other date from it (`FIXTURE_NOW - 3 days`) so the relationships hold whatever the real date is.
- **No `Math.random`, no `Guid.NewGuid()`, no `now()`** in fixture construction. Where a generator library is used, **seed it** and pin the seed in the file.
- **Export the constants the tests assert on.** If a test hard-codes `61` and the fixture later says `62`, the test starts asserting a coincidence.
- **No dependence on the local timezone or the real weekday.** If the logic cares about weekends, set the reference date to a known Wednesday and say so in a comment.

## Referential integrity across a dataset

For a multi-table or multi-endpoint fixture, consistency is what makes it useful — and the usual mistake is masking each table independently, which destroys the joins and produces a dataset where nothing links up.

- **Map each real identifier to one synthetic identifier, consistently** — a deterministic pseudonymisation, applied the same way everywhere the id appears, so foreign keys still join.
- **Keep the cardinality realistic.** One athlete with 400 activities and one with 3 exercises pagination and empty states; 50 athletes with 50 activities each exercises nothing.
- **Keep the ordering and the gaps.** Real data has missing days, duplicate timestamps, out-of-order arrivals and a record created by a different code path five years ago. A perfectly regular fixture tests a world that does not exist.
- **But note what pseudonymisation is not.** A consistent mapping is *reversible given the mapping*, and re-identifiable from the quasi-identifiers alone even without it. It is a safety measure for a test dataset, not anonymisation. Do not describe a pseudonymised dataset as anonymous, and do not treat it as safe to publish.

## The shape that keeps earning its place

For any fixture covering a schema or an adapter, include:

- A field **present** on one record
- The same field **explicitly null** on a second
- The same field **absent entirely** from a third
- A nested object, and an array — including an empty array
- A boundary value at each edge of every band the code tests (see `single-source-constants`)
- A record created by a legacy or alternative path, missing fields the current path always sets
- A **planted canary secret**

Present / null / absent is three distinct cases that most mapping code conflates, and the conflation is invisible against a fixture exercising only one of them.

### The canary

Plant a recognisable value in the input and assert it is **absent** from every output, log, export, error message and rendered page:

```ts
export const CANARY = 'SEEDED-SECRET-DO-NOT-EMIT-7f3a1c';
```

```bash
# after a run that produced output
grep -rn "SEEDED-SECRET-DO-NOT-EMIT" ./out ./logs && exit 1
```

This is the cheapest test of a masking, redaction, logging or export path that exists, and it catches the case nobody writes a test for: the value coming out through a route you did not think of.

## Masking an existing dataset

Where the job is to derive test data *from* a real dataset rather than invent it:

- **Work on a copy, in an isolated environment.** Never mask in place, and never mask across a network you do not control.
- **Allowlist, do not denylist.** Start from "nothing is carried through" and name the fields that may be, with a reason. A denylist misses the column added last week and the free-text field nobody categorised.
- **Fail closed on an unknown field.** A new column with no masking rule must fail the run, not pass through untouched. This single rule prevents most masking leaks.
- **Preserve format where format is load-bearing** — a masked value must still satisfy the column's constraints, checksums and length, or the fixture cannot be loaded.
- **Verify afterwards, do not assume.** Grep the output for the canary, for known real values, for anything matching an email/phone/id pattern, and for the source's own high-cardinality columns. Count distinct values and compare against the source: a column that came out with the same distinct count and the same distribution may not have been masked at all.
- **Do not mask and then publish.** Re-identification from quasi-identifiers is the normal outcome, not an exotic attack.

## Reviewing a fixture

```bash
# identifying patterns in test data
rg -nE '[A-Za-z0-9._%+-]+@(?!example\.(com|org|net|invalid))[A-Za-z0-9.-]+\.[A-Za-z]{2,}' tests/ fixtures/
rg -nE '\b(19|20)[0-9]{2}-[01][0-9]-[0-3][0-9]\b' tests/ | head       # real-looking DOBs
rg -nE '\b[0-9]{1,3}\.[0-9]{4,}\b' tests/                             # precise lat/long
rg -nEi 'api[_-]?key|secret|password|bearer |BEGIN [A-Z ]*PRIVATE KEY' tests/ fixtures/

# is any fixture actually a captured production payload?
rg -l 'X-Request-Id|x-amzn-|set-cookie' tests/ fixtures/
```

Also check git history, not just the working tree — a payload removed in a later commit is still in the repository and still published.

## Checklist

- [ ] Every identifying field is invented, and obviously synthetic to a human
- [ ] Reserved domains, IP ranges and phone ranges used, so a leak fails safe
- [ ] No date of birth, precise location, precise timestamp sequence, or free text carried through
- [ ] Structure, ordering, nullability, units and value ranges reproduced faithfully
- [ ] Fixed reference date exported; no random, no real clock, seeds pinned
- [ ] Constants the tests assert on are exported from the fixture
- [ ] Present / explicitly-null / absent all covered, plus nesting, arrays and boundaries
- [ ] Synthetic ids are consistent across files so joins still work
- [ ] A canary secret is planted and asserted absent from every output path
- [ ] Nothing under confidentiality is reproduced, in fixtures or in public issues
- [ ] Git history checked, not only the working tree
- [ ] The dataset is described as pseudonymised, not anonymous, if that is what it is

## Related skills

- `api-quirk-fixtures` — reproducing the traits of a real API in a synthetic fixture
- `live-api-probe` — what may and may not be written down after seeing real data
- `container-integration-tests` — seeding the same shaped data across providers
- `single-source-constants` — boundary values worth including
- `test-theatre-audit` — a fixture that agrees with the code and therefore cannot fail
