# Roadmap

Done in V0.4: independent holdout generator, distribution shifts, policy-driven
evidence classification with configurable confidence, replay protection,
receipt v2, schema migrations, crash-consistency tests, MCP-style gateway,
secret redaction, doctor diagnostics, experiment runner + tables + conclusion.

Remaining (genuinely unfinished):

- Probabilistic (seeded-random) sampling across families, not deterministic
  seed increments
- More environment families (git, databases, containers, network)
- Receipt signatures and key lifecycle management
- Drift classes still unimplemented: content drift, scope drift, symlink
  topology, git state drift
- Composition verification as an admission gate (currently measurement only)
- Multi-process exposure accounting (single-process lock today)
- Longitudinal evaluation against real agent workloads
