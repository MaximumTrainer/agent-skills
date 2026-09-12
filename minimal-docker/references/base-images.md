# Base Images

## Comparison

Sizes are approximate, uncompressed, single-arch, and drift over time — use them for ballpark expectations, not claims. Measure the real image when you can.

| Base | ~Size | libc | Shell | Pkg mgr | Non-root default | Good for |
|---|---|---|---|---|---|---|
| `scratch` | 0 | none | no | no | no (set `USER`) | Fully static binaries |
| `gcr.io/distroless/static` | ~2 MB | none | no | no | `:nonroot` tag (65532) | Static binaries needing certs/tz/passwd |
| `gcr.io/distroless/base` | ~20 MB | glibc | no | no | `:nonroot` tag | Dynamically linked binaries (glibc + libssl) |
| `gcr.io/distroless/cc` | ~25 MB | glibc | no | no | `:nonroot` tag | Rust/C/C++ needing GCC runtime libs |
| `gcr.io/distroless/<lang>` | varies | glibc | no | no | `:nonroot` tag | Node, Java, Python (Debian's version) |
| `cgr.dev/chainguard/<name>` | small | glibc (Wolfi) | no (`-dev` has) | no (`-dev` has apk) | yes | Low-CVE, daily-rebuilt runtimes |
| MS chiseled (`*-chiseled`) | ~15–110 MB | glibc (Ubuntu) | no | no | yes (1654) | .NET |
| `alpine` | ~8 MB | musl | ash | apk | no | Go, static tools, pure-JS Node |
| `busybox` | ~4 MB | varies | yes | no | no | Tiny utilities, simple httpd |
| `debian:<ver>-slim` | ~75 MB | glibc | bash | apt | no | When you need apt packages at runtime |
| `<lang>:<ver>-slim` | 120–250 MB | glibc | bash | apt | varies | Python/Node runtime stage |
| `<lang>:<ver>` (full) | 800 MB–1.2 GB | glibc | bash | apt | no | **Build stage only** |

Distroless images come per Debian release (suffix like `-debian12`); check for the newest suffix when writing a new Dockerfile. Each has a `:debug` (and `:debug-nonroot`) variant with a busybox shell for troubleshooting.

Chainguard's free public images have historically only offered the `:latest` / `:latest-dev` tags, with version-pinned tags behind a subscription — check current terms before recommending them for pinned production builds. Docker Hardened Images and Ubuntu chiseled images are other hardened options worth mentioning when the user cares about CVE counts.

## Typical final image sizes

Rough targets to sanity-check your result:

| Stack | Minimal approach | Typical size |
|---|---|---|
| Go | static on distroless/scratch | 5–25 MB |
| Rust | distroless/cc or scratch | 5–30 MB |
| .NET | Native AOT on chiseled runtime-deps | 20–40 MB |
| .NET | chiseled aspnet | 110–150 MB |
| Java | jlink JRE on debian-slim | 80–150 MB |
| Node.js | distroless/slim, prod deps only | 150–300 MB |
| Python | slim + venv | 150–400 MB (ML stacks: GBs) |
| Static site | nginx-unprivileged:alpine | 25–60 MB |

If the result is far above the range, look for: a full `<lang>` image as the final stage, dev dependencies shipped, build caches baked into layers, missing `.dockerignore`, or files deleted in a later layer (deletion doesn't reclaim space from earlier layers).

## What scratch doesn't have

Everything. Specifically, you may need to add:

- **CA certificates** — `/etc/ssl/certs/ca-certificates.crt`, or any outbound HTTPS fails with x509 errors.
- **Timezone data** — `/usr/share/zoneinfo`, or embed it (Go: `time/tzdata`).
- **/etc/passwd and /etc/group** — only if something looks up the user by name. Numeric `USER 10001` avoids this.
- **/tmp** — doesn't exist; create it in the build stage with mode 1777 and copy it, or mount a tmpfs.
- **A libc** — dynamically linked binaries fail with the misleading `exec /app: no such file or directory` (it's the dynamic loader that's missing, not the binary). Check with `file` or `ldd` in the build stage.

`distroless/static` provides the first four already, which is why it's usually the better default than raw scratch.

## glibc vs musl

Alpine uses musl libc; Debian, Ubuntu, distroless, Wolfi and chiseled images use glibc.

Choose glibc (slim/distroless) when:
- Using Python with compiled dependencies (manylinux wheels target glibc; musllinux coverage is thinner).
- Shipping prebuilt binaries or native addons built for glibc.
- The app is allocation-heavy and performance-sensitive (musl's malloc is slower).
- DNS behaviour matters (musl's resolver differs: no `search`/`ndots` parity in some versions, parallel A/AAAA queries, TCP fallback history).

Alpine is fine when the binary is static anyway, or for pure interpreted code with no native deps. Never build on one libc and run on the other.

## Pinning and updates

- Tag pinning (`python:3.12-slim-bookworm`) gives predictable major/minor versions but the underlying image still changes as patches land — good for security, less good for reproducibility.
- Digest pinning (`python:3.12-slim-bookworm@sha256:...`) is fully reproducible. Pair it with Renovate or Dependabot so digests get bumped and security patches aren't frozen out.
- Rebuild regularly even if your code hasn't changed; the base image CVE fixes only reach you on rebuild.
