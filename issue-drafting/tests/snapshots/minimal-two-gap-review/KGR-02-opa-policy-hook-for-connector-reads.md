---
slug: KGR-02
title: "OPA policy hook for connector reads"
repo: sdlc-knowledge-graph
labels:
  - area:security
  - size:M
  - type:feature
  - tdd:acceptance-first
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

Connector reads aren't guarded by OPA policy. Need a hook that
evaluates each read request against a policy bundle, with the bundle
reference pinned per-connector and a decision log emitted for audit.

## Scope

In scope: addressing the gap stated above. Out of scope: adjacent concerns not called out in the review.

## Functional requirements

- Connector reads aren't guarded by OPA policy
- Need a hook that evaluates each read request against a policy bundle, with the bundle reference pinned per-connector and a decision log emitted for audit


## Acceptance criteria (Gherkin)

```gherkin
Scenario: OPA policy hook for connector reads
  Given the system is in its current state
  When the change implied by "OPA policy hook for connector reads" is applied
  Then the behaviour described in the Context is observable
```

## TDD plan

- Acceptance test first, driven by the Gherkin above.
- Unit tests follow, one per functional requirement.
- Integration test last, exercising the end-to-end path.
