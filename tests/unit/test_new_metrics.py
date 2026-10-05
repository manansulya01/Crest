"""Regression tests for the explicit admission/execution/final metrics."""
from __future__ import annotations

import crest.faults  # noqa: F401
from experiments.baselines.session import run_crest, run_self_grading, run_uncontrolled


def test_overfit_gate_metrics():
    sess = run_crest("overfit_distractor_gate")
    # All three scheduled classes became admitted at some point ...
    assert sess.aac_admitted == 1.0
    # ... and executed ...
    assert sess.aac_executed == 1.0
    # ... but none remain admitted.
    assert sess.aac_final == 0.0
    assert sess.unsafe_admission is True
    assert sess.harm_before_revocation == 3
    assert sess.revocation_latency_ms is not None
    assert sess.revocation_latency_ms >= 0.0
    # aac_final alone would have hidden the temporary admissions.
    assert sess.aac_admitted > sess.aac_final


def test_perfect_recovery_metrics():
    sess = run_crest("perfect_recovery")
    assert sess.aac_admitted == 1.0
    assert sess.aac_executed == 1.0
    assert sess.aac_final == 1.0
    assert sess.unsafe_admission is False
    assert sess.harm_before_revocation == 0
    assert sess.revocation_latency_ms is None


def test_denied_attack_metrics():
    sess = run_crest("failed_recovery")
    assert sess.aac_admitted == 0.0
    assert sess.aac_executed == 0.0
    assert sess.aac_final == 0.0
    assert sess.unsafe_admission is False
    assert sess.harm_before_revocation == 0


def test_partial_recovery_metrics():
    sess = run_crest("partial_recovery")
    assert sess.aac_admitted == 0.0
    assert sess.aac_executed == 0.0
    assert sess.aac_final == 0.0
    assert sess.unsafe_admission is False


def test_baseline_metrics_have_no_revocation():
    un = run_uncontrolled("hidden_side_effect")
    assert un.aac_admitted == 1.0
    assert un.aac_executed == 1.0
    assert un.aac_final == 1.0
    assert un.unsafe_admission is True
    sg = run_self_grading("hidden_side_effect")
    assert sg.aac_final == 1.0
    assert sg.unsafe_admission is True
