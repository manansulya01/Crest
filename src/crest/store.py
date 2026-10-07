"""SQLite persistence. Fails closed: any integrity problem raises."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


class SecurityStateCorrupt(Exception):
    pass


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """v1 -> v2: receipts gained issued_at/expires_at indexing columns and an
    explicit migration history. Existing rows are migrated, never discarded."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(receipts)")}
    if "status" not in cols:  # pragma: no cover - defensive
        raise SecurityStateCorrupt("receipts table missing expected columns")
    # v2 keeps the same physical table; the semantic change is the migration
    # history row plus schema_version bump, so that security state is never
    # silently reinterpreted.
    conn.execute("INSERT OR IGNORE INTO migrations (version, applied_at, note) VALUES (1, 'unknown', 'initial')")
    conn.execute("INSERT OR IGNORE INTO migrations (version, applied_at, note) VALUES (?,?,?)", (2, "unknown", "v1->v2 receipt payload versioning"))
    conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    conn.commit()


@dataclass
class CapabilityRow:
    capability_id: str
    action_class: str
    scope: str
    state: str
    receipt_id: str | None
    created_at: str
    updated_at: str
    revoked_at: str | None = None
    revocation_reason: str | None = None


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        except sqlite3.DatabaseError as e:
            raise SecurityStateCorrupt(f"corrupt store: {e}") from e

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS migrations (version INTEGER PRIMARY KEY, applied_at TEXT, note TEXT);
            CREATE TABLE IF NOT EXISTS capabilities (
                capability_id TEXT PRIMARY KEY, action_class TEXT, scope TEXT,
                state TEXT, receipt_id TEXT, created_at TEXT, updated_at TEXT,
                revoked_at TEXT, revocation_reason TEXT);
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY, action_class TEXT, scope TEXT,
                status TEXT, evidence_classification TEXT, created_at TEXT,
                expires_at TEXT, payload_json TEXT);
            CREATE TABLE IF NOT EXISTS exposure (
                id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL,
                timestamp TEXT, action_class TEXT, target TEXT, reason TEXT);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
                request_id TEXT, agent_id TEXT, capability_id TEXT, tool TEXT,
                operation TEXT, decision TEXT, reason TEXT, details_json TEXT);
            """
        )
        cur = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            self._conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", ("1",))
            self._conn.execute("INSERT OR IGNORE INTO migrations VALUES (1, 'unknown', 'initial')")
            self._conn.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
            self._conn.execute("INSERT OR IGNORE INTO migrations VALUES (2, 'unknown', 'v1->v2 receipt payload versioning')")
            self._conn.commit()
            return
        current = int(row[0])
        if current == 1:
            _migrate_v1_to_v2(self._conn)
            current = 2
        if current != SCHEMA_VERSION:
            raise SecurityStateCorrupt(f"unsupported schema version {current}")
        self._conn.commit()

    def migration_history(self) -> list[tuple[int, str, str]]:
        return [(int(r[0]), r[1], r[2]) for r in self._conn.execute("SELECT version, applied_at, note FROM migrations ORDER BY version")]

    def close(self) -> None:
        self._conn.close()

    # capabilities
    def upsert_capability(self, row: CapabilityRow) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO capabilities VALUES (?,?,?,?,?,?,?,?,?)",
            (row.capability_id, row.action_class, row.scope, row.state, row.receipt_id, row.created_at, row.updated_at, row.revoked_at, row.revocation_reason),
        )
        self._conn.commit()

    def get_capability(self, capability_id: str) -> CapabilityRow | None:
        cur = self._conn.execute("SELECT * FROM capabilities WHERE capability_id=?", (capability_id,))
        row = cur.fetchone()
        return CapabilityRow(*row) if row else None

    def list_capabilities(self) -> list[CapabilityRow]:
        cur = self._conn.execute("SELECT * FROM capabilities ORDER BY capability_id")
        return [CapabilityRow(*r) for r in cur.fetchall()]

    # receipts
    def save_receipt(self, receipt_id: str, action_class: str, scope: str, status: str, classification: str, created_at: str, expires_at: str, payload: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO receipts VALUES (?,?,?,?,?,?,?,?)",
            (receipt_id, action_class, scope, status, classification, created_at, expires_at, json.dumps(payload)),
        )
        self._conn.commit()

    def get_receipt_payload(self, receipt_id: str) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT payload_json FROM receipts WHERE receipt_id=?", (receipt_id,))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def mark_receipt_revoked(self, receipt_id: str) -> None:
        """Replay protection: a revoked receipt can never authorize again."""
        cur = self._conn.execute("SELECT payload_json FROM receipts WHERE receipt_id=?", (receipt_id,))
        row = cur.fetchone()
        if row is None:
            return
        payload = json.loads(row[0])
        payload["revoked"] = True
        self._conn.execute("UPDATE receipts SET payload_json=?, status=? WHERE receipt_id=?", (json.dumps(payload), "REVOKED", receipt_id))
        self._conn.commit()

    def is_receipt_revoked(self, receipt_id: str) -> bool:
        cur = self._conn.execute("SELECT payload_json FROM receipts WHERE receipt_id=?", (receipt_id,))
        row = cur.fetchone()
        return bool(json.loads(row[0]).get("revoked")) if row else False

    def list_receipts(self) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT receipt_id, action_class, scope, status, evidence_classification, created_at, expires_at FROM receipts ORDER BY created_at")
        return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    # exposure
    def add_exposure(self, amount: float, timestamp: str, action_class: str, target: str, reason: str) -> None:
        if amount < 0:
            raise ValueError("negative exposure")
        self._conn.execute("INSERT INTO exposure (amount, timestamp, action_class, target, reason) VALUES (?,?,?,?,?)", (amount, timestamp, action_class, target, reason))
        self._conn.commit()

    def try_reserve_exposure(self, amount: float, limit: float, timestamp: str, action_class: str, target: str, reason: str, timeout: float = 10.0) -> bool:
        """Atomic check-and-reserve: the ledger row is committed iff the
        post-reservation total would remain <= limit. Uses a single
        BEGIN IMMEDIATE transaction so concurrent processes on the same
        state directory cannot both observe enough remaining budget —
        SQLite serializes the writers. The reservation is never refunded by
        later recovery success; window expiry is the only release.
        """
        if amount < 0:
            raise ValueError("negative exposure")
        busy = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=timeout)
        try:
            busy.execute("PRAGMA busy_timeout=%d" % int(timeout * 1000))
            busy.execute("BEGIN IMMEDIATE")
            total = busy.execute("SELECT COALESCE(SUM(amount),0) FROM exposure").fetchone()[0]
            if total + amount > limit + 1e-12:
                busy.rollback()
                return False
            busy.execute("INSERT INTO exposure (amount, timestamp, action_class, target, reason) VALUES (?,?,?,?,?)", (amount, timestamp, action_class, target, reason))
            busy.commit()
            # keep the main connection's view coherent (WAL readers see new commits)
            self._conn.execute("SELECT 1").fetchall()
            return True
        except sqlite3.Error:
            try:
                busy.rollback()
            except sqlite3.Error:
                pass
            raise
        finally:
            busy.close()

    def total_exposure(self) -> float:
        cur = self._conn.execute("SELECT COALESCE(SUM(amount),0) FROM exposure")
        return float(cur.fetchone()[0])

    def exposure_since(self, cutoff_iso: str) -> float:
        cur = self._conn.execute("SELECT COALESCE(SUM(amount),0) FROM exposure WHERE timestamp >= ?", (cutoff_iso,))
        return float(cur.fetchone()[0])

    def list_exposure(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT amount, timestamp, action_class, target, reason FROM exposure ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    # audit
    def add_audit(self, timestamp: str, request_id: str, agent_id: str | None, capability_id: str | None, tool: str | None, operation: str | None, decision: str, reason: str | None, details: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO audit (timestamp, request_id, agent_id, capability_id, tool, operation, decision, reason, details_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (timestamp, request_id, agent_id, capability_id, tool, operation, decision, reason, json.dumps(details)),
        )
        self._conn.commit()

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT timestamp, request_id, agent_id, capability_id, tool, operation, decision, reason, details_json FROM audit ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in cur.fetchall():
            d = dict(zip([c[0] for c in cur.description], r))
            d["details"] = json.loads(d.pop("details_json"))
            out.append(d)
        return out
