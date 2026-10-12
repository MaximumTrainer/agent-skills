---
name: issue-drafting
description: Turn a review of a repository — agent-systems audit, white-paper follow-ups, Fable backlog, plan.md elaboration — into a folder of draft GitHub issues in the Context/Scope/FRs/Gherkin/TDD convention, one file per gap, labelled against the target repo's known scheme and with size:XL candidates pre-split into independently shippable walking-skeleton slices before they ship. Use when a review has already surfaced many gaps and the next step is turning each into an issue, when picking up a long tail of untyped findings, when translating an ADR or plan.md row into trackable issues, or when "write up these gaps" would otherwise mean an evening of pasting. One-at-a-time elaboration of a single thin issue is `spec-by-example-issue`'s job, not this one; this is batch mode. Covers the five-section contract, per-repo label profiles vendored as the single source of truth, slug persistence across review reordering, and the walking-skeleton heuristic that keeps XL work from being filed as one deathstar issue.
license: MIT
metadata:
  version: "1.0.0"
---

# Draft issues in batches, keep slugs stable, split XL before filing

A review of a codebase or an initiative produces more than one gap at a
time: ten issues for a KG + Chorus joint review, eleven for a
white-paper follow-up, twenty-six for a Fable-driven game review. Each
one of those is in principle a `spec-by-example-issue` job, but doing
twenty-six of them end to end one-by-one is where most backlogs
quietly die.

This skill is the batch pass. It turns a review markdown file into one
draft per gap, each with the five sections the convention requires,
labelled against the target repo's known scheme, with stable slugs so
reruns don't renumber already-filed issues. The drafts come out as a
folder; `issue-filing` sends them to GitHub.

The output is scaffolds. A human (or a stronger model) tightens the FR
list and Gherkin before anything is filed. The point of the skill is
to make the first-pass structuring free.

## When to use it

- A review has already produced ≥5 named gaps and the next step is
  turning each into an issue.
- A long tail of findings needs catching up (VR-09..VR-26 shape).
- An ADR or plan.md row names several concrete gaps that should each
  be trackable issues.
- An agent is asked to "file these as issues" against a review doc.

If the input is one thin issue — a single placeholder with no body —
use `spec-by-example-issue` instead. The probe-first discipline there
is more valuable than the mechanical scaffolding here.

## The convention

Every draft carries YAML frontmatter — slug, title, repo, labels,
milestone, blocks/blocked_by, parent — and five body sections:

1. **Context** — current state and why that's a gap.
2. **Scope** — in bounds, explicitly out of bounds.
3. **Functional requirements** — observable behaviour that must land.
4. **Acceptance criteria (Gherkin)** — executable Given/When/Then.
5. **TDD plan** — acceptance test first, unit tests per FR,
   integration test last.

The exact rendered form is pinned in `tests/snapshots/`. The
human-readable version of the same contract lives in
`references/convention.md`.

## Review input format

Each gap in the review is a top-level `## Gap: <title>` section. Within it:

- Prose body — becomes the Context section.
- A hint line like `Area: ontology. Size: M. Type: feature.` on its
  own line. Keys the convention knows about: `area`, `size`, `type`,
  `priority`, `module`, `tag`.
- For `Size: XL` only — a `### Slices` subsection with bullets of the
  form `- KEY: title (Size: M)`. The parser recognises this and the
  renderer emits one parent plus one child per slice, each carrying
  `parent: <parent-slug>`. See `references/xl-slicing.md`.

Fixture examples live in `assets/fixtures/reviews/`.

## Repo profiles

`references/repo-profiles.yaml` is the single source of truth for
which labels a repo accepts. Adding a repo is one entry; correcting a
scheme is one edit. The file is vendored into every consuming repo via
`skill-exchange` so the schemes can't drift.

Known profiles ship with: `sdlc-knowledge-graph` (area:/size:/tdd:/
type: namespaces), `virtualrow` (flat labels), `chorus` (module:/size:/
type:).

## Running it

```
python3 scripts/issue_drafting/cli.py \
    --review   assets/fixtures/reviews/mini-kg-review.md \
    --profile  sdlc-knowledge-graph \
    --slug-prefix KG \
    --out      drafts/ \
    --slugs    drafts/.slugs.json
```

Exit codes: 0 success, 2 unknown profile / bad arguments / unknown
label at render time.

## How the scaffolder earns its five sections

- **Context** ← the gap body, unchanged.
- **Scope** ← a boilerplate "in scope / out of scope" the author
  edits first; a tight Scope prevents the issue from drifting in
  implementation.
- **Functional requirements** ← one bullet per sentence in the body,
  as a starting point. Collapse, lift verbs, cut.
- **Gherkin** ← one Scenario per gap. Rewrite as a test can execute.
- **TDD plan** ← the three-tier default.

The eval suite doesn't grade quality; it grades that the five
sections exist and the labels resolve. Quality is the author's job.

## Slug stability

Positional by default (`{prefix}-01`, `{prefix}-02` in review order).
With `--slugs <path>`, the mapping persists across runs keyed by the
title's hash. Reorder the review, add a gap, remove a gap — existing
titles keep their slugs; new titles get the next free number.

This matters because a slug is often what gets filed as the GitHub
issue number comment, cross-referenced from an ADR, or cited in a
plan.md row. Drifting slugs break those links silently.

## Pre-splitting XL

Any gap tagged `Size: XL` must carry a `### Slices` subsection naming
≥1 independently shippable children. The parent captures the full
scope; each child is a walking-skeleton slice sized S/M/L. Each
child's acceptance criteria must stand alone — no child's Gherkin
depends on a sibling.

Worked example in `references/xl-slicing.md`: AUTH on the KG, split
into AUTH-1..5. The convention is: whenever you'd file an XL, you've
already lost; split first, file second.

## Changing the convention

The snapshot in `tests/snapshots/minimal-two-gap-review/` is the
rendered form of the convention. To change it:

1. Edit the template or renderer under `scripts/issue_drafting/`.
2. Run `python3 tests/run.py` — the snapshot case fails with a diff.
3. Hand-review the diff.
4. Promote: `PROMOTE=1 python3 tests/run.py minimal-two-gap-review`.
5. Update `references/convention.md` to match.

If the diff isn't what you intended, you've found a regression, not a
convention change.

## Composition with issue-filing

The output folder of this skill is the input folder of `issue-filing`.
The contract between them is the draft file: YAML frontmatter plus
the five sections. Hand-written drafts to that contract file as
cleanly as scaffolded ones.
