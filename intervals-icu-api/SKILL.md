---
name: intervals-icu-api
description: Integrate with the Intervals.icu API correctly — authentication, the endpoints, the response quirks that have each caused a real bug, and the rules for writing to an athlete's activity reversibly. Use when reading or writing Intervals.icu data, building training or fitness analysis on it, debugging "why does my dashboard show the wrong value", adding a wellness/activity/streams/laps call, or writing fixtures for it. Also covers the derived training metrics (CTL/ATL/TSB) and where their thresholds belong.
license: MIT
metadata:
  version: "1.0.0"
---

# Intervals.icu API

Intervals.icu is the shared integration point across several projects here, and the same handful of its behaviours has caused the same bugs repeatedly. This skill is the accumulated cost of those.

Read the quirks section **before** writing any handling. Every row in it was a real defect, and most of them fail silently — producing a plausible wrong number rather than an error.

## Authentication

HTTP Basic, with the **literal username `API_KEY`** and the athlete's key as the password:

```js
const auth = 'Basic ' + Buffer.from(`API_KEY:${process.env.ICU_KEY}`).toString('base64');
```

```python
requests.get(url, auth=("API_KEY", os.environ["ICU_KEY"]))
```

- The athlete id is of the form `i123456` and goes in the path (`/api/v1/athlete/i123456/...`). It is **not** the username.
- Credentials come from the environment, never a file, never a fixture, never a log line. See `live-api-probe`.
- **No background use of an athlete's credentials.** Fetch on user action only, unless the athlete has explicitly authorised a background sync. A key is not consent to poll.
- Store keys sealed (an envelope cipher, a secrets manager), never in the clear, and never in a log line or an error message.

### Base path in development

Projects proxy the API in development, so the base is a relative prefix (`INTERVALS_BASE = '/intervals'`) outside production. Two consequences that have each cost time:

- A **live probe must rewrite the base to the real origin**, or every request 404s in a way that looks like an API change.
- **Never match request paths by substring** against `/intervals` in tests — the base is itself `/intervals`, so `callsMatching('/intervals')` matches every request ever made. Use narrow helpers (`lapDataRequests()`, `streamRequests()`).

## The endpoints

| Endpoint | Returns | Watch out for |
|---|---|---|
| `/athlete/{id}/profile` | Athlete profile, zones, weight | Weight is `icu_weight`; the Strava-sourced `weight` is null |
| `/athlete/{id}/activities` | Activity list | **Newest-first** |
| `/athlete/{id}/activities?oldest=&newest=` | Date-ranged list | Dates are `YYYY-MM-DD` in the athlete's local zone |
| `/athlete/{id}/wellness` | Daily wellness rows (HRV, RHR, sleep, CTL/ATL/TSB) | **Oldest-first** — the opposite of activities |
| `/athlete/{id}/events` | Planned workouts and races | Future-dated by nature |
| `/activity/{id}/streams` | Time series | A **bare array** of `{type, data}`, not a keyed object |
| `/activity/{id}/intervals` | Laps / intervals | Auto-detected laps have `label: null` |
| `/athlete/{id}/pace-curve` | Best pace over distance | Values below ~250 m are corrupt |

## The quirks that have caused real bugs

### Ordering — the one that bites hardest

**`/activities` is newest-first. `/wellness` is oldest-first.** Both return a bare array. Nothing in either payload announces its direction.

A codebase that reads `entries[0]` for "the latest" is correct for activities and silently reads a value from the start of the window for wellness. The observed failure was an HRV reading 60 days stale, presented as today's — no error, no warning, a plausible number.

Normalise direction at the adapter boundary. Sort explicitly by date and never rely on the order the API returned:

```ts
const rows = [...wellness].sort((a, b) => b.id.localeCompare(a.id)); // wellness id is the date
```

### Future-dated wellness rows are forecasts

Intervals.icu projects CTL/ATL/TSB forward. A `/wellness` response routinely contains rows dated **after today**, and they are predictions, not measurements.

Consequence if assumed away: a planned rest day reports the athlete as already recovered, and a readiness recommendation is made from data that has not happened. Filter to rows at or before today for anything describing current state, and treat future rows as a separate, explicitly-labelled projection.

### Nulls that must not become zero

- **`max_speed: null`** on manual entries and activities with no GPS. A required-number schema erases the whole activity; defaulting to `0` reads as "stationary" and drags every average down.
- **`label: null`** on every auto-detected lap. A `z.string().optional()` rejects them — and since auto-detected laps are most laps, *all* rep analysis is lost.
- **`null` samples mid-array** in velocity and power streams. `Math.max` and running sums produce `NaN` for the entire series, not for one sample.
- **Weight** is in `icu_weight`; the Strava-sourced `weight` is null. Body-weight-relative loads come out empty if you read the wrong one.

