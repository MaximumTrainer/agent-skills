# KG agent-systems mini review

Repo: sdlc-knowledge-graph

## Gap: freshness marker on context packs

Context packs don't carry an as-of timestamp, so an agent reading one
can't tell whether a fact is current or stale. Agents need a published
freshness marker on every pack, and a query API that lets a caller
reject packs older than a specified bound.

Area: ontology. Size: M. Type: feature.

## Gap: OPA policy hook for connector reads

Connector reads aren't guarded by OPA policy. Need a hook that
evaluates each read request against a policy bundle, with the bundle
reference pinned per-connector and a decision log emitted for audit.

Area: security. Size: M. Type: feature.
