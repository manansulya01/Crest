# Crest runtime architecture (v0)

Layers: agent -> gateway -> runtime (normalize, capability registry, receipt
validation, exposure controller, constitutional admission, execution guard,
observation, audit) -> adapters (filesystem/git/shell).

- `agent_runtime.CrestRuntime` is the only path from agent requests to adapters.
- **Evidence is graded**: `VERIFIED_FIXTURE` / `VERIFIED_FAMILY` /
  `VERIFIED_GENERAL` via `GeneralizationVerifier` (`fixtures` seeds split into
  train + verify, holdout evaluated separately). Classification only
  strengthens with cross-family holdout success; fixture receipts never become
  family/general without a fresh verifier pass.
- `DriftDetector` compares the evidence family (`single_file`,
  `directory_tree`, ...) against the actual workspace layout on every
  execution and revokes on full mismatch.
- Adapters require an `AdapterContext` issued only after admission; constructing
  an adapter by hand with `context=None` fails closed.
- Constitutional policy (`CrestConfig`) is frozen; only file edits plus restart
  change it, never agent requests.
- Evidence (receipts) comes only from `Verifier` runs; agents never write them.
- Every decision writes audit events before execution and after observation.
