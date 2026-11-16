"""SQLite persistence for the CREST product.

The product database is deliberately separate from the research runtime's
capability store.  It stores task history, plans, executions, evidence,
approvals, provider configuration, routing rules, and the audit trail.

Design notes
------------
* WAL mode + a busy timeout keep local concurrent readers/writers safe.
* All timestamps are UTC ISO-8601 strings.
* Provider API keys are never stored in plaintext.  CREST 1.1 adds a
  DPAPI-encrypted credential table; older databases that only name an
  environment variable continue to work.
* Schema changes are applied by ordered, idempotent migrations.  A legacy
  database created by the earlier single-file prototype is renamed, not
  deleted, so existing local history is preserved.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .platform import SCHEMA_VERSION, app_data_dir, database_path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_data_dir() -> Path:
    """Return the persistent application data directory.

    ``CREST_DATA_DIR`` overrides the default so tests and portable installs can
    use an isolated directory.  The default is stable across launches instead
    of depending on the current working directory.
    """
    return app_data_dir()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser().resolve() if path else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self.initialize()

    # ------------------------------------------------------------------ core
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------- migration
    def initialize(self) -> None:
        with self._init_lock:
            conn = self.connect()
            try:
                self._rename_legacy_tables(conn)
                conn.executescript(_SCHEMA_SQL)
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if version == 0:
                    # A fresh baseline schema (or a renamed legacy database).
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, note) VALUES (?,?,?)",
                        (1, now_iso(), "CREST 1.0 baseline schema"),
                    )
                    conn.execute("PRAGMA user_version=1")
                    version = 1
                if version > SCHEMA_VERSION:
                    raise RuntimeError(
                        f"database schema {version} is newer than this application ({SCHEMA_VERSION}); "
                        "upgrade CREST instead of downgrading the database"
                    )
                for target in range(version + 1, SCHEMA_VERSION + 1):
                    migration = _MIGRATIONS[target]
                    migration(conn)
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, note) VALUES (?,?,?)",
                        (target, now_iso(), _MIGRATION_NOTES[target]),
                    )
                    conn.execute(f"PRAGMA user_version={target}")
                self._seed(conn)
                conn.commit()
            finally:
                conn.close()

    def schema_version(self) -> int:
        with self.read() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    def checkpoint(self) -> None:
        """Flush the WAL so a clean shutdown leaves a compact database."""
        try:
            with self.read() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.DatabaseError:
            pass

    def _rename_legacy_tables(self, conn: sqlite3.Connection) -> None:
        """Preserve, rather than overwrite, a database from the 1.0 prototype."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if row is None:
            return
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
        if "idempotency_key" in cols:
            return
        suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        for table in ("tasks", "executions", "audit_events", "settings"):
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if exists:
                conn.execute(f'ALTER TABLE "{table}" RENAME TO "legacy_{table}_{suffix}"')
        conn.commit()

    def _seed(self, conn: sqlite3.Connection) -> None:
        # Imported lazily to avoid a circular import at module load.
        from .settings import DEFAULT_SETTINGS

        ts = now_iso()
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?,?,?)",
                (key, _json(value), ts),
            )

        providers = [
            {
                "id": "mock",
                "kind": "mock",
                "name": "Offline Mock Provider",
                "enabled": 1,
                "base_url": "",
                "api_key_env": "",
                "default_model": "mock-fast",
                "models": ["mock-fast", "mock-reasoning"],
                "input_cost_per_1k": 0.0,
                "output_cost_per_1k": 0.0,
                "max_output_tokens": 2048,
                "timeout_seconds": 30.0,
            },
            {
                "id": "gemini",
                "kind": "gemini",
                "name": "Google Gemini",
                "enabled": 0,
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "api_key_env": "GEMINI_API_KEY",
                "default_model": "gemini-2.5-flash",
                "models": ["gemini-2.5-flash"],
                "input_cost_per_1k": 0.0,
                "output_cost_per_1k": 0.0,
                "max_output_tokens": 2048,
                "timeout_seconds": 60.0,
            },
            {
                "id": "openai-compatible",
                "kind": "openai_compatible",
                "name": "OpenAI-compatible endpoint",
                "enabled": 0,
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "default_model": "gpt-4o-mini",
                "models": ["gpt-4o-mini"],
                "input_cost_per_1k": 0.0,
                "output_cost_per_1k": 0.0,
                "max_output_tokens": 2048,
                "timeout_seconds": 60.0,
            },
        ]
        for p in providers:
            conn.execute(
                """INSERT OR IGNORE INTO providers
                   (id, kind, name, enabled, base_url, api_key_env, default_model,
                    models_json, input_cost_per_1k, output_cost_per_1k,
                    max_output_tokens, timeout_seconds, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    p["id"], p["kind"], p["name"], p["enabled"], p["base_url"],
                    p["api_key_env"], p["default_model"], _json(p["models"]),
                    p["input_cost_per_1k"], p["output_cost_per_1k"],
                    p["max_output_tokens"], p["timeout_seconds"], ts, ts,
                ),
            )

        count = conn.execute("SELECT COUNT(*) FROM routing_rules").fetchone()[0]
        if count == 0:
            rules = [
                (10, "high", "mock", "mock-reasoning", 1),
                (20, "med", "mock", "mock-fast", 1),
                (30, "low", "mock", "mock-fast", 1),
                (100, "*", "mock", "mock-fast", 1),
            ]
            for priority, risk, provider, model, enabled in rules:
                conn.execute(
                    """INSERT INTO routing_rules
                       (priority, risk_class, provider, model, enabled, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (priority, risk, provider, model, enabled, ts, ts),
                )

    # -------------------------------------------------------------- helpers
    def integrity(self) -> dict[str, Any]:
        with self.read() as conn:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
            result = [r[0] for r in rows]
        return {"ok": result == ["ok"], "result": result}

    def counts(self) -> dict[str, int]:
        tables = [
            "tasks", "plans", "executions", "execution_steps", "evidence",
            "approvals", "audit_events", "providers", "routing_rules",
            "provider_usage", "provider_credentials",
        ]
        with self.read() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }

    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


