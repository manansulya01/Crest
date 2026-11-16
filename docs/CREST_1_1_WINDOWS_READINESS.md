# CREST 1.1 — Windows readiness record

This record states exactly what was built and what was executed on Windows. It
distinguishes verified behaviour from implemented-but-not-live-validated work.

## Identity and provenance

| Item | Value |
| --- | --- |
| Branch | `feat/crest-1.0-product` |
| Starting HEAD | `ae791c45023f8304042a511485ecf0e72cd7036e` (CREST 1.0) |
| 1.1 foundation commit | `579c9be3ab5a17678219d4b1ade21f7c0c617ef8` |
| Final implementation commit | `5e7210a997d702763eed57451b0ee72364acccd0` |
| Application / schema version | `1.1.0` / `2` |
| Security posture | Level 3 — supervised personal use |
| History | No force-push, no rewrite, no merge to main, no public release |

## Environment (all Windows checks executed on Windows 11 x64)

- Windows 11 10.0.26300; WebView2 157.0.4341.60
- Python 3.12.10; PyInstaller 6.22.3; FastAPI 0.136.3; uvicorn 0.51.0
- Rust/Cargo 1.97.0; Tauri CLI 2.12.4; Node 25.7.0
- DPAPI `crypt32` available; credential backend reported as `dpapi`

## Artifact

| Item | Value |
| --- | --- |
| Installer | `src-tauri\target\release\bundle\nsis\CREST_1.1.0_x64-setup.exe` |
| Size | 41,773,831 bytes (39.84 MiB) |
| SHA-256 | `D324B6CCD4E0E57527DAEC497C1DDE82914468D09A4D6D519512A4A5EDCE1987` |
| Bundled sidecar | `crest-backend.exe`, 40,577,636 bytes (PyInstaller onefile) |
| Rebuild | `packaging\build_windows.ps1` |
| Verification | `packaging\verify_windows.ps1` → `packaging/verify_windows_report.json` |

## Features delivered

Native window and icon/metadata; hidden backend sidecar lifecycle; no terminal;
graceful token-protected shutdown; single-instance focus; startup diagnostics
and runtime port discovery; persistent local settings in `%LOCALAPPDATA%\CREST`;
NSIS installer, data-preserving upgrade and uninstall, browser fallback retained.

DPAPI credential encryption with non-Windows AES-GCM dev fallback; no plaintext,
no credential return, no secret in logs/exports; loopback-only bind; CSRF and
origin protection; trusted hosts, size limits, security headers.

SQLite v1→v2 migration, transaction integrity, verified SHA-256 backups,
pre-restore snapshots, retention and safe deletion; interrupted-task recovery,
idempotent transitions, bounded retries/timeouts, cancellable backoff, global
pause/resume/stop-all, rotating redacted logs, health checks.

Manual / Supervised / Bounded autonomous modes enforced server-side with
high-risk gating in every mode; Gemini and OpenAI-compatible adapters with
connection tests, discovery, usage history and policy-safe fallback (local
loopback validation only); first-run wizard, working controls, empty/error
states, search/filter, persistent themes, keyboard accessibility, responsive
layouts, loading/progress.

## Tests and environments

| Check | Result |
| --- | --- |
| Product suite (incl. 18 1.1 tests + 4 soak) | **61 passed** (Windows) |
| Full suite (research + product) | **493 passed** in 109 s (Windows) |
| Frontend build | 56 modules; JS 479.67 kB / 132.31 kB gzip; CSS 67.09 kB / 12.19 kB gzip |
| Frontend lint | 0 errors; 9 pre-existing React warnings |
| Sidecar smoke (source and packaged exe) | health, `/app`, assets, CSRF, shutdown OK |
| Bounded soak | 30 sequential + 12 concurrent executions, 8 backup/verify cycles, 8 pause cycles — passed |
| Windows installer verification | **PASS** (details below) |

## Fresh-install verification (executed on this Windows machine)

| Check | Observed |
| --- | --- |
| Silent install exit / files | 0 / 3 installed files including sidecar + uninstaller |
| Health / version / schema | `ok` / `1.1.0` / `2` |
| Credential backend | `dpapi`, `windows_dpapi = true` |
| Native window | Title `CREST`, one window; backend visible windows: 0 |
| Backend instances | 1 root after first launch and after a second launch |
| Web app served | `/app` 200, bundled JS asset 200 |
| CSRF | Write without token denied (403); write with token succeeded |
| Task execution | Offline task completed through installed app |
| Credential | Stored with DPAPI; secret absent from response and database bytes |
| Graceful close | Desktop 0, backend 0, runtime descriptor removed |
| Restart | Task and credential configuration persisted |
| In-place upgrade | Exit 0; task and credential preserved |
| Uninstall | Exit 0; app files removed; `crest.db` and data directory preserved |

## Security findings

- No plaintext secret was found in the database or API responses during the
  installed-app check.
- Browser-origin writes without the per-process CSRF token are denied; writes
  with a valid token succeed.
- The backend is loopback-only with a single instance and no visible console.
- No remote telemetry or logging is present.
- Residual: DPAPI protects against other users, not against the owning user;
  evidence is content-addressed but not signed; installer is unsigned.

## Limitations and unclaimed work

- Gemini and paid OpenAI-compatible endpoints were **not** called live; no
  credentials or paid usage were used. Validation used a local loopback server.
- Cost figures depend on user-entered pricing; they are not billing measurements.
- Installer is not code-signed; SmartScreen warnings may appear on other machines.
- Browser E2E and mobile screenshots were not re-run for the 1.1 UI changes.
- No tag, GitHub Release, or merge to main was created.
- Not a multi-user or production safety guarantee.

## Final status

**WINDOWS INSTALLATION VERIFIED — SUPERVISED DAILY USE READY**

This status is limited to the Windows 11 environment and the executed checks
above. It is not a claim of live-provider validation, code signing, production
multi-tenant safety, or general release readiness.
