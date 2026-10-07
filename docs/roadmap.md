# Roadmap

Done in V0.4: independent holdout generator, distribution shifts, policy-driven
evidence classification with configurable confidence, replay protection,
receipt v2 with Ed25519 signatures and dev-key store, schema migrations,
crash-consistency tests, MCP-style gateway, secret redaction, doctor
diagnostics, experiment runner + tables + conclusion, pinned-target
content/identity/type drift, config-tamper fail-closed parsing, verifier
gaming regression tests.

Remaining (genuinely unfinished):

- Probabilistic (seeded-random) sampling across families, not deterministic
  seed increments
- More environment families (git, databases, containers, network)
- Production receipt key custody (HSM/KMS) and remote attestation
- Drift classes still unimplemented: scope drift, permission drift,
  environment drift (content/identity/type/topology drift ARE implemented
  and revoke on detection)
- Composition verification as an admission gate (currently measurement only)
- Multi-process exposure accounting (single-process lock today)
- Longitudinal evaluation against real agent workloads
