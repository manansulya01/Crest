# CREST 1.1 — security model

## Trust boundary

The packaged app has two processes: a Tauri WebView shell and a Python/FastAPI
backend. The backend binds to **loopback only**, picks a free port, and exposes
a per-process runtime descriptor to the shell. No remote listener is opened.

## Local request protection

- `TrustedHostMiddleware` with a loopback host allowlist.
- CORS restricted to known local/Tauri origins; credentials are not allowed.
- State-changing browser requests must send `X-Crest-CSRF` from
  `GET /api/v1/security/csrf`. Non-browser clients without an `Origin` header
  are not subject to CSRF checks.
- `Sec-Fetch-Site: cross-site` is denied, request bodies are size-limited, and
  security headers (CSP, nosniff, frame-ancestors, referrer, permissions) are set.
- Optional bearer token via `CREST_API_TOKEN`; compared in constant time.

## Credential storage

- Windows: DPAPI `CryptProtectData`/`CryptUnprotectData` with per-provider
  entropy, `CRYPTPROTECT_UI_FORBIDDEN`, ciphertext in SQLite. No plaintext key
  reaches settings, audit, logs, exports, or API responses.
- Non-Windows development: AES-GCM with a local 0600 key file, explicitly
  reported as weaker and never used on Windows.
- The credential API returns only status metadata (provider, method, timestamp).

## Filesystem and data safety

- Backups/imports validate paths and reject traversal and credential-like fields.
- Restore creates a pre-restore snapshot; integrity and SHA-256 are verified.
- Logs are redacted before writing and rotate with bounded retention.
- Database is SQLite WAL with foreign keys, transactions, and schema migrations
  that preserve existing rows.

## Process behaviour

- No terminal window on Windows (Tauri + PyInstaller windowed bootloader +
  `CREATE_NO_WINDOW`).
- Single-instance handling focuses the existing window; a secondary launch does
  not shut down the shared backend.
- Graceful shutdown calls a token-protected endpoint, then terminates the child
  and removes the runtime descriptor.

## Residual risks / honest limits

- A malicious process running as the same Windows user can read local data or
  DPAPI-protected secrets under that user's account; DPAPI protects against
  other users, not against the owner.
- Evidence is content-addressed but **not cryptographically signed**.
- No live external provider validation, no code signing, no hardware-backed key
  storage, and no multi-user isolation.
- Security posture remains **Level 3 — supervised personal use**, not a
  production safety guarantee.
