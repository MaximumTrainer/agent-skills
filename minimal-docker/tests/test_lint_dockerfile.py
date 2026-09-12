"""Unit tests for scripts/lint_dockerfile.py. Stdlib only: python -m unittest discover -s tests"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINTER = ROOT / "scripts" / "lint_dockerfile.py"

spec = importlib.util.spec_from_file_location("lint_dockerfile", LINTER)
lint_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint_mod)

GOOD_GO = """\
    # syntax=docker/dockerfile:1
    ARG GO_VERSION=1.24
    FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-bookworm AS build
    WORKDIR /src
    COPY go.mod go.sum ./
    RUN --mount=type=cache,target=/go/pkg/mod go mod download
    COPY . .
    RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/app ./cmd/app

    FROM gcr.io/distroless/static-debian12:nonroot
    COPY --from=build /out/app /app
    USER 65532:65532
    ENTRYPOINT ["/app"]
"""


class LintTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def lint(self, content, dockerignore=True):
        (self.dir / "Dockerfile").write_text(textwrap.dedent(content))
        ignore = self.dir / ".dockerignore"
        if dockerignore:
            ignore.write_text(".git\n")
        elif ignore.exists():
            ignore.unlink()
        return lint_mod.lint(str(self.dir / "Dockerfile"))

    def rules(self, findings, severities=("error", "warn", "info")):
        return {f.rule for f in findings if f.severity in severities}

    def assertRule(self, content, rule, **kw):
        findings = self.lint(content, **kw)
        self.assertIn(rule, self.rules(findings), f"expected '{rule}' in {findings}")
        return findings

    def assertNoRule(self, content, rule, **kw):
        findings = self.lint(content, **kw)
        self.assertNotIn(rule, self.rules(findings), f"unexpected '{rule}' in {findings}")
        return findings


class TestCleanDockerfile(LintTestCase):
    def test_good_go_has_no_findings(self):
        self.assertEqual(self.lint(GOOD_GO), [])


class TestBaseImages(LintTestCase):
    def test_untagged_base(self):
        self.assertRule("FROM node\nUSER 1000\n", "untagged-base")

    def test_latest_tag(self):
        self.assertRule("FROM alpine:latest\nUSER 1000\n", "latest-tag")

    def test_digest_pinned_is_fine(self):
        f = self.lint("FROM alpine@sha256:" + "a" * 64 + "\nUSER 1000\n")
        self.assertFalse(self.rules(f) & {"untagged-base", "latest-tag"})

    def test_scratch_stage_refs_and_args_are_not_flagged(self):
        f = self.lint("""\
            ARG V=3.12
            FROM python:${V}-slim AS build
            FROM build AS test
            FROM scratch
            USER 10001
        """)
        self.assertFalse(self.rules(f) & {"untagged-base", "latest-tag"})

    def test_fat_final_language_image(self):
        self.assertRule("FROM python:3.12\nUSER 1000\n", "fat-final-base")

    def test_fat_final_build_image(self):
        self.assertRule("FROM golang:1.24\nUSER 1000\n", "fat-final-base")

    def test_slim_final_is_fine(self):
        self.assertNoRule("FROM python:3.12-slim\nUSER 1000\n", "fat-final-base")

    def test_jdk_build_stage_only_is_fine(self):
        self.assertNoRule("""\
            FROM eclipse-temurin:21-jdk AS build
            FROM eclipse-temurin:21-jre
            USER 1000
        """, "fat-final-base")


class TestUser(LintTestCase):
    def test_missing_user(self):
        self.assertRule("FROM debian:bookworm-slim\n", "root-user")

    def test_explicit_root(self):
        self.assertRule("FROM debian:bookworm-slim\nUSER root\n", "root-user")
        self.assertRule("FROM debian:bookworm-slim\nUSER 0:0\n", "root-user")

    def test_nonroot_base_without_user_is_fine(self):
        for base in ("gcr.io/distroless/static-debian12:nonroot",
                     "mcr.microsoft.com/dotnet/aspnet:8.0-noble-chiseled",
                     "nginxinc/nginx-unprivileged:alpine"):
            with self.subTest(base=base):
                self.assertNoRule(f"FROM {base}\n", "root-user")

    def test_named_user_on_scratch(self):
        self.assertRule("FROM scratch\nUSER app\n", "named-user-scratch")

    def test_only_final_stage_user_counts(self):
        self.assertRule("""\
            FROM debian:bookworm-slim AS build
            USER 1000
            FROM debian:bookworm-slim
        """, "root-user")


class TestRunInstructions(LintTestCase):
    BASE = "FROM debian:bookworm-slim\nUSER 1000\n"

    def test_apt_update_alone(self):
        self.assertRule(self.BASE + "RUN apt-get update\n", "apt-update-alone")

    def test_apt_recommends_and_lists(self):
        f = self.lint(self.BASE + "RUN apt-get update && apt-get install -y curl\n")
        self.assertTrue({"apt-recommends", "apt-lists"} <= self.rules(f))

    def test_apt_done_right(self):
        f = self.lint(self.BASE + textwrap.dedent("""\
            RUN apt-get update \\
             && apt-get install -y --no-install-recommends curl \\
             && rm -rf /var/lib/apt/lists/*
        """))
        self.assertFalse(self.rules(f) & {"apt-update-alone", "apt-recommends", "apt-lists"})

    def test_apt_lists_only_checked_in_final_stage(self):
        self.assertNoRule("""\
            FROM debian:bookworm-slim AS build
            RUN apt-get update && apt-get install -y --no-install-recommends gcc
            FROM debian:bookworm-slim
            USER 1000
        """, "apt-lists")

    def test_apk_without_no_cache(self):
        self.assertRule("FROM alpine:3.20\nUSER 1000\nRUN apk add curl\n", "apk-cache")
        self.assertNoRule("FROM alpine:3.20\nUSER 1000\nRUN apk add --no-cache curl\n", "apk-cache")

    def test_pip_cache_in_final_stage(self):
        self.assertRule("FROM python:3.12-slim\nUSER 1000\nRUN pip install flask\n", "pip-cache")
        self.assertNoRule("FROM python:3.12-slim\nUSER 1000\nRUN pip install --no-cache-dir flask\n",
                          "pip-cache")

    def test_npm_install(self):
        self.assertRule("FROM node:22-slim\nUSER node\nRUN npm install\n", "npm-install")
        self.assertNoRule("FROM node:22-slim\nUSER node\nRUN npm install -g pnpm\n", "npm-install")

    def test_sudo(self):
        self.assertRule(self.BASE + "RUN sudo ls\n", "sudo")


class TestCacheOrder(LintTestCase):
    def test_copy_all_then_install(self):
        self.assertRule("""\
            FROM node:22-slim
            COPY . .
            RUN npm ci
            USER node
        """, "cache-order")

    def test_add_all_then_install(self):
        self.assertRule("""\
            FROM python:3.12-slim
            ADD . .
            RUN pip install --no-cache-dir -r requirements.txt
            USER 1000
        """, "cache-order")

    def test_deps_before_copy_is_fine(self):
        self.assertNoRule("""\
            FROM node:22-slim
            COPY package.json package-lock.json ./
            RUN npm ci
            COPY . .
            RUN npm run build
            USER node
        """, "cache-order")

    def test_compile_after_copy_is_fine(self):
        self.assertNoRule("""\
            FROM golang:1.24 AS build
            COPY . .
            RUN go build -o /app .
            FROM scratch
            USER 10001
        """, "cache-order")

    def test_uv_two_phase_sync_is_fine(self):
        self.assertNoRule("""\
            FROM python:3.12-slim
            RUN --mount=type=bind,source=uv.lock,target=uv.lock uv sync --frozen --no-install-project
            COPY . .
            RUN uv sync --frozen
            USER 1000
        """, "cache-order")


class TestOtherRules(LintTestCase):
    def test_add_local_file(self):
        self.assertRule("FROM alpine:3.20\nUSER 1\nADD app.py /app/\n", "add-vs-copy")

    def test_add_url_or_tarball_is_fine(self):
        self.assertNoRule("FROM alpine:3.20\nUSER 1\nADD https://example.com/x /x\n", "add-vs-copy")
        self.assertNoRule("FROM alpine:3.20\nUSER 1\nADD rootfs.tar.gz /\n", "add-vs-copy")

    def test_secret_env_and_arg_are_errors(self):
        for line in ("ENV API_TOKEN=abc", "ENV DB_PASSWORD abc", "ARG AWS_SECRET_ACCESS_KEY",
                     "ARG GITHUB_TOKEN"):
            with self.subTest(line=line):
                f = self.lint(f"FROM alpine:3.20\nUSER 1\n{line}\n")
                self.assertIn("secret-in-build", self.rules(f, ("error",)))

    def test_non_secret_env_is_fine(self):
        self.assertNoRule("FROM alpine:3.20\nUSER 1\nENV PORT=8080 NODE_ENV=production\n",
                          "secret-in-build")

    def test_shell_form_cmd_and_entrypoint(self):
        self.assertRule("FROM alpine:3.20\nUSER 1\nCMD node server.js\n", "shell-form")
        self.assertRule("FROM alpine:3.20\nUSER 1\nENTRYPOINT /app\n", "shell-form")
        self.assertNoRule('FROM alpine:3.20\nUSER 1\nCMD ["node", "server.js"]\n', "shell-form")

    def test_maintainer(self):
        self.assertRule("FROM alpine:3.20\nUSER 1\nMAINTAINER dan\n", "maintainer")

    def test_missing_dockerignore(self):
        self.assertRule(GOOD_GO, "dockerignore", dockerignore=False)

    def test_missing_syntax_directive(self):
        self.assertRule("FROM alpine:3.20\nUSER 1\n", "syntax-directive")

    def test_single_stage(self):
        self.assertRule("FROM alpine:3.20\nUSER 1\n", "single-stage")

    def test_no_from(self):
        self.assertRule("RUN echo hi\n", "no-from")


class TestParsing(LintTestCase):
    def test_line_continuations_and_inline_comments(self):
        f = self.lint("""\
            FROM debian:bookworm-slim
            USER 1000
            RUN apt-get update \\
                # install tools
                && apt-get install -y curl
        """)
        self.assertIn("apt-recommends", self.rules(f))
        self.assertNotIn("apt-update-alone", self.rules(f))

    def test_heredoc_body_is_not_parsed_as_instructions(self):
        f = self.lint("""\
            # syntax=docker/dockerfile:1
            FROM debian:bookworm-slim
            RUN <<EOF
            USER root
            CMD echo not-an-instruction
            EOF
            USER 1000
        """)
        self.assertFalse(self.rules(f) & {"root-user", "shell-form"})

    def test_line_numbers_point_at_instruction_start(self):
        f = self.lint("FROM alpine:3.20\nUSER 1\n\nRUN apk add \\\n  curl\n")
        apk = [x for x in f if x.rule == "apk-cache"][0]
        self.assertEqual(apk.line, 4)


class TestCli(LintTestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(LINTER), *args],
                              capture_output=True, text=True)

    def test_exit_code_and_json(self):
        (self.dir / "Dockerfile").write_text("FROM alpine:3.20\nENV API_KEY=x\n")
        r = self.run_cli(str(self.dir / "Dockerfile"), "--json")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertTrue(any(d["rule"] == "secret-in-build" and d["severity"] == "error" for d in data))

    def test_clean_exit_zero(self):
        (self.dir / "Dockerfile").write_text(textwrap.dedent(GOOD_GO))
        (self.dir / ".dockerignore").write_text(".git\n")
        r = self.run_cli(str(self.dir / "Dockerfile"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("no issues found", r.stdout)

    def test_missing_file(self):
        self.assertEqual(self.run_cli(str(self.dir / "nope")).returncode, 2)


class TestReferenceTemplates(LintTestCase):
    """Every complete template in references/languages.md must lint without errors or warnings."""

    def test_templates_are_clean(self):
        text = (ROOT / "references" / "languages.md").read_text()
        blocks = re.findall(r"```dockerfile\n(.*?)```", text, re.S)
        self.assertGreater(len(blocks), 5)
        checked = 0
        for i, block in enumerate(blocks):
            if "...then a runtime stage" in block:
                continue  # intentionally partial snippet
            with self.subTest(template=i, first_line=block.splitlines()[0]):
                f = self.lint(block)
                bad = [x for x in f if x.severity in ("error", "warn")]
                self.assertEqual(bad, [], f"template {i} has findings: {bad}")
                checked += 1
        self.assertGreater(checked, 5)


if __name__ == "__main__":
    unittest.main()
