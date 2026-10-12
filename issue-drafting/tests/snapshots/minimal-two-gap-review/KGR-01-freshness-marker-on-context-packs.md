---
slug: KGR-01
title: "freshness marker on context packs"
repo: sdlc-knowledge-graph
labels:
  - area:ontology
  - size:M
  - type:feature
  - tdd:acceptance-first
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

Context packs don't carry an as-of timestamp, so an agent reading one
can't tell whether a fact is current or stale. Agents need a published
freshness marker on every pack, and a query API that lets a caller
reject packs older than a specified bound.

## Scope

In scope: addressing the gap stated above. Out of scope: adjacent concerns not called out in the review.

## Functional requirements

- Context packs don't carry an as-of timestamp, so an agent reading one can't tell whether a fact is current or stale
- Agents need a published freshness marker on every pack, and a query API that lets a caller reject packs older than a specified bound


## Acceptance criteria (Gherkin)

```gherkin
Scenario: freshness marker on context packs
  Given the system is in its current state
  When the change implied by "freshness marker on context packs" is applied
  Then the behaviour described in the Context is observable
```

## TDD plan

- Acceptance test first, driven by the Gherkin above.
- Unit tests follow, one per functional requirement.
- Integration test last, exercising the end-to-end path.
