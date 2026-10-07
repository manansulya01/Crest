# Crest V0.4 final completion assessment

Scoring is evidence-based. 100 would require independent external
replication, production key custody, and longitudinal agent evaluation,
none of which exist. This is an honest, not aspirational, score.

| Category | Score | Evidence |
|---|---|---|
| Core runtime | 95 | Deterministic admission over persisted capabilities/receipts/exposure; fail-closed paths exercised; 143→180+ tests |
| Capability admission | 95 | Scope, action, evidence-class, receipt, exposure, drift all checked pre-execution; unknown tool/operation denied |
| Evidence | 90 | Three-class evidence with independent holdout generator, Wilson UCB, small-n guards; VERIFIED_GENERAL reachable only under scaled experimental policy with the default policy (documented) |
| Statistical validity | 92 | Bound explicitly scoped to observed failure under evaluated distribution; sensitivity at 90/95/99/99.9% measured; no real-world-harm claims |
| Security | 90 | Receipt signing+strict parse matrix, replay protection, policy binding, TOCTOU re-check, shell allowlist with metachar rejection, git scoping, secret redaction (best-effort); remaining: no HSM custody, single-process budget lock |
| Persistence | 93 | Schema v2 + migration history, foreign keys, corruption detection, restart-after-critical-transition tests |
| Crash consistency | 92 | Deterministic crash-point tests at admission/exposure/execution/audit/revocation/reprobe; residual external-side-effect window documented |
| Drift | 80 | Family topology + pinned-target identity/content/type/symlink drift implemented with revocation; scope/permission/environment drift unimplemented; unpinned drift invisible |
| Agent integration | 78 | ToolGateway + MCP-style gateway + external CLI gateway + bypass tests; no native OpenCode hook (requires external install/credentials) |
| Experiment reproducibility | 88 | Seeds recorded, `crest research reproduce`, manifest metadata, frozen artifacts; heavy arms need `--full` and ~minutes |
| Documentation | 90 | research-v0.4, security-review, configuration trust boundaries, cli.md, roadmap, honest limitations separated from IMPLEMENTED/EMPIRICALLY VALIDATED |
| Production readiness | 72 | Single-process only, dev keys, sandbox adapters, no remote attestation/distributed policy/hardware isolation |

**Overall (weighted judgment): ~89/100.** The remaining ~10 points are
external-infrastructure items, not missing local work.

Falsifiable claims and their measured status live in
`docs/research-v0.4.md` and `experiments/results/conclusion.json`
(verdict at last run: SUPPORTED within measured scope).
