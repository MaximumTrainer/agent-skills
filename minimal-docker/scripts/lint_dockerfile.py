#!/usr/bin/env python3
"""
Heuristic linter for Dockerfile size and security anti-patterns.

Usage:
    python3 lint_dockerfile.py [path/to/Dockerfile] [--json]

Exit code: 1 if any "error" findings, else 0.

This is deliberately simple and dependency-free. It catches common patterns,
not intent — always read the Dockerfile yourself as well.
"""

# PEP 604 annotations (`str | None`) are evaluated at class-definition time
# without this, so the module raised TypeError on Python 3.9 - which is what a
# lot of machines still have first on PATH. The linter then looked broken
# rather than the Dockerfile.
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}

# Final-stage images that are almost always build-only / oversized.
FAT_IMAGE_PATTERNS = [
    (r"^(docker\.io/)?(library/)?golang(:|$)", "golang"),
    (r"^(docker\.io/)?(library/)?rust(:|$)", "rust"),
    (r"^(docker\.io/)?(library/)?maven(:|$)", "maven"),
    (r"^(docker\.io/)?(library/)?gradle(:|$)", "gradle"),
    (r"^(docker\.io/)?(library/)?gcc(:|$)", "gcc"),
    (r"mcr\.microsoft\.com/dotnet/sdk", "dotnet sdk"),
    (r"-jdk(-|$)|:.*jdk", "JDK"),
]
# Language images that are fat unless slim/alpine/distroless variants.
FULL_LANG_IMAGES = ["python", "node", "ruby", "php", "openjdk", "eclipse-temurin"]
LEAN_MARKERS = ["slim", "alpine", "distroless", "chiseled", "jre", "minimal", "chainguard"]
NONROOT_BASE_MARKERS = ["nonroot", "chiseled", "unprivileged", "cgr.dev/chainguard"]

# Dependency-install steps (not compile steps — those legitimately follow 'COPY . .').
DEP_INSTALL_RE = re.compile(
    r"\b(npm (ci|install|i)\b|yarn install\b|yarn\s*$|pnpm (install|i)\b|pip3? install|"
    r"uv sync|uv pip install|poetry install|pipenv install|go mod download|cargo chef cook|"
    r"cargo fetch|bundle install|composer install|dotnet restore|dependency:go-offline)"
)
SECRET_NAME_RE = re.compile(
    r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|ACCESS_?KEY|CREDENTIALS?)", re.I
)


@dataclass
class Finding:
    severity: str
    line: int
    rule: str
    message: str


@dataclass
class Instruction:
    line: int
    cmd: str
    args: str
    stage: int


@dataclass
class Stage:
    index: int
    base: str
    name: str | None
    line: int
    instructions: list = field(default_factory=list)


def parse(text):
    """Return (instructions, has_syntax_directive). Handles continuations, comments, heredocs."""
    lines = text.splitlines()
    has_syntax = any(re.match(r"^#\s*syntax\s*=", l.strip(), re.I) for l in lines[:5])
    instructions = []
    buf, start = "", None
    heredoc_end = None
    for i, raw in enumerate(lines, 1):
        if heredoc_end is not None:
            if raw.strip() == heredoc_end:
                heredoc_end = None
            continue
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if buf and stripped.startswith("#"):
            continue  # comment inside continuation
        if start is None:
            start = i
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        buf += stripped
        m = re.match(r"^(\w+)\s*(.*)$", buf, re.S)
        if m:
            cmd, args = m.group(1).upper(), m.group(2).strip()
            instructions.append((start, cmd, args))
            hd = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", args)
            if hd and cmd in ("RUN", "COPY"):
                heredoc_end = hd.group(1)
        buf, start = "", None
    return instructions, has_syntax


def build_stages(raw_instructions):
    stages, idx = [], -1
    for line, cmd, args in raw_instructions:
        if cmd == "FROM":
            idx += 1
            parts = [p for p in args.split() if not p.startswith("--")]
            base = parts[0] if parts else ""
            name = None
            if len(parts) >= 3 and parts[1].upper() == "AS":
                name = parts[2]
            stages.append(Stage(idx, base, name, line))
        if idx >= 0:
            stages[idx].instructions.append(Instruction(line, cmd, args, idx))
    return stages


