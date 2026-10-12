# KG auth XL review

Repo: sdlc-knowledge-graph

## Gap: identity, auth and policy for KG reads/writes

The KG has no identity or auth model. Reads and writes need a signed
principal, a scope, and a policy decision before they land. The work
is too large to ship as one issue — it should land as a walking
skeleton with each slice independently useful.

Area: security. Size: XL. Type: foundation.

### Slices

- AUTH-1: Signed-principal plumbing on read path, deny-by-default (Size: M)
- AUTH-2: Scope model and token exchange from identity provider (Size: M)
- AUTH-3: Policy decision point wired to AUTH-1 reads (Size: M)
- AUTH-4: Write path signed principal + policy (Size: M)
- AUTH-5: Decision log + audit export (Size: S)
