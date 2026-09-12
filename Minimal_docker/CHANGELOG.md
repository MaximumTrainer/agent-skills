# Changelog

All notable changes to this skill are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the skill uses
[Semantic Versioning](https://semver.org/). The version lives in the
`metadata.version` field of `SKILL.md`.

## [Unreleased]

## [1.0.0] - 2026-09-10

### Added
- `SKILL.md` with a five-step workflow: analyse, choose base, write multi-stage Dockerfile, verify, deliver.
- Language templates for Go, Rust, Python, Node.js, Java, .NET, static sites and C/C++ (`references/languages.md`).
- Base image comparison, scratch pitfalls, glibc vs musl and pinning guidance (`references/base-images.md`).
- `scripts/lint_dockerfile.py`: heuristic linter for size and security anti-patterns, with `--json` output.
- `scripts/inspect_image.sh`: reports image size, layers, user, leftover tooling and setuid files.
- `assets/dockerignore.template`.
- Unit tests, a Docker smoke test, evals, CI workflow and packaging tool.
