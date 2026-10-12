---
slug: VR-10
title: "Replay CLI for race recordings"
repo: virtualrow
labels:
  - tooling
  - size:L
  - priority:P3
milestone: null
blocks: []
blocked_by:
  - VR-09
parent: null
---

## Context

Race recordings exist but there's no tool to replay one
deterministically for debugging. Need a CLI that takes a recording
and renders it offline, driven by the same input stream the HUD sees.

## Scope

In scope: CLI replay from a recording file, deterministic output.
Out of scope: visual diffing between replays.

## Functional requirements

- CLI accepts a recording file path and renders it offline
- Replay is deterministic frame-for-frame

## Acceptance criteria (Gherkin)

```gherkin
Scenario: deterministic replay
  Given a recorded race
  When the CLI replays it twice
  Then both runs produce identical frame hashes
```

## TDD plan

- Acceptance test first on identical frame hashes
- Unit tests on the deterministic rng seeding
- Integration test on a canned recording
