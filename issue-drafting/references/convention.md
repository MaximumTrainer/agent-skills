# The issue convention

The convention this skill produces, in English. The snapshots in
`snapshots/` are the canonical rendered form; this document explains
what each section is for and how to tighten a scaffold before filing.

## Why five sections

Every issue a reviewer picks up — human or model — needs to answer the
same four questions before any code gets written:

- **Context** — what is the current state, and why is that a gap?
- **Scope** — what is in bounds, and what is explicitly out?
- **Functional requirements** — what observable behaviour must land?
- **Acceptance criteria (Gherkin)** — how will we know it did?
- **TDD plan** — how do we drive it with tests, starting from the Gherkin?

Any issue missing one of these forces the next reader to recover it
from context the author no longer has. The convention makes that
recovery unnecessary.

## What the scaffolder gives you

The generator produces each section mechanically from the review:

- Context ← the gap body, unchanged.
- Scope ← boilerplate "in scope: addressing this gap; out of scope:
  adjacent concerns not called out". Edit this first — a tight Scope
  prevents the issue from drifting during implementation.
- Functional requirements ← one bullet per sentence in the body. This
  is a starting point; collapse duplicates, lift verbs to the front,
  cut the ones that are really Scope.
- Gherkin ← one Scenario per gap, with the title repeated. Rewrite as
  Given/When/Then that a test can execute.
- TDD plan ← acceptance test first, unit tests per FR, integration
  test last. Keep or tighten.

The eval doesn't grade quality; it grades that the five sections exist
and the labels resolve. Quality is the author's job.

## Labels

Resolved from hints in the review line against the repo's profile. The
profile is the source of truth. If a label doesn't resolve, the CLI
exits 2 with a message listing the profile's known labels for that
namespace. Don't add a label by hand to the draft frontmatter — add it
to the profile and re-run.

## Pre-splitting XL

Any gap tagged `Size: XL` must carry a `### Slices` subsection naming
≥1 independently shippable children. The parent captures the full
scope; each child is a walking-skeleton slice sized S / M / L. Each
child's acceptance criteria must stand alone — no child's Gherkin
depends on a sibling.

Worked example: AUTH #94 in the SDLC Knowledge Graph was split into
AUTH-1..5 (`references/xl-slicing.md`, `fixtures/reviews/auth-xl.md`).
The convention is: whenever you'd file an XL, you've already lost;
split first, file second.

## Slugs

Positional by default — `{prefix}-01`, `{prefix}-02`, in review order.
With `--slugs <path>`, the mapping persists across runs keyed by the
title's hash. Reorder the review, add a gap, remove a gap — existing
titles keep their slugs; new titles get the next free number.

This matters because a slug is often what gets filed as the GitHub
issue number comment, cross-referenced from an ADR, or cited in a
plan.md row. Drifting slugs break those links silently.

## Changing the convention

The snapshot in `snapshots/minimal-two-gap-review/` is the rendered
form of the convention. To change it:

1. Edit the template or renderer.
2. Run `python evals/run.py` — the snapshot case will fail with a diff.
3. Hand-review the diff. Is this the convention change you intended?
4. Promote: `PROMOTE=1 python evals/run.py minimal-two-gap-review`.
5. Update this document to match.

If the diff isn't what you intended, you've found a regression, not a
convention change.
