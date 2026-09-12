---
name: deliberate-decisions
description: Keep and consult a register of choices that look like bugs and are not, plus dormant code that must not be extended, so an agent or a new contributor does not "fix" them in passing. Use before fixing something odd-looking, when a design appears wrong or inefficient, when tempted to simplify code that has a comment saying not to, when closing work that diverged from its spec, and when asked why the code does something surprising. Check the register before fixing; add to it when you make a non-obvious choice.
license: MIT
metadata:
  version: "1.0.0"
---

# Deliberate decisions — do not "fix" these

Every mature codebase contains choices that look wrong and are right. Left undocumented, each one gets "fixed" by the next person, breaks something subtle, and gets reverted — often more than once, because the revert does not explain anything either.

This is a sharper problem with coding agents than with people. An agent reads the local code, sees something that violates a general best practice, and has both the confidence and the speed to change it. It does not have the two hours of debugging that produced the odd-looking line. A register is how that context survives.

The rule is symmetrical:

> **Before changing something that looks wrong, check whether it is recorded as deliberate. After choosing something that looks wrong, record it.**

## Check before you fix

When you encounter code that appears to be a defect, an inefficiency or an oversight, look for the decision before writing the fix. In rough order of speed:

```bash
# the usual locations
sed -n '/Deliberate decisions\|Decisions that differ\|Known dormant\|What NOT to do/,/^## /p' README.md AGENTS.md CLAUDE.md 2>/dev/null
ls docs/adr/ docs/decisions/ 2>/dev/null

# a comment at the site
rg -n -B2 -A4 'deliberate|on purpose|intentional|do not "?fix|DO NOT|do not simplify|leave this' <file>

# has it been fixed and reverted before?
git log --oneline -S '<the odd expression>' -- <file>
git log --oneline --grep='revert' -- <file>

# was it specified, argued, or rejected?
gh issue list --state all --search '<keyword>'
```

`git log -S` is the highest-value check and the most skipped. A line that has been added, removed and re-added is a line somebody already learned about the hard way, and the commit message that restored it usually explains why.

Then:

- **Recorded as deliberate** → leave it. If you disagree, argue it in the issue or the ADR, not in a passing commit.
- **Recorded as a known gap** → it is already tracked. Do not re-file it, and do not "discover" it as a defect. See `gap-issue`.
- **Not recorded, and you are confident it is wrong** → fix it, and add a test that pins the correct behaviour.
- **Not recorded, and you are unsure** → ask, or leave it and say what you found. An unexplained oddity you flagged is more useful than an unexplained oddity you changed.

**A known gap is not a defect you discovered.** Filing it again, or reporting it as a new finding, wastes the reader's attention and makes your other findings less credible.

## The four kinds of entry

A register mixes four distinct things. Label them, because the correct response differs.

### 1. Decided — looks wrong, is chosen

A real design choice, made with reasons, that a reader will want to undo.

```markdown
### Rep wall clocks are read as rep *starts*, not rep ends

The design document describes the chip's wall clock as the moment the rep ended.
Against a real chip it is the moment the rep *started*; treating it as the end
shifted every split by the rep duration. Verified to ±1.0 s in both modes.
Do not "correct" this back to match the design document — the document is wrong
and is noted as such.
```

### 2. Constrained — looks wrong, is forced

Imposed by a platform, a dependency, a licence or an external system. Nothing to argue about; it needs to be known so nobody spends an afternoon on it.

```markdown
### The FIT recorder defers setData/addLap by one timer tick

Lap and session developer fields are dropped if `setData()` and `addLap()` run
in one path with no yield. The deferral is load-bearing. Do not "simplify" it
away; the fields silently vanish from the file, and the file still validates.
```

### 3. Dormant — present, unmaintained, do not extend

Code that still builds and still passes its tests, and is on its way out.

```markdown
### FreelapProtocol.mc / PacketAssembler.mc — retired in #61

These describe a connection-oriented protocol the chip does not speak. They
build and their tests pass. Do not add to them, do not reference them from new
code, and do not document them in the user guide.
```

