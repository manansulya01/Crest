# CREST 1.0 — Product Guide

CREST 1.0 is a local-first **outcome-constrained inference control plane** for
AI agents. It is the product layer built on top of the existing CREST research
runtime. Agents propose work; the engine decides whether execution is allowed,
records what happened, verifies the result, and can refuse to accept an outcome
it cannot support with sufficient independent evidence.

> Agents propose. Evidence decides.

CREST is **not** an unconditional safety guarantee. The tested posture is
Level 3 — supervised personal use on a single local machine. See
[`PRODUCT_OPERATIONS.md`](PRODUCT_OPERATIONS.md) for the operational boundary
and [`security-model.md`](security-model.md) for the research security model.

---

## 1. What ships in 1.0

| Component | Location | Purpose |
| --- | --- | --- |
| Product engine | `src/crest/product/` | Policy, planning, execution, budgets, approvals, verification, evidence, gate, audit |
| HTTP API | `src/crest/product/api.py` | FastAPI application, also re-exported as `crest.api:app` |
| Web app | `web/` | React 19 + React Router 7 single-page app |
| Public site | `web/src/pages/LandingPage.tsx` | Product site at `/` |
| Desktop launcher | `crest_desktop.py` | Starts the local server and opens the app in the default browser |
| Research runtime | `src/crest/` (existing) | Unchanged CLI, runtime, evidence, and experiment code |
| Tests | `tests/product/` | 39 product tests covering API, policy, budgets, approvals, gate, recovery, persistence, auth, export, interruption |

The default data directory is `~/.crest` (override with `CREST_DATA_DIR`). It
contains the SQLite database (`crest.db`) and WAL files.

---

## 2. Quickstart

### Requirements

- Python 3.11+
- Node.js 20+ (only to build the web app)

### Install

```bash
pip install -e ".[product]"
```

The `product` extra installs FastAPI, Uvicorn, and HTTPX. The research runtime
has no dependency on the product extra.

### Build the web app (once)

```bash
cd web
npm install
npm run build
cd ..
```

### Run

