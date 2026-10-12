---
slug: VR-13
title: "Third of three"
repo: virtualrow
labels:
  - camera
  - size:S
milestone: null
blocks: []
blocked_by:
  - VR-12
parent: null
---

## Context

Third draft of three. Depends on VR-12 so dependency ordering is also
exercised.

## Scope

In scope: being third.

## Functional requirements

- Files after VR-12 lands
- Carries a cross-ref line pointing at VR-12's issue number

## Acceptance criteria (Gherkin)

```gherkin
Scenario: cross-ref follows filing
  Given VR-12 is filed with number N
  When filer runs
  Then this issue's body contains "Blocked by: #N"
```

## TDD plan

- Transformation test on the edited body