This category matters more than it looks: an agent asked to add a feature will happily extend the dormant module, because it is the one whose name matches the request. Say so explicitly, and say where new code should go instead.

### 4. Provisional — chosen for now, with a trigger

A knowingly temporary choice, with the condition that should end it.

```markdown
### Email-only sign-in with a signed cookie, standing in for real auth

Adequate for a single-athlete deployment. Revisit when there is a second
tenant, or before any public deployment. Tracked in #34.
```

Give it a **trigger**, not a date. "Before the first external user" is actionable; "Q3" is not.

## Writing an entry

Four things, and the third is the one people omit:

1. **What the code does** that looks wrong — in the reader's words, as they will encounter it.
2. **Why** — the reason, concretely. Not "for performance": *what* was slow, measured how.
3. **What happens if you change it** — the failure mode, specifically. This is what stops the change, because it is what a reader can check. "The fields silently vanish from the file, and the file still validates" does more work than any amount of "please don't".
4. **Where to argue it** — the issue or ADR number.

Two rules of thumb:

- **Put it at the site and in the register.** A one-line comment at the code (`// deliberate — see ADR-0007: the yield is load-bearing`) is what the next reader will actually see; the register is where it is explained. Neither alone is enough: the comment has no room for the reason, and the register is not open when someone is editing the line.
- **Prefer a test over prose where the behaviour can be pinned.** A test named `deferSetDataByOneTick_soLapFieldsSurvive` both documents the decision and enforces it. Prose asks for cooperation; a failing test does not. Where such a test exists, reference it from the entry.

## Where the register lives

Use what the repository already has rather than adding a fifth location:

| Location | Good for |
|---|---|
| `README.md` § *Decisions that differ from the design doc* | A short list in a small repo; highly visible |
| `AGENTS.md` / `CLAUDE.md` § *Do not* / *What NOT to do* | Agent-facing, read at the start of every session |
| `docs/adr/NNNN-*.md` | Substantial architectural decisions with context and consequences |
| Issue labelled `decision` or `wontfix` | Something actively argued; keeps the discussion attached |
| A comment plus a named test | Anything mechanically enforceable |

Keep one canonical location per repository and cross-reference into it. Four half-registers is the failure mode, and it is the common one.

ADRs are **append-only**: supersede an entry with a new one that references it, never edit the original. The superseded reasoning is how a reader understands why the decision changed.

## Pruning

A register that only grows stops being read. Review it when the surrounding code changes:

- **Dormant** entries are removed when the code is removed. Actually remove the code — a dormant module that has been dormant for a year is a maintenance cost and an invitation.
- **Provisional** entries are resolved when their trigger fires. Check them when the trigger's condition changes, not on a calendar.
- **Constrained** entries are removed when the constraint lifts — a dependency upgrade, a platform version. Note the version in the entry so this is checkable.
- **Decided** entries are permanent, unless genuinely revisited and superseded.

## Checklist

**Before changing something odd-looking:**

- [ ] Checked README / AGENTS / CLAUDE / ADRs for an entry
- [ ] Checked for a comment at the site, and `git log -S` for a previous fix-and-revert
- [ ] Checked the issue list, including closed and `wontfix`
- [ ] If recorded: left it alone, and argued it in the issue if I disagree
- [ ] If unrecorded and unclear: flagged it rather than changed it

**After making a non-obvious choice:**

- [ ] Entry added to the one canonical register, labelled decided / constrained / dormant / provisional
- [ ] States what it does, why, and what breaks if changed
- [ ] A comment at the site points at the entry
- [ ] A test pins the behaviour where that is possible
- [ ] Provisional entries have a trigger, not a date

## Related skills

- `gap-issue` — for something open and unverified, as opposed to settled
- `docs-drift-guard` — keeping the dormant list out of the user-facing guide
- `single-source-constants` — for a *value* that looks wrong and is chosen
- `spec-by-example-issue` — checking the register before specifying a "fix"
- `engineering-white-paper` — the long-form version of a decision worth explaining at length
