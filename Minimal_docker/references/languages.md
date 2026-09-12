# Language Templates

Adapt these to the project — paths, binary names, ports and build commands will differ. Version numbers are shown as `ARG`s so they're easy to bump; set them to match the project's toolchain file (`go.mod`, `rust-toolchain.toml`, `.python-version`, `.nvmrc`, `global.json`, etc.) and check that the tag exists.

An `ARG` declared before the first `FROM` can be used in any `FROM` line, which keeps builder and runtime versions in sync.

## Contents
- [Go](#go)
- [Rust](#rust)
- [Python](#python)
- [Node.js](#nodejs)
- [Java](#java)
- [.NET](#net)
- [Static sites / SPAs](#static-sites--spas)
- [C / C++](#c--c)

---

## Go

Go is the easiest case: with `CGO_ENABLED=0` you get a fully static binary.

```dockerfile
# syntax=docker/dockerfile:1
ARG GO_VERSION=1.24

FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
ARG TARGETOS TARGETARCH
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go build -trimpath -ldflags="-s -w" -o /out/app ./cmd/app

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/app /app
USER 65532:65532
ENTRYPOINT ["/app"]
```

Notes:
- `--platform=$BUILDPLATFORM` + `GOOS/GOARCH` cross-compiles natively instead of emulating under QEMU — much faster for `buildx --platform linux/amd64,linux/arm64`.
- If there's no `go.sum` (no dependencies), drop it from the `COPY`.
- `-trimpath` removes local paths from the binary (reproducibility); `-s -w` strips symbol/debug tables (~25–30% smaller).
- If the app needs cgo (e.g. `mattn/go-sqlite3`), either switch to a pure-Go alternative (`modernc.org/sqlite`) or build with cgo and use `distroless/base` or `distroless/cc`.

**Scratch variant** (when you want zero extra files):

```dockerfile
FROM golang:${GO_VERSION}-bookworm AS build
# ... build as above ...
RUN mkdir -m 1777 /out/tmp

FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build /out/tmp /tmp
COPY --from=build /out/app /app
USER 10001:10001
ENTRYPOINT ["/app"]
```

For timezone data on scratch, embed it in the binary: `import _ "time/tzdata"` or build with `-tags timetzdata` (adds ~450 KB).

---

## Rust

Two routes: glibc build on `distroless/cc` (simplest, works with most crates), or a fully static musl build for `scratch`/`distroless/static`.

### glibc → distroless/cc

```dockerfile
# syntax=docker/dockerfile:1
ARG RUST_VERSION=1.85

FROM rust:${RUST_VERSION}-slim-bookworm AS build
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked \
 && mkdir -p /out && cp target/release/myapp /out/myapp

FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=build /out/myapp /myapp
USER 65532:65532
ENTRYPOINT ["/myapp"]
```

The `target` dir is a cache mount, so it's not in any layer — that's why the binary is copied out to `/out` inside the same `RUN`.

If crates link system libraries (e.g. `openssl-sys` → `libssl-dev`, `pkg-config`), install the `-dev` packages in the build stage only. Prefer `rustls` features over OpenSSL — it removes the runtime dependency entirely.

### Static musl → scratch

```dockerfile
FROM rust:${RUST_VERSION}-alpine AS build
RUN apk add --no-cache musl-dev
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    cargo build --release --locked \
 && mkdir -p /out && cp target/release/myapp /out/myapp

FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build /out/myapp /myapp
USER 10001:10001
ENTRYPOINT ["/myapp"]
```

On `rust:alpine` the default target is musl, so the output is static. musl's allocator is slow for allocation-heavy workloads — consider `mimalloc` or `jemallocator` as the global allocator. Alpine images need `apk add ca-certificates` if the file isn't already present at `/etc/ssl/certs/ca-certificates.crt`.

### Dependency caching for large projects

Cache mounts help locally but not on ephemeral CI runners. `cargo-chef` builds dependencies as a separate cacheable layer:

```dockerfile
FROM rust:${RUST_VERSION}-slim-bookworm AS chef
RUN cargo install cargo-chef --locked
WORKDIR /src

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS build
COPY --from=planner /src/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
RUN cargo build --release --locked

# ...then a runtime stage exactly as in the distroless/cc example above
```

### Cargo profile for size

```toml
[profile.release]
strip = true
lto = true
codegen-units = 1
# panic = "abort"      # smaller, but only if nothing relies on unwinding
# opt-level = "z"      # optimise for size over speed — measure first
```

---

## Python

Python can't be a static binary, so the goal is: build wheels/venv with compilers in one stage, copy only the venv + source into a clean runtime stage.

**Critical gotcha:** a virtualenv hard-codes the path to its interpreter. Builder and runtime must use the *same* Python at the *same* path — easiest by using the same `python:<ver>-slim` image for both stages. Copying a venv from `python:3.12-slim` into `distroless/python3` (which uses Debian's `/usr/bin/python3`, a different version) will break.

### With uv (preferred when `uv.lock` exists)

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS build
# Pin a specific uv version for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:${PYTHON_VERSION}-slim-bookworm
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "myapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The first `uv sync` installs only dependencies (cached layer); the second installs the project itself.

### With pip / requirements.txt

```dockerfile
FROM python:${PYTHON_VERSION}-slim-bookworm AS build
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

FROM python:${PYTHON_VERSION}-slim-bookworm
# Runtime shared libs only — NOT the -dev packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY . .
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
USER 10001
CMD ["python", "-m", "myapp"]
```

The pattern "`-dev` package in build, runtime `.so` package in final" applies to any C dependency (`libpq-dev`→`libpq5`, `libxml2-dev`→`libxml2`, etc.). If all dependencies ship manylinux wheels, the build stage needs no compilers at all.

Notes:
- Avoid Alpine for Python unless there are zero compiled dependencies; musl wheels are less common and source builds are slow.
- Don't ship test suites, notebooks, or `.git` — cover them in `.dockerignore`.
- Large ML stacks (torch, tensorflow) dominate size; use CPU-only wheels (`--index-url https://download.pytorch.org/whl/cpu`) when GPU isn't needed.

---

## Node.js

Separate production dependencies from build dependencies: the build stage needs devDependencies (TypeScript, bundlers), the runtime doesn't.

```dockerfile
# syntax=docker/dockerfile:1
ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev

FROM node:${NODE_VERSION}-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM gcr.io/distroless/nodejs${NODE_VERSION}-debian12:nonroot
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
EXPOSE 3000
CMD ["dist/server.js"]
```

Notes:
- The distroless Node image's entrypoint is already `node`, so `CMD` is just the script path.
- Check that a distroless tag exists for the chosen Node major; if not, use `node:${NODE_VERSION}-slim` with `USER node` for the runtime stage.
- pnpm: `pnpm install --frozen-lockfile --prod`; yarn berry: `yarn workspaces focus --production`. Enable the package manager via corepack or install it in the build stage.
- Native addons (bcrypt, sharp, better-sqlite3) must be compiled against the same libc as the runtime: build on `-slim` for a Debian/distroless runtime, on `-alpine` for an Alpine runtime. Never mix.
- If the app is bundled to a single file (esbuild, ncc, Bun build), you may not need `node_modules` in the runtime at all.
- **Next.js:** set `output: "standalone"` in `next.config.*`, then copy `.next/standalone` to `/app`, `.next/static` to `/app/.next/static`, and `public` to `/app/public`; `CMD ["server.js"]`. This typically cuts images from ~1 GB to ~150 MB.

---

## Java

Options, smallest first: GraalVM native-image (static-ish binary, complex build) → jlink custom JRE → stock JRE image.

### jlink custom runtime

```dockerfile
# syntax=docker/dockerfile:1
ARG JAVA_VERSION=21

FROM eclipse-temurin:${JAVA_VERSION}-jdk AS build
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.m2 ./mvnw -q -DskipTests package \
 && cp target/*.jar /app.jar
RUN jdeps --ignore-missing-deps -q --recursive --multi-release ${JAVA_VERSION} \
      --print-module-deps /app.jar > /modules.txt \
 && jlink --add-modules "$(cat /modules.txt)" \
      --strip-debug --no-man-pages --no-header-files --compress=zip-6 \
      --output /jre

FROM debian:bookworm-slim
ENV JAVA_HOME=/opt/jre PATH="/opt/jre/bin:$PATH"
COPY --from=build /jre /opt/jre
COPY --from=build /app.jar /app/app.jar
USER 10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/app.jar"]
```

Notes:
- `--compress=zip-6` is JDK 21+ syntax; on 17 use `--compress=2`.
- `jdeps` struggles with Spring Boot fat jars (dependencies are nested). Either extract the jar first and point `--class-path` at the libs, or start from a known module list and add until it runs: `java.base,java.logging,java.naming,java.management,java.security.jgss,java.instrument,java.sql,java.desktop,jdk.unsupported,jdk.crypto.ec`. Always smoke-test — missing modules fail at runtime, not build time.
- Alternative with less effort: `gcr.io/distroless/java${JAVA_VERSION}-debian12:nonroot`, whose entrypoint already runs `java -jar`, so `CMD ["/app/app.jar"]`.
- Spring Boot layered jars improve caching: extract with `java -Djarmode=tools -jar app.jar extract --layers --launcher` (Boot 3.3+; older versions use `-Djarmode=layertools extract`) and `COPY` each layer (dependencies, spring-boot-loader, snapshot-dependencies, application) separately.
- Set `-XX:MaxRAMPercentage` so the JVM respects container memory limits sensibly.

---

## .NET

Microsoft ships "chiseled" Ubuntu images: no shell, no package manager, non-root by default (user `app`, UID 1654).

### Framework-dependent

```dockerfile
# syntax=docker/dockerfile:1
ARG DOTNET_VERSION=8.0

FROM mcr.microsoft.com/dotnet/sdk:${DOTNET_VERSION} AS build
WORKDIR /src
COPY *.sln ./
COPY src/MyApp/*.csproj src/MyApp/
RUN --mount=type=cache,target=/root/.nuget/packages dotnet restore
COPY . .
RUN --mount=type=cache,target=/root/.nuget/packages \
    dotnet publish src/MyApp -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:${DOTNET_VERSION}-noble-chiseled
WORKDIR /app
COPY --from=build /out .
EXPOSE 8080
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Native AOT (smallest)

Add to the `.csproj`: `<PublishAot>true</PublishAot>` and, if culture-specific formatting isn't needed, `<InvariantGlobalization>true</InvariantGlobalization>`.

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:${DOTNET_VERSION} AS build
RUN apt-get update && apt-get install -y --no-install-recommends clang zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*
# ... restore / copy as above ...
RUN dotnet publish src/MyApp -c Release -r linux-x64 -o /out

FROM mcr.microsoft.com/dotnet/runtime-deps:${DOTNET_VERSION}-noble-chiseled
WORKDIR /app
COPY --from=build /out/MyApp .
ENTRYPOINT ["./MyApp"]
```

Notes:
- ASP.NET Core images listen on port 8080 by default (since .NET 8), which works for non-root.
- If the app needs ICU or time zones and isn't using invariant globalization, use the `-chiseled-extra` variant.
- Check available tags on MCR for the target .NET version; tag naming (`jammy`/`noble`) follows the Ubuntu release.

---

## Static sites / SPAs

Build with Node, serve with an unprivileged web server:

```dockerfile
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Optional SPA fallback: COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
```

`nginx-unprivileged` runs as UID 101 and listens on 8080. For SPAs with client-side routing, add `try_files $uri $uri/ /index.html;` in the server config.

---

## C / C++

- Easiest: build statically on Alpine (`gcc -static` / `-DCMAKE_EXE_LINKER_FLAGS=-static`) and ship on `scratch`.
- If static linking isn't practical (glibc-only deps), build on Debian and ship on `gcr.io/distroless/cc-debian12`. Use `ldd /out/app` in the build stage to list shared libraries, and `COPY` any not already in distroless/cc into the runtime stage at the same paths.
