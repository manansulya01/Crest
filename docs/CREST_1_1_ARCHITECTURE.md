# CREST 1.1 — architecture

## Packaged topology

```
CREST.exe (Tauri WebView window)
  ├── spawns / supervises  binaries/crest-backend.exe (PyInstaller, hidden)
  │     └── FastAPI + SQLite + engine, bound to 127.0.0.1:<free port>
  ├── reads %LOCALAPPDATA%\CREST\runtime.json (port, token, version)
  └── navigates to http://127.0.0.1:<port>/app
```

The backend serves the built React app from inside its own bundle, so the shell
does not need a separate static file server. `crest_desktop.py` (browser
launcher) remains as the 1.0 fallback and is never described as native.

## Backend modules (new in 1.1)

| Module | Responsibility |
| --- | --- |
| `platform.py` | Version 1.1.0, schema 2, Windows paths, env overrides |
| `credentials.py` | DPAPI / AES-GCM credential store, status helpers |
| `logging_setup.py` | Rotating redacted logs, tail/prune helpers |
| `backup.py` | Verified snapshots, manifests, restore, import validation |
| `sidecar.py` | Loopback server, runtime descriptor, graceful exit |
| `db.py` | v1→v2 migration, new tables/columns, checkpoint |
| `settings.py` | Mode, pause, resilience, backup and log settings |
| `policy.py` | Operating modes enforced before every provider call |
| `providers.py` | Retries, Retry-After, rate-limit errors, discovery, usage |
| `engine.py` | Lifecycle, cancellation, usage, backups, diagnostics, health |
| `api.py` | CSRF/origin protection, control/credential/backup/log endpoints |

## Reliability design

- Interrupted executions are marked interrupted on startup; terminal
  transitions are idempotent; duplicate starts are rejected.
- Retries are bounded by both provider and global settings; waits are
  cancellable; timeouts are checked before each attempt.
- Pause is a persisted setting checked at start, before calls, and during
  backoff. Stop-all cancels active tasks without deleting data.
- WAL checkpoints on clean shutdown; verified backups preserve data across
  upgrade and uninstall.

## Frontend

Typed API client with CSRF bootstrap/retry, first-run wizard, top-bar
pause/resume/stop-all and mode badge, provider credential/usage UI, backup and
restore controls, and expanded system diagnostics. The UI is a client only —
every authorization decision is made by the backend.

## Build and verification

`packaging/build_windows.ps1` builds web → PyInstaller sidecar → Tauri NSIS
installer. `packaging/verify_windows.ps1` performs a real Windows install,
launch, health/CSRF/execution/credential checks, shutdown, restart, upgrade,
and uninstall. Results are recorded in `packaging/verify_windows_report.json`.
