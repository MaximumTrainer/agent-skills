---
name: verify-and-ship
description: Run the same checks CI runs before pushing, open the pull request, then confirm the CI run on the default branch is genuinely green. Use whenever asked to push, commit and push, open a PR, merge, ship, land, or "verify the build is green" after a change, and when asked whether a change would pass CI. Covers reproducing each CI job locally in cost order, the commands whose exit code lies about success, why the run on main — not the one on the PR — is what proves the work landed, and deleting the merged branches safely once it has.
license: MIT
metadata:
  version: "1.1.0"
---

# Verify, then ship

Work is not shipped when the code is written, and not when the pull request is green. It is shipped when the CI run **on the default branch** has passed. Everything before that is a prediction.

Two failure modes this skill exists to prevent: pushing something that CI will reject, costing a round trip of five to fifteen minutes; and reporting success from a command that exited zero without having verified anything.

## 1. Reproduce the gate locally, in cost order

Read `.github/workflows/*.yml` and run the same jobs in the same order. Run them cheapest first and stop at the first failure — there is no value in discovering a lint error after a twelve-minute end-to-end suite.

A typical order:

```bash
# 1. Commit messages — cheapest to fail, most annoying to fix (needs a rebase)
npx --no-install commitlint --from origin/main --to HEAD

# 2. Static analysis and unit tests — per component
cd backend  && ./gradlew check --console=plain
cd frontend && npm run verify

# 3. Anything `verify` does not cover but CI does
cd frontend && npm run format:check

# 4. End-to-end — only when the change touches the API surface, the UI or the stack
docker compose up -d --build --wait
cd e2e && npx playwright test
docker compose down -v
```

**Check what the aggregate script actually covers.** A `verify` or `check` script often omits one job that CI runs — commonly `format:check`, a coverage threshold, or a matrix dimension. Diff the workflow against the script rather than trusting the script's name. This is the single most common cause of a push that fails CI after a locally green run.

### Sweeps the default run does not do

If CI runs a matrix and you ran one cell, you have not run the gate. The dimensions that actually catch things:

- **Timezone.** Run the suite under at least one negative and one positive offset, and one with a half-hour offset. Date-boundary logic passes in UTC and fails in `Pacific/Chatham`.
  ```bash
  for tz in UTC America/Los_Angeles Australia/Sydney Pacific/Chatham; do
    TZ=$tz npm test -- --run || echo "FAILED under $tz"
  done
  ```
- **Locale**, where any formatting or parsing is involved.
- **The other operating system**, where paths, line endings or a native dependency are involved.
- **Clean install**, where a lockfile changed: `npm ci`, not `npm install`.

### When a local run cannot really run

If Docker is unavailable, container-backed integration and acceptance suites did not run — they reported "skipped" or passed vacuously. Say that, rather than reporting the build as green. A claim of green that CI then contradicts is worse than saying a suite was not checked.

On Windows, Testcontainers needs the Docker Desktop named pipe or every container test fails with "Could not find a valid Docker environment":

```bash
DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine ./gradlew check --console=plain
```

Run `docker context ls` for the endpoint if that pipe name does not exist. A Docker failure looks like a wall of failing tests but is not a code failure — read the `Caused by` before believing it.

## 2. Commit

- Conventional type, and the issue reference if the repo's `commitlint` requires one: `feat(backend): record split times from the chip (#42)`.
- One logical step per commit. If this change was driven test-first, the red and green commits stay separate — see `outside-in-tdd`.
- Never `--no-verify`. If a hook fails, the hook is right.
- Do not commit build output, credentials, developer keys, `*.der`, captures containing identifying data, or anything the `.gitignore` was written to exclude. Grep before committing when the change went near credentials:
  ```bash
  git diff --cached | grep -nEi 'api[_-]?key|secret|password|token\s*[:=]|BEGIN [A-Z ]*PRIVATE KEY'
  ```

## 3. Push a branch, not the default branch

```bash
git push -u origin <branch>
```

Do not push to the default branch directly, even where nothing mechanically prevents it. The CI run on the default branch is usually a *push* trigger, so a direct push turns a broken build into a broken default branch, and the next person to clone inherits it.

## 4. Open the pull request

