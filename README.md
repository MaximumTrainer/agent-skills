# minimal-docker

An agent skill that teaches Claude to build **small, secure, production-ready Docker images**. It uses multi-stage builds, the smallest base image that actually works, non-root users, and layer ordering that keeps rebuilds fast.

Without guidance, AI-generated Dockerfiles tend to be single-stage, run as root, sit on a 1 GB base image, and reinstall every dependency on each code change. This skill replaces those habits with a consistent workflow and a set of tested templates.

## What it does

When Claude is asked to write, optimise, or review a Dockerfile, the skill guides it through five steps:

1. **Analyse the app.** Claude identifies the language, runtime version, native dependencies, and whether the app can be built as a static binary. It also works out runtime needs such as CA certificates, time zones, writable directories, and target architectures.
2. **Choose a runtime base.** Claude picks from scratch, distroless, Chainguard, chiseled, Alpine, or slim images, based on what the app needs at runtime rather than habit.
3. **Write a multi-stage Dockerfile.** Build tooling stays in the build stage. Dependencies are installed before source is copied, and BuildKit cache mounts keep package caches out of the image. The final image runs as a numeric non-root UID with an exec-form entrypoint, and a `.dockerignore` is always included.
4. **Verify the image.** Claude builds the image, inspects it, and smoke-tests it with a read-only root filesystem. If Docker isn't available, it says so and gives you the commands to run rather than quoting sizes it didn't measure.
5. **Explain the result.** Claude states which base it chose and why, what it removed, what the image runs as, and what the trade-offs are, such as how to debug an image with no shell.

The skill triggers on requests like:

- "Containerize this FastAPI app"
- "Why is my Docker image 1.2 GB?"
- "Write a Dockerfile for my Rust service that runs on arm64 and amd64"
- "Harden this Dockerfile"
- Deploying to Kubernetes, Cloud Run, Fly.io, ECS and similar platforms, even when "minimal" is never mentioned

## What's included

```
minimal-docker/
├── SKILL.md                     # Workflow and principles Claude follows
├── README.md                    # This file
├── references/
│   ├── languages.md             # Multi-stage templates per language
│   └── base-images.md           # Base image comparison and trade-offs
├── scripts/
│   ├── lint_dockerfile.py       # Static checker for size/security anti-patterns
│   └── inspect_image.sh         # Inspects a built image
└── assets/
    └── dockerignore.template    # Starting .dockerignore
```

### Language templates

`references/languages.md` has annotated, copy-adaptable templates for these stacks:

| Stack | Approach | Typical final size |
|---|---|---|
| Go | `CGO_ENABLED=0` static binary on distroless/static or scratch, with native cross-compilation | 5–25 MB |
| Rust | glibc on distroless/cc, or static musl on scratch, plus a cargo-chef caching pattern | 5–30 MB |
| Python | uv or pip venv built in a slim stage and copied into a matching slim runtime | 150–400 MB |
| Node.js | Separate prod/dev dependency stages on a distroless or slim runtime, plus Next.js standalone | 150–300 MB |
| Java | jlink custom JRE, the distroless Java alternative, and Spring Boot layered jars | 80–150 MB |
| .NET | Chiseled images, or Native AOT on chiseled `runtime-deps` | 20–150 MB |
| Static sites | Node build stage served by `nginx-unprivileged` | 25–60 MB |
| C/C++ | Static musl build, or `ldd`-guided copy into distroless/cc | varies |

These sizes are rough, uncompressed guides, and real results depend on your dependencies.

### Base image guide

`references/base-images.md` compares the common runtime bases by size, libc, shell, and default user. It lists what scratch is missing, such as CA certificates and `/tmp`, and why that causes the misleading `exec /app: no such file or directory` error. It also explains when to choose glibc over musl and how to pin images by tag or digest.

## Using the scripts directly

The scripts work without Claude, so you can run them yourself or in CI.

### lint_dockerfile.py

This script is a dependency-free heuristic linter and needs Python 3.10 or later. It checks for about 20 anti-patterns:

