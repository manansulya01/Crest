# CREST Product Discovery — Baseline

## Repository state (verified)

- HEAD: `cf3fbe8e61cc4c748052bdc812e8e13f22ee4a41`
- Branch: `feat/crest-v0.4-research-complete`
- Working tree: clean
- Full test suite: 368 passed

## Implemented capabilities (verified against code)

### Inference runtime (`src/crest/inference.py`)
- `InferencePolicy`: model allowlists, token/character limits, abstract cost units,
  window budgets, retry policy, timeout, usage requirements.
- `InferenceRuntime.infer()`: request validation → model allowlist → duplicate check →
  budget reservation (conservative, never refunded) → adapter call (with retries) →
  response validation → usage recording → audit trail.
- `HttpChatAdapter`: OpenAI-compatible transport (live, verified against Gemini).
- `FakeModelAdapter`: deterministic test adapter.
- Budget enforcement: `Store.try_begin_inference` (atomic at SQLite level).
- Usage ledger: `inference_requests` table (reservation, usage, status, digest).
- Unknown-cost tracking: `cost_known` flag, `usage_reported` on responses.
- Retry logic: `max_attempts`, `retry_on_transient`, `retry_backoff_seconds`.
- Response validation: model match, usage presence, token limits, finish reason,
  non-empty output, request_id match.

### What is NOT implemented
- No CLI command for inference (Python API only).
- No multi-tenant budget hierarchy (per-key/per-user/per-team).
- No streaming support.
- No distributed execution or distributed budget enforcement.
- No semantic verification (only schema/structural checks).
- No audit export or financial reporting.
- No cost reconciliation with provider billing.

### Verified live functionality
- `gemini-3.5-flash-lite`: 10/10 tasks correct, usage reported, cost_known=True.
- `gemini-3.8-flash`: unavailable (read timeout).

### Verified fake/simulated functionality
- 368 tests passing (inference, benchmark, validation, security).
- Fake-mode benchmark: 50% cost reduction at equal quality (circular — see
  docs/v0.9-simulation-audit.md).
- Non-circular simulation: CREST does not beat cost-aware baseline
  (admission too conservative; cheap model unreliable).

### Key experimental findings
1. Routing hypothesis NOT supported (non-circular simulation, 5 signal strengths × 5 seeds).
2. Admission rule is mathematically sound but too conservative for unreliable models.
3. Fake-mode 50% advantage was circular (routing feature = failure predictor).
4. Cascade (verify-then-escalate) with structural verification adds nothing over
   cost_aware because structural checks can't detect semantic errors.
5. Prior art (FrugalGPT, Hybrid LLM, RouteNLP) shows LLM routing is well-studied;
   CREST's contribution is not in the routing algorithm.

### Current decision
PIVOT (from routing to verification/constrained execution as potential product wedge).
