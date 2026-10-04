"""Milestone-1 end-to-end test: admit, execute, keep active, then revoke."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crest.capabilities import CapabilityState
from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.learner import BrokenProposer, HeuristicProposer
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
            allowed_action_classes=frozenset({"delete_file"}),
            receipt_ttl_seconds=3600.0,
            exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )


def test_milestone1_full_cycle():
    rt = make_runtime()
    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"important")
        learner = HeuristicProposer()
        recovery = learner.propose("delete_file", "a.txt")

        decision = rt.evaluate_and_admit(
            action_class="delete_file", target_scope="*", target="a.txt", params={},
            recovery=recovery, test_config=TestConfig(trials=8, repeat_trials=2, seed=7), now=NOW,
        )
        assert decision.allow
        assert rt.capability("delete_file").state == CapabilityState.ADMITTED

        result = rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.2, now=NOW)
        assert result.ok and not ws.exists("a.txt")
        assert rt.capability("delete_file").state == CapabilityState.ACTIVE
    finally:
        ws.cleanup()


def test_broken_recovery_fails_verification_and_blocks():
    rt = make_runtime()
    recovery = BrokenProposer().propose("delete_file", "a.txt")
    decision = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target="a.txt", params={},
        recovery=recovery, test_config=TestConfig(trials=5, repeat_trials=1, seed=3), now=NOW,
    )
    assert not decision.allow
    assert rt.capability("delete_file").state == CapabilityState.FORBIDDEN


def test_probe_failure_revokes_capability():
    rt = make_runtime()
    learner = HeuristicProposer()
    recovery = learner.propose("delete_file", "a.txt")
    decision = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target="a.txt", params={},
        recovery=recovery, test_config=TestConfig(trials=5, repeat_trials=1, seed=5), now=NOW,
    )
    assert decision.allow

    # Environment drift: recovery program silently stops working (simulated by
    # substituting a noop program that the learner now controls).
    from crest.recovery import RecoveryProgram

    rt.register_recovery_program("delete_file", RecoveryProgram(kind="noop"))

    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"important")
        with pytest.raises(RecoveryProbeFailure):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.2, now=NOW)
        assert rt.capability("delete_file").state == CapabilityState.REVOKED
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.2, now=NOW)
    finally:
        ws.cleanup()
