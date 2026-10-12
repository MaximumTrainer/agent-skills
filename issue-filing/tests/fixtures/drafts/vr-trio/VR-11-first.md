---
slug: VR-11
title: "First of three"
repo: virtualrow
labels:
  - hud
  - size:S
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

First draft of a three-draft fixture used to test partial-failure recovery.

## Scope

In scope: being first.

## Functional requirements

- Files successfully

## Acceptance criteria (Gherkin)

```gherkin
Scenario: files
  Given no state
  When filer runs
  Then this issue is created first
```

## TDD plan

- One acceptance test
