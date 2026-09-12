---
name: mcp-server-tools
description: Design and build MCP (Model Context Protocol) server tools that an LLM can actually use well — tool granularity, schemas that prevent wrong calls, structured errors the model can recover from, and returning what the model can read rather than what is easy to serialise. Use when writing or adding a tool to an MCP server, designing the tool surface for one, debugging a model that misuses a tool, deciding between stdio and HTTP transport, or sandboxing model-authored code execution.
license: MIT
metadata:
  version: "1.0.0"
---

# Building MCP server tools

An MCP server's quality is decided almost entirely by its **tool surface**: how many tools there are, what they are named, what their schemas permit, and what they return. The implementation behind a tool is ordinary software; the interface is the hard part, because its consumer is a model that cannot ask a clarifying question mid-call and cannot read your source.

The single most useful reframing:

> A tool result is a **prompt fragment**. It is going straight into the model's context to be reasoned over. Design it for a reader, not for a parser.

## Design the tool surface first

Write out the loop the model will actually run before implementing anything. For a text-to-3D server, that loop is:

```
describe → model writes CadQuery code → execute_cad → render_views returns PNGs
  → model critiques its own render → revise → validate_mesh → export_model
```

That loop *is* the product. Once written down, it tells you what the tools are, what each must return for the next step to be possible, and what would constitute a regression. Here, the visual feedback loop is the whole value — so anything that makes renders slower than a couple of seconds, or breaks image return, is a regression regardless of what else it improves.

Then apply these:

- **One tool per meaningful action**, named as a verb the model would reach for. `execute_cad`, `render_views`, `validate_mesh`, `export_model`.
- **Do not expose your internal API one-to-one.** Twelve CRUD tools where the model needs one workflow tool is a surface that invites wrong sequences.
- **Do not build one mega-tool with a `mode` parameter** either. The model chooses tools by description; a mode enum hides the choice inside an argument where the descriptions cannot help it.
- **Ten to twenty tools is comfortable.** Beyond that, selection accuracy falls and the token cost of the definitions becomes real. Prefer fewer, richer tools; consider splitting into multiple servers by domain.
- **Make the common path one call.** If every use starts with three calls in a fixed order, that is one tool.

## Schemas that prevent wrong calls

The schema is the only documentation the model reliably reads. Every constraint you express is a class of failed call you never have to handle.

- **Enums over free strings.** `format: "stl" | "step" | "glb" | "3mf"` cannot be called with `"STL "`.
- **Describe every field**, including the obvious ones. Say the unit, the coordinate convention, the expected range, and what happens at the default.
- **Mark required fields required.** An optional field the model must pass is a silent failure mode.
- **Bound numbers** with `minimum`/`maximum`. The model respects them, and you get to delete a validation branch.
- **Use `additionalProperties: false`** so a hallucinated field is an immediate, legible error rather than a silently ignored intent.
- **Prefer a flat schema.** Deeply nested objects are where malformed calls come from; two levels is a reasonable ceiling.
- **Name ids for what they identify** — `part_id`, not `id` — and say where one comes from ("from a prior `execute_cad` result").

Write the tool description for someone who has never seen the system: what it does, when to use it, when *not* to, and what it returns. Include the precondition. "Requires a part created by `execute_cad` in this session" saves a whole failed call.

## Return what the model can read

This is where most MCP servers waste their context budget and their usefulness.

- **Never return a blob the model cannot interpret.** Meshes, geometry, binary payloads, base64 of a non-image — the model cannot read any of it, and it consumes the context that the actual answer needed. Return **images and measurements** instead.
- **Images come back as image content blocks**, not as a path or a base64 string in text. Cap the dimensions (800×600 is plenty for critique), and compose multiple views into one grid image rather than returning six separate ones.
- **Return measurements, not just pictures.** Bounding box, volume, wall thickness, watertightness, face count. The model can reason over a number; it can only impressionistically judge an image.
- **Summarise, do not dump.** A 4,000-row query result should come back as counts, aggregates and the first few rows, with a way to page. Say explicitly that it was truncated and how to get more — silent truncation makes the model confidently wrong.
- **Include what changed** after a mutation, so the model does not need a follow-up read.
- **Persistent artefacts get a stable reference**, not their contents: a part id, a session key, a URL.

## Errors the model can act on

An error is a prompt too. Its job is to make the model's *next* attempt succeed.

```
Structured, actionable:
  CadQueryError at line 7: Workplane has no pending wires.
    offending code:  .extrude(10)
    likely cause:    extrude() called before a closed profile was created
    suggestion:      add .rect(w, h) or .circle(r) before .extrude()

Useless:
  Traceback (most recent call last): ... 40 lines ... TypeError
```

