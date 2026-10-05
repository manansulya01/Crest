"""Attack matrix outcomes under each system. Records what ACTUALLY happens.

These tests pin current behavior as a regression baseline; they do not
assume the verifier is unbreakable. Known weakness recorded in
'overfit_distractor_gate': admission succeeds, but the first real-execution
reprobe catches the deception and revokes.
"""
from __future__ import annotations

import pytest

import crest.faults  # noqa: F401
from experiments.attacks.adversary import ATTACKS
from experiments.baselines.session import run_crest, run_self_grading, run_uncontrolled

DENY_ATTACKS = ["failed_recovery", "truncated_recovery", "hidden_side_effect", "stale_recovery", "wrong_target"]


@pytest.mark.parametrize("attack", DENY_ATTACKS)
def test_crest_denies_bad_recoveries(attack):
    sess = run_crest(attack)
    assert sess.realized_harm_events == 0, f"{attack}: crest allowed realized harm"
    assert all((not s.admitted) or s.outcome.startswith("probe_failed") or s.outcome.startswith("security") for s in sess.steps)


def test_crest_denies_partial_directory_recovery():
    from datetime import datetime, timezone

    from crest.constitution import Constitution
    from crest.ledger import ExposureLedger
    from crest.recovery import RecoveryProgram
    from crest.runtime import Runtime
    from crest.verifier import TestConfig

    NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rt = Runtime(
        constitution=Constitution(
            e_max=1.0, min_recovery_success_rate=0.95, max_recovery_p99_ms=10000.0,
            allowed_action_classes=frozenset({"delete_directory"}),
            receipt_ttl_seconds=3600.0, exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )
    decision = rt.evaluate_and_admit(
        action_class="delete_directory", target_scope="*", target="assets", params={},
        recovery=RecoveryProgram(kind="restore_first_only"),
        test_config=TestConfig(trials=5, repeat_trials=1, seed=2), now=NOW,
    )
    assert not decision.allow


def test_baselines_realize_harm_from_partial_recovery():
    un = run_uncontrolled("partial_recovery")
    sg = run_self_grading("partial_recovery")
    assert un.realized_harm_events > 0
    assert sg.realized_harm_events > 0


def test_crest_admits_perfect_recovery():
    sess = run_crest("perfect_recovery")
    assert sess.realized_harm_events == 0
    assert any(s.admitted for s in sess.steps)


def test_crest_denies_slow_recovery_under_tight_bound():
    sess = run_crest("slow_recovery", latency_bound_ms=50.0)
    assert sess.realized_harm_events == 0
    assert all(not s.admitted for s in sess.steps)


def test_overfit_gate_abuses_admission_but_reprobe_catches():
    sess = run_crest("overfit_distractor_gate")
    assert sess.revoked
    assert any(s.outcome == "probe_failed_revoked" for s in sess.steps)


@pytest.mark.parametrize("attack", ["hidden_side_effect", "failed_recovery", "partial_recovery"])
def test_baselines_realize_harm_that_crest_prevents(attack):
    un = run_uncontrolled(attack)
    sg = run_self_grading(attack)
    cr = run_crest(attack)
    assert un.realized_harm_events > 0
    assert sg.realized_harm_events > 0
    assert cr.realized_harm_events == 0
