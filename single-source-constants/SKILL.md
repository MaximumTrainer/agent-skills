---
name: single-source-constants
description: Find thresholds, bands and limits duplicated between domain logic, UI copy, tests and documentation, and collapse them to one definition everything else derives from. Use when a displayed value contradicts what the app does, when adding a threshold or configuration value, when a user asks "why does it say X when it does Y", when a README restates a number the code owns, and when reviewing a change that hard-codes a boundary. Two user-visible bugs in these projects were caused by exactly this and both looked like calculation bugs.
license: MIT
metadata:
  version: "1.0.0"
---

# Constant drift

A threshold written down twice is a threshold that will eventually disagree with itself.

The reason this matters more than it sounds: the duplicate is almost always in *prose* — a tooltip, a README table, an error message — so it is never type-checked, never tested, and drifts without a single failing test. And when it surfaces, it surfaces as a bug report about the calculation, so the investigation starts in the wrong place.

Both instances found in these projects were user-visible, and both looked like calculation bugs when they were documentation bugs:

- A strength-zone tooltip and the README both advertised the "Tired" band as **−10 to −20**. The code used **0 to −20**. An athlete at TSB −1.05 saw "Tired" beside a tooltip saying they should be Fresh, and reported it as broken scoring. Nothing was wrong with the scoring.
- An age-degradation constant lived correctly in one module and was imported by another — fine — but the same 0.7%-per-year curve was *also* restated in prose in three places, each of which could drift independently.

## The pattern

**One definition in the domain; everything else derived from it.**

The move that does the real work is putting the **human-readable text in the domain object too**. That is what stops UI copy being retyped, and retyped copy is where drift starts.

```ts
// src/domain/sprint/core.ts — the only place these numbers exist
export const STRENGTH_ZONE_BANDS: readonly StrengthZoneBand[] = [
  { zone: 'fresh',  min: 0,        max: Infinity, label: 'Fresh',
    range: '0 or above', focus: 'Max intent',   guidance: '…' },
  { zone: 'tired',  min: -20,      max: 0,        label: 'Tired',
    range: '0 to −20',   focus: 'Maintain',     guidance: '…' },
  { zone: 'buried', min: -Infinity, max: -20,     label: 'Buried',
    range: 'below −20',  focus: 'Recover',      guidance: '…' },
];

export function getStrengthZoneBand(tsb: number): StrengthZoneBand { … }
```

Then every consumer derives:

- **The domain rule** calls `getStrengthZoneBand(tsb)` rather than re-testing the numbers.
- **The UI scale** renders `label` and `range` from the same array, so adding a band changes the display with no further edit.
- **Tooltip and help copy is generated, not typed:**

```ts
const STRENGTH_ZONE_TOOLTIP = [
  'Your readiness band, from training stress balance.',
  ...STRENGTH_ZONE_BANDS.map(b => `${b.label} (TSB ${b.range}): ${b.focus}.`),
].join(' ');
```

- **The tests** iterate the array and assert the bands are contiguous and non-overlapping, rather than restating each boundary.
- **The README** describes the *shape* and points at the constant, rather than restating the numbers:

  > Readiness is banded by TSB. The bands, their labels and their guidance are defined in `STRENGTH_ZONE_BANDS` in `src/domain/sprint/core.ts`.

That README sentence cannot drift. The one it replaced did.

## Design rules

- **Define bands as data, not as a chain of `if`s.** An `if/else if` ladder over thresholds cannot be enumerated, rendered, or checked for gaps. An array can.
- **Include the presentation text in the definition** — `label`, `range`, `unit`, `guidance`. If the UI needs a word for a band, the domain object owns that word.
- **Half-open intervals, stated once.** Decide `[min, max)` and apply it everywhere. Most boundary bugs are an inconsistent inclusive/exclusive edge, and a shared `contains()` on the band fixes them all at once.
- **Derive dependent constants; never restate them.** If a display threshold is "half the alert threshold", compute it. A second literal that happens to be half is a literal that will stop being half.
- **Units in the name or the type.** `timeoutMs`, `distanceM`, `Duration`. A bare `300` will be read as seconds by the next person.
- **Configuration values follow the same rule**: one config object, read from the environment in exactly one place, documented in `.env.example` and the README's table — where the table is generated from the config object if the project can manage it. See `hexagonal-architecture`.

## Finding existing drift

Numeric literals and the words around them are both worth grepping. Search for the *number*, everywhere, including prose:

```bash
# a threshold you already know about — search all file types, docs included
rg -n --no-ignore -- '-20|−20' -g '!node_modules' -g '!*.lock'

# suspicious bare numeric literals in comparisons
rg -nE '[<>]=?\s*-?[0-9]+(\.[0-9]+)?' --type ts --type kt --type cs -g '!*test*' | head -40

# the same threshold word in code and in docs
rg -ni 'tired|buried|threshold|limit|max_|_max' -g '*.md' -g '*.html' | head -30

# percentages and rates restated in prose
rg -nE '[0-9]+(\.[0-9]+)?\s*%' -g '*.md' -g '*.html' -g '*.vue' -g '*.tsx'
```

Then for each literal found in prose, ask: **does the code own this number?** If yes, the prose must point at it instead.

A high-value sweep: every number that appears in both a source file and a Markdown/HTML file is a drift candidate. That intersection is usually short and almost always contains at least one real defect.

## Add the check

Once collapsed, keep it collapsed:

1. **Contiguity test** — assert the bands cover the domain with no gap and no overlap, and that the boundary values land in the band you expect. This catches the edit that changes one edge and forgets its neighbour.
2. **Generated-copy test** — assert the tooltip/help string contains each band's label and range, so a band added without copy fails.
3. **Docs drift check** — where a doc must contain a value, generate that section from the constant. See `docs-drift-guard`.
4. **A lint rule against magic numbers** in the domain layer, with an allowlist for 0 and 1.

The contiguity test is the cheapest and catches the most. Write it first.

## When duplication is legitimate

Two cases, and both need a comment saying which one it is:

- **A wire-format or protocol constant** that mirrors an external specification. It must not be derived from your domain value, because it is not yours — if they diverge, that is information. Mirror it deliberately, and add a test that fails when the two disagree, so the divergence is announced rather than discovered. This is the pattern used where a decoder in one language and a tool in another must agree: two definitions, plus a vector test that fails the moment they drift apart.
- **A test's expected value.** A test that asserts `getBand(-1.05).label === 'Tired'` should hard-code `'Tired'` — deriving the expectation from the constant under test makes the test tautological. Assert the *outcome* against a literal; never re-implement the *rule*.

## Checklist

- [ ] Each threshold, band and limit has exactly one definition, in the domain
- [ ] Bands are data with a boundary helper, not an `if` ladder
- [ ] Presentation text (`label`, `range`, `unit`, guidance) lives in the definition
- [ ] UI copy and tooltips are generated from it, not typed
- [ ] Documentation describes the shape and names the constant, rather than restating values
- [ ] Dependent constants are computed, not restated
- [ ] Units are in the name or the type
- [ ] A contiguity/boundary test exists, and a generated-copy test where copy is derived
- [ ] Any legitimate duplicate is commented as such and has a test asserting the two agree

## Related skills

- `docs-drift-guard` — stopping the documentation half of this from drifting
- `hexagonal-architecture` — one composition root, one place that reads configuration
- `spec-by-example-issue` — writing boundary examples at each edge of a band
- `api-quirk-fixtures` — exporting fixture constants so tests cannot assert coincidences
- `deliberate-decisions` — for a value that looks wrong and is chosen