def lint(path):
    findings = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    raw, has_syntax = parse(text)
    stages = build_stages(raw)
    add = lambda sev, line, rule, msg: findings.append(Finding(sev, line, rule, msg))

    if not stages:
        add("error", 0, "no-from", "No FROM instruction found.")
        return findings

    stage_names = {s.name for s in stages if s.name}
    final = stages[-1]

    if not has_syntax:
        add("info", 1, "syntax-directive",
            "Add '# syntax=docker/dockerfile:1' as the first line to enable BuildKit "
            "features (cache/secret mounts, heredocs).")

    ctx_dir = os.path.dirname(os.path.abspath(path))
    if not os.path.exists(os.path.join(ctx_dir, ".dockerignore")):
        add("warn", 0, "dockerignore",
            "No .dockerignore next to the Dockerfile — .git, node_modules, venvs and "
            "secrets may be sent to the build context and copied into the image.")

    if len(stages) == 1:
        add("info", final.line, "single-stage",
            "Single-stage build: compilers, package managers and build caches end up in "
            "the final image. Consider a multi-stage build.")

    # Base image checks
    for s in stages:
        base = s.base
        if base.lower() == "scratch" or base in stage_names or "$" in base:
            continue
        ref = base.split("@")[0]
        tag = ref.split("/")[-1].split(":", 1)[1] if ":" in ref.split("/")[-1] else None
        if "@sha256:" in base:
            pass
        elif tag is None:
            add("warn", s.line, "untagged-base",
                f"Base image '{base}' has no tag (implicitly :latest). Pin a version.")
        elif tag == "latest":
            add("warn", s.line, "latest-tag",
                f"Base image '{base}' uses :latest. Pin a version (and ideally a digest).")

    # Final stage base fatness
    fb = final.base.lower()
    if fb not in ("scratch",) and fb not in {n.lower() for n in stage_names} and "$" not in fb:
        for pat, label in FAT_IMAGE_PATTERNS:
            if re.search(pat, fb) and not any(m in fb for m in ("jre", "distroless")):
                add("warn", final.line, "fat-final-base",
                    f"Final stage uses a {label} build image ('{final.base}'). Copy the "
                    f"artifact into a minimal runtime image instead.")
                break
        else:
            name_part = re.sub(r"^(docker\.io/)?(library/)?", "", fb).split(":")[0]
            if name_part in FULL_LANG_IMAGES and not any(m in fb for m in LEAN_MARKERS):
                add("warn", final.line, "fat-final-base",
                    f"Final stage uses full '{final.base}'. Prefer a -slim, distroless "
                    f"or similar variant for the runtime stage.")

    # USER in final stage
    users = [i for i in final.instructions if i.cmd == "USER"]
    base_nonroot = any(m in fb for m in NONROOT_BASE_MARKERS)
    if not users and not base_nonroot:
        add("warn", final.line, "root-user",
            "Final stage never sets USER, so the container runs as root. Add a numeric "
            "non-root user, e.g. 'USER 10001:10001' (or 65532 on distroless).")
    elif users:
        last = users[-1].args.split(":")[0].strip()
        if last in ("root", "0"):
            add("warn", users[-1].line, "root-user",
                "Final USER is root. Switch to a numeric non-root UID.")
        elif not last.isdigit() and "$" not in last and fb == "scratch":
            add("warn", users[-1].line, "named-user-scratch",
                f"USER '{last}' on scratch needs /etc/passwd; use a numeric UID instead.")

    # Per-instruction checks
    for s in stages:
        is_final = s is final
        copy_all_seen = None
        deps_before_copy = False
        for ins in s.instructions:
            a = ins.args
            if ins.cmd == "RUN":
                if re.search(r"\bapt-get\s+update\b", a) and not re.search(r"\bapt-get\s+(-\S+\s+)*install\b", a):
                    add("warn", ins.line, "apt-update-alone",
                        "'apt-get update' in its own RUN gets cached and goes stale. Combine "
                        "it with 'apt-get install' in one RUN.")
                if re.search(r"\bapt-get\s+(-\S+\s+)*install\b", a) or re.search(r"\bapt\s+install\b", a):
                    if "--no-install-recommends" not in a:
                        add("warn", ins.line, "apt-recommends",
                            "apt install without --no-install-recommends pulls in extra packages.")
                    if is_final and "/var/lib/apt/lists" not in a and "type=cache" not in a:
                        add("warn", ins.line, "apt-lists",
                            "Remove apt lists in the same RUN: '&& rm -rf /var/lib/apt/lists/*'.")
                if re.search(r"\bapk\s+(-\S+\s+)*add\b", a) and "--no-cache" not in a and "type=cache" not in a:
                    add("warn", ins.line, "apk-cache",
                        "Use 'apk add --no-cache' to avoid storing the index in the layer.")
                if is_final and re.search(r"\bpip3?\s+install\b", a) and "--no-cache-dir" not in a \
                        and "type=cache" not in a:
                    add("info", ins.line, "pip-cache",
                        "pip cache is stored in the layer. Use --no-cache-dir or a BuildKit "
                        "cache mount.")
                if re.search(r"\bnpm\s+(install|i)\b(?!\s+-g)", a):
                    add("info", ins.line, "npm-install",
                        "Prefer 'npm ci' (lockfile-exact, reproducible) over 'npm install'.")
                if re.search(r"\bsudo\b", a):
                    add("warn", ins.line, "sudo", "Avoid sudo in Dockerfiles; switch USER instead.")
                if DEP_INSTALL_RE.search(a):
                    if copy_all_seen and not deps_before_copy:
                        add("warn", ins.line, "cache-order",
                            f"Dependencies are installed only after copying the whole context "
                            f"(line {copy_all_seen}), so every source edit reinstalls them. Copy "
                            f"manifests/lockfiles first and install deps before 'COPY . .'.")
                        copy_all_seen = None  # report once per COPY
                    elif not copy_all_seen:
                        deps_before_copy = True
            if ins.cmd in ("COPY", "ADD"):
                parts = [p for p in a.split() if not p.startswith("--")]
                if "--from" not in a and len(parts) >= 2 and parts[0] in (".", "./"):
                    copy_all_seen = ins.line
            if ins.cmd == "ADD":
                src = ([p for p in a.split() if not p.startswith("--")] or [""])[0]
                if not re.match(r"https?://|git@", src) and not re.search(r"\.(tar|tgz|tar\.\w+)$", src):
                    add("warn", ins.line, "add-vs-copy",
                        "Use COPY for local files; ADD has implicit URL/tar behaviour.")
            elif ins.cmd in ("ENV", "ARG"):
                key = re.split(r"[=\s]", a, 1)[0]
                if SECRET_NAME_RE.search(key):
                    add("error", ins.line, "secret-in-build",
                        f"{ins.cmd} '{key}' looks like a secret; it persists in image metadata/"
                        f"history. Use 'RUN --mount=type=secret,id=...' or runtime env instead.")
            elif ins.cmd in ("CMD", "ENTRYPOINT") and is_final:
                if not a.startswith("["):
                    add("warn", ins.line, "shell-form",
                        f"{ins.cmd} uses shell form; the app won't be PID 1 (no SIGTERM) and it "
                        f"fails on images without /bin/sh. Use exec form: {ins.cmd} [\"...\"].")
            elif ins.cmd == "MAINTAINER":
                add("info", ins.line, "maintainer",
                    "MAINTAINER is deprecated; use LABEL org.opencontainers.image.authors=...")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line))
    return findings


def main():
    # The clean-run line prints a check mark. On a cp1252 console (a default
    # Windows Python) that print raises UnicodeEncodeError, so a Dockerfile with
    # no issues exits 1 with a traceback while a bad one reports normally -
    # exactly backwards. Pin the streams rather than dropping the character.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    path = args[0] if args else "Dockerfile"
    if not os.path.isfile(path):
        print(f"Dockerfile not found: {path}", file=sys.stderr)
        sys.exit(2)
    findings = lint(path)
    if as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        if not findings:
            print(f"✓ {path}: no issues found")
        for f in findings:
            loc = f"L{f.line}" if f.line else "--"
            print(f"[{f.severity.upper():5}] {loc:>5}  {f.rule}: {f.message}")
        counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}
        if findings:
            print(f"\n{counts['error']} error(s), {counts['warn']} warning(s), {counts['info']} info")
    sys.exit(1 if any(f.severity == "error" for f in findings) else 0)


if __name__ == "__main__":
    main()
