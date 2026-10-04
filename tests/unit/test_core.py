"""Unit tests for constitutional rules, state machine, receipts, workspace."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from crest.admission import admit
from crest.capabilities import Capability, CapabilityState, IllegalTransition
from crest.constitution import Constitution
from crest.receipts import CapabilityReceipt, RecoveryEvidence
from crest.workspace import Workspace, WorkspaceError


def make_constitution() -> Constitution:
    return Constitution(
        e_max=1.0,
        min_recovery_success_rate=0.95,
        max_recovery_p99_ms=5000.0,
        allowed_action_classes=frozenset({"delete_file"}),
        receipt_ttl_seconds=3600.0,
        exposure_window_seconds=3600.0,
    )


def make_evidence(**over) -> RecoveryEvidence:
    base = dict(
        test_count=10,
        failed_tests=0,
        recovery_success_rate=1.0,
        recovery_latency_p50_ms=1.0,
        recovery_latency_p95_ms=2.0,
        recovery_latency_p99_ms=3.0,
        residual_exposure_ucb=0.01,
        propagation_depth=0,
        verification_environment="sandbox-v1",
        verification_version="sandbox-v1",
        test_config_digest="x",
        random_seed=0,
    )
    base.update(over)
    return RecoveryEvidence(**base)


def test_illegal_transition_proposed_to_admitted():
    cap = Capability("delete_file")
    cap.transition(CapabilityState.PROPOSED)
    with pytest.raises(IllegalTransition):
        cap.transition(CapabilityState.ADMITTED)


def test_cannot_skip_verification():
    cap = Capability("delete_file")
    with pytest.raises(IllegalTransition):
        cap.transition(CapabilityState.VERIFYING)
    cap.transition(CapabilityState.PROPOSED)
    with pytest.raises(IllegalTransition):
        cap.transition(CapabilityState.VERIFIED)


def test_revoked_requires_reverification():
    cap = Capability("delete_file")
    for s in (CapabilityState.PROPOSED, CapabilityState.VERIFYING, CapabilityState.VERIFIED, CapabilityState.ADMITTED, CapabilityState.ACTIVE, CapabilityState.REVOKED):
        cap.transition(s)
    with pytest.raises(IllegalTransition):
        cap.transition(CapabilityState.ADMITTED)
    cap.transition(CapabilityState.VERIFYING)


def test_workspace_path_escape_blocked():
    ws = Workspace.temporary()
    try:
        with pytest.raises(WorkspaceError):
            ws.read("../outside.txt")
    finally:
        ws.cleanup()


def test_admission_denies_expired_and_failed():
    now = datetime.now(timezone.utc)
    ev = make_evidence()
    r = CapabilityReceipt.create(
        action_class="delete_file",
        target_scope="*",
        recovery_program_digest="d",
        evidence=ev,
        status="VERIFIED",
        now=now - timedelta(hours=2),
        ttl_seconds=60,
    )
    d = admit(receipt=r, current_exposure=0.0, constitution=make_constitution(), now=now)
    assert not d.allow and any("expired" in reason for reason in d.reasons)
