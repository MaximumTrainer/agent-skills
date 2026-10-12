# Changelog

All notable changes to the `issue-filing` skill.

## 1.0.0 - 2026-10-12

Initial version. Six eval cases pinning dry-run call sequence, dependency
ordering, idempotent reruns via `issue:` write-back, label-mismatch
preflight, partial-failure recovery, and cross-ref rewriting. Runs against
the real `gh` CLI; eval suite shims gh via PATH.
