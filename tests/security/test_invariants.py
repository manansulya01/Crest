"""Automated tests for the security invariants in the specification."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from crest.capabilities import CapabilityState
from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.learner import BrokenProposer, HeuristicProposer
from crest.receipts import CapabilityReceipt, RecoveryEvidence
from crest.runtime import Runtime, SecurityError
from crest.verifier import TestConfig, Verifier
from crest.workspace import Workspace

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_runtime() -> Runtime:
    constitution = Constitution(
        e_max=1.0,
        min_recovery_success_rate=0.95,
        max_recovery_p99_ms=10000.0,
        allowed_action_classes=frozenset({"delete_file"}),
        receipt_ttl_seconds=3600.0,
        exposure_window_seconds=3600.0,
    )
    return Runtime(constitution=constitution, ledger=ExposureLedger())


def admit_delete_file(rt: Runtime, recovery=None, target="a.txt"):
    learner = HeuristicProposer()
    recovery = recovery or learner.propose("delete_file", target)
    return rt.evaluate_and_admit(
        action_class="delete_file",
        target_scope="*",
        target=target,
        params={},
        recovery=recovery,
        test_config=TestConfig(trials=5, repeat_trials=1, seed=1),
        now=NOW,
    )


def make_ws(target="a.txt") -> Workspace:
    ws = Workspace.temporary()
    ws.write(target, b"hello")
    return ws


def test_invariant1_unverified_action_cannot_execute():
    rt = make_runtime()
    ws = make_ws()
    try:
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW)
        assert ws.exists("a.txt")
    finally:
        ws.cleanup()


def test_invariant2_learner_cannot_grant_capability():
    learner = HeuristicProposer()
    assert not any(
        hasattr(learner, name)
        for name in ("grant", "admit", "execute", "transition", "revoke", "set_state", "approve")
    )
    rt = make_runtime()
    rt.evaluate_and_admit  # only Runtime mutates capability state
    assert rt.capability("delete_file").state == CapabilityState.FORBIDDEN


def test_invariant3_learner_cannot_modify_e_max():
    rt = make_runtime()
    with pytest.raises(FrozenInstanceError):
        rt.constitution.e_max = 999  # type: ignore[misc]


def test_invariant4_learner_cannot_modify_ledger():
    learner = HeuristicProposer()
    assert not hasattr(learner, "ledger")
    rt = make_runtime()
    assert rt.ledger.total() == 0.0
    assert not hasattr(learner.propose("delete_file", "a.txt"), "ledger")


def test_invariant5_learner_cannot_manufacture_receipt():
    rt = make_runtime()
    forged = CapabilityReceipt.create(
        action_class="delete_file",
        target_scope="*",
        recovery_program_digest="forged",
        evidence=RecoveryEvidence(
            test_count=1000, failed_tests=0, recovery_success_rate=1.0,
            recovery_latency_p50_ms=1, recovery_latency_p95_ms=1, recovery_latency_p99_ms=1,
            residual_exposure_ucb=0.0, propagation_depth=0,
            verification_environment="sandbox-v1", verification_version="sandbox-v1",
            test_config_digest="fake", random_seed=0,
        ),
        status="VERIFIED",
        now=NOW,
        ttl_seconds=3600,
    )
    # Learner injects the forged receipt directly into the runtime's store.
    rt.receipts["delete_file"] = forged
    # But the capability was never admitted through the constitutional path.
    assert not rt.capability("delete_file").executable
    ws = make_ws()
    try:
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()


def test_invariant6_revoked_capability_cannot_execute():
    rt = make_runtime()
    d = admit_delete_file(rt)
    assert d.allow
    rt.revoke("delete_file", "test")
    ws = make_ws()
    try:
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()


def test_invariant7_failed_verification_cannot_expand_scope():
    rt = make_runtime()
    d = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*", target="a.txt", params={},
        recovery=BrokenProposer().propose("delete_file", "a.txt"),
        test_config=TestConfig(trials=5, repeat_trials=1, seed=1), now=NOW,
    )
    assert not d.allow
    assert rt.capability("delete_file").state == CapabilityState.FORBIDDEN
    ws = make_ws()
    try:
        assert ws.exists("a.txt")
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()


def test_invariant8_receipt_scope_must_match_target():
    rt = make_runtime()
    d = rt.evaluate_and_admit(
        action_class="delete_file", target_scope="*.txt", target="a.txt", params={},
        recovery=HeuristicProposer().propose("delete_file", "a.txt"),
        test_config=TestConfig(trials=5, repeat_trials=1, seed=1), now=NOW,
    )
    assert d.allow
    ws = make_ws("b.json")
    try:
        ws.write("a.txt", b"x")
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="b.json", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()


def test_invariant9_expired_receipt_cannot_authorize():
    rt = make_runtime()
    d = admit_delete_file(rt)
    assert d.allow
    ws = make_ws()
    try:
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW + timedelta(hours=2))
    finally:
        ws.cleanup()


def test_invariant10_recovery_does_not_refund_exposure():
    rt = make_runtime()
    d = admit_delete_file(rt)
    assert d.allow
    ws = make_ws()
    try:
        res = rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.5, now=NOW)
        assert res.ok
        assert rt.ledger.total() == 0.5
    finally:
        ws.cleanup()


def test_tampered_receipt_rejected():
    rt = make_runtime()
    d = admit_delete_file(rt)
    assert d.allow
    receipt = rt.receipts["delete_file"]
    import dataclasses as dc

    tampered = dc.replace(receipt, target_scope="**/*")
    assert not tampered.is_hash_valid()
    rt.receipts["delete_file"] = tampered
    ws = make_ws()
    try:
        with pytest.raises(SecurityError):
            rt.execute(ws, action_class="delete_file", target="a.txt", estimated_exposure=0.1, now=NOW)
    finally:
        ws.cleanup()
