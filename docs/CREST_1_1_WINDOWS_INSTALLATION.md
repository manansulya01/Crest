# CREST 1.1 — Windows installation

CREST 1.1 is a **native Windows application**. A Tauri WebView window owns the
UI and manages a hidden Python/FastAPI backend sidecar. It is not a browser
launcher; `crest_desktop.py` remains available as the 1.0 browser fallback.

## Requirements

- Windows 10/11 x64 with WebView2 (the installer can download the bootstrapper).
- No Python, Node, or terminal is needed to **use** the installed app.

## Install

1. Run `CREST_1.1.0_x64-setup.exe`.
2. Choose the default *current user* installation (recommended) or another folder.
3. Launch CREST from the Start menu or desktop shortcut.

The app appears as a normal window titled **CREST**. No console window opens.

## Where data lives

All persistent state is under `%LOCALAPPDATA%\CREST` (override with the
`CREST_DATA_DIR` environment variable before launch):

| Path | Contents |
| --- | --- |
| `crest.db` | SQLite database (schema v2), including DPAPI-encrypted credentials |
| `logs\crest.log` | Rotating, redacted application log (2 MB × 5) |
| `backups\` | Verified SQLite snapshots with SHA-256 manifests |
| `runtime.json` | Ephemeral loopback port/shutdown descriptor, removed on clean exit |

## Upgrade

Run a newer installer over the existing installation. The database, backups,
logs, and credentials are preserved. A second launch while CREST is already
running focuses the existing window instead of creating a duplicate backend.

## Uninstall

Use *Settings → Apps → CREST → Uninstall* or `uninstall.exe` in the install
folder. The application files are removed; `%LOCALAPPDATA%\CREST` is **kept**
so a later reinstall restores your data. Delete that directory manually only
when you intend to discard everything.

## Build from source (developers)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
powershell -ExecutionPolicy Bypass -File packaging\verify_windows.ps1
```

The build script produces
`src-tauri\target\release\bundle\nsis\CREST_1.1.0_x64-setup.exe`.
The verification script performs a real silent install, launch, API, shutdown,
restart, upgrade, and uninstall cycle on this Windows machine.

## Portability / fallback

Running `python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000` and
opening `http://127.0.0.1:8000/app` remains supported. On non-Windows
development hosts, credential storage falls back to AES-GCM with a local key
file and is explicitly labelled as such; it is never used on Windows.
