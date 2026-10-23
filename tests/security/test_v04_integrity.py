"""Crash consistency, replay protection, and receipt serialization tests."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

import crest.faults  # noqa: F401
from crest.receipts import SCHEMA_VERSION, CapabilityReceipt, RecoveryEvidence, canonical_json
from crest.recovery import RecoveryProgram
from crest.store import SCHEMA_VERSION as STORE_SCHEMA
from crest.store import SecurityStateCorrupt, Store

from tests.conftest import make_runtime


def evidence(**over) -> RecoveryEvidence:
    base = dict(test_count=10, failed_tests=0, recovery_success_rate=1.0,
                recovery_latency_p50_ms=1.0, recovery_latency_p95_ms=1.0, recovery_latency_p99_ms=1.0,
                residual_exposure_ucb=0.01, propagation_depth=0, verification_environment="sandbox-v1",
                verification_version="v", test_config_digest="cfg", random_seed=0)
    base.update(over)
    return RecoveryEvidence(**base)


def admit(rt):
    return rt.verify_and_admit(action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)


# ---------------- serialization / integrity ----------------

def test_receipt_canonical_serialization_is_stable():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    r = CapabilityReceipt.create(action_class="delete_file", target_scope="*", recovery_program_digest="d", evidence=evidence(), status="VERIFIED", now=now, ttl_seconds=60, receipt_id="fixed-id")
    first = r.canonical_payload()
    second = r.canonical_payload()
    assert first == second
    # key order in the input dict must not matter
    shuffled = json.loads(first)
    reordered = {k: shuffled[k] for k in reversed(list(shuffled))}
    assert canonical_json(reordered) == canonical_json(shuffled)


def test_receipt_roundtrip_preserves_validity():
    now = datetime.now(timezone.utc)
    r = CapabilityReceipt.create(action_class="modify_file", target_scope="docs/*", recovery_program_digest="d", evidence=evidence(), status="VERIFIED", now=now, ttl_seconds=60)
    r2 = CapabilityReceipt.from_dict(r.to_dict())
    assert r2.receipt_id == r.receipt_id and r2.is_hash_valid()


def test_receipt_tampering_any_field_breaks_hash():
    import dataclasses

    now = datetime.now(timezone.utc)
    r = CapabilityReceipt.create(action_class="delete_file", target_scope="*", recovery_program_digest="d", evidence=evidence(), status="VERIFIED", now=now, ttl_seconds=60)
    for field, value in (("action_class", "modify_file"), ("target_scope", "**"), ("status", "VERIFIED_GENERAL"), ("recovery_program_digest", "x")):
        tampered = dataclasses.replace(r, **{field: value})
        assert not tampered.is_hash_valid(), field


def test_receipt_binds_receipt_id():
    import dataclasses

    now = datetime.now(timezone.utc)
    r = CapabilityReceipt.create(action_class="delete_file", target_scope="*", recovery_program_digest="d", evidence=evidence(), status="VERIFIED", now=now, ttl_seconds=60)
    assert not dataclasses.replace(r, receipt_id="stolen").is_hash_valid()


def test_receipt_schema_version_is_explicit():
    now = datetime.now(timezone.utc)
    r = CapabilityReceipt.create(action_class="delete_file", target_scope="*", recovery_program_digest="d", evidence=evidence(), status="VERIFIED", now=now, ttl_seconds=60)
    assert r.schema_version == SCHEMA_VERSION == 2
    assert r.receipt_version == "2.0"


# ---------------- replay ----------------

def test_revoked_capability_revokes_its_receipt(workspace):
    rt = make_runtime(workspace)
    out = admit(rt)
    rid = out["receipt_id"]
    assert not rt.store.is_receipt_revoked(rid)
    rt.revoke("delete_file:*", "manual")
    assert rt.store.is_receipt_revoked(rid)


def test_revoked_receipt_cannot_authorize_even_if_capability_restored(workspace):
    rt = make_runtime(workspace)
    out = admit(rt)
    rid = out["receipt_id"]
    rt.revoke("delete_file:*", "manual")
    # attacker restores the capability row by hand but keeps the old receipt
    from crest.store import CapabilityRow

    row = CapabilityRow("delete_file:*", "delete_file", "*", "ADMITTED", rid, "t0", "t0")
    rt.store.upsert_capability(row)
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok
    assert res.reason == "RECEIPT_REVOKED"
    assert (workspace / "data" / "a.txt").exists()


def test_replay_after_revoke_cannot_restore_authority(workspace):
    """After a real revocation path (drift), the authorizing receipt is dead
    and cannot be replayed even if the capability row is reinstated."""
    rt = make_runtime(workspace)
    out = rt.verify_generalized(action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.single_file",), verification_cases=4, holdout_cases=4, shift_cases=2)
    rid = out["receipt_id"]
    nested = workspace / "nested"
    nested.mkdir()
    (nested / "x.txt").write_text("x", encoding="utf-8")
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "nested/x.txt"})
    assert res.reason.startswith("DRIFT_DETECTED")
    assert rt.store.is_receipt_revoked(rid)

    from crest.store import CapabilityRow

    row = CapabilityRow("delete_file:*", "delete_file", "*", "ADMITTED", rid, "t0", "t0")
    rt.store.upsert_capability(row)
    res2 = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "nested/x.txt"})
    assert not res2.ok
    rt.close()


# ---------------- migrations ----------------

def test_fresh_database_records_migration_history(workspace):
    store = Store(workspace / ".crest" / "crest.db")
    history = store.migration_history()
    assert [h[0] for h in history] == [1, 2, 3]
    store.close()


def test_v1_database_is_migrated_not_discarded(workspace):
    db = workspace / ".crest" / "crest.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE capabilities (capability_id TEXT PRIMARY KEY, action_class TEXT, scope TEXT, state TEXT, receipt_id TEXT, created_at TEXT, updated_at TEXT, revoked_at TEXT, revocation_reason TEXT);
        CREATE TABLE receipts (receipt_id TEXT PRIMARY KEY, action_class TEXT, scope TEXT, status TEXT, evidence_classification TEXT, created_at TEXT, expires_at TEXT, payload_json TEXT);
        CREATE TABLE exposure (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, timestamp TEXT, action_class TEXT, target TEXT, reason TEXT);
        CREATE TABLE audit (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, request_id TEXT, agent_id TEXT, capability_id TEXT, tool TEXT, operation TEXT, decision TEXT, reason TEXT, details_json TEXT);
        INSERT INTO meta VALUES ('schema_version','1');
        INSERT INTO receipts VALUES ('legacy-receipt','delete_file','*','VERIFIED','VERIFIED_FIXTURE','t0','t1','{}');
        """
    )
    conn.commit()
    conn.close()

    store = Store(db)
    assert store.get_receipt_payload("legacy-receipt") is not None  # not discarded
    assert [h[0] for h in store.migration_history()] == [1, 2, 3]
    store.close()


