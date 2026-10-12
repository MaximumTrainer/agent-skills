---
slug: VR-99
title: "A draft carrying a label VR doesn't have"
repo: virtualrow
labels:
  - module:connectors
  - size:M
milestone: null
blocks: []
blocked_by: []
parent: null
---

## Context

This draft uses a Chorus-style `module:connectors` label against the
VirtualRow repo, which uses a flat label scheme. The preflight must
reject it before any `gh issue create` is attempted.

## Scope

In scope: proving the preflight guard.

## Functional requirements

- Preflight fails before any create call

## Acceptance criteria (Gherkin)

```gherkin
Scenario: preflight rejects unknown labels
  Given a draft carrying a label not in the repo
  When the filer runs
  Then no issue is created
```

## TDD plan

- Preflight test with a known-bad label fixture
