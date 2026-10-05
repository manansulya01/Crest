"""Milestone 2 security invariants (extends Milestone 1)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import crest.faults  # noqa: F401  register fault handlers
from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.recovery import RecoveryProgram
from crest.runtime import RecoveryProbeFailure, Runtime, SecurityError
from crest.verifier import TestConfig
from crest.workspace import Workspace

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_runtime() -> Runtime:
    return Runtime(
        constitution=Constitution(
            e_max=1.0,
            min_recovery_success_rate=0.95,
            max_recovery_p99_ms=10000.0,
            allowed_action_classes=frozenset({"delete_file", "modify_file"}),
            receipt_ttl_seconds=3600.0,
            exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )


def admit(rt, recovery, seed_content=None):
    return rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target="a.txt", params={},
        recovery=recovery,
        test_config=TestConfig(trials=5, repeat_trials=1, seed=3, seed_target_content=seed_content),
        now=NOW,
    )


def test_distribution_shift_triggers_revocation():
    rt = make_runtime()
    # Verification environment: target content happens to equal what the
    # stale recovery writes, so the bad program PASSES verification.
    d = admit(rt, RecoveryProgram(kind="restore_stale"), seed_content="STALE CONTENT")
    assert d.allow  # the verifier was fooled by the homogeneous environment

    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"REAL DATA")  # environment has shifted
        with pytest.raises(RecoveryProbeFailure):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.3, now=NOW)
        assert rt.capability("delete_file").state.value == "REVOKED"
    finally:
        ws.cleanup()


def test_replayed_receipt_cannot_silently_preserve_authority_after_shift():
    rt = make_runtime()
    d = admit(rt, RecoveryProgram(kind="restore_stale"), seed_content="STALE CONTENT")
    assert d.allow

    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"REAL DATA")
        with pytest.raises(RecoveryProbeFailure):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.3, now=NOW)
        # same admission record, shifted environment: second attempt must deny
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.3, now=NOW)
    finally:
        ws.cleanup()


def test_repeated_execution_cannot_reset_exposure_budget():
    rt = make_runtime()
    d = admit(rt, RecoveryProgram(kind="restore_from_snapshot"))
    assert d.allow
    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"x")
        rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.4, now=NOW)
        ws.write("a.txt", b"y")
        rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.4, now=NOW)
        assert abs(rt.ledger.total() - 0.8) < 1e-9
        ws.write("a.txt", b"z")
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.4, now=NOW)
    finally:
        ws.cleanup()


def test_out_of_scope_target_denied_even_after_admit():
    rt = make_runtime()
    d = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="a.txt", target="a.txt", params={},
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        test_config=TestConfig(trials=4, repeat_trials=1, seed=1), now=NOW,
    )
    assert d.allow
    ws = Workspace.temporary()
    try:
        ws.write("other.txt", b"z")
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="other.txt", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()