def test_future_schema_version_fails_closed(workspace):
    db = workspace / ".crest" / "crest.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    Store(db).close()
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(SecurityStateCorrupt):
        Store(db)


# ---------------- crash consistency ----------------

def test_capability_not_phantom_after_crash_between_admission_and_execution(workspace):
    """A crash before execution must leave no evidence that an action ran."""
    rt = make_runtime(workspace)
    admit(rt)
    exposure_before = rt.store.total_exposure()
    rt.close()  # simulate crash: no execution happened

    rt2 = make_runtime(workspace)
    assert rt2.store.total_exposure() == exposure_before
    assert (workspace / "data" / "a.txt").exists()  # nothing executed
    rt2.close()


def test_revocation_survives_crash(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    rt.revoke("delete_file:*", "crash-test")
    rt.close()
    rt2 = make_runtime(workspace)
    assert rt2.get_capability("delete_file:*")["state"] == "REVOKED"
    assert rt2.store.is_receipt_revoked(rt2.get_capability("delete_file:*")["receipt_id"])
    rt2.close()


def test_exposure_is_not_lost_on_restart(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    total = rt.store.total_exposure()
    rt.close()
    rt2 = make_runtime(workspace)
    assert rt2.store.total_exposure() == total
    rt2.close()


def test_audit_survives_crash(workspace):
    rt = make_runtime(workspace)
    admit(rt)
    rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    n = len(rt.audit())
    rt.close()
    rt2 = make_runtime(workspace)
    assert len(rt2.audit()) >= n
    rt2.close()


def test_partial_transaction_does_not_create_capability(workspace):
    """A crash inside store writes must not leave a half-created capability."""
    db = workspace / ".crest" / "crest.db"
    rt = make_runtime(workspace)
    admit(rt)
    rt.close()
    # simulate torn write: capability row without receipt
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE capabilities SET receipt_id=NULL WHERE capability_id='delete_file:*'")
    conn.commit()
    conn.close()
    rt2 = make_runtime(workspace)
    res = rt2.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason in ("MISSING_RECEIPT", "RECEIPT_NOT_FOUND")
    rt2.close()