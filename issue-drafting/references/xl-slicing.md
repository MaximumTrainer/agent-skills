# Walking-skeleton slicing for size:XL

## The rule

If you can see a gap is XL at review time, you've already lost the
option of filing it as one issue. Split it before it's filed, not after
it's blocked for three months.

## The split heuristic

Ask: *what is the smallest change that moves the system from "no
support for X" to "support for X, in a thin but end-to-end way"?*

That is the first child. The remaining children thicken or widen the
skeleton without changing its shape.

For AUTH on the KG (fixture: `fixtures/reviews/auth-xl.md`):

- **AUTH-1** — Signed-principal plumbing on the read path, deny-by-default.
  Thin end-to-end: an unauthenticated read now fails. No scopes, no
  policy, no audit. The skeleton is standing.
- **AUTH-2** — Scope model and token exchange from the identity provider.
  The skeleton can now describe who's asking.
- **AUTH-3** — Policy decision point wired to the reads from AUTH-1.
  The skeleton can now decide whether to answer.
- **AUTH-4** — Same, write path.
- **AUTH-5** — Decision log and audit export. The skeleton can now be
  reviewed after the fact.

Each child's acceptance criteria stand alone. AUTH-3 doesn't require
AUTH-2 to ship — it can ship against hardcoded scopes and be rewired
when AUTH-2 lands. That independence is what makes the split a walking
skeleton rather than a sequential plan.

## The signal the split is wrong

Any of these is a smell:

- Child N's Gherkin uses a term that only exists after Child M (M > N
  conceptually) lands. → Reorder or merge.
- A child "just does the groundwork" with no observable behaviour. →
  Fold it into the next child that actually ships observable behaviour.
- The children can only ship in a fixed sequence. → You've split the
  task, not the system. Try again.

## Writing the Slices subsection

In the review:

```markdown
## Gap: identity, auth and policy for KG reads/writes

<prose body stating the gap>

Area: security. Size: XL. Type: foundation.

### Slices

- AUTH-1: Signed-principal plumbing on read path, deny-by-default (Size: M)
- AUTH-2: Scope model and token exchange from identity provider (Size: M)
- AUTH-3: Policy decision point wired to AUTH-1 reads (Size: M)
- AUTH-4: Write path signed principal + policy (Size: M)
- AUTH-5: Decision log + audit export (Size: S)
```

The parser recognises `### Slices` under a `Size: XL` gap and the
renderer emits one parent + N children, each carrying its sized label
and `parent: <parent-slug>`.
