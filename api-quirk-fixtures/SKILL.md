---
name: api-quirk-fixtures
description: Turn a real third-party API behaviour into a fixture trait, a failing test, a fix and a documented row, so the wrong assumption can never quietly return. Use when live data disagrees with the code's assumptions, when a schema rejects a real payload, when adding any handling for how an upstream API actually behaves, when a bug is traced to a field that was null or ordered unexpectedly, and when writing or reviewing fixtures for an external integration. Covers why fixtures that share the code's assumptions cannot fail, and the quirk catalogue worth checking first.
license: MIT
metadata:
  version: "1.0.0"
---

# Capture an API quirk as a regression

Almost every significant integration bug has the same shape: **the code assumed something about the upstream API that is not true, and no test disagreed, because the fixtures encoded the same assumption.**

That is the part worth internalising. The fixture was not merely incomplete — it was written by the same person, at the same time, from the same reading of the same documentation as the code. It agrees with the code by construction. Adding more tests against it cannot help.

So the fix is never just the code change. It is making the fixture **tell the truth**, so the assumption can never quietly return.

## The loop

1. **Observe it live.** Hit the real endpoint and confirm the behaviour is real and reproducible, not a one-off. See `live-api-probe`.
2. **Reproduce it in the fixture.** Add the trait to the fixture module, and add a line to the "real-world traits these fixtures reproduce" list at the top of that file.
3. **Write the failing test** asserting the *correct* behaviour. Run it and watch it fail — a test that never failed proves nothing. See `outside-in-tdd`.
4. **Fix the code.**
5. **Document it** in the integration's quirks table: the trait, and the consequence if it is assumed away.

Step 2 before step 3, and step 3 before step 4. If you fix the code first, you will not find out whether the test was capable of catching it.

## Why the trait list at the top of the fixture matters

A fixture file grows to hundreds of lines of plausible-looking data, and nobody can tell by reading it which parts are load-bearing. A header comment listing each real-world trait the fixture reproduces turns it from data into documentation:

```ts
/**
 * Real-world traits these fixtures reproduce:
 *  - /activities is newest-first; /wellness is OLDEST-first
 *  - max_speed is null on manual and no-GPS activities
 *  - auto-detected laps always carry label: null
 *  - velocity streams contain null samples mid-array
 *  - future-dated wellness rows are forecasts, not measurements
 *  - ...
 */
```

Now a change that removes a trait is visible in review, and a reader who is about to "tidy up" an odd-looking null knows it is there on purpose.

## Fixture rules

- **No production data.** Reproduce the *shape, ordering and value ranges* of real responses; invent the identity. A synthetic athlete id, a synthetic name, a synthetic date of birth. See `synthetic-test-data`.
- **Deterministic.** A fixed reference date (`FIXTURE_NOW`), no `Math.random`, no dependence on the real weekday, the real calendar or the local timezone. A fixture that changes with the clock produces a suite that fails on Tuesdays, and a suite that fails on Tuesdays gets ignored.
- **Export the constants the tests assert on.** `FIXTURE_TODAY_HRV`, `REST_DAY_TODAY`. If a test hard-codes `61` and the fixture later says `62`, the test starts asserting a coincidence. Exporting the value means a fixture change cannot silently invalidate an assertion — it either updates it or breaks it loudly.
- **Add a named scenario builder** for a distinct situation rather than overloading the base catalogue. `buildRestDayScenario()`, `withProjectedFutureRows()`. A base fixture that has been bent to serve nine scenarios serves none of them clearly.
- **Capture real payloads verbatim** where licensing and privacy allow, scrubbed of identity. A hand-written fixture reflects what you believe; a captured one reflects what happened.

## The stub

Prefer an in-memory stub serving every endpoint the integration uses, recording each request, over per-test mocking of the HTTP client:

```ts
const api = createApiStub({
  activities: [...],
  wellness: [...],
  failing: { '/wellness': 503 },   // force a status
});
```

It lets a test assert on **what was requested**, not only on what came back — which is how you catch a request burst, a missing pagination follow-up, or a call that never happened.

**Match request paths precisely.** A substring match is a trap when the base path is itself a prefix: if the dev-proxy base is `/intervals`, then `callsMatching('/intervals')` matches *every* request. Provide narrow helpers (`lapDataRequests()`, `streamRequests()`) and use them.

## Schema conventions

These four decisions cause most of the damage, and all four are invisible until a real payload arrives.

