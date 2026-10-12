# VirtualRow mini review

Repo: virtualrow

## Gap: HUD input latency instrumentation

The HUD has no instrumentation for input-to-render latency. We can't
measure regressions or compare controller paths without a tracked
number per frame.

Tag: hud. Size: M. Priority: P2.

## Gap: tooling for replaying race recordings

Race recordings exist but there's no tool to replay one deterministically
for debugging. Need a CLI that takes a recording and renders it offline.

Tag: tooling. Size: L. Priority: P3.
