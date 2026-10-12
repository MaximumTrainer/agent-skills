---
name: minimal-docker
description: Build small, secure, production-ready Docker images using multi-stage builds, minimal base images (scratch, distroless, Chainguard, Alpine, slim), non-root users, and tight layer caching. Use this skill whenever the user asks to write, containerize, dockerize, optimize, slim down, shrink, harden, or review a Dockerfile or container image, including requests like "make my image smaller", "why is my Docker image 1GB", "containerize this app", "write a Dockerfile for my Go/Rust/Python/Node/Java/.NET service", or "use distroless/scratch". Also use it when a task will produce a Dockerfile as a side effect (deploying to Kubernetes, Cloud Run, Fly, ECS, etc.), even if the user never says "minimal".
license: MIT
metadata:
  version: "2.0.0"
---

# Minimal Docker Containers

Measured note (fixture re-run, 2026-10): without this skill the model already writes a good multi-stage Dockerfile. It picks a slim or distroless base, sets `CGO_ENABLED=0` and `--platform=$BUILDPLATFORM` for Go, uses `output: "standalone"` for Next.js, orders manifests before source, runs as a numeric non-root user, uses exec-form `CMD`, adds a `.dockerignore`, calls out a secret in `ENV` first, and labels unmeasured sizes as estimates. None of that is repeated here.

What it did **not** do unaided is the production hardening below. Across four baseline runs it never pinned a digest, never designed for a read-only root filesystem and never used a secret mount, and it gave a debug route or a health check decision once each. The with-skill runs did most of these every time. That gap is what this skill is for, so treat each item as a default to apply, not an option to mention.

## The defaults the model skips

1. **Pin the base by digest.** Write `FROM image:tag@sha256:<digest>` for every stage, or say plainly that you could not resolve the digest and give the command (`docker buildx imagetools inspect image:tag`). Pair it with Renovate or Dependabot so the pin is not frozen forever. A tag is a pointer someone else moves.
2. **Design for a read-only root filesystem.** Decide which paths the app writes to, declare them (`/tmp` as tmpfs, a volume for anything else), and give the run command: `docker run --read-only --tmpfs /tmp` or `readOnlyRootFilesystem: true` with an `emptyDir` in Kubernetes. If the app cannot run read-only, say what writes where.
3. **Build-time secrets go through a secret mount.** If a token is needed during the build (private registry, `pip` index, `npm` auth), use `RUN --mount=type=secret,id=...` and show the matching `docker build --secret` flag. Runtime secrets come from the orchestrator. Never `ARG` or `ENV`.
4. **Say how to debug the image you just made.** A distroless or scratch image has no shell, and the first person on call will try `docker exec sh`. Name the route: the `:debug` distroless tag for a debug build, `docker debug`, or `kubectl debug -it <pod> --image=busybox --target=<container>`.
5. **State the health check decision.** Shell-less images cannot run `HEALTHCHECK CMD curl`. Either give the binary a health subcommand (`HEALTHCHECK CMD ["/app", "healthcheck"]`) or say the orchestrator's probes cover it, and write which.
6. **Lint before you deliver.** Run `python3 scripts/lint_dockerfile.py <Dockerfile>` on your own output, and on the user's Dockerfile before reviewing it. It catches patterns, not intent, so read the file yourself too.
7. **Measure when you can.** If Docker is available, build and run `bash scripts/inspect_image.sh <image>` for the size, layers, user and shell presence, then smoke-test with `docker run --rm --read-only --tmpfs /tmp`. If it is not available, say so and give the commands.

## Reference files

- `references/languages.md`: per-language multi-stage templates (Go, Rust, Python, Node.js, Java, .NET, static sites). Read the section for the stack you are containerising.
- `references/base-images.md`: base image trade-offs (glibc vs musl, debug variants, typical final sizes).
- `scripts/lint_dockerfile.py`: heuristic checker for size and security anti-patterns.
- `scripts/inspect_image.sh`: size, layers, user, entrypoint and shell presence of a built image.
- `assets/dockerignore.template`: starting `.dockerignore`.