- **`null` versus absent.** Many APIs emit an explicit `null` for an absent value, not an omitted key. In Zod that is `.nullish()`, not `.optional()`; with Jackson it is the difference between a missing field and a present null. Get it wrong and the schema rejects real payloads — and because your fixture omits the key instead of nulling it, every test passes.
- **"No data" is not "zero".** `max_speed: null` means there was no GPS trace. Defaulting it to `0` makes it read as "stationary", which drags averages down and is indistinguishable from a real measurement. Keep the absence, all the way through to the presentation layer, and render it as "no data". Where a default genuinely is zero, transform explicitly and say why.
- **Do not reject on an unexpected field.** A provider adding a field is not a breaking change; a strict schema turns it into one.
- **Validate at the boundary, once.** Parse the payload into your own canonical type at the edge of the adapter. Downstream code should never see the vendor's shape, so a vendor change has one place to be absorbed. See `hexagonal-architecture`.

## The quirk catalogue

Check these before assuming you have found something new — the answer is often already here. These are real, from real integrations, and most of them cost a debugging session before they were understood.

**Ordering**

| Trait | Consequence if assumed away |
|---|---|
| One collection newest-first, a sibling collection **oldest**-first | `entries[0]` silently reads a 60-day-old value |
| No `ORDER BY`, or an unordered set | Results differ between environments and between runs |
| Pagination without a stable sort | Records are duplicated across pages, or skipped |

**Nulls and absence**

| Trait | Consequence if assumed away |
|---|---|
| A numeric field is `null` on records created by a different path (manual entry, no sensor) | A required-number schema erases the record entirely |
| An optional label is **always** null for auto-generated items | `.optional()` rejects them, so all downstream analysis of them is lost |
| `null` samples appear mid-array in a numeric stream | `Math.max` and running sums produce `NaN` for the whole series |
| The same value lives under two field names, one of which is always null | The feature comes out empty and looks unimplemented |

**Shape**

| Trait | Consequence if assumed away |
|---|---|
| An endpoint returns a bare array of `{type, data}` rather than a keyed object | `streams.velocity.data` yields nothing, silently |
| A single result is returned unwrapped, a multiple result wrapped in an envelope | Parsing works in testing and fails on the second record |
| A field's type varies (string or number; object or array) | Deserialisation fails only for some records |

**Semantics — the expensive ones**

| Trait | Consequence if assumed away |
|---|---|
| Future-dated rows are **forecasts**, not measurements | A planned rest day reports the subject as already recovered |
| A category field does not mean what its name implies (warm-ups typed `WORK`; the peak sits in a `RECOVERY` row) | The category cannot be used to identify what you are looking for |
| A derived average can exceed the recorded maximum on short samples | Impossible values propagate as if real |
| Values below a threshold are corrupt artefacts of the provider's own smoothing | Anything derived from them is nonsense, with no error to notice |
| Units are not what the field name says, or precision is finer than the source can measure | Rounding errors accumulate per element |

**Operational**

| Trait | Consequence if assumed away |
|---|---|
| Per-item request bursts draw a `429` | Whatever is requested last silently disappears |
| A `200` carrying an error body | Failures are counted as successes |
| Silent truncation at a page-size limit | Large accounts quietly lose data |
| Clock skew, or timestamps in the server's local zone | Off-by-one-day at the boundary, in one timezone only |

## Rate limits

A `429` that is caught and logged is data loss. Handle it as a first-class case: a single shared limiter for the integration, honour `Retry-After`, bound the retries, and **fail loudly** when the budget is exhausted rather than returning a partial result that looks complete.

Where a partial result is genuinely acceptable, make the partiality visible in the return type — a result object carrying what was fetched and what was not — so a caller cannot mistake it for the whole.

## Definition of done

- [ ] The behaviour was confirmed against the live API, not just reasoned about
- [ ] The fixture reproduces the trait, and the trait is listed in the fixture header
- [ ] The test failed before the fix and passes after, and you watched it fail
- [ ] Constants the test asserts on are exported from the fixture, not hard-coded in the test
- [ ] The quirks table in the README (or integration doc) has a row: the trait and its consequence
- [ ] No production data, no identifying values, in the fixture
- [ ] "No data" is still distinguishable from zero at every layer

## Related skills

- `live-api-probe` — confirming the behaviour against a real account safely
- `synthetic-test-data` — inventing fixture identities without production data
- `test-theatre-audit` — fixtures that agree with the code and therefore cannot fail
- `container-integration-tests` — when the dependency can be run locally instead of stubbed
- `single-source-constants` — where a threshold discovered this way should live
- `intervals-icu-api` — the worked example this catalogue is largely drawn from
