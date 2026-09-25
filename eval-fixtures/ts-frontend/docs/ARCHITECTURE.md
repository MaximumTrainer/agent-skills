# Architecture

The scene lives under `src/scene/`. Shared state is a single Zustand store in
`src/state/store.ts`; components subscribe to it directly.

Telemetry arrives over a WebSocket at 30 Hz and is written straight into the
store.
