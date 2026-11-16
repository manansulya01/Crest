# CREST 1.1 — changelog

## 1.1.0 (2026-11-16)

### Native Windows application
- Tauri 2 WebView shell with single-instance handling, native window/icon,
  no terminal during normal use, and graceful shutdown via token endpoint.
- PyInstaller backend sidecar bundled with the built React app; loopback-only
  with runtime port discovery.
- NSIS current-user installer with data-preserving upgrade and uninstall.

### Security
- Windows DPAPI credential encryption (AES-GCM portable fallback off Windows);
  secrets never returned, logged, or exported.
- CSRF token + origin enforcement for browser writes, trusted-host allowlist,
  request-size limits, and security headers.
- Redacted rotating logs; path-traversal-safe backups and import validation.

### Reliability
- SQLite schema v2 with data-preserving v1 migration, WAL checkpoints.
- Verified backups with SHA-256 manifests, pre-restore snapshots, retention.
- Bounded retries/backoff, Retry-After handling, rate limiting, cancellable
  waits, pause/resume/stop-all, interrupted-task recovery.

### Providers and autonomy
- Gemini and OpenAI-compatible adapters completed (local loopback validated);
  model discovery, usage history, credential-aware status.
- Backend-enforced Manual, Supervised, and Bounded autonomous modes; high-risk
  gating preserved in every mode.

### Interface
- First-run setup wizard, mode badge, global controls, credential and usage UI,
  backup/restore UI, retry/rate-limit settings, expanded diagnostics.

### Validation
- Product suite 61 passing (including 18 1.1 tests and 4 bounded soak tests);
  full suite 493 passing; frontend build and lint clean.
- Windows installer verified on Windows 11: fresh install, native window,
  CSRF enforcement, task execution, DPAPI storage, graceful shutdown, restart
  persistence, in-place upgrade, and data-preserving uninstall.

### Not changed
- Research runtime, benchmarks, experiments, and 1.0 tests are preserved.
- No live Gemini/OpenAI calls, no code signing, no public release, no merge
  to main. Status remains supervised daily use.
