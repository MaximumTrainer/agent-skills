---
slug: VR-12
title: "Second of three"
repo: virtualrow
labels:
  - tooling
  - size:S
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

Second draft of three. The mock is configured to fail on this one in
the recovery case.

## Scope

In scope: being second.

## Functional requirements

- Files successfully on retry

## Acceptance criteria (Gherkin)

```gherkin
Scenario: files on retry
  Given a transient failure on first attempt
  When filer runs again
  Then this issue is created without duplicating VR-11
```

## TDD plan

- One acceptance test
