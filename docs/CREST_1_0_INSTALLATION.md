# CREST 1.0 — Installation Guide

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend build, optional)

## Install

```bash
pip install -e .
```

## Initialize

```bash
mkdir my-project && cd my-project
crest init --root .
```

## Start the backend

```bash
uvicorn crest.api:app --host 127.0.0.1 --port 8000
```

## Open the dashboard

Open http://127.0.0.1:8000 in your browser.

Or use the desktop launcher:

```bash
python crest_desktop.py
```

## Build the frontend (optional)

```bash
cd web && npm install && npm run build
```

The built frontend is served automatically by the backend if `web/dist/` exists.

## Configuration

Edit `crest.yaml` in your project directory. Key settings:
- `budget`: maximum exposure budget
- `provider`: model provider (default: mock)
- `autonomy_level`: 1-5

## Troubleshooting

- **Port in use:** Change port with `--port 8001`
- **Database errors:** Delete `.crest/crest.db` and restart
- **Import errors:** Ensure `pip install -e .` was run from the project root