The general rule: Intervals.icu emits explicit `null` for absent values, not `undefined` or an omitted key. Use `.nullish()`, not `.optional()`. And keep "no data" distinguishable from zero all the way to the presentation layer — render it as "no data", never as `0`. See `api-quirk-fixtures`.

### `/streams` shape

A bare array of `{ type, data }` objects:

```json
[{"type": "velocity_smooth", "data": [...]}, {"type": "watts", "data": [...]}]
```

Reading `streams.velocity_smooth.data` yields `undefined` with no error. Index it into a map at the boundary, and assert the stream you need was actually present — a requested stream that the activity does not have is simply absent from the array.

### Lap `type` does not mean what it says

Warm-up jogs are typed `WORK`, and the session's peak effort frequently sits in a lap typed `RECOVERY`. **Lap `type` cannot be used to identify sprint efforts.** Identify them by the measurements — velocity, duration, distance — not by the category.

Relatedly: `average_speed` can **exceed** `max_speed` on short laps, which produces a flying velocity faster than the rep's own peak. Both fields are computed differently upstream; do not assume the invariant.

### Pace curve below ~250 m is corrupt

Values there imply things like 100 m in 1 second. Anything derived from them is nonsense, and there is no error to notice. Floor the distance you read from the curve, and say in the code why.

### Rate limiting

Per-activity request bursts draw `429`. The observed failure mode is that **whatever was requested last silently disappears** — so a sync of 40 activities returns 34 and looks complete.

Use one shared limiter for the whole integration, honour `Retry-After`, bound retries, and **fail loudly** when the budget is exhausted rather than returning a partial result that looks whole. Where partial is acceptable, make it visible in the return type.

## Writing to an athlete's account

Writing into someone's training history is the highest-consequence thing these integrations do. One rule governs it:

> **Never write to an athlete's activity without a way to identify and undo what we wrote.**

In practice:

- **Deterministic names** for anything created (`FL #3`), so a re-sync updates rather than duplicates.
- **A fenced block** in any description field you touch, with explicit start and end markers. Rewrite only between the markers. The athlete's own prose outside them survives every re-sync untouched.
- **Your own custom fields**, namespaced, never overwriting a field the athlete or another tool owns.
- **Their intervals are theirs.** Do not delete or reorder an athlete's manually-created intervals.
- **Refuse ambiguity up front.** Attaching to an activity that already belongs to another session should be refused with an explanation, not resolved by guessing.
- **Idempotent.** Every write will be retried. Re-running a sync must converge, not accumulate.
- **Read back and diff.** After writing, re-read the activity and report every way it differs from what was intended. This is the only way to catch a silently-rejected field, and it is how several of the quirks above were found.

## Derived training metrics

CTL, ATL and TSB come back on wellness rows — do not recompute them unless you must, and if you do, say which definition you used.

- **CTL** — chronic training load, ~42-day exponentially weighted load. "Fitness."
- **ATL** — acute training load, ~7-day. "Fatigue."
- **TSB** — CTL − ATL. "Form." Positive means fresher than the recent average.

Two cautions:

- **TSB bands are a modelling choice, not a fact.** Where a project bands TSB into readiness zones, those boundaries belong in **one** place in the domain, with their labels and guidance text, and every tooltip, README table and UI scale derives from it. A tooltip advertising "Tired: −10 to −20" beside code using `0 to −20` produced a user-facing bug report that looked like broken scoring. See `single-source-constants`.
- **The load model is cycling-derived.** For sprint, strength and other neuromuscular work, TSS-style load underestimates central nervous system cost. If a project reasons about CNS recovery, it needs its own model, and the documentation should say the metric is being repurposed.

## Fixtures

Because so many of the quirks are silent, the fixture is the only thing that can hold the line. A fixture written from the documentation encodes the same assumptions as the code and cannot fail.

Reproduce, at minimum:

- `/activities` newest-first **and** `/wellness` oldest-first, in the same fixture
- A future-dated wellness row
- An activity with `max_speed: null`
- Laps with `label: null`
- A velocity stream containing `null` samples
- `/streams` as a bare array
- `average_speed > max_speed` on one short lap
- A `429` scenario

List each trait in a header comment, export the constants tests assert on, use a fixed reference date, and invent the athlete — a synthetic id, a synthetic name, a synthetic date of birth. Never a real athlete's data. See `synthetic-test-data` and `api-quirk-fixtures`.

## Related skills

- `api-quirk-fixtures` — the loop for capturing a new quirk; the general catalogue
- `live-api-probe` — confirming a behaviour against a real account safely
- `synthetic-test-data` — building the fixture athlete
- `single-source-constants` — where TSB bands and thresholds belong
- `hexagonal-architecture` — normalising direction, nulls and shape at the adapter boundary