Rules:

- **Return the exception type, the line number and the offending snippet.** Never a bare traceback, and never a silent failure.
- **Never fail silently, and never return a plausible empty result** instead of an error. An empty array where an error belongs is the worst possible outcome: the model treats it as a fact.
- **Distinguish "invalid input, fix and retry" from "not possible, do something else."** The model's recovery differs, and it cannot tell them apart from a generic message.
- **Errors are tool results, not protocol errors** (`isError: true`), so the model sees them and can respond. A transport-level failure just looks like a broken server.
- Keep them short. A 200-line error crowds out the context needed to fix it.

## Executing model-authored code

If the server runs code the model wrote, that is the security boundary of the whole system.

- **Never `exec()` in the server process.** All execution goes through one sandbox module — a subprocess, with a hard timeout, no network, and a temporary working directory.
- **One code path for it.** If there are two ways to execute, one of them is unhardened.
- **Confine all writes to the session's temp directory.** Render and export must not be able to write elsewhere; check the resolved path, not the supplied one.
- **Bound everything**: wall-clock timeout, memory, output size. An unbounded result can exhaust the host or the context window.
- Where a container or a WASM runtime is available, prefer it to a subprocess.

## Session and state

- **Key state by MCP session**, not globally. Two clients must not see each other's parts.
- **Keep the history the model needs to iterate** — for a CAD server, the code that produced each part plus its current geometry, so a revision can be a diff rather than a rewrite.
- **Make state inspectable** with a `list_*` tool. A model that cannot see what exists will invent an id.
- Bound the session: a maximum object count and an eviction policy, or a long-running client leaks.

## Transport and structure

- **stdio** for a local client launching the server as a subprocess — the default, and the simplest.
- **Streamable HTTP** for a remote or shared server. Then authentication, per-session isolation and rate limiting are all yours to implement.
- Support both where it is cheap; keep transport selection out of the tool implementations.

Structural conventions that keep a server maintainable:

- **One tool per file**, registered in one place. The registry is then the readable index of the surface.
- **Type hints everywhere**, with a strict type checker and a linter in the gate.
- **The tool function is a thin adapter**: validate, delegate to a domain function, format the result. The domain function is testable without MCP. See `hexagonal-architecture`.

## Testing

- **Unit-test the domain functions directly**, with no MCP involved. That is where the logic is.
- **Test the tool layer for schema and formatting**: a malformed call produces a structured error; a result is shaped as expected.
- **Golden-file tests** for anything generated — compare exported artefact hashes and **perceptual** hashes for rendered images (an exact pixel match is too brittle across driver versions).
- **Never make live third-party API calls in unit tests.** Mock the HTTP client; gate integration tests on the key being present — and give them a start guard so a skipped suite is not reported as a pass. See `test-theatre-audit` and `container-integration-tests`.
- **Keep an end-to-end smoke script** that runs the whole loop (`build → render → validate → export`) and is part of the gate. For a server whose value is a feedback loop, this is the test that matters.
- **Pin version-sensitive dependencies.** Where rendering and export are sensitive to a geometry kernel's version, do not upgrade casually — run the golden tests after any bump.

## Keep the spec ahead of the code

For a server built to a specification: **do not add tools beyond the spec without updating the spec first.** The tool surface is the contract, and a surface that grows ad hoc becomes one no model can navigate and no document describes. See `docs-drift-guard`.

## Checklist

- [ ] The model's loop is written down, and the tools follow from it
- [ ] Tools are verbs; no internal API mirrored one-to-one; no `mode` mega-tool
- [ ] Every field described with units and range; enums, bounds, `additionalProperties: false`
- [ ] Descriptions state when to use, when not to, preconditions, and what is returned
- [ ] No unreadable blobs returned; images as image content, capped and composed
- [ ] Measurements returned alongside any image
- [ ] Truncation is explicit, with a way to get more
- [ ] Errors carry type, line, snippet and a suggestion; `isError`, never silent
- [ ] All model-authored code runs in one sandbox: subprocess, timeout, no network, temp cwd
- [ ] Session-keyed state, inspectable, bounded
- [ ] Domain logic testable without MCP; golden and smoke tests in the gate
- [ ] Spec updated before the surface grew

## Related skills

- `hexagonal-architecture` — the tool function as a thin adapter over a testable domain
- `claude-api` — model ids, pricing and parameters when building on the Claude API
- `test-theatre-audit` — credential-gated suites that pass while testing nothing
- `docs-drift-guard` — keeping the spec and the tool surface in step
- `deliberate-decisions` — recording pinned versions and the constraints behind them
