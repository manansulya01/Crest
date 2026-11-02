# Technical Validation — Verified Execution Runtime

## Hypothesis

CREST's fail-closed execution (invalid output → denied, with auditable evidence trail)
provides a measurable advantage over a simple "call model + Pydantic validate + retry"
baseline in terms of (a) invalid outputs that are silently treated as successful,
and (b) completeness of the audit trail.

## Experiment design

### Task
Structured extraction: given a text, extract a JSON object with required fields.
Some model responses will be malformed (missing fields, wrong types, invalid JSON).

### Baseline (simple approach)
1. Call model.
2. Parse JSON. If parse fails → retry (up to 3).
3. Validate with Pydantic schema. If invalid → retry (up to 3).
4. If all retries exhausted → return last response (even if invalid).
5. No audit trail.

### CREST approach
1. Call model through InferenceRuntime.
2. Runtime validates response (request_id match, model match, usage, token limits,
   finish reason, non-empty output).
3. If validation fails → denied (not successful). Audit record created.
4. Retry via runtime's retry policy.
5. If all retries exhausted → denied. Audit record created.
6. Full audit trail (request_id, model, usage, attempts, status, digest).

### Measurement
- Invalid outputs silently treated as successful: count per strategy.
- Retry count: per strategy.
- Audit completeness: does every attempt have a record? (CREST: yes by construction;
  baseline: no).
- Cost: total tokens consumed (including retries).
- Latency: total wall-clock time.

### Provider
Fake provider (FakeModelAdapter) with configurable failure modes. Live provider
not available for the strong model; cheap model (gemini-3.5-flash-lite) is
available but the experiment is designed for the fake provider to test the
mechanism.

### Status
PROTOCOL WRITTEN. Experiment to be run with fake provider. Live verification
blocked (strong model unavailable).

### Why this tests differentiation
The key question is: does CREST's fail-closed execution catch invalid outputs
that a simple "retry and hope" approach would silently accept? If the model
returns invalid JSON that happens to parse but has wrong field values, the
baseline (Pydantic schema check) would catch it — but only if the developer
implemented the check. CREST enforces it by default.

The differentiator is not the validation itself (Pydantic does that) but the
combination of: (a) fail-closed by default, (b) audit trail for every attempt,
(c) budget enforcement during retries, (d) unknown-cost honesty.
