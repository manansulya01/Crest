# CREST 1.0 — Product Architecture

CREST 1.0 adds a product layer beside the existing research runtime. The
research runtime (`src/crest/agent_runtime.py`, `runtime.py`, `gateway.py`,
`store.py`, `verifier.py`, adapters, CLI, experiments, and their tests) is
unchanged and remains available.

## Layers

```text
Browser
  ├─ Public site        /  /docs  /security
  └─ Product web app    /app/*
          │  JSON over HTTP
          ▼
FastAPI application     src/crest/product/api.py  (crest.api:app)
          │
          ▼
Product engine          src/crest/product/engine.py
  ├─ settings.py        typed, validated global settings
  ├─ policy.py          autonomy, permissions, custom policies
  ├─ planner.py         deterministic plans
  ├─ providers.py       mock, Gemini, OpenAI-compatible adapters
  ├─ verification.py    deterministic checks + optional verifier
  ├─ db.py              SQLite WAL persistence and migrations
  └─ Strong High-Risk Gate
          │
          ▼
SQLite                  ~/.crest/crest.db  (CREST_DATA_DIR overrides)
```

The frontend is a client, not an authority. Every control is re-checked in the
engine. A modified browser, a direct HTTP call, or a stale page cannot grant
authority the engine does not allow.

## Request flow

1. **Create** — validate fields, global autonomy ceiling, provider route,
   budgets, output format, custom policy, and risk/approval requirements.
2. **Plan** — persist a deterministic plan. Planning is allowed even in
   observe mode.
3. **Authorize** — `authorize_action` checks the autonomy level, the global
   ceiling, the task's custom policy (level 5), provider availability, key
   presence, external-call permission, and budgets.
4. **Approve** — if required, persist a pending approval bound to the current
   policy fingerprint and set the task to `awaiting_approval`.
5. **Execute** — record an execution and ordered steps; call the provider with
   cost/token/time limits; account for usage.
6. **Recover** — on a recoverable verification failure, retry up to the
   configured limit. Recovery never bypasses verification or the gate.
7. **Verify** — run deterministic checks (plain text, `contains:`,
   `not_contains:`, `regex:`, JSON parsing) and optionally a provider-backed
   verifier. Independence is recorded.
8. **Gate** — for high-risk acceptance, require independent evidence. If it is
   insufficient, `ABSTAIN` and retain the output for inspection.
9. **Audit** — persist every state transition, policy decision, approval,
   provider call, verification, gate decision, and setting change. Redaction
   runs before persistence.

## Persistence

SQLite in WAL mode with foreign keys enabled and a 15-second busy timeout.
Migrations are tracked in `schema_migrations`; `PRAGMA user_version` is set.

| Table | Contents |
| --- | --- |
| `settings` | JSON values for declared keys only |
| `providers` | Provider configuration; never API keys |
| `tasks` | Task definition, status, usage, result, verification, gate |
| `plans` | Persisted plans and steps |
| `executions` | Attempts with status, timing, errors, usage |
| `execution_steps` | Ordered step records |
| `evidence` | Content-addressed records, hashes, provenance, independence |
| `approvals` | Decisions bound to policy fingerprints |
| `audit_events` | Append-only product audit trail |
| `routing_rules` | Risk-class routing and fallback |

Task deletion is soft by default; audit events remain. Startup calls
`recover_interrupted()` so unfinished executions become `interrupted`, never
`completed`.

## Policy model

`policy.py` defines five levels. Each has default allowed actions. The global
ceiling defaults to 3; new tasks default to 2. Higher autonomy expands what the
agent may attempt but never removes budgets, approvals, verification, or the
gate.

Custom policies at level 5 accept only a fixed key set and a fixed action set.
Unknown keys or actions fail closed. A custom policy can only narrow
permissions.

## Providers

- **Mock** — deterministic, offline, no keys. Supports demo scenarios that
  exercise failure, recovery, budget, approval, and gate paths.
- **Gemini** — reads its key from an environment variable at call time.
- **OpenAI-compatible** — configurable base URL, key environment variable, and
  models.

External calls are disabled by default. A provider can be `disabled`,
`key_missing`, or `ready`. Pricing is operator-configured; unset pricing records
$0 while token limits remain authoritative.

## Evidence and the gate

Evidence records carry a SHA-256 hash, kind, status, task and execution ids,
source type/id, independence flag, and timestamps. Hashing provides integrity,
not authenticity. CREST does not sign evidence with an externally held key.

The Strong High-Risk Gate is a narrow veto: it can refuse acceptance, but it
cannot manufacture acceptance. With mock-only evidence it abstains for
high-risk tasks.

## Web application

React 19, React Router 7, TypeScript, Vite, and a custom CSS design system with
light/dark themes. There is no external UI component library.

- Public: `/`, `/docs`, `/security`, 404.
- App: `/app` (dashboard), tasks, new task, task detail, approvals, autonomy,
  providers, routing, evidence, audit, budgets, demos, settings, system.
- All API access goes through `web/src/lib/api.ts`.
- An optional bearer token is stored in `localStorage` under `crest.token`.
- The built app is served by FastAPI from `web/dist` with an SPA fallback.
- Vite dev mode proxies `/api` to `127.0.0.1:8000`.

## Desktop launcher

`crest_desktop.py` starts the local FastAPI server and opens `/app` in the
default browser. It is a convenience launcher, not a native package. It warns
when `web/dist` has not been built.

## Trust boundaries

In scope: one trusted operator, a local machine, localhost binding, and tasks
created through the local API.

Partially addressed: multi-process SQLite access, local browser threats,
sensitive task content retention, and optional bearer authentication.

Out of scope: multi-tenant isolation, remote untrusted users, signed
attestations, provider supply-chain guarantees, and an attacker who already
controls the host or Python process.
