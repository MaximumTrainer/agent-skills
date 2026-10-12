---
name: r3f-best-practices
description: React Three Fiber (R3F) and Poimandres ecosystem best practices. Use when writing, reviewing, or optimizing R3F code. Triggers on tasks involving @react-three/fiber, @react-three/drei, zustand, @react-three/postprocessing, @react-three/rapier, or leva.
license: MIT
metadata:
  author: three-agent-skills
  version: "2.0.0"
---

# React Three Fiber Best Practices

Measured note (fixture re-run, 2026-10): this skill measured +0% on all three of its evals. Without it the model already spots `setState` inside `useFrame` and moves the change to a ref, replaces whole-store zustand subscriptions with selectors and `getState()` in the frame loop, and toggles `visible` instead of remounting, with preloading for async assets. The old "Critical Patterns" section repeated exactly that, so it is gone.

What is left is a reference you open for a specific question, plus one version trap the model's own example got wrong.

## Version trap: zustand v5

A selector that returns a new object, such as `useStore(s => ({ x: s.x, y: s.y }))`, re-renders on every store change in v5 and can loop. Wrap it in `useShallow` from `zustand/react/shallow` (zustand 4.4+). Passing `shallow` as the hook's second argument is deprecated in 4.x and does nothing in v5 unless the store came from `createWithEqualityFn` in `zustand/traditional`. `store.subscribe(selector, listener)` needs the `subscribeWithSelector` middleware; a plain store takes one listener. Details in `references/rules/perf-zustand-selectors.md`.

## Rule files

Open the one that matches the question. These are the only rules vendored here; `references/rules/_sections.md` lists categories for more rules than exist, so do not cite a rule ID that has no file.

| Question | File |
|---|---|
| State changes inside the frame loop | `references/rules/perf-never-set-state-in-useframe.md` |
| Zustand selectors, `useShallow`, transient subscriptions | `references/rules/perf-zustand-selectors.md` |
| Show/hide without a stutter | `references/rules/perf-visibility-toggle.md` |
| Measuring draw calls and frame time | `references/rules/perf-r3f-perf.md` |
| Frame-rate independent motion | `references/rules/frame-delta-time.md` |
| Loading models with drei | `references/rules/drei-use-gltf.md` |
| Suspense boundaries and fallbacks | `references/rules/loading-suspense.md` |

For the Three.js objects underneath (disposal, instancing, pixel ratio, shaders, WebGPU), use `three-best-practices`.

## Related skills

- `three-best-practices` — the underlying Three.js rules these build on
- `screenshot-verify` — capturing a WebGL canvas, which needs its own frame wait

> Consolidated into this collection from the `virtualrow` project. Upstream tips from [100 Three.js Tips](https://www.utsubo.com/blog/threejs-best-practices-100-tips) by [Utsubo](https://www.utsubo.com); see the upstream attribution in `three-best-practices`.
