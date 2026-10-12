# Label sync between repo-profiles.yaml and GitHub

The filer's preflight compares each draft's labels against the live
set returned by `gh label list --repo <repo>`. If a draft label isn't
on the repo, preflight fails with `LabelMismatch`, exit 2, and the
list of offending `<slug>: <label>` pairs on stderr.

## What usually goes wrong

- The profile in `issue-drafting` lists a label the repo hasn't been
  updated to carry yet. → Add the label on the repo via `gh label
  create` or the Settings UI, then re-run.
- The profile and the repo are out of step on namespacing (e.g. KG
  uses `area:security` but the repo was initialised with just
  `security`). → Rename on the repo with `gh label edit` so one
  convention wins; then update the profile if the repo's form is the
  one you want.
- A label was added to the profile and vendored into other repos but
  the repo you're filing to was missed. → `gh label clone <template-repo>
  --repo <target-repo>` is the fast way to copy a label set.

## Why not auto-create missing labels

Because labels encode decisions: that `priority:P0` means "drop
everything", that `size:XL` must be split before filing. Auto-creating
labels from drafts would let a typo in a draft silently add
`priotity:P0` to the repo. The filer prefers an explicit
`gh label create` as a separate operation.

## When the live label list is empty

The mock's default is an empty label list — in that case the preflight
skips the check (nothing to compare against). The real `gh` returns
an empty list only when the token can't read the repo at all, which
would already have failed `gh auth status`.