```bash
gh pr create --fill --title "<what now works>" --body-file <path>
```

Fill in the template honestly. Where it asks for the commit SHAs of each outside-in step — the red acceptance commit, the red API commit, the green implementation commit — take them from `git log --oneline`; a reviewer uses them to check the red-then-green sequence. **If the implementation was written before the tests, say so in the PR** rather than implying a sequence the history does not show.

Tick acceptance criteria only where they are true. Where a criterion was verified manually, record the step and its actual result. Where one was not verified at all, say so and file it — see `gap-issue`.

## 5. Wait for the checks

```bash
gh pr checks --watch
```

If a job fails, read the real failure rather than guessing:

```bash
gh run view <id> --log-failed
```

Fix it on the branch. Do not merge around a failing job, and do not weaken the check to make it pass. See `ci-failure-triage`.

## 6. Merge

```bash
gh pr merge --merge
```

Match the repository's existing history. Where the red-then-green commits are the audit trail, keep `--merge` — squashing destroys the evidence that the sequence happened. Where the history is linear, squash.

## 7. Confirm the default branch is green

Merging starts a **second** CI run, on the default branch. The work is not landed until that one passes:

```bash
gh run list --branch main --limit 1
gh run watch <id>
```

Report the conclusion of *that* run, not the PR's. They differ more often than people expect: the merge can combine two independently green branches into a broken main, and the default-branch workflow often runs jobs the PR workflow skips — deployment, publishing, a release build.

If it fails, say so plainly and fix forward.

### The exit code that lies

`gh run watch` and some `gh` subcommands **exit non-zero on a run that concluded successfully**, and some exit zero while a run is still in progress. Do not infer the result from the exit status. Read the conclusion explicitly:

```bash
gh run list --branch main --limit 1 --json conclusion,status,displayTitle,url
```

Treat `"conclusion": "success"` as the only evidence of success. `status: in_progress` with no conclusion is not a pass, and `cancelled`, `skipped` and `neutral` are not passes either.

Where a repository has more than one workflow on the default branch, check **each** of them. A green test workflow beside a red publish workflow is not green.

## 8. Clean up, once — and only once — main is green

A merged branch is evidence until the default branch has proved the merge. Until
then it is the thing you rebuild from if the merge has to come out, so **do not
delete anything while the default-branch run is still going**.

Once it has concluded `success`:

```bash
# Remote branches: `gh pr merge --delete-branch` already removed them. Confirm,
# rather than assuming — a protected branch or a failed delete leaves it behind.
git ls-remote --heads origin

# Local tracking refs for branches the remote no longer has
git remote prune origin --dry-run     # read it first
git remote prune origin

# Local branches whose work is genuinely in main
git branch --merged main | grep -v '^\*\|main'
```

`--merged main` is the whole safety property, and it is worth understanding why:
a branch is listed only when its tip is an ancestor of `main`, so everything on
it is already there. Delete with `-d`, never `-D`:

```bash
git branch --merged main | grep -v '^\*\|main' | xargs -r git branch -d
```

`-d` refuses a branch that is not merged. `-D` deletes it anyway, and the only
copy of the work with it. If `-d` refuses, that refusal is information — find
out what is on the branch before overriding it.

**A squash merge breaks this.** Squashing rewrites the commits, so the branch tip
is *not* an ancestor of `main` and `--merged` will not list it even though every
line landed. `-d` will refuse it, correctly by its own rule and unhelpfully by
yours. Confirm the work is in main by diffing against it, then delete
deliberately:

```bash
git diff --stat main..<branch>       # empty means main already has it all
git branch -D <branch>               # only after that diff is empty
```

Closing the pull requests is not a separate step: merging closes them. A PR
still showing "open" after a merge means the merge did not happen — check
before reporting it as landed.

## Reporting

Say which jobs ran, which passed, and which did not really run. Name the workflow and conclusion you actually read. If a suite was skipped because a dependency was unavailable, say that instead of folding it into an overall green.

## Related skills

- `ci-failure-triage` — when the default branch is already red
- `outside-in-tdd` — the commit sequence the PR template asks you to evidence
- `gap-issue` — recording a criterion that shipped unverified
- `docs-drift-guard` — the documentation check that belongs in this gate
