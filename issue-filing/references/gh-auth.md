# gh auth for issue-filing

The filer calls `gh auth status` on every run as the first thing it
does. If auth is missing or expired, the filer exits with code 2 and
prints the stderr `gh` produced — don't swallow that error, it tells
you exactly what to fix.

## Required scopes

The filer uses `gh issue create` and `gh issue edit`, which need:

- `repo` (full repository scope) — covers both create and edit on
  public and private repos you own.

For a public-repo-only workflow (`public_repo`) and read-only access
to labels, `public_repo` alone is enough.

## Checking what you have

```
gh auth status --show-token
```

The output names the scopes attached to the token.

## Adding a scope

```
gh auth refresh --scopes repo
```

Prompts for the OAuth flow in a browser.

## Why we don't shell out beyond gh

Historically a filer like this would call the REST API directly with
`curl` and a PAT. The gh CLI handles auth refresh, rate-limit
backoff, retry on transient errors, and output formatting for us — so
we stay on top of it rather than reinventing the pieces.
