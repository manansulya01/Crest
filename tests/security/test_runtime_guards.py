"""Fail-closed guards in the execution window.

These tests simulate concurrent tampering between the admission decision and
execution: the capability can vanish, or its scope can change, after the
decision has been issued. The runtime must deny, revoke, and audit — never
authorize and never crash.
"""
from __future__ import annotations

import sqlite3

import pytest

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def _rt(tmp_path) -> CrestRuntime:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "a.txt").write_text("hello", encoding="utf-8")
    return CrestRuntime(
        CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest")
    )


def _admit(rt: CrestRuntime) -> None:
    rt.verify_and_admit(
        action_class="modify_file",
        scope="*",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        target="data/a.txt",
        trials=3,
    )


def _delete_capability_row(rt: CrestRuntime) -> None:
    conn = sqlite3.connect(str(rt.config.resolved_state_dir / "crest.db"))
    try:
        conn.execute("DELETE FROM capabilities")
        conn.commit()
    finally:
        conn.close()


def _request(rt: CrestRuntime):
    return rt.execute(
        agent_id="agent-1",
        tool="filesystem",
        operation="modify_file",
        arguments={"path": "data/a.txt", "content": "tampered"},
    )


def test_normal_execution_still_succeeds(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        result = _request(rt)
        assert result.ok
        assert (tmp_path / "data" / "a.txt").read_text(encoding="utf-8") == "tampered"
    finally:
        rt.close()


def test_scope_drift_after_decision_denies_and_revokes(tmp_path, monkeypatch):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        original = rt._evaluate

        def tampering_evaluate(*args, **kwargs):
            decision = original(*args, **kwargs)
            if decision.allowed:
                # concurrent tamper: scope narrowed after the decision
                row = rt.store.get_capability(decision.capability_id)
                row.scope = "images/*"
                rt.store.upsert_capability(row)
            return decision

        monkeypatch.setattr(rt, "_evaluate", tampering_evaluate)
        result = _request(rt)

        assert not result.ok
        assert result.reason.startswith("SCOPE_DRIFT")
        assert rt.store.get_capability("modify_file:*").state == "REVOKED"
        assert any(
            event["decision"] == "DRIFT_DETECTED"
            for event in rt.store.recent_audit(20)
        )
        # nothing was executed
        assert (tmp_path / "data" / "a.txt").read_text(encoding="utf-8") == "hello"
    finally:
        rt.close()


def test_vanishing_capability_after_decision_fails_closed(tmp_path, monkeypatch):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        original = rt._evaluate

        def tampering_evaluate(*args, **kwargs):
            decision = original(*args, **kwargs)
            if decision.allowed:
                # concurrent tamper: capability row deleted after the decision
                _delete_capability_row(rt)
            return decision

        monkeypatch.setattr(rt, "_evaluate", tampering_evaluate)
        result = _request(rt)

        assert not result.ok
        assert result.reason == "CAPABILITY_NOT_FOUND"
        assert rt.store.total_exposure() == 0.0
        assert any(
            event["decision"] == "EXECUTION_ERROR"
            for event in rt.store.recent_audit(20)
        )
        assert (tmp_path / "data" / "a.txt").read_text(encoding="utf-8") == "hello"
    finally:
        rt.close()


def test_vanishing_capability_during_reservation_fails_closed(tmp_path, monkeypatch):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        original_reserve = rt.store.try_reserve_exposure

        def tampering_reserve(*args, **kwargs):
            reserved = original_reserve(*args, **kwargs)
            if reserved:
                # concurrent tamper: capability row deleted after the
                # exposure reservation but before the TOCTOU re-check
                _delete_capability_row(rt)
            return reserved

        monkeypatch.setattr(rt.store, "try_reserve_exposure", tampering_reserve)
        result = _request(rt)

        assert not result.ok
        assert result.reason == "CAPABILITY_NOT_FOUND"
        assert (tmp_path / "data" / "a.txt").read_text(encoding="utf-8") == "hello"
    finally:
        rt.close()


def test_revoked_capability_cannot_execute(tmp_path):
    rt = _rt(tmp_path)
    try:
        _admit(rt)
        rt.revoke("modify_file:*")
        result = _request(rt)
        assert not result.ok
        assert result.reason == "CAPABILITY_REVOKED"
    finally:
        rt.close()
