# CREST 1.0 — Operations Guide

This guide covers installation, running, configuration, backup, retention, and
troubleshooting for the CREST 1.0 product layer. It assumes a single trusted
operator on a local machine.

## 1. Supported posture

- Security posture: **Level 3 — supervised personal use**.
- Bind to `127.0.0.1`. Do not expose the API to a network without a reverse
  proxy, TLS, authentication, and a separate security review.
- External provider calls and spending are disabled by default.
- The tested execution path is the offline mock provider. Live external
  providers were not validated in this release.

## 2. Requirements

- Python 3.11+ (validated on Python 3.12)
- Node.js 20+ and npm (only for building the web app)
- SQLite 3.35+ (bundled with Python)

## 3. Install

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# POSIX:   source .venv/bin/activate
pip install -e ".[product]"
```

The product extra installs FastAPI, Uvicorn, and HTTPX. If you only need the
research runtime, `pip install -e .` is sufficient.

### Build the web app

```bash
cd web
npm install
npm run build
cd ..
```

The build writes `web/dist/`. The API serves it automatically. If `web/dist`
is missing, the API still starts and shows setup instructions at `/`.

### Fresh-install check

```bash
python -c "import crest, fastapi, uvicorn, httpx; print(crest.__version__)"
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000/api/v1/health>. Expected: `status: ok`,
`version: 1.0.0`, `database: ok`.

## 4. Run

```bash
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

or:

```bash
python crest_desktop.py
```

The desktop launcher starts the same server and opens `/app` in the default
browser. It is browser-based, not a native binary.

### Frontend development

```bash
# terminal 1
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000

# terminal 2
cd web
npm run dev
```

Vite serves on port 5173 and proxies `/api` to `127.0.0.1:8000`.

## 5. Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `CREST_DATA_DIR` | `~/.crest` | Database and WAL location |
| `CREST_API_TOKEN` | unset | Require a bearer token on API routes except health |
| `CREST_HOST` | `127.0.0.1` | Desktop launcher bind address |
| `CREST_PORT` | `8000` | Desktop launcher port |
| `CREST_CORS_ORIGINS` | localhost/127.0.0.1 dev origins | Comma-separated allowed origins |
| `CREST_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver,::1` | Trusted Host middleware |
| `VITE_API_BASE` | empty (same origin) | Build-time API base for a separately hosted frontend |
| `GEMINI_API_KEY` | unset | Gemini adapter key, read at call time |
| `OPENAI_API_KEY` | unset | Default key env for the OpenAI-compatible adapter; configurable per provider |

Provider API keys are never stored in SQLite, returned by the API, included in
exports, or written to audit detail.

Application settings (autonomy ceiling, budgets, provider enablement, routing,
retention, external-call permission, verifier configuration) are managed in the
app and persisted in SQLite.

## 6. Backup

Use the API export:

```bash
curl -s http://127.0.0.1:8000/api/v1/export > crest-backup.json
```

Or copy the SQLite database while the server is stopped:

```bash
# stop the server first
cp ~/.crest/crest.db ~/.crest/crest.db.bak
```

A live copy of a WAL database must include `crest.db-wal` and `crest.db-shm`,
or use SQLite's online backup API. The JSON export is the simplest consistent
backup and never contains credentials.

## 7. Upgrade

1. Back up with `GET /api/v1/export`.
2. Stop the server.
3. Update the code and reinstall: `pip install -e ".[product]"`.
4. Rebuild the web app: `cd web && npm install && npm run build`.
5. Start the server. Migrations run automatically.
6. Check `/api/v1/health` and `/api/v1/diagnostics`.

There is no in-place rollback tooling. Restore from the backup if a migration
fails.

## 8. Retention and purge

Retention is disabled by default. When enabled in Settings:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/maintenance/purge?confirm=true"
```

When retention is disabled, the endpoint requires `force=true`. Purging is
destructive; back up first.

## 9. Troubleshooting

### Port already in use

```text
[Errno 10048] only one usage of each socket address
```

Use another port (`--port 8001`) or stop the existing process. On Windows:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
```

### Product dependencies missing

```text
CREST's product dependencies are not installed.
```

Run `pip install -e ".[product]"` from the repository root.

### Web app not built

The API starts, but `/` shows setup instructions and `/app` is unavailable.
Run `cd web && npm install && npm run build`.

### 401 Unauthorized

`CREST_API_TOKEN` is set on the server. Enter the token in Settings, or send
`Authorization: Bearer <token>`.

### External provider denied

Check, in order:

1. The provider is enabled.
2. Its key environment variable is present in the server process.
3. `allow_external_calls` is enabled.
4. The task budget covers the call.
5. The route points at the provider and model you expect.

### Task is `awaiting_approval`

Open **Approvals** or the task detail page. Approvals expire after one hour and
are invalidated by task edits.

### Task `abstained`

This is a successful refusal. Inspect the gate reason and evidence. A
high-risk task with mock-only evidence will always abstain; rerun with stronger
independent evidence if you need acceptance.

### `budget_exhausted`

The pre-flight estimate or the response exceeded the cost/token budget. Raise
the budget within the global maximum, or use a smaller model.

### Database integrity warning

Open **System** and run diagnostics. If integrity fails, stop the server and
restore from a backup. Do not edit the database by hand.

### Interrupted tasks after a crash

Startup recovery marks unfinished executions `interrupted`. Re-run the task
explicitly; CREST never silently resumes or reports it complete.

## 10. Security hygiene

- Keep the server bound to `127.0.0.1`.
- Set `CREST_API_TOKEN` if other local users can reach the port.
- Leave external calls disabled until you have configured pricing and budgets.
- Review approvals and abstentions rather than treating them as noise.
- Do not put credentials in task descriptions or acceptance criteria.
- Treat evidence hashes as integrity checks, not signatures.
- Report security issues privately through the repository security policy.
