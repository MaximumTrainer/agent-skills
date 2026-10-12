---
name: issue-filing
description: Take a folder of drafted GitHub issues — written by `issue-drafting`, or hand-authored to the same five-section contract — and file them to a repo via the `gh` CLI with the right labels, in dependency order, cross-referenced, and idempotent across reruns. Use when a drafted backlog needs to land in a repo (the "evening of clicking through the GitHub UI" problem), when a long tail of unfiled drafts needs catching up (VR-09..VR-26 shape), when re-filing a batch after a label-scheme change on the target repo, or when any batch of issues needs filing without hand-work per issue. Covers preflight label validation that fails before any issue is created, topological ordering by `blocked_by`, write-back of issue numbers into draft frontmatter so a mid-run gh failure is safely resumable, and a second-pass cross-ref rewrite that adds `Blocks: #N` / `Blocked by: #N` lines once every slug has a number.
license: MIT
metadata:
  version: "1.0.0"
---

# File a drafted backlog without the evening of clicking

A reviewed codebase or an elaborated plan produces a folder of issue
drafts — each a markdown file with YAML frontmatter and the five
sections. The next step is routinely done by hand: open each file,
click "new issue", paste, select labels, submit, note down the issue
number, open the next one. For a backlog of 26 issues it's an
evening. For a backlog of 11 it's still an evening, because the
state-shuffling cost per issue is the limiting factor, not the typing.

This skill is the one-command pass. It takes a folder of drafts and
fills a repo, in the right order, with the right labels, with
cross-refs resolved. If something goes wrong mid-way, a rerun picks up
where it left off.

The companion authoring skill is `issue-drafting`. Its output folder
is this skill's input folder. The contract between them is the draft
file.

## When to use it

- A drafted backlog needs to land in a repo.
- A long tail of unfiled drafts needs catching up.
- Re-filing after a label-scheme change in the target repo.
- Any batch of drafts, hand-written or generated, that fits the
  five-section contract.

If the user wants to file one issue, `gh issue create` from a template
is cheaper. This skill earns its keep from the fourth issue upward.

## What the filer does

In one invocation:

1. **Preflight.** Checks `gh auth status`; fetches the live labels on
   the target repo; rejects any draft carrying a label the repo
   doesn't define. Exits 2 before any issue is created.
2. **Topological sort.** Orders drafts so a draft listed in another's
   `blocked_by` is filed first.
3. **File.** `gh issue create` per draft, with every label and the
   milestone from the frontmatter. On each success, writes
   `issue: N` into the draft's frontmatter so a rerun skips it.
4. **Cross-refs.** Reloads the drafts (now all carrying issue numbers)
   and runs a second pass of `gh issue edit` to append `Blocks: #N`
   and `Blocked by: #N` lines to each body.

## Running it

```
python3 scripts/issue_filing/cli.py \
    --drafts drafts/ \
    --repo MaximumTrainer/virtualrow
```

Exit codes: 0 success; 2 bad args, auth failure, label mismatch;
3 gh failure mid-run (safe to re-run — successful creates were
written back).

## Guarantees

- **Fail-fast on label mismatch** — zero `gh issue create` calls
  before the preflight gate.
- **Order** — a draft that depends on another is never filed first.
- **Idempotent** — a rerun on a folder whose drafts already carry
  `issue:` numbers makes zero create calls.
- **Recoverable** — a mid-run gh failure leaves successful creates
  written back; a rerun completes the rest without duplicating.
- **Cross-refs** — once every slug has a number, `Blocks` / `Blocked
  by` lines are added to the live issue bodies in a single edit per
  dependent draft.

Each of these is pinned by a test case in `tests/suite.yaml` running
against a mock `gh` on PATH.

## The draft contract

A draft is a markdown file with YAML frontmatter:

```yaml
---
slug: VR-10
title: "Replay CLI for race recordings"
repo: virtualrow
labels: [tooling, size:L, priority:P3]
milestone: null
blocks: []
blocked_by: [VR-09]
parent: null
---

## Context
...
## Scope
...
## Functional requirements
...
## Acceptance criteria (Gherkin)
...
## TDD plan
...
```

Post-filing, the frontmatter gains `issue: N`. Idempotence lives on
that line.

## Preflight: label validation

The filer calls `gh label list --repo <repo>` and compares each
draft's labels. Any label a draft carries that the repo doesn't have
causes `LabelMismatch` with the full list of offending `<slug>:
<label>` pairs on stderr. Nothing is filed.

Common fixes in `references/label-sync.md`. The short version:
`gh label create` on the repo, then re-run — the filer doesn't
auto-create labels because labels encode decisions and a typo
shouldn't propagate.

## Dependency order

The filer builds a topological sort over `blocked_by`. If VR-10
depends on VR-09, VR-09 is filed first so its issue number is
available for the cross-ref rewrite. Cycles raise `CycleError`
naming the slug involved — treated as an authoring error, not
resolved.

Edits always follow creates — never interleaved. That lets the
cross-ref pass see every issue number before writing any ref.

## Idempotence by write-back

On each successful `gh issue create`, the filer writes `issue: N`
into the draft's frontmatter in-place. A rerun loads the drafts, sees
every one carries an `issue:` line, and skips the create loop
entirely.

That's also how recovery works: a mid-run gh failure leaves the
drafts that succeeded carrying their numbers; a rerun completes the
rest.

## gh CLI auth

The filer uses `gh issue create` and `gh issue edit` — scopes needed
are `repo` (private + public) or `public_repo` for public-only. See
`references/gh-auth.md`.

## Testing

Six behavioural cases in `tests/suite.yaml`, each running the real
filer against a mock `gh` on PATH (`tests/fixtures/mock_gh/gh`):

- `dry-run-vr-mini` — exact call sequence snapshot.
- `dependency-ordering` — a `blocked_by` edge drives create order.
- `idempotence` — rerun makes zero creates.
- `label-mismatch-fails-fast` — unknown label blocks every create.
- `partial-failure-recovery` — a mock-injected failure on the 2nd of
  3 creates is recovered by the second run.
- `cross-ref-rewriting` — the body passed to `gh issue edit` contains
  the resolved `Blocked by: #N` line.

Run with `python3 tests/run.py`. The mock-shim boundary is the whole
`gh` CLI — the filer's production code path and the eval path are the
same code path.

## Composition with issue-drafting

`issue-drafting`'s output folder is this skill's input. The contract
between them is the draft file: five sections plus the frontmatter.
Hand-written drafts to that contract file as cleanly as generated
ones.
