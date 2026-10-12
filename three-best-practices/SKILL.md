---
name: three-best-practices
description: Three.js performance optimization and best practices guidelines. Use when writing, reviewing, or optimizing Three.js code. Triggers on tasks involving 3D scenes, WebGL/WebGPU rendering, geometries, materials, textures, lighting, shaders, or TSL.
license: MIT
metadata:
  author: three-agent-skills
  version: "3.0.0"
  three-version: "0.182.0+"
---

# Three.js Best Practices

Measured note (fixture re-run, 2026-10): this skill measured +0% on all three of its evals. Without it the model already explains that removing a mesh does not free GPU memory and disposes geometry, materials and textures on level unload, switches thousands of identical meshes to `InstancedMesh`, and caps the pixel ratio and uses `setAnimationLoop` with clock delta for phones. The old quick-reference and "Key Patterns" sections restated those defaults, so they are gone.

What is left is a reference you open for a specific, version-sensitive question. The rules target three r0.182+.

## Version traps

- WebGPU: import `WebGPURenderer` from `three/webgpu` and TSL from `three/tsl`, and `await renderer.init()` (or use `setAnimationLoop`) before the first render. It falls back to WebGL2 on its own. See `references/rules/webgpu-renderer.md`.
- Node materials: TSL assigns to slots such as `colorNode` on `MeshStandardNodeMaterial`, not to `onBeforeCompile` string patches. See `references/rules/tsl-material-slots.md`.
- Upgrades: check `references/rules/migration-checklist.md` before bumping three across a release; color management and lighting units changed under people who skipped it.

## Rule files

Open the one that matches the question. These are the only rules vendored here; `references/rules/_sections.md` lists categories for more rules than exist, so do not cite a rule ID that has no file.

| Question | File |
|---|---|
| Freeing GPU memory | `references/rules/memory-dispose-geometry.md` |
| Reusing objects instead of allocating per frame | `references/rules/object-pooling.md` |
| Frame-rate independent updates | `references/rules/render-delta-time.md` |
| Too many draw calls | `references/rules/draw-call-optimization.md`, `references/rules/geometry-instanced-mesh.md` |
| Model size and load time | `references/rules/gltf-loading-optimization.md`, `references/rules/asset-compression.md` |
| LCP, CLS and first frame | `references/rules/core-web-vitals.md` |
| Phones and low-end GPUs | `references/rules/mobile-optimization.md`, `references/rules/shader-mobile.md` |
| Shadows and light cost | `references/rules/lighting-shadows-advanced.md` |
| Post-processing cost | `references/rules/postprocessing-optimization.md`, `references/rules/tsl-post-processing.md` |
| Picking and raycasts | `references/rules/raycasting-optimization.md` |
| TSL: why, slots, compute, full API | `references/rules/tsl-why-use.md`, `references/rules/tsl-material-slots.md`, `references/rules/tsl-compute-shaders.md`, `references/rules/tsl-complete-reference.md` |
| WebGPU renderer | `references/rules/webgpu-renderer.md` |
| Import maps without a bundler | `references/rules/setup-use-import-maps.md` |
| Animation mixer and clips | `references/rules/animation-system.md` |
| Physics engines | `references/rules/physics-integration.md` |
| WebXR | `references/rules/webxr-setup.md` |
| Positional audio | `references/rules/audio-spatial.md` |
| Context loss and recovery | `references/rules/error-handling-recovery.md` |
| Version upgrades | `references/rules/migration-checklist.md` |
| Inspecting a running scene | `references/rules/debug-devtools.md` |

## Related skills

- `r3f-best-practices` — the React Three Fiber layer on top of these rules
- `screenshot-verify` — capturing a WebGL canvas, which needs its own frame wait

## Sources & Credits

> Compiled from the official guidelines on the Three.js `llms` branch maintained by [mrdoob](https://github.com/mrdoob) and [100 Three.js Tips](https://www.utsubo.com/blog/threejs-best-practices-100-tips) by [Utsubo](https://www.utsubo.com). Consolidated into this collection from the `virtualrow` project.
