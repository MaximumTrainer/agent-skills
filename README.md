# agent-skills

A consolidated collection of agent skills distilled from the engineering practices across the [MaximumTrainer](https://github.com/MaximumTrainer) projects.

Each directory is a self-contained skill: a `SKILL.md` with YAML frontmatter (`name`, `description`) and a body of procedural guidance. Copy a directory into `.claude/skills/` in any repository — or into `~/.claude/skills/` to make it available everywhere — and the agent will load it when its description matches the task.

## Why these exist

Reviewing 27 repositories in this space turned up the same practices being reinvented independently: outside-in TDD in nine of them, ports-and-adapters in eight, documentation drift guards in five, the same Intervals.icu API quirks handled in six. Where a repo already had skills, they were local to that repo and referenced its own file paths, so none of the knowledge travelled.

The skills here are the **portable** version of that knowledge. Most of the specific detail in them was paid for once already — a silent slot that never fired, an HRV reading 60 days stale, five tests passing against an emulator that never started — and is written down so it is not paid for again.

## The skills

### Core engineering practice

| Skill | Use when |
|---|---|
| [outside-in-tdd](outside-in-tdd/) | Implementing a feature or bug fix test-first; "do issue N"; reviewing whether a change was actually test-driven |
| [hexagonal-architecture](hexagonal-architecture/) | Adding a feature, endpoint, repository or integration; deciding where a class belongs; a domain class importing a framework type |
| [verify-and-ship](verify-and-ship/) | Pushing, opening a PR, merging, shipping; "verify the build is green" |
| [ci-failure-triage](ci-failure-triage/) | The build is red; "is main broken"; a flaky test |
| [single-source-constants](single-source-constants/) | A displayed value contradicts behaviour; adding a threshold; "why does it say X when it does Y" |
| [deliberate-decisions](deliberate-decisions/) | Before "fixing" something odd-looking; after making a non-obvious choice |
| [kotlin-idioms](kotlin-idioms/) | Writing or reviewing Kotlin on Spring Boot/JPA; a `!!` in a diff; ktlint or detekt failing |

### Specification and tracking

| Skill | Use when |
|---|---|
| [spec-by-example-issue](spec-by-example-issue/) | Elaborating a thin issue into requirements and acceptance criteria; picking up the next piece of work |
| [gap-issue](gap-issue/) | Closing work with something unverified; "create issues for anything incomplete"; reconciling a backlog |
| [docs-drift-guard](docs-drift-guard/) | Changing docs; a stale website; a README describing a removed feature |
| [engineering-white-paper](engineering-white-paper/) | Writing up an engineering practice, kata or facilitation guide |

### Testing integrity

| Skill | Use when |
|---|---|
| [test-theatre-audit](test-theatre-audit/) | Auditing whether a suite actually runs; a bug shipped past a green build |
| [container-integration-tests](container-integration-tests/) | Testing an adapter against a real database or emulator; replacing mocks with the real thing |
| [api-quirk-fixtures](api-quirk-fixtures/) | Live data disagrees with the code; a schema rejects a real payload |
| [live-api-probe](live-api-probe/) | Confirming behaviour against a real third-party account, safely |
| [synthetic-test-data](synthetic-test-data/) | Building fixtures or seed data; masking a dataset; tempted to copy a production record |

### Platform-specific

| Skill | Use when |
|---|---|
| [minimal-docker](minimal-docker/) | Writing, optimising or hardening a Dockerfile; containerising an app |
| [connect-iq-monkeyc](connect-iq-monkeyc/) | Garmin Connect IQ / Monkey C; FIT developer fields; BLE on a watch |
| [qt6-cross-platform](qt6-cross-platform/) | Qt6 C++ desktop or WASM; Qt5 migration; AppImage packaging |
| [three-best-practices](three-best-practices/) | Three.js scenes, WebGL/WebGPU, geometries, materials, shaders, TSL |
| [r3f-best-practices](r3f-best-practices/) | React Three Fiber and the Poimandres ecosystem |
| [screenshot-verify](screenshot-verify/) | A change touches the UI; screenshotting an app; regenerating doc screenshots |

### Integrations

| Skill | Use when |
|---|---|
| [intervals-icu-api](intervals-icu-api/) | Reading or writing Intervals.icu data; training and fitness analysis on it |
| [mcp-server-tools](mcp-server-tools/) | Writing or adding a tool to an MCP server; designing its tool surface |

### Reuse across repositories

| Skill | Use when |
|---|---|
| [skill-exchange](skill-exchange/) | Seeded into every other repo: check this catalogue before writing a new skill, vendor what fits, send general improvements back |

`skill-exchange` is the meta-skill. Seed it into any repository and it pulls from
here and contributes back, so a lesson learned in one repo reaches the others.

```bash
mkdir -p .claude/skills/skill-exchange/scripts
curl -fsSL https://raw.githubusercontent.com/MaximumTrainer/agent-skills/main/skill-exchange/SKILL.md   -o .claude/skills/skill-exchange/SKILL.md
curl -fsSL https://raw.githubusercontent.com/MaximumTrainer/agent-skills/main/skill-exchange/scripts/skills.py   -o .claude/skills/skill-exchange/scripts/skills.py

python3 .claude/skills/skill-exchange/scripts/skills.py list
python3 .claude/skills/skill-exchange/scripts/skills.py pull outside-in-tdd
python3 .claude/skills/skill-exchange/scripts/skills.py status
```

[`catalogue.json`](catalogue.json) is what seeded repos read. It is **generated**
from the SKILL.md files by `tools/build_catalogue.py`, and CI fails if it drifts
— the same derived-with-a-drift-check pattern [docs-drift-guard](docs-drift-guard/)
describes. Never edit it by hand; rebuild it after changing any skill.

## Using a skill

```bash
# one skill, in one project
cp -r outside-in-tdd /path/to/project/.claude/skills/

# everything, everywhere
cp -r */ ~/.claude/skills/
```

The agent selects a skill by matching its `description` against the task, so no invocation is needed — though `/outside-in-tdd` style invocation works where the harness supports it.

The skills cross-reference each other by name in their *Related skills* sections. They are designed to compose: `outside-in-tdd` leans on `hexagonal-architecture` for the structure that makes fast tests possible, and hands off to `verify-and-ship` at the end; `api-quirk-fixtures` is fed by `live-api-probe` and constrained by `synthetic-test-data`.

## Provenance

| Source | What came from it |
|---|---|
| `SdlcKnowledgeGraph` | The verify-gate / land-pr sequence; generated-website drift checking; outside-in commit discipline |
| `SilverSprint` | The API-quirk loop; constant drift; live-account probing; the screenshot capture traps |
| `chorus` | Shipping and green-main; backlog reconciliation; requirement-id traceability |
| `synthetic-fabricate` | Test-theatre patterns; Testcontainers emulator practice; gap issues; docs/HTML twins |
| `freelap-intervals` | Outside-in rings; typed errors; non-negotiables; the deliberate-decisions register |
| `garmin-freelap` | Connect IQ and Monkey C; inject-don't-fetch; honest reporting of unverifiable work |
| `MaximumTrainer_Redux` | Qt6 migration and packaging; headless screenshot verification; three-document sync |
| `OpenFactstore`, `Waymark`, `OpenDataMask`, `paved-road` | Ports and adapters; the dependency rule; red-green-refactor |
| `OpenDataMask`, `OpenFactstore`, `SdlcKnowledgeGraph` | Kotlin conventions; the detekt/Kotlin version coupling |
| `virtualrow` | `three-best-practices` and `r3f-best-practices`, consolidated unchanged |
| `llm-cad`, `Intervals-Gemini-Fitness-Intel` | MCP tool design; sandboxing model-authored code |
| `white-papers` | The practice white-paper structure |
| `OpenDataMask`, `synthetic-fabricate` | Synthetic data, masking discipline, canary secrets |

## Conventions

- One directory per skill; **the directory name matches the frontmatter `name`** so it is drop-in for `.claude/skills/`.
- `description` in the third person, saying what the skill does *and* when to use it, with the phrases a user would actually type.
- Bodies are imperative and specific. Concrete commands over general advice; a named failure mode over a warning.
- Where a rule exists because something broke, the body says what broke. That is what stops the rule being "simplified" away.
- `references/`, `scripts/` and `assets/` subdirectories only where they carry weight — see `minimal-docker/` for the fullest example.
- Every skill carries `evals/evals.json`, and every eval marks at least one **discriminating** expectation — one the skill alone should produce.

## Measuring whether a skill earns its keep

A skill's value is the difference it makes, not how good it reads. Each eval runs the same task twice — with the skill and without — and the number that matters is the **delta**.

This is not a formality. Measured across 26 skills, **eight produce no measurable difference at all**: the model already writes `InstancedMesh`, caps the pixel ratio, and reaches for a distroless base unprompted. The skills that do earn their keep change an *ordering* or a *default* rather than supplying a fact — `hexagonal-architecture` scores +67% because it puts the outbound port before the adapter and the in-memory fake before the real one.

> Facts are in the weights. Orderings are not.

**[docs/EVALUATING.md](docs/EVALUATING.md)** is the procedure and, more usefully, the reasons — every one of which is a mistake made here first, usually one that produced a confident wrong number before it was caught.

## Versioning

Each skill carries a semver `metadata.version` in its frontmatter. A `pre-commit`
hook bumps it automatically for every skill a commit touches.

```bash
bash tools/install-hooks.sh        # once per clone
```

Hooks live in `.githooks/` (tracked) rather than `.git/hooks/` (not cloned), so
each clone opts in once by pointing `core.hooksPath` at them.

### What it does

A skill is any top-level directory containing a `SKILL.md`. When a commit on the
version branch stages any file inside one — `SKILL.md`, a reference, a script —
that skill's patch version is bumped and `SKILL.md` is re-staged into the same
commit.

| Situation | Behaviour |
|---|---|
| Edit to a skill's files | Patch bump, in the same commit |
| Brand-new skill | Keeps the version it declares; a first commit is not a bump |
| Version already changed by hand in the commit | Left alone — the manual value wins |
| Only the version line changed | Left alone, so the hook cannot bump in a loop |
| Commit touches no skill | Nothing happens |
| Commit on any other branch | Nothing happens |

```bash
SKILL_BUMP=minor git commit -m "feat: add a section"   # minor instead of patch
SKILL_BUMP=major git commit -m "feat!: restructure"    # major
SKILL_VERSION_SKIP=1 git commit -m "wip"               # hook runs, no bump
git commit --no-verify -m "wip"                        # hook does not run
```

Configure the branch, or version on every branch:

```bash
git config skills.versionBranch main     # default
git config skills.versionBranch ""       # every branch
```

### Manual and CI use

```bash
python3 tools/bump_skill_versions.py --check                 # validate all versions (CI)
python3 tools/bump_skill_versions.py --staged --dry-run      # what would a commit bump?
python3 tools/bump_skill_versions.py --all --level minor      # bump every skill
python3 -m unittest discover -s tests -v                      # 35 tests, incl. real commits
```

### Two limitations worth knowing

- **`pre-commit` is the only hook that can do this.** `prepare-commit-msg` and
  `commit-msg` both stage into the *next* commit and leave a dirty index, so
  neither can amend the commit being created. That is also why the bump level
  comes from `SKILL_BUMP` rather than a conventional-commit prefix — `pre-commit`
  never sees the commit message.
- **A PR merge does not fire it.** `pre-commit` does not run for merge commits, so
  if work reaches `main` through a merged pull request the bump has to happen on
  the branch — which it does, if you set `skills.versionBranch` to `""` or to your
  working branch. Amending also re-bumps, because git does not tell `pre-commit`
  that a commit is an `--amend`; use `SKILL_VERSION_SKIP=1` when amending.

## Licence

MIT — see [LICENSE](LICENSE).
