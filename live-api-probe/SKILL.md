---
name: live-api-probe
description: Run real code against a real third-party account to find out what the API actually does, then delete the harness — with strict credential and PII hygiene. Use to confirm a domain or sync change behaves on real data, to diagnose "why does my dashboard show X", to discover an API behaviour the fixtures do not reproduce, or to ground a specification before writing it. Covers scratch-harness conventions, credential handling that never persists a secret, rate limiting, and what may and may not be written down afterwards.
license: MIT
metadata:
  version: "1.0.0"
---

# Probe a live account

Fixtures prove the code does what you believe. Only a live run proves you believed the right thing.

Most real defects in these integrations were found this way and could not have been found any other way: lap data silently discarded, a value read from the wrong end of a window, a payload shape that was an array where the code expected an object. No unit test would have caught any of them, because the fixtures shared the code's assumptions. See `api-quirk-fixtures`.

A live probe is a **diagnostic**, not a test. It is temporary by design: written, run, read, deleted. What survives is a fixture trait, a test, and a documented row.

## Credentials

Environment variables only. Never write them to a file, never commit them, never paste them into a test that stays on disk.

```bash
ICU_ID=<athlete id> ICU_KEY=<api key> npx vitest run tests/__live.test.ts
```

- **Read-only or least-privilege credentials** where the provider offers them. A probe should not be able to mutate the account.
- **If the user pastes credentials in chat**, use them for the run and let them stay in the transcript — do not persist them anywhere. Do not echo them back, do not put them in a filename, and do not include them in a summary.
- **Never log the credential**, and be careful with what logs *near* it: a request-dump helper will happily print an `Authorization` header. Redact at the logging boundary, not at each call site.
- Know the auth scheme's shape before guessing. Several APIs use HTTP Basic with a literal username and the key as the password:
  ```js
  'Basic ' + Buffer.from(`API_KEY:${process.env.ICU_KEY}`).toString('base64')
  ```
- **Grep before committing anything** from a session that touched credentials:
  ```bash
  git diff | grep -nEi 'i[0-9]{5,}|api[_-]?key|secret|password|bearer |[:=]\s*gh[pous]_'
  git status --porcelain           # is the scratch harness still there?
  ```

Ask the user for credentials rather than hunting for them. Do not read `.env`, a keychain, a credential helper, or another project's config to find a key that was not offered — that is a different account than the one you were invited to use.

## The harness

Write it, run it, **delete it**.

Use a name that is recognisably scratch and ignored by the test runner's default include pattern, or explicitly ignored — `tests/__live.test.ts`, `scripts/__probe.py`. The `__` prefix marks it as not part of the suite. Add it to `.gitignore` if the repo does not already exclude it.

Drive **real production code**, not a hand-written client. The point is to exercise the adapter and the domain path a user would hit; a bespoke `fetch` call only tells you about the API, not about your handling of it.

```ts
import { describe, it } from 'vitest';
import { buildDashboardState } from '../src/application/dashboard-sync';

describe('live', () => {
  it('dumps derived state', async () => {
    const state = await buildDashboardState({ /* real http adapter */ });
    console.dir(state, { depth: null });
  }, 120_000);
});
```

Two mechanical traps:

- **Rewrite the dev-proxy base to the real host.** Where the base path is a relative proxy prefix outside production (`INTERVALS_BASE = '/intervals'`), a live run must point at the real origin or every request 404s in a way that looks like an API change.
- **Raise the timeout.** A real multi-endpoint fetch takes far longer than a unit test's default, and a timeout failure looks like a hang.

**Print the raw payload as well as the derived state.** The derived state tells you whether the code is right; the raw payload tells you why it is wrong. Dump the untouched response for at least one record of each kind, and read it rather than skimming it — the whole value of the exercise is in the field you were not expecting.

## Be a good citizen

You are hitting someone's real account on a shared service.

- **Rate-limit.** Use the project's existing limiter rather than bypassing it; per-item request bursts draw `429` and whatever was requested last silently disappears. If the probe fetches per-record detail, add a delay and a concurrency cap.
- **Read, do not write.** A probe must not create, update or delete anything in a real account without the user explicitly asking for a write test. If a write is genuinely necessary: confirm first, write something unmistakably marked as a test, and record how to identify and undo it.
- **Smallest window that answers the question.** Two weeks of data, not two years. Narrow the date range and the record count before widening.
- **Cache the response to a local file** during investigation so repeated analysis does not re-hit the API — and delete that file afterwards, because it contains real personal data.

## What survives the probe

Delete the harness, and any cached payload. Then keep only what is safe to keep:

**May be written down** — the *shape* of reality:

- Field names, types, nullability, ordering, envelope shape
- Units, precision, the range values actually occupy
- Status codes, error bodies, rate-limit behaviour, pagination mechanics
- Semantic surprises: a field that does not mean what it is called

**Must not be written down** — the *identity*:

- Real account ids, names, emails, dates of birth, locations
- Real measurements attributable to a person
- Captured payloads containing any of the above, in a fixture, an issue, a commit or a PR

Convert the finding into a synthetic fixture that reproduces the shape and invents the identity. See `synthetic-test-data`. Where the underlying specification was shared in confidence, implement it — do not reproduce it, and keep byte tables out of public issues.

Then run the `api-quirk-fixtures` loop: fixture trait, failing test, fix, documented row.

## Reporting honestly

Say what you ran it against and what you actually observed. Distinguish clearly:

- **Observed** — "the `/wellness` response for this account is oldest-first; the first element was dated 2026-01-14, 61 days before today."
- **Inferred** — "so `entries[0]` is reading a stale value."
- **Not checked** — "I did not verify whether that holds for an account with fewer than 30 rows."

One account is one data point. A behaviour seen once may be an account-specific configuration, a plan-tier difference, or a provider-side experiment. Say "confirmed against one live account" rather than "the API does X", and where it matters, check a second account or a second date range before hard-coding the assumption.

Never report a live verification you did not perform. "Not run — no credentials available" is an acceptable line; a fabricated green is not. See `gap-issue`.

## Checklist

- [ ] Credentials came from the user or the environment, never from hunting through config
- [ ] Nothing persisted a secret — no file, no fixture, no log line, no filename, no summary
- [ ] The harness drove real production code, and has been deleted
- [ ] Cached payloads deleted
- [ ] Rate limiter honoured; read-only; smallest useful window
- [ ] Raw payload read, not just the derived state
- [ ] Findings recorded as shape, with identity invented
- [ ] `git status` clean of scratch files; `git diff` grepped for secrets
- [ ] The finding became a fixture trait, a failing test, a fix and a documented row
- [ ] Report distinguishes observed from inferred, and says it was one account

## Related skills

- `api-quirk-fixtures` — the loop this feeds, and the quirk catalogue to check first
- `synthetic-test-data` — turning a real payload into a safe fixture
- `spec-by-example-issue` — grounding a specification in what the API really does
- `intervals-icu-api` — a worked example, including the auth scheme and rate-limit behaviour
- `gap-issue` — when a live check was not possible
