---
name: single-source-constants
description: Collapse a threshold that is written down twice - once in code, once in prose - into one definition everything else derives from, including the human-readable text. Use when a displayed value contradicts what the app does, when a user asks "why does it say X when it does Y", when a README restates a number the code owns, or when adding a band or tier. Covers the audit that finds existing drift and the one case where duplication is correct.
license: MIT
metadata:
  version: "2.0.0"
---

# Constant drift

A threshold written down twice will eventually disagree with itself. The duplicate is almost always in *prose* — a tooltip, a README row, an error message — so it is never type-checked, never tested, and drifts without a failing test. When it surfaces it looks like a calculation bug, so the investigation starts in the wrong place.

Measured note: an eval run without this skill diagnosed the drift, proposed a single band table, generated the tooltip from it and wrote boundary tests. Most of what follows is what a careful engineer does anyway. Three things were *not* produced unaided, and they are what this skill is now.

## 1. The evidence, so the diagnosis comes first

Both instances found in these projects were user-visible, and both were reported as broken calculations:

- A strength-zone tooltip and the README advertised the "Tired" band as **−10 to −20**. The code used **0 to −20**. An athlete at TSB −1.05 saw "Tired" beside a tooltip saying Fresh. Nothing was wrong with the scoring.
- An age-degradation constant lived correctly in one module and was imported by another — fine — but the same 0.7%/year curve was *also* restated in prose in three places.

So when a displayed value contradicts behaviour, **look for a second definition before reading the calculation.**

## 2. The presentation text belongs in the domain object

This is the move that does the real work, and the one usually missed. Putting `label`, `range`, `unit` and `guidance` *in the band definition* is what stops UI copy being retyped — and retyped copy is where drift starts.

```ts
export const STRENGTH_ZONE_BANDS: readonly StrengthZoneBand[] = [
  { zone: 'fresh', min: 0, max: Infinity, label: 'Fresh',
    range: '0 or above', focus: 'Max intent', guidance: '…' },
  …
];

// tooltip is generated, never typed
const TOOLTIP = STRENGTH_ZONE_BANDS
  .map(b => `${b.label} (TSB ${b.range}): ${b.focus}.`).join(' ');
```

And the README describes the *shape*, naming the constant rather than restating values:

> Readiness is banded by TSB. The bands, labels and guidance are defined in
> `STRENGTH_ZONE_BANDS` in `src/domain/sprint/core.ts`.

That sentence cannot drift. The one it replaced did.

## 3. The audit that finds existing drift

Search for the *number* everywhere, prose included — then take the intersection:

```bash
rg -n --no-ignore -- '-20|−20' -g '!node_modules' -g '!*.lock'
rg -nE '[0-9]+(\.[0-9]+)?\s*%' -g '*.md' -g '*.html' -g '*.vue' -g '*.tsx'
rg -ni 'threshold|limit|band|tier' -g '*.md' -g '*.html' | head -30
```

**Every number appearing in both a source file and a Markdown/HTML file is a drift candidate.** That intersection is usually short and almost always contains at least one real defect. For each, ask: does the code own this number? If so, the prose must point at it instead.

Copy and i18n files are where the duplicate most often hides — search them explicitly, not just source and docs.

## When duplication is correct

Two cases, and both need a comment saying which:

- **A wire-format or protocol constant** mirroring an external specification. It must *not* be derived from your domain value, because it is not yours — if the two diverge, that is information. Mirror it deliberately and add a test that fails when they disagree, so the divergence is announced rather than discovered. This is the pattern where a decoder in one language and a tool in another must agree: two definitions plus a vector test.
- **A test's expected value.** `getBand(-1.05).label === 'Tired'` should hard-code `'Tired'`. Deriving the expectation from the constant under test makes the test tautological. Assert the outcome against a literal; never re-implement the rule.

## Related skills

- `docs-drift-guard` — the documentation half of the same problem
- `hexagonal-architecture` — one place that reads configuration
- `deliberate-decisions` — for a value that looks wrong and is chosen
