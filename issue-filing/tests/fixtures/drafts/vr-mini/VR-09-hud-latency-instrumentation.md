---
slug: VR-09
title: "HUD input latency instrumentation"
repo: virtualrow
labels:
  - hud
  - size:M
  - priority:P2
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

The HUD has no instrumentation for input-to-render latency. We can't
measure regressions or compare controller paths without a tracked
number per frame.

## Scope

In scope: HUD latency per frame as a tracked metric.
Out of scope: physics-step latency, networking latency.

## Functional requirements

- Latency per frame is measured from input event to render completion
- Metric is tracked and exposed to the dev HUD overlay

## Acceptance criteria (Gherkin)

```gherkin
Scenario: input latency is observable
  Given the HUD is running in dev mode
  When an input event occurs
  Then the dev overlay shows the latency in ms within one frame
```

## TDD plan

- Acceptance test first for the overlay number
- Unit tests on the latency sampler
- Integration test exercising a controller through to render
