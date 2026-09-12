---
name: minimal-docker
description: Build small, secure, production-ready Docker images using multi-stage builds, minimal base images (scratch, distroless, Chainguard, Alpine, slim), non-root users, and tight layer caching. Use this skill whenever the user asks to write, containerize, dockerize, optimize, slim down, shrink, harden, or review a Dockerfile or container image, including requests like "make my image smaller", "why is my Docker image 1GB", "containerize this app", "write a Dockerfile for my Go/Rust/Python/Node/Java/.NET service", or "use distroless/scratch". Also use it when a task will produce a Dockerfile as a side effect (deploying to Kubernetes, Cloud Run, Fly, ECS, etc.), even if the user never says "minimal".
license: MIT
metadata:
  version: "1.0.0"
---

# Minimal Docker Containers

Goal: produce an image that contains the application and **only** what it needs at runtime — no compilers, package managers, shells, build caches, or test files — while staying debuggable and reproducible.

Smaller images pull faster, start faster, and have far fewer CVEs because every package you don't ship is a package you don't have to patch. But "smallest possible" is not always "best": a 2 MB scratch image that nobody can debug at 3am is worse than a 20 MB distroless one. Optimise for *minimal runtime surface*, then size.

## Workflow

### 1. Understand the app before writing anything

Inspect the project (manifest files, lockfiles, entrypoint, existing Dockerfile). Determine:

- **Language / runtime** and version (check `go.mod`, `Cargo.toml`, `pyproject.toml`/`requirements*.txt`/`uv.lock`, `package.json` + lockfile, `pom.xml`/`build.gradle`, `*.csproj`).
- **Can it be a static binary?** Go (with `CGO_ENABLED=0`), Rust (musl target), .NET Native AOT, GraalVM native-image. Static binaries unlock `scratch` / `distroless/static`.
- **Native dependencies**: C extensions (numpy, psycopg, bcrypt, sharp, etc.), `libc` requirements, system libs (libpq, libssl, ffmpeg, ImageMagick). These decide glibc vs musl and what must be copied into the runtime stage.
- **Runtime needs**: outbound TLS (CA certs), timezone handling (tzdata), writable dirs (`/tmp`, cache dirs), listening port, config via env vars, locale.
- **Target platform(s)**: amd64, arm64, or both (affects cross-compilation and base image choice).

If an existing Dockerfile is present, run `python3 scripts/lint_dockerfile.py <Dockerfile>` first to surface obvious problems, then read it yourself — the linter catches patterns, not intent.

### 2. Choose the runtime base

Pick the smallest base that satisfies the runtime needs from step 1. Read `references/base-images.md` for detailed trade-offs (glibc vs musl, debug variants, CVE posture, licensing of Chainguard tags).

| App shape | First choice | Fallback |
|---|---|---|
| Fully static binary, no TLS/tz needs | `scratch` | `gcr.io/distroless/static` |
| Static binary needing CA certs / tz / non-root user | `gcr.io/distroless/static:nonroot` | `scratch` + copied certs/passwd |
| Dynamically linked against glibc (Rust default, C/C++) | `gcr.io/distroless/cc:nonroot` | `debian:<ver>-slim` |
| Python | `python:<ver>-slim` runtime stage (or distroless python when versions align) | Alpine only if no C extensions |
| Node.js | `gcr.io/distroless/nodejs<ver>` or `node:<ver>-slim` | `node:<ver>-alpine` |
| Java | jlink custom JRE on `debian:<ver>-slim` / distroless base, or `distroless/java<ver>` | `eclipse-temurin:<ver>-jre` |
| .NET | chiseled `runtime-deps` (AOT) or chiseled `aspnet` | `aspnet:<ver>-alpine` |
| Static website | `nginx:<ver>-alpine` (or unprivileged variant) | `busybox` httpd |

Avoid Alpine by default for Python and for anything with prebuilt glibc binaries — musl differences cause slow source builds, subtle DNS behaviour changes, and occasional allocator performance issues. Alpine is fine for Go, static tools, and pure-JS Node apps.

### 3. Write a multi-stage Dockerfile

Language-specific templates live in `references/languages.md`. Read the section for the detected language and adapt it — don't paste it blindly. Every Dockerfile should follow these principles:

**Structure**
- `# syntax=docker/dockerfile:1` on the first line so BuildKit features (cache/secret mounts, heredocs) are available.
- A `build` stage with the full toolchain, and a final stage that only `COPY --from=build` the artifacts.
- Name stages (`AS build`, `AS runtime`) and keep the final stage last so `docker build` targets it by default.

**Caching (fast rebuilds)**
- Copy dependency manifests and lockfiles first, install dependencies, *then* copy source. Changing source should not reinstall dependencies.
- Use BuildKit cache mounts for package-manager caches instead of baking them into layers: `RUN --mount=type=cache,target=/root/.cache/...`.
- Use the lockfile-respecting install command (`npm ci`, `uv sync --frozen`, `cargo build --locked`, `go mod download`).

