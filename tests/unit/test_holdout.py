"""Holdout generalization experiment tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import crest.faults  # noqa: F401
import experiments.holdout.arm_faults  # noqa: F401
from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.recovery import RecoveryProgram
from crest.runtime import RecoveryProbeFailure, Runtime
from crest.verifier import TestConfig
from crest.workspace import Workspace

from experiments.holdout.env import TARGET, build_env_a, build_env_b

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_runtime() -> Runtime:
    return Runtime(
        constitution=Constitution(
            e_max=1.0, min_recovery_success_rate=0.95, max_recovery_p99_ms=10000.0,
            allowed_action_classes=frozenset({"delete_file"}),
            receipt_ttl_seconds=3600.0, exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )


def test_environment_a_and_b_differ_deterministically():
    wa, wb = Workspace.temporary(), Workspace.temporary()
    try:
        sa, sb = build_env_a(wa), build_env_b(wb)
        assert sa != sb
        assert all("/" not in k for k in sa)
        assert any("/" in k for k in sb)
        assert sa[TARGET] != sb[TARGET]
    finally:
        wa.cleanup(); wb.cleanup()


def test_exact_state_overfit_passes_A_fails_B():
    rt = make_runtime()
    program = RecoveryProgram(kind="exact_state_gate_restore", params={"prefix": "seed-"})
    decision = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target=TARGET, params={},
        recovery=program, test_config=TestConfig(trials=4, repeat_trials=1, seed=7), now=NOW,
    )
    assert decision.allow  # passes the A-fixture verifier trials

    ws = Workspace.temporary()
    try:
        build_env_b(ws)
        with pytest.raises(RecoveryProbeFailure):
            rt.execute(ws, action_class="delete_file", target=TARGET, estimated_exposure=0.3, now=NOW)
        assert rt.capability("delete_file").state.value == "REVOKED"
    finally:
        ws.cleanup()


def test_perfect_recovery_passes_A_and_B():
    rt = make_runtime()
    program = RecoveryProgram(kind="restore_from_snapshot")
    decision = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target=TARGET, params={},
        recovery=program, test_config=TestConfig(trials=4, repeat_trials=1, seed=7), now=NOW,
    )
    assert decision.allow
    ws = Workspace.temporary()
    try:
        build_env_b(ws)
        res = rt.execute(ws, action_class="delete_file", target=TARGET, estimated_exposure=0.3, now=NOW)
        assert res.ok
    finally:
        ws.cleanup()


def test_existing_overfit_gate_reproduces_under_holdout():
    rt = make_runtime()
    program = RecoveryProgram(kind="overfit_distractor_gate")
    decision = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target=TARGET, params={},
        recovery=program, test_config=TestConfig(trials=4, repeat_trials=1, seed=7), now=NOW,
    )
    assert decision.allow
    ws = Workspace.temporary()
    try:
        build_env_b(ws)
        with pytest.raises(RecoveryProbeFailure):
            rt.execute(ws, action_class="delete_file", target=TARGET, estimated_exposure=0.3, now=NOW)
    finally:
        ws.cleanup()


def test_learner_metadata_has_no_holdout_access():
    from experiments.attacks.adversary import ScriptedAdversary

    learner = ScriptedAdversary("restore_from_snapshot")
    assert not any(hasattr(learner, name) for name in ("holdout", "env_b", "environment_b", "expected_outcome"))
