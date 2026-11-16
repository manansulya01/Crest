# CREST 1.1 — troubleshooting

## The window does not appear

- Check **System → Application** in the browser fallback to see whether the
  backend started. A startup error window shows the exact reason.
- Confirm WebView2 is installed; the NSIS installer downloads it if allowed.
- Look at `logs\crest.log` in `%LOCALAPPDATA%\CREST` (passwords/keys are redacted).

## "Cannot reach the CREST API"

The backend binds only to loopback and chooses a free port recorded in
`runtime.json`. If the descriptor is stale after a force-kill, restart CREST;
the shell detects and clears stale descriptors. The browser fallback requires
`python -m uvicorn crest.api:app --host 127.0.0.1 --port 8000`.

## "Missing or invalid CSRF token; reload the application"

The backend rotates a per-process token. The client caches it and retries once.
A persistent error means the page outlived a backend restart — reload the app.

## Credential errors

- "DPAPI could not decrypt…" — the ciphertext belongs to a different Windows
  user or machine. Use **Set key** to replace it.
- Non-Windows development uses AES-GCM with `credentials.key` in the data dir;
  this is labelled in the UI and is never used on Windows.
- Credentials are never displayed; do not expect a "show key" control.

## Provider calls fail

Check: external calls enabled in Settings, provider enabled, key configured,
base URL correct, model in the configured list, and rate limit. Inspect
**Providers → Usage history** for the sanitized error and retry count. Live
Gemini/OpenAI behaviour was not validated in this release.

## Tasks stuck awaiting approval

Approvals expire after one hour and are invalidated by task edits. Re-execute
the task to request a fresh approval. High-risk tasks may still abstain at the
gate even after approval — this is expected when independent evidence is absent.

## Database integrity warning

Stop CREST, restore the newest verified snapshot (see backup guide), and reopen.
If no snapshot exists, export what is readable via the JSON export before
seeking further recovery.

## Uninstall/reinstall

Uninstall preserves `%LOCALAPPDATA%\CREST`. To start completely fresh, delete
that directory yourself after uninstalling. This removes all tasks, credentials,
logs, and backups irreversibly.
