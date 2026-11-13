# CREST 1.0 — HTTP API

The product API is a FastAPI application exposed as `crest.api:app`. All
product routes live under `/api/v1`. Interactive OpenAPI documentation is
served at `/api/docs`; the schema is at `/api/openapi.json`.

## Run

```bash
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

## Authentication

By default the API is unauthenticated and bound to `127.0.0.1`. Set
`CREST_API_TOKEN` on the server to require a bearer token on every `/api/`
route except `/api/v1/health`:

```bash
export CREST_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

```http
Authorization: Bearer <token>
```

The web app reads an optional token from `localStorage` under `crest.token`.
The token is never stored server-side.

## Error format

Errors use FastAPI's standard shape:

```json
{ "detail": "task is already queued or running" }
```

| Status | Meaning |
| --- | --- |
| 400 | Invalid request or state transition |
| 401 | Missing or invalid bearer token |
| 404 | Unknown task, evidence, or route |
| 409 | Conflict (already running, no pending approval, duplicate idempotency key) |
| 422 | Validation failure or policy/limit rejection |
| 502 | Provider failure |

Policy denials can also produce a persisted task with status `denied` while the
HTTP call returns an error; fetch the task to inspect the reason.

---

## Health and diagnostics

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness, version, database status. Never requires auth. |
| GET | `/api/v1/diagnostics` | Runtime, database integrity, provider, and safety state. |
| GET | `/api/v1/system/info` | Version, platform, data directory, frontend build state, posture. |

## Tasks

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/tasks` | Create a task. |
| GET | `/api/v1/tasks` | List tasks. Filters: `status`, `risk_class`, `search`, `limit` (1–200), `offset`. |
| GET | `/api/v1/tasks/{id}` | Full task with plan, executions, evidence, approvals, events. |
| PATCH | `/api/v1/tasks/{id}` | Edit a task. Resets pending state and expires approvals. |
| DELETE | `/api/v1/tasks/{id}` | Soft delete by default; `?hard=true` removes the record. |
| POST | `/api/v1/tasks/{id}/plan` | Generate and persist a deterministic plan. |
| POST | `/api/v1/tasks/{id}/execute` | Execute. `?wait=true` waits for the terminal state. |
| POST | `/api/v1/tasks/{id}/approve` | Approve or reject a pending decision. |
| POST | `/api/v1/tasks/{id}/cancel` | Cooperative cancellation. |
| GET | `/api/v1/tasks/{id}/events` | Audit events for a task. |
| GET | `/api/v1/tasks/{id}/evidence` | Evidence records for a task. |
| GET | `/api/v1/tasks/{id}/report` | Download a JSON task report. |

### Create a task

```http
POST /api/v1/tasks
Content-Type: application/json

{
  "title": "Summarize the release notes",
  "description": "Return a short summary.",
  "risk_class": "low",
  "autonomy_level": 2,
  "provider": "mock",
  "model": "mock-fast",
  "budget": 1.0,
  "token_budget": 4096,
  "timeout_seconds": 30,
  "acceptance_criteria": ["CREST"],
  "output_format": "text",
  "demo_scenario": null,
  "custom_policy": null,
  "idempotency_key": null
}
```

Fields:

- `title` (required, 1–200 characters)
- `description` (0–10,000 characters)
- `risk_class`: `low` | `med` | `high`
- `autonomy_level`: 1–5, subject to the global ceiling
- `provider`, `model`: optional; defaults come from settings
- `budget`: > 0, ≤ 1,000,000; defaults to the configured default
- `token_budget`: > 0, ≤ 10,000,000
- `timeout_seconds`: > 0, ≤ 3,600
- `acceptance_criteria`: up to 20 strings
- `output_format`: `text` | `json`
- `demo_scenario`: `verification_failure` | `recovery` | `approval_required` | null
- `custom_policy`: object; only valid at level 5
- `idempotency_key`: optional; a repeated key returns the existing task

Unknown fields are rejected (`extra="forbid"`).

### Execute

```http
POST /api/v1/tasks/{id}/execute?wait=true
```

Without `wait`, the call returns after queuing and the task runs on the engine's
executor. With `wait=true`, the call blocks until the terminal state and returns
the task. A task that needs approval returns `{ "task": ..., "approval": ...,
"status": "awaiting_approval" }`.

Terminal task statuses: `completed`, `failed`, `abstained`, `denied`,
`budget_exhausted`, `cancelled`, `rejected`, `interrupted`, `timed_out`.

### Approve or reject

```http
POST /api/v1/tasks/{id}/approve
Content-Type: application/json

{
  "decision": "approve",
  "note": "Reviewed the scope",
  "start_execution": true,
  "wait": true
}
```

`decision` is `approve` or `reject`. Approvals are bound to the policy
fingerprint, expire after one hour, and are single-use.

## Providers and routing

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/providers` | Provider configuration and status. Never returns secrets. |
| GET | `/api/v1/models` | Flattened model catalog with availability and pricing. |
| PUT | `/api/v1/providers/{id}` | Update name, enablement, base URL, key env var, models, pricing, limits. |
| POST | `/api/v1/providers/{id}/test` | Explicit connection test. Requires `confirm: true`; external providers require external calls enabled. |
| GET | `/api/v1/routing` | Rules and fallback setting. |
| PUT | `/api/v1/routing` | Replace rules. |

Provider status values: `ready`, `disabled`, `key_missing`. The response
includes `key_present` but never the key itself.

## Settings and autonomy

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/settings` | Current settings and ceilings. |
| PUT | `/api/v1/settings` | Update settings with server-side validation. |
| GET | `/api/v1/autonomy/levels` | Level descriptions, permission matrix, and current ceiling. |

`PUT /api/v1/settings` rejects unknown fields and inconsistent values (for
example, a default budget above the maximum task budget).

## Evidence, audit, approvals, budgets

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/evidence` | Filters: `task_id`, `kind`, `status`, `search`, `limit`, `offset`. |
| GET | `/api/v1/evidence/{id}` | Full evidence record with content and hash. |
| GET | `/api/v1/audit` | Filters: `task_id`, `event_type`, `search`, `limit` (1–1000), `offset`. |
| GET | `/api/v1/approvals` | Filter by `status`; paginated. |
| GET | `/api/v1/stats/overview` | Dashboard aggregates and recent activity. |
| GET | `/api/v1/budgets/summary` | Limits, totals, and per-task usage. |

## Backup and maintenance

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/export` | Full JSON backup without credentials. |
| POST | `/api/v1/maintenance/purge?confirm=true` | Apply the retention policy. `force=true` is required when retention is disabled. |

## Minimal end-to-end example

```bash
BASE=http://127.0.0.1:8000

TASK=$(curl -s -X POST "$BASE/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API smoke test",
    "description": "Offline execution",
    "risk_class": "low",
    "autonomy_level": 2,
    "provider": "mock",
    "model": "mock-fast",
    "budget": 1,
    "token_budget": 4096,
    "timeout_seconds": 30,
    "acceptance_criteria": ["CREST"]
  }' | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -X POST "$BASE/api/v1/tasks/$TASK/execute?wait=true" | python -m json.tool
```

Expected: the task ends `completed`, verification `passed`, gate `ACCEPT`, and
the result is labelled as offline mock output.

For a high-risk task, execution first returns `awaiting_approval`. Approving it
leads to `abstained` with gate `ABSTAIN` because mock evidence is not
independent.