**Size**
- Nothing from the build stage leaks unless explicitly copied.
- In any stage that uses apt: `apt-get update && apt-get install -y --no-install-recommends ... && rm -rf /var/lib/apt/lists/*` in a single `RUN`. For apk: `apk add --no-cache`.
- Strip binaries (`-ldflags="-s -w"` for Go, `strip = true` in Cargo profile).
- Exclude dev dependencies (`npm ci --omit=dev`, `uv sync --no-dev`, `pip install` only runtime requirements).
- Always provide a `.dockerignore` (template: `assets/dockerignore.template`). A missing one silently sends `.git`, `node_modules`, venvs and secrets into the build context.

**Security**
- Run as non-root with a **numeric** UID (`USER 65532:65532` or `USER 10001`). Numeric IDs work on scratch/distroless (no `/etc/passwd` lookup needed) and satisfy Kubernetes `runAsNonRoot`.
- Pin base image versions (e.g. `python:3.12-slim-bookworm`, not `python:latest`). For production, suggest pinning by digest (`image:tag@sha256:...`) and using Renovate/Dependabot to bump it.
- Never `COPY` secrets or pass them via `ARG`/`ENV` — they persist in image history. Use `RUN --mount=type=secret,id=...`.
- Use `COPY`, not `ADD`, unless you specifically need remote-URL or tar-extraction behaviour.
- Design for `--read-only` root filesystems: write only to explicitly declared dirs (`/tmp` via tmpfs, or a volume).

**Runtime behaviour**
- Exec-form `ENTRYPOINT`/`CMD` (`["/app"]`), so the process is PID 1 and receives SIGTERM. Shell form breaks signal handling and doesn't work without a shell anyway.
- If the app spawns children or doesn't reap zombies, use `docker run --init` or add `tini`.
- `EXPOSE` the port as documentation; set sensible `ENV` defaults (`PYTHONUNBUFFERED=1`, `NODE_ENV=production`).
- Shell-less images can't run `HEALTHCHECK CMD curl ...`. Either have the binary expose a health subcommand (`HEALTHCHECK CMD ["/app", "healthcheck"]`) or rely on orchestrator probes (Kubernetes liveness/readiness). Say which you chose.
- Add OCI labels when useful (`org.opencontainers.image.source`, `.version`, `.revision`) — they cost nothing.

### 4. Verify

If Docker is available, build and check the result rather than assuming it works:

```bash
docker build -t app:minimal .
bash scripts/inspect_image.sh app:minimal      # size, layers, user, shell presence
docker run --rm --read-only --tmpfs /tmp -p 8080:8080 app:minimal   # smoke test
```

Things to confirm: the app actually starts (missing shared libs show up as `exec ... no such file or directory` on scratch — usually a dynamically linked binary), outbound HTTPS works (CA certs present), the user is non-root, and the size is in the expected range for the stack (see `references/base-images.md`). If `dive` is installed, `dive app:minimal` shows wasted space per layer.

If Docker isn't available in the environment, say so plainly and give the user the commands above to run themselves. Don't claim a size you didn't measure — give expected ranges instead.

### 5. Deliver

Provide:
1. The `Dockerfile` (and `.dockerignore`), as files if you have a filesystem.
2. A short explanation of the key choices: which base image and why, what was stripped, the user it runs as.
3. Build/run commands, including `--platform linux/amd64,linux/arm64` with `docker buildx` if multi-arch matters.
4. Honest trade-offs: e.g. "no shell in the final image — use `docker debug` or the `:debug` distroless tag to troubleshoot."

When optimising an existing Dockerfile, show before/after size (measured or estimated) and list each change with its reason, so the user can accept or reject them individually.

## Debugging minimal images

Users will hit "I can't exec into it". Point them at the options rather than adding a shell back into production:
- `gcr.io/distroless/*:debug` tags include a busybox shell — use for a debug build only.
- `docker debug <container>` (Docker Desktop) attaches a toolbox to a running shell-less container.
- Kubernetes: `kubectl debug -it <pod> --image=busybox --target=<container>` (ephemeral container sharing the process namespace).
- Build a `debug` target stage in the same Dockerfile (`docker build --target debug`).

## Reference files

- `references/languages.md` — Multi-stage templates and gotchas for Go, Rust, Python, Node.js, Java, .NET, and static sites. Read the relevant section when writing a Dockerfile.
- `references/base-images.md` — Base image comparison, glibc vs musl, what scratch lacks, typical final image sizes. Read when choosing a base or explaining trade-offs.
- `scripts/lint_dockerfile.py` — Heuristic checker for common size/security anti-patterns. Run on existing Dockerfiles and on your own output before delivering.
- `scripts/inspect_image.sh` — Reports size, layer sizes, configured user, entrypoint, and whether a shell/package manager exists in a built image.
- `assets/dockerignore.template` — Starting `.dockerignore`; trim or extend for the project.
