# Evaluating a skill

A skill's value is the difference it makes, not how good it reads. This
document is the procedure for measuring that difference, and the reasons each
step is the way it is. Every reason below is a mistake that was actually made
here, usually one that produced a confident wrong number first.

## What is being measured

For each eval, the same task runs twice — once with the skill in the sandbox,
once without — and both answers are graded against the same expectations. The
number that matters is the **delta**. A high with-skill pass rate means nothing
on its own; the baseline model is strong and clears most expectations unaided.

Only expectations marked `discriminating` are graded. An expectation both arms
satisfy measures the model, not the skill, and averaging it in drags every
delta toward zero.

## The procedure

```bash
# 1. Stage. Both arms get the fixture; only one gets the skill.
python3 tools/stage_eval.py --workspace WS --all-for SKILL [SKILL ...]

# 2. Run. One agent per PROMPT.txt, each confined to its own sandbox.
#    The agent must not read this repository.

# 3. Write the blinded keys and print the judge prompts (two per eval).
python3 tools/make_judge_keys.py WS --prompts

# 4. Judge. One agent per prompt. Judges do not see the skill.

# 5. Aggregate.
python3 tools/aggregate_evals.py WS --json benchmark.json
```

## Why each step is like that

### The sandbox contains a real repository

Isolation was introduced because a baseline run wandered the working directory,
read `container-integration-tests/SKILL.md`, and answered using the skill it was
supposed to be blind to.

The fix overshot. Staging an **empty** directory removed the task along with the
contamination, and **eight skills measured +0%** under it. A skill that changes
an *ordering* — read the issue before writing code, check the existing fixtures
before inventing one, diff the aggregate script against the workflow — cannot
bite when there is nothing to read. Both arms answer from the prompt alone and
converge on the same essay.

So an eval may name a `fixture` from `eval-fixtures/`, copied into both arms
identically. The fixtures carry the properties being measured on purpose:

| Fixture | Carries |
|---|---|
| `kotlin-service` | concrete service injected into a controller, `!!` on an `Optional`, a test that asserts `!= null`, README band table that disagrees with the code |
| `ts-frontend` | `setState` in `useFrame`, whole-store subscription, uncapped `devicePixelRatio`, `scene.remove` with no dispose, a `verify` script that omits the `format:check` CI runs |
| `py-service` | `ENV DATABASE_PASSWORD`, fat base image, `10 MB` in the docs against `20 * 1024 * 1024` in config, `30 seconds` against `45000` ms |
| `node-integration` | an existing `docs/API-QUIRKS.md` and `tests/fixtures/`, oldest-first wellness rows read as `rows[0]` |
| `qt-desktop` | auto-slot bound to a removed Qt5 signal signature, AppImage packaging with no off-machine verification |
| `connectiq-app` | unguarded web-request payload, UINT32 read into a signed value |

**An eval with no `fixture` runs bare, deliberately.** A prompt carrying its
subject inline, or one that is pure authoring, gains nothing from scenery, and
scenery invites the runner to wander.

### Grading is by blind judge, never by pattern

Regex grading was the instrument's weakest joint and produced results that were
simply wrong:

- `code-review` scored **−50%** because the pattern was narrower than the
  response. The answer *did* satisfy the expectation, in different words.
- Re-grading 15 runs with judges moved two skills by more than **30 points in
  opposite directions** — so the error was not a consistent bias that cancels.

`make_judge_keys.py` writes `JUDGE.json` beside each eval with the arm labels
shuffled, so a judge reading only the key and the two `response.md` files cannot
tell which is which. It also prints the rubric, so the rubric is versioned here
rather than retyped per run — retyping is how a rubric drifts between the runs
you are comparing.

### Two judges, and disagreements are printed

A single judge decided several published results by a whisker, and in three
cases said so unprompted. Two judges now grade every eval. Where they split, the
expectation scores a half **and is listed as contested** — because a contested
expectation is a badly written expectation, and the wording is what needs
fixing, not the arithmetic.

`aggregate_evals.py` also lists any run that got only one judge, so a soft
number cannot be quoted as a hard one.

### Expectations must not punish the skill's own advice

The sharpest lesson here. `outside-in-tdd` measured **−17%**: the baseline
asserted an observed test failure in a sandbox with no repository to run
anything in, and the with-skill arm refused — *"these are predictions, not
observations."*

**The skill taught the honest answer and the expectation scored it wrong.**

So: before adding an expectation, ask *would following this skill cause an
answer to fail this?* If it might, rewrite it to accept the honest form. The
judge rubric carries the same rule, and `check_evals.py` requires at least one
discriminating mark per eval.

## What a good expectation looks like

- **Specific enough to grade.** "The response is helpful" is not gradeable.
- **Discriminating.** If you cannot imagine the baseline failing it, it belongs
  in `expectations` but not in `discriminating`.
- **About an ordering or a default, not a fact.** Facts are in the weights.
  `hexagonal-architecture` scores +67% because it changes the *sequence* —
  outbound port before adapter, in-memory fake before the real one. The skills
  measuring zero are the ones restating well-published best practice that the
  baseline produces unprompted every time.

## Reading the output

```
eval                     with       without    delta
hexagonal-architecture-2  2/2 100%      0/2 0%    +100%
```

- A **half** in the passed column means the two judges split on one expectation.
- `non-discriminating expectations` — passed in both arms. Retarget or unmark them.
- `contested expectations` — the judges disagreed. Rewrite the wording.
- `single-judge runs` — only one opinion. Treat that delta as soft.

## Decay

Every number is against one model at one date. `three-best-practices` almost
certainly *did* lift when it was written; it measures zero now because the model
improved, not because the skill got worse.

**Skill value decays silently and nothing else here detects it.** Nothing in the
repository would tell you: the frontmatter is valid, the evals pass, CI is green,
and the SKILL.md is accurate. It has simply stopped being needed.

So each model version gets a committed benchmark, and the next one is diffed
against it:

```bash
python3 tools/aggregate_evals.py WS --model claude-opus-5 \
    --json benchmarks/claude-opus-5.json

python3 tools/diff_benchmark.py benchmarks/claude-opus-5.json \
                                benchmarks/claude-opus-6.json
```

The output is a worklist, not a score:

| Verdict | Meaning | Action |
|---|---|---|
| `DECAYED` | lift has fallen to roughly nothing | Shrink to whatever the model still does not do, or reduce to a stub |
| `WEAKER` | lift dropped but has not reached zero | Read the responses; find what the skill stopped adding |
| `IMPROVED` | lift rose | Usually the skill was edited. Occasionally the model regressed — worth knowing which |

A shift below `--threshold` (default 10%) is not reported. Two judges over three
evals do not resolve five points, and **treating noise as decay is how a good
skill gets deleted.**

This is the expected end state for a skill that taught a *fact* rather than an
*ordering*. Facts arrive in the weights eventually. That is not a failure of the
skill; it is the skill having been overtaken, and the honest response is to
shrink it rather than to keep shipping it.
