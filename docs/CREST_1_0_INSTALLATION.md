# CREST 1.0 — Installation Guide

This guide covers the CREST 1.0 product layer (FastAPI API, React web app, and
offline mock provider). The research runtime remains available and installs
without the product extra.

## Prerequisites

- Python 3.11+ (validated on Python 3.12)
- Node.js 20+ and npm (only to build the web app)
- Windows, macOS, or Linux

## 1. Create an environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# POSIX
source .venv/bin/activate
```

## 2. Install CREST

From the repository root:

```bash
pip install -e ".[product]"
```

The `product` extra adds FastAPI, Uvicorn, and HTTPX. For the research runtime
only:

```bash
pip install -e .
```

Verify the install:

```bash
python -c "import crest, fastapi, uvicorn, httpx; print(crest.__version__)"
```

Expected: `1.0.0`.

## 3. Build the web app

```bash
cd web
npm install
npm run build
cd ..
```

The build writes `web/dist/`. The API serves it automatically. If you skip this
step, the API still starts and shows setup instructions at `/`.

## 4. Start the backend

```bash
python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> for the product site and
<http://127.0.0.1:8000/app> for the app. OpenAPI docs are at
<http://127.0.0.1:8000/api/docs>.

Check health:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected:

```json
{"status":"ok","version":"1.0.0","timestamp":"...","database":"ok"}
```

## 5. Or use the desktop launcher

```bash
python crest_desktop.py
```

The launcher starts the same local server and opens `/app` in the default
browser. It is **browser-based**, not a packaged native application. Set
`CREST_HOST` and `CREST_PORT` to change the bind address.

## 6. Data directory

The default is `~/.crest`. Override it before starting the server:

```bash
# Windows PowerShell
$env:CREST_DATA_DIR="C:\path\to\crest-data"

# POSIX
export CREST_DATA_DIR="$HOME/crest-data"
```

The directory contains `crest.db` and WAL files. Back up with
`GET /api/v1/export`; see `docs/PRODUCT_OPERATIONS.md`.

## 7. First offline run

1. Open **Offline demos**.
2. Run **Successful offline execution**: expect `Completed`, verification
   passed, gate `ACCEPT`.
3. Run **High-risk gate abstention**: approve the pending decision, then expect
   `abstained` and gate `ABSTAIN`. This is intentional: mock-only evidence is
   not independent evidence.

No provider keys and no network calls are needed. External calls are disabled
by default.

## 8. Optional external providers

External providers are disabled by default and were not live-validated in this
release.

1. Set the key in the **server process environment**, for example
   `GEMINI_API_KEY` for Gemini.
2. In **Providers**, enable the provider and configure models and pricing.
3. In **Settings**, enable `allow_external_calls`.
4. Set a small task budget and keep high-risk/external approval enabled.
5. Use **Test connection** explicitly before running a task.

Keys are read at call time and are never stored in SQLite or returned by the
API.

## 9. Research CLI

The original research runtime is unchanged:

```bash
cd your-project
crest init --root .
crest verify --action modify_file --recovery restore_from_snapshot --target README.md --scope '*'
crest exec filesystem modify_file --arg path=README.md --arg content='hello'
crest status
crest audit
```

See `docs/cli.md` for the full command reference.

## 10. Troubleshooting

- **Port in use:** stop the existing process or use `--port 8001`.
- **Missing product dependencies:** run `pip install -e ".[product]"`.
- **Blank page at `/app`:** build the frontend (`cd web && npm install && npm
  run build`) and reload.
- **401 Unauthorized:** `CREST_API_TOKEN` is set; enter the token in Settings or
  send a bearer token.
- **External provider denied:** check enablement, key presence,
  `allow_external_calls`, budget, and route.
- **Database errors:** back up, stop the server, and inspect diagnostics. Do not
  edit the database by hand.

For deeper guidance, see `docs/PRODUCT_GUIDE.md`,
`docs/PRODUCT_OPERATIONS.md`, and `docs/PRODUCT_API.md`.
