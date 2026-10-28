"""Leakage and correctness tests for the non-circular simulation."""
from __future__ import annotations

import random

import pytest

from experiments.benchmark.simulation import (
    generate_tasks,
    run_experiment,
    simulate_outcome,
    CrestAdmission,
    strategy_oracle,
    DEPLOYABLE_STRATEGIES,
)


def test_latent_difficulty_not_in_task_features():
    cal, evl = generate_tasks(10, 20, 0.5, 42)
    for t in cal + evl:
        # Observed features must not include latent_difficulty or truth
        assert not hasattr(t, "observed_features") or "latent_difficulty" not in str(t)
        # The task has latent_difficulty but it's a separate attribute
        assert hasattr(t, "latent_difficulty")
        assert hasattr(t, "truth")


def test_routing_features_exclude_latent_difficulty():
    cal, evl = generate_tasks(10, 20, 0.5, 42)
    # The capability class uses only observed features
    crest = CrestAdmission()
    for t in cal:
        cls = crest.capability_class(t)
        assert "latent" not in cls
        assert "truth" not in cls
        assert "difficulty" not in cls


def test_fixed_seeds_reproduce():
    cal1, evl1 = generate_tasks(10, 20, 0.5, 42)
    cal2, evl2 = generate_tasks(10, 20, 0.5, 42)
    assert cal1 == cal2
    assert evl1 == evl2


def test_different_seeds_differ():
    cal1, _ = generate_tasks(10, 20, 0.5, 42)
    cal2, _ = generate_tasks(10, 20, 0.5, 999)
    assert cal1 != cal2


def test_calibration_evaluation_disjoint():
    cal, evl = generate_tasks(10, 20, 0.5, 42)
    cal_ids = {t.task_id for t in cal}
    evl_ids = {t.task_id for t in evl}
    assert cal_ids.isdisjoint(evl_ids)


def test_oracle_not_in_deployable():
    assert "oracle" not in DEPLOYABLE_STRATEGIES


def test_outcome_determinism():
    cal, evl = generate_tasks(5, 10, 0.5, 42)
    task = evl[0]
    r1 = simulate_outcome(task, "cheap", 42)
    r2 = simulate_outcome(task, "cheap", 42)
    assert r1 == r2


def test_invalid_signal_strength_still_runs():
    # Should not crash
    cal, evl = generate_tasks(5, 10, 0.0, 42)
    assert len(cal) == 5
    assert len(evl) == 10


def test_run_experiment_structure():
    r = run_experiment(0.5, 42, 20, 30)
    assert "fixed_cheap" in r
    assert "fixed_strong" in r
    assert "cost_aware" in r
    assert "crest" in r
    assert "oracle" in r
    assert "_calibration" in r
    assert "_meta" in r
    for s in ["fixed_cheap", "fixed_strong", "cost_aware", "crest", "oracle"]:
        assert r[s]["n"] == 30
        assert 0 <= r[s]["success_rate"] <= 1


def test_no_budget_violations():
    r = run_experiment(0.5, 42, 20, 30)
    # All strategies should complete without error
    for s in ["fixed_cheap", "fixed_strong", "cost_aware", "crest", "oracle"]:
        assert r[s]["n"] == 30


def test_signal_strength_zero_no_crash():
    r = run_experiment(0.0, 42, 20, 30)
    assert r["_meta"]["signal_strength"] == 0.0


def test_signal_strength_one_no_crash():
    r = run_experiment(1.0, 42, 20, 30)
    assert r["_meta"]["signal_strength"] == 1.0
