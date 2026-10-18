"""Deep doctor diagnostics must catch cross-table invariant violations.

These tests construct both healthy and deliberately corrupted stores and
assert that ``diagnose_deep`` reports exactly the conditions it claims to
detect, without flagging valid states.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.doctor import ERROR, diagnose_deep
from crest.recovery import RecoveryProgram


def _rt(tmp_path, **overrides) -> CrestRuntime:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    return CrestRuntime(
        CrestConfig(
            workspace_root=tmp_path,
            state_dir=tmp_path / ".crest",
            **overrides,
        )
    )


def _admit(rt: CrestRuntime) -> None:
    rt.verify_and_admit(
        action_class="modify_file",
        scope="*",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        target="a.txt",
        trials=3,
    )


def _codes(findings: list[dict]) -> set[str]:
    return {finding["code"] for finding in findings}


def _errors(findings: list[dict]) -> list[dict]:
    return [finding for finding in findings if finding["level"] == ERROR]


def test_healthy_state_is_deep_ok(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        findings = diagnose_deep(rt)
        assert _errors(findings) == []
        assert "DEEP_OK" in _codes(findings)
        assert "MIGRATIONS_OK" in _codes(findings)
    finally:
        rt.close()


def test_empty_store_is_deep_ok(tmp_path):
    rt = _rt(tmp_path)
    try:
        findings = diagnose_deep(rt)
        assert _errors(findings) == []
        assert "DEEP_OK" in _codes(findings)
    finally:
        rt.close()


def test_orphan_receipt_is_detected(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        row = rt.store.get_capability("modify_file:*")
        row.receipt_id = "receipt-that-does-not-exist"
        rt.store.upsert_capability(row)

        findings = diagnose_deep(rt)
        assert "CAPABILITY_ORPHAN_RECEIPT" in _codes(findings)
        assert "DEEP_OK" not in _codes(findings)
    finally:
        rt.close()


def test_missing_receipt_id_is_detected(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        row = rt.store.get_capability("modify_file:*")
        row.receipt_id = None
        rt.store.upsert_capability(row)

        findings = diagnose_deep(rt)
        assert "CAPABILITY_NO_RECEIPT" in _codes(findings)
    finally:
        rt.close()


def test_revoked_receipt_with_admitted_capability_is_detected(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        rt.revoke("modify_file:*")
        # Attacker resurrects the capability row without fresh evidence; the
        # receipt is already revoked by the real revocation path.
        row = rt.store.get_capability("modify_file:*")
        row.state = "ADMITTED"
        rt.store.upsert_capability(row)

        findings = diagnose_deep(rt)
        assert "CAPABILITY_REVOKED_RECEIPT" in _codes(findings)
        assert "DEEP_OK" not in _codes(findings)
    finally:
        rt.close()


def test_active_capability_with_revoked_receipt_is_detected(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        rt.revoke("modify_file:*")
        row = rt.store.get_capability("modify_file:*")
        row.state = "ACTIVE"
        rt.store.upsert_capability(row)

        findings = diagnose_deep(rt)
        codes = _codes(findings)
        assert "CAPABILITY_REVOKED_RECEIPT" in codes
        assert "ACTIVE_REVOKED_RECEIPT" in codes
    finally:
        rt.close()


def test_revocation_not_persisted_is_a_warning_only(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        # Capability marked revoked directly; the receipt was never revoked.
        row = rt.store.get_capability("modify_file:*")
        row.state = "REVOKED"
        rt.store.upsert_capability(row)

        findings = diagnose_deep(rt)
        assert "REVOCATION_NOT_PERSISTED" in _codes(findings)
        assert _errors(findings) == []
    finally:
        rt.close()


def test_exposure_over_budget_is_detected(tmp_path):
    rt = _rt(tmp_path, e_max=1.0)
    try:
        rt.store.add_exposure(
            2.0,
            datetime.now(timezone.utc).isoformat(),
            "modify_file",
            "a.txt",
            "tampered ledger",
        )
        findings = diagnose_deep(rt)
        assert "EXPOSURE_OVER_BUDGET" in _codes(findings)
    finally:
        rt.close()


def test_negative_exposure_row_is_detected(tmp_path):
    rt = _rt(tmp_path)
    try:
        db = rt.config.resolved_state_dir / "crest.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO exposure (amount, timestamp, action_class, target, reason) "
            "VALUES (?,?,?,?,?)",
            (-1.0, "2026-01-01T00:00:00+00:00", "modify_file", "a.txt", "tampered"),
        )
        conn.commit()
        conn.close()

        findings = diagnose_deep(rt)
        assert "EXPOSURE_NEGATIVE" in _codes(findings)
    finally:
        rt.close()


def test_audit_empty_warning_when_capabilities_exist(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        db = rt.config.resolved_state_dir / "crest.db"
        conn = sqlite3.connect(str(db))
        conn.execute("DELETE FROM audit")
        conn.commit()
        conn.close()

        findings = diagnose_deep(rt)
        assert "AUDIT_EMPTY" in _codes(findings)
    finally:
        rt.close()


def test_audit_empty_not_flagged_on_fresh_store(tmp_path):
    # No capabilities yet: an empty audit log is expected, not a warning.
    rt = _rt(tmp_path)
    try:
        findings = diagnose_deep(rt)
        assert "AUDIT_EMPTY" not in _codes(findings)
    finally:
        rt.close()