- Base images without a tag or using `:latest`
- A full build image (golang, sdk, jdk) used as the final stage
- No `USER`, or `USER root`
- Secret-looking `ENV` or `ARG` values
- `COPY . .` placed before the dependency install
- `apt-get update` in its own layer, or apt installs without `--no-install-recommends` or cleanup
- `apk add` without `--no-cache`
- `ADD` used for local files
- Shell-form `CMD` or `ENTRYPOINT`
- A missing `.dockerignore`

```bash
python3 scripts/lint_dockerfile.py path/to/Dockerfile
python3 scripts/lint_dockerfile.py path/to/Dockerfile --json   # machine-readable
```

Example output:

```
[ERROR]    L3  secret-in-build: ENV 'API_TOKEN' looks like a secret; it persists in image metadata/history. ...
[WARN ]    L1  root-user: Final stage never sets USER, so the container runs as root. ...
[WARN ]    L8  cache-order: Dependencies are installed only after copying the whole context (line 5), ...
[WARN ]    L9  shell-form: CMD uses shell form; the app won't be PID 1 (no SIGTERM) ...

1 error(s), 10 warning(s), 4 info
```

The script exits with code `1` if there are any errors, so it can gate a CI job. It matches patterns rather than understanding intent, so treat warnings as prompts to look, not as verdicts.

### inspect_image.sh

This script needs Docker and bash. It reports the following for a built image:

- Image size
- The largest layers
- The configured user, entrypoint, and exposed ports
- Any leftover shells, package managers, compilers, or `curl`/`wget`
- Any setuid or setgid binaries

It reads the filesystem through `docker export`, so it also works on images with no shell.

```bash
docker build -t myapp:minimal .
bash scripts/inspect_image.sh myapp:minimal
```

## Installation

**Claude apps:** open the packaged `minimal-docker.skill` file in a conversation and click **Save skill**. You can also upload it through the Skills section of Claude's settings. See [support.claude.com](https://support.claude.com) for current instructions.

**Claude Code:** copy the folder into a skills directory. Use your personal directory to have the skill in every project, or a project directory to share it with your team through git:

```bash
# Personal (all projects)
cp -r minimal-docker ~/.claude/skills/

# Project (commit it and your team gets it too)
mkdir -p .claude/skills && cp -r minimal-docker .claude/skills/
```

Start a new session to pick up the skill.

## Design choices

These defaults are opinionated. If your team's conventions differ, edit `SKILL.md` to match.

- **Minimal runtime surface comes before minimal size.** A 20 MB distroless image you can debug beats a 2 MB scratch image you can't, so the skill defaults to distroless over raw scratch.
- **Alpine is not the default for Python** or for anything with prebuilt glibc binaries. musl differences cause slow source builds and subtle runtime issues.
- **Numeric UIDs** (`10001`, or `65532` on distroless) work on scratch and satisfy Kubernetes `runAsNonRoot`.
- **No shell in production.** For debugging, the skill points to distroless `:debug` tags, `docker debug`, and `kubectl debug` rather than adding a shell back.
- **Honest verification.** Claude reports only image sizes it has actually measured and gives estimated ranges otherwise.

## Limitations

- Version numbers in the templates, such as Go 1.24, Node 22, and `-debian12` distroless suffixes, go stale. Claude is instructed to match the project's toolchain files and check that tags exist, but check the pinned versions before shipping.
- The Chainguard free tier has historically limited public images to `:latest`, so check its current terms before using it for pinned production builds.
- The jlink approach needs a smoke test, because missing Java modules fail at runtime, not at build time.
- `inspect_image.sh` reports the size Docker records locally, which can differ from the compressed size in a registry.

## Customising

- **Change defaults:** edit the base-image table and principles in `SKILL.md`.
- **Add a language:** add a section to `references/languages.md` and a row to the table above.
- **Add lint rules:** each check in `lint_dockerfile.py` is a small, self-contained block inside `lint()`.
- **Enforce house style:** add your registry mirror, required labels, or approved base images to `SKILL.md` so Claude applies them every time.