```bash
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The API serves the built web app when
`web/dist/` exists, including the public site at `/`, the app at `/app`, and
the OpenAPI docs at `/api/docs`.

Alternatively:

```bash
python crest_desktop.py
```

The desktop launcher is **browser-based**. It starts the same local server and
opens `/app` in your default browser. It is not a packaged native binary.

### First run offline

1. Open **Offline demos** in the app.
2. Run **Successful offline execution**. Expected: `Completed`, verification
   passed, gate `ACCEPT`.
3. Run **High-risk gate abstention**. The task first waits for approval. After
   you approve it, mock-only evidence is insufficient for the Strong High-Risk
   Gate, so the task ends `abstained` with gate `ABSTAIN`. The output is
   retained for inspection. This is the intended result, not a failure.

No provider keys and no network calls are required.

---

## 3. Core concepts

### Task

A unit of work with:

- title and description
- risk class: `low`, `med`, `high`
- autonomy level: 1–5
- provider and model route
- cost budget, token budget, and timeout
- acceptance criteria
- output format: `text` or `json`
- optional offline demo scenario
- optional custom policy at level 5

Task creation is validated server-side against global settings. Unknown fields
are rejected.

### Plan

A deterministic, persisted sequence of steps. Planning is always permitted;
each execution action is authorized separately. A plan does not grant
execution authority.

### Execution

One attempt to run a task. Executions record ordered steps, usage, errors,
timing, and cancellation state. If the process stops mid-run, startup recovery
marks unfinished executions `interrupted`; they are never reported complete.

### Evidence

Content-addressed records with SHA-256 hashes and provenance. Evidence kinds
include provider output, deterministic checks, verifier results, and gate
decisions. Each record carries an independence flag.

Hashing proves integrity, not origin and not truth. CREST does not sign
evidence with a key held outside the local process.

### Approval

A human decision bound to the current policy fingerprint. Approvals expire
after one hour, are single-use, and are invalidated when a task is edited.
Approving never bypasses verification or the gate.

### Gate decision

- `ACCEPT` — the outcome is accepted under the applicable evidence rules.
- `ABSTAIN` — CREST refuses to accept an outcome it cannot support; the output
  is retained for inspection.
- `REJECT` — the outcome is rejected.

For high-risk acceptance, the Strong High-Risk Gate requires independent
evidence. With mock-only evidence, the gate abstains by design.

---

## 4. Autonomy levels

The global ceiling defaults to **level 3**. New tasks default to **level 2**.
Levels 4 and 5 require explicit elevation in Settings or the Autonomy page.

| Level | Name | Behavior |
| --- | --- | --- |
| 1 | Observe | Plans and records intent. Provider calls are denied. |
| 2 | Assisted | Requires a fresh human approval before the provider call. |
| 3 | Bounded | Executes inside budgets, verification, and a bounded recovery limit. |
| 4 | Adaptive | Allows bounded adaptation inside the same budgets and gate. Requires elevation. |
| 5 | Custom | Adds an optional per-task policy that can only narrow permissions. Requires elevation. |

No level bypasses budgets, verification, approvals, or the gate. A task whose
autonomy exceeds the global ceiling is denied at creation and again at
execution.

### Custom policies (level 5)

Allowed keys:

- `allowed_actions`
- `allowed_providers`
- `allowed_models`
- `allowed_risk_classes`
- `require_approval`
- `max_cost`
- `max_tokens`
- `timeout_seconds`
- `notes`

Unknown keys and unknown actions fail closed. A custom policy can only narrow
what the global policy already allows.

---

## 5. Budgets and limits

Defaults:

| Setting | Default |
| --- | --- |
| Default cost budget | $1.00 per task |
| Maximum task budget | $10.00 |
| Default token budget | 4,096 |
| Maximum token budget | 32,768 |
| Default timeout | 60 s |
| Maximum execution time | 120 s |
| Recovery attempts | 1 |

Budgets are checked before the provider call and after the response. A task
that exceeds its cost or token budget ends `budget_exhausted`; no accepted
result is recorded. Cost accounting depends on per-provider pricing configured
by the operator. Unset pricing records $0 while token limits remain
authoritative.

---

## 6. Providers

| Provider | Kind | Default state | Network |
| --- | --- | --- | --- |
| Mock | `mock` | Enabled | None |
| Gemini | `gemini` | Disabled | External |
| OpenAI-compatible | `openai_compatible` | Disabled | External |

- API keys are read from process environment variables at call time. They are
  never written to SQLite, returned by the API, included in exports, or printed
  in audit detail.
- `allow_external_calls` is `false` by default. Enabling an external provider
  does not enable spending; external calls must also be allowed explicitly.
- Connection tests are explicit actions and are refused for external providers
  while external calls are disabled.
- Live external providers were **not** validated in this release. The tested
  execution path is the offline mock provider.

Provider configuration in the app covers enablement, base URL, key environment
variable name, models, default model, per-1K input/output pricing, maximum
output tokens, and timeout.

---

## 7. Routing

Routing rules map a risk class (or `*`) to a provider and model, with a
priority. The task's explicit provider/model is used first. Rules apply when a
task does not pin a route. Fallback is disabled by default. Provider
availability, key presence, external-call permission, and budgets are still
enforced after routing.

---

## 8. Verification and the gate

Verification is deterministic by default. Acceptance criteria support plain
text, `contains:`, `not_contains:`, and `regex:` forms. JSON output is parsed
and validated.

An optional provider-backed verifier can be configured. If the verifier uses
the same provider and model as the generator, the resulting evidence is
recorded as **not independent**.

Gate behavior:

- Low/medium risk: a passing verification can be accepted.
- High risk: approval is required first; acceptance additionally requires
  independent evidence.
- Failed verification is never reported complete; the gate records `REJECT`.
- Insufficient independent evidence produces `ABSTAIN`, not acceptance.

---

## 9. Offline demo scenarios

The mock provider is deterministic and makes no network calls. Demo scenarios
exercise real engine paths:

| Scenario | Expected path |
| --- | --- |
| Successful execution | Completed, verification passed, gate ACCEPT |
| Verification failure | Failed verification; never accepted |
| Recovery | First attempt fails, bounded retry succeeds, recovery recorded |
| Budget exhaustion | Pre-flight budget check stops before spending |
| Observe-mode denial | Level 1 plans but the provider call is denied |
| Assisted approval | Level 2 pauses before the provider call |
| High-risk gate abstention | Approval first, then ABSTAIN with output retained |
| Custom-policy denial | Level 5 policy allows planning only |

Every mock output is labelled as simulated. Simulated output is not evidence of
live model reliability.

---

## 10. Data, export, and retention

- SQLite in WAL mode, foreign keys on, integrity checks available in System.
- `GET /api/v1/export` returns a JSON backup without credentials.
- Soft delete hides a task; audit events remain.
- Retention is disabled by default. When enabled, `POST
  /api/v1/maintenance/purge?confirm=true` removes old records according to the
  configured retention window.

Back up the database before upgrades or destructive maintenance. See
[`PRODUCT_OPERATIONS.md`](PRODUCT_OPERATIONS.md).

---

## 11. Known limits

- Level 3 posture: supervised personal use, not a multi-tenant production
  service.
- Evidence is content-addressed but not signed.
- Live external providers were not validated.
- The desktop launcher is browser-based, not a native package.
- Cost accounting depends on operator-configured pricing.
- The frontend is a client. The engine is the authority; direct API calls are
  subject to the same policy.

For the full validation record, see
[`PRODUCT_COMPLETION_TRACKER.md`](PRODUCT_COMPLETION_TRACKER.md).