def _apply_v2(conn: sqlite3.Connection) -> None:
    """Add credential metadata, provider usage history, and retry settings."""
    provider_columns = {row[1] for row in conn.execute("PRAGMA table_info(providers)")}
    if "retry_max" not in provider_columns:
        conn.execute("ALTER TABLE providers ADD COLUMN retry_max INTEGER NOT NULL DEFAULT 2")
    if "rate_limit_per_minute" not in provider_columns:
        conn.execute(
            "ALTER TABLE providers ADD COLUMN rate_limit_per_minute INTEGER NOT NULL DEFAULT 30"
        )
    conn.executescript(_V2_SQL)


_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {2: _apply_v2}
_MIGRATION_NOTES: dict[int, str] = {
    2: "CREST 1.1 credentials, provider usage, retry and rate-limit settings",
}


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    base_url TEXT NOT NULL DEFAULT '',
    api_key_env TEXT NOT NULL DEFAULT '',
    default_model TEXT NOT NULL DEFAULT '',
    models_json TEXT NOT NULL DEFAULT '[]',
    input_cost_per_1k REAL NOT NULL DEFAULT 0.0,
    output_cost_per_1k REAL NOT NULL DEFAULT 0.0,
    max_output_tokens INTEGER NOT NULL DEFAULT 1024,
    timeout_seconds REAL NOT NULL DEFAULT 60.0,
    last_test_status TEXT,
    last_test_at TEXT,
    last_test_detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    risk_class TEXT NOT NULL DEFAULT 'low',
    autonomy_level INTEGER NOT NULL DEFAULT 2,
    status TEXT NOT NULL DEFAULT 'pending',
    provider TEXT,
    model TEXT,
    budget REAL NOT NULL DEFAULT 1.0,
    token_budget INTEGER NOT NULL DEFAULT 4096,
    timeout_seconds REAL NOT NULL DEFAULT 60.0,
    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
    output_format TEXT NOT NULL DEFAULT 'text',
    demo_scenario TEXT,
    custom_policy TEXT,
    result TEXT,
    result_hash TEXT,
    verification_status TEXT,
    gate_decision TEXT,
    gate_reason TEXT,
    cost REAL NOT NULL DEFAULT 0.0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_deleted ON tasks(deleted_at);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_plans_task ON plans(task_id);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 1,
    provider TEXT,
    model TEXT,
    started_at TEXT,
    completed_at TEXT,
    cost REAL NOT NULL DEFAULT 0.0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_executions_task ON executions(task_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);

CREATE TABLE IF NOT EXISTS execution_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    detail_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_steps_execution ON execution_steps(execution_id);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    execution_id TEXT,
    kind TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    independent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_task ON evidence(task_id);
CREATE INDEX IF NOT EXISTS idx_evidence_created ON evidence(created_at);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    execution_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    policy_fingerprint TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    consumed_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_approvals_task ON approvals(task_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    execution_id TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    detail TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_events(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);

CREATE TABLE IF NOT EXISTS routing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority INTEGER NOT NULL DEFAULT 100,
    risk_class TEXT NOT NULL DEFAULT '*',
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_V2_SQL = """
CREATE TABLE IF NOT EXISTS provider_credentials (
    provider_id TEXT PRIMARY KEY,
    ciphertext BLOB NOT NULL,
    method TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id TEXT NOT NULL,
    model TEXT NOT NULL,
    task_id TEXT,
    execution_id TEXT,
    status TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0.0,
    latency_ms REAL NOT NULL DEFAULT 0.0,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON provider_usage(provider_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_task ON provider_usage(task_id);
"""

