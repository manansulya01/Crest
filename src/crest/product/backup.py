"""Verified SQLite backups, restores, and export validation for CREST 1.1."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import Database, now_iso
from .platform import VERSION

_NAME_RE = re.compile(r"^crest-backup-[0-9TZ-]+-[0-9a-f]{8}\.db$")


class BackupError(Exception):
    """A backup operation failed validation or could not complete safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _database_summary(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=15.0)
    try:
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        counts: dict[str, int] = {}
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        for table in tables:
            try:
                counts[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            except sqlite3.DatabaseError:
                counts[table] = -1
        return {"integrity": integrity, "ok": integrity == ["ok"], "schema_version": version, "counts": counts}
    finally:
        conn.close()


class BackupManager:
    def __init__(self, db: Database, directory: str | Path):
        self.db = db
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- paths
    def _resolve(self, name: str) -> Path:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise BackupError("invalid backup name")
        candidate = (self.directory / name).resolve()
        try:
            candidate.relative_to(self.directory)
        except ValueError as exc:
            raise BackupError("backup path escapes the approved backup directory") from exc
        if not candidate.is_file():
            raise BackupError("backup file not found")
        return candidate

    def _manifest_path(self, backup: Path) -> Path:
        return backup.with_suffix(backup.suffix + ".json")

    # --------------------------------------------------------------- create
    def create(self, *, note: str = "", keep: int = 10) -> dict[str, Any]:
        name = f"crest-backup-{_utc_stamp()}-{uuid.uuid4().hex[:8]}.db"
        final = self.directory / name
        temp = self.directory / f".{name}.tmp"
        source = sqlite3.connect(str(self.db.path), timeout=30.0)
        target = sqlite3.connect(str(temp))
        try:
            source.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.commit()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"backup failed: {exc}") from exc
        finally:
            target.close()
            source.close()
        summary = _database_summary(temp)
        if not summary["ok"]:
            try:
                os.remove(temp)
            except OSError:
                pass
            raise BackupError("backup failed SQLite integrity verification")
        os.replace(temp, final)
        manifest = {
            "backup": name,
            "created_at": now_iso(),
            "app_version": VERSION,
            "sha256": _sha256(final),
            "size_bytes": final.stat().st_size,
            "schema_version": summary["schema_version"],
            "counts": summary["counts"],
            "note": note[:500],
            "verified": True,
        }
        self._manifest_path(final).write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._prune(max(1, min(int(keep), 100)))
        return manifest

    def _prune(self, keep: int) -> None:
        backups = sorted(
            [p for p in self.directory.glob("crest-backup-*.db") if _NAME_RE.match(p.name)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in backups[keep:]:
            for target in (path, self._manifest_path(path)):
                try:
                    target.unlink()
                except OSError:
                    pass

    # ----------------------------------------------------------------- list
    def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(
            [p for p in self.directory.glob("crest-backup-*.db") if _NAME_RE.match(p.name)],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            manifest: dict[str, Any] = {}
            manifest_path = self._manifest_path(path)
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    manifest = {}
            stat = path.stat()
            out.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "created_at": manifest.get("created_at")
                    or datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "sha256": manifest.get("sha256", ""),
                    "schema_version": manifest.get("schema_version"),
                    "note": manifest.get("note", ""),
                    "manifest_present": bool(manifest),
                }
            )
        return out

    # --------------------------------------------------------------- verify
    def verify(self, name: str) -> dict[str, Any]:
        path = self._resolve(name)
        summary = _database_summary(path)
        digest = _sha256(path)
        manifest: dict[str, Any] = {}
        manifest_path = self._manifest_path(path)
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise BackupError("backup manifest is unreadable") from exc
        hash_ok = bool(manifest.get("sha256")) and manifest.get("sha256") == digest
        valid = bool(summary["ok"]) and (not manifest or hash_ok)
        return {
            "name": path.name,
            "valid": valid,
            "integrity": summary["integrity"],
            "schema_version": summary["schema_version"],
            "counts": summary["counts"],
            "sha256": digest,
            "manifest_sha256": manifest.get("sha256"),
            "hash_matches_manifest": hash_ok,
            "created_at": manifest.get("created_at"),
            "note": manifest.get("note", ""),
        }

    # -------------------------------------------------------------- restore
    def restore(self, name: str, *, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise BackupError("explicit confirmation is required to restore a backup")
        path = self._resolve(name)
        verification = self.verify(name)
        if not verification["valid"]:
            raise BackupError("backup failed verification; restore refused")
        with self.db.read() as conn:
            active = int(
                conn.execute(
                    "SELECT COUNT(*) FROM executions WHERE status IN ('queued','running')"
                ).fetchone()[0]
            )
        if active:
            raise BackupError("stop or cancel active executions before restoring a backup")
        pre_restore = self.create(note=f"pre-restore snapshot before {name}", keep=20)
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
        target = sqlite3.connect(str(self.db.path), timeout=30.0)
        try:
            source.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.commit()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"restore failed: {exc}") from exc
        finally:
            target.close()
            source.close()
        self.db.initialize()
        integrity = self.db.integrity()
        if not integrity["ok"]:
            raise BackupError("database integrity check failed after restore")
        return {
            "restored": name,
            "pre_restore_backup": pre_restore["backup"],
            "schema_version": verification["schema_version"],
            "counts": self.db.counts(),
            "integrity": integrity,
        }


# --------------------------------------------------------------- import rules
_FORBIDDEN_IMPORT_KEYS = {
    "api_key", "apikey", "password", "secret", "token", "access_token",
    "refresh_token", "private_key", "authorization", "ciphertext",
}


def validate_export_payload(payload: Any) -> dict[str, Any]:
    """Validate a CREST JSON export without applying it.

    Import is intentionally validation-only in 1.1: the supported restore path
    is the verified SQLite backup.  This endpoint lets users confirm that an
    exported file is intact and free of credential material.
    """
    if not isinstance(payload, dict):
        raise BackupError("export must be a JSON object")
    if payload.get("export_version") not in ("1.0", "1.1"):
        raise BackupError("unsupported export_version")
    application = payload.get("application")
    if not isinstance(application, dict) or application.get("name") != "CREST":
        raise BackupError("export is not a CREST export")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise BackupError("export is missing the tables object")
    allowed_tables = {
        "tasks", "plans", "executions", "execution_steps", "evidence",
        "approvals", "audit_events", "routing_rules", "provider_usage",
    }
    unknown = set(tables) - allowed_tables
    if unknown:
        raise BackupError(f"export contains unsupported tables: {sorted(unknown)}")

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 20:
            raise BackupError("export nesting is too deep")
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in _FORBIDDEN_IMPORT_KEYS:
                    raise BackupError(f"export contains credential-like field: {key}")
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)

    walk(payload)
    counts = {
        table: len(rows) if isinstance(rows, list) else -1
        for table, rows in tables.items()
    }
    if any(count < 0 for count in counts.values()):
        raise BackupError("every table entry must be a list")
    return {
        "valid": True,
        "export_version": payload.get("export_version"),
        "application_version": application.get("version"),
        "generated_at": payload.get("generated_at"),
        "counts": counts,
        "note": "Validation only. Use a verified database backup to restore state.",
    }
