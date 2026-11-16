# CREST 1.1 — backup and restore

## Automatic snapshots

With **Settings → Backups** enabled (default), CREST creates verified SQLite
snapshots in `%LOCALAPPDATA%\CREST\backups`, keeps the configured number
(default 10), and writes a SHA-256 manifest for each. Rotation is bounded.

## Manual snapshot

Use **Create backup now**, optionally with a note. The API responds only after:
1. SQLite `PRAGMA integrity_check` passes on the temporary copy, and
2. the SHA-256 manifest has been written.

An unverified snapshot is never presented as valid.

## Verify and download

Each snapshot can be **Verify**d (integrity + checksum against manifest) or
**Download**ed as a `.db` file. Verification never modifies the database.

## Restore — **Settings → Restore…**

Restoring is confirm-only and:
1. creates a **pre-restore snapshot** of the current database first,
2. replaces the database, and
3. records a `BACKUP_RESTORED` audit event.

Because of the pre-restore snapshot, a mistaken restore is reversible. Stop
active tasks before restoring; running work is interrupted by the file swap.

## JSON export vs database backup

- **Download JSON backup** (Settings → Data management) exports tasks, plans,
  executions, evidence, approvals, audit, routing, usage, and settings. It
  **excludes credential ciphertext**. It is for inspection/portability, not a
  byte-exact restore.
- Import validation (`/api/v1/import/validate`) rejects credential-like fields
  and malformed structures before anything is applied.

## Retention

Task retention and log rotation are separate settings. **Purge** permanently
deletes soft-deleted tasks older than the retention window and is always an
explicit, confirmed action. Logs rotate at 2 MB × 5 files.

## Recovery instructions

If the app reports a degraded database: stop CREST, use the newest verified
backup, restore it, then reload. If credentials no longer decrypt (different
Windows user or machine), re-enter them in Providers — the rest of your data is
unaffected.
