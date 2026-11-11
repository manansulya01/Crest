"""Focused tests for the Sequential Evidence Accumulation (SEA) prototype."""
from __future__ import annotations

import math

import pytest

from experiments.benchmark.sequential_evidence import (
    calibrate_base_rates,
    strategy_sequential,
    run_sea_experiment,
    run_sea_full,
    summarize_sea,
    _llr,
)
from experiments.benchmark.verification_intelligence import (
    generate_vi_tasks,
    simulate_verify,
    T0,
    T1,
    T2,
    T3,
)


def test_llr_direction():
    # A pass must be positive evidence for correctness; a fail must be negative.
    assert _llr(T3, True) > 0
    assert _llr(T3, False) < 0
    # Stronger verifier (lower FPR) contributes more evidence.
    assert _llr(T3, True) > _llr(T2, True) > _llr(T1, True) > _llr(T0, True)


def test_generate_vi_tasks_determinism():
    cal1, evl1 = generate_vi_tasks(20, 30, 42)
    cal2, evl2 = generate_vi_tasks(20, 30, 42)
    assert cal1 == cal2 and evl1 == evl2


def test_cal_eval_disjoint():
    cal, evl = generate_vi_tasks(20, 30, 42)
    assert {t.task_id for t in cal}.isdisjoint({t.task_id for t in evl})


def test_calibrate_base_rates_uses_calibration_split():
    cal, evl = generate_vi_tasks(50, 100, 42)
    rates = calibrate_base_rates(cal, 42)
    # Every returned rate must lie strictly inside (0, 1) so log-odds are finite.
    assert rates
    for risk, p in rates.items():
        assert 0.0 < p < 1.0


def test_calibrate_base_rates_matches_empirical():
    import random
    from experiments.benchmark import verification_intelligence as vi
    from experiments.benchmark.verification_intelligence import _stable_seed

    cal, _ = generate_vi_tasks(80, 40, 42)
    rates = calibrate_base_rates(cal, 42)
    for risk in {t.risk_level for t in cal}:
        subset = [t for t in cal if t.risk_level == risk]
        correct = 0
        for t in subset:
            rng = random.Random(_stable_seed(t.task_id, "cheap", 42))
            if rng.random() > (0.05 + 0.4 * t.latent_difficulty):
                correct += 1
        expected = min(max(correct / len(subset), 0.05), 0.95)
        assert abs(rates[risk] - expected) < 1e-9


def test_strategy_sequential_returns_safe_values():
    cal, evl = generate_vi_tasks(50, 100, 42)
    rates = calibrate_base_rates(cal, 42)
    for task in evl[:5]:
        success, cost, trace = strategy_sequential(task, 42, rates)
        assert isinstance(success, bool)
        assert cost > 0
        assert isinstance(trace, dict)


def test_strategy_sequential_is_deterministic():
    cal, evl = generate_vi_tasks(50, 100, 42)
    rates = calibrate_base_rates(cal, 42)
    a = [strategy_sequential(t, 42, rates) for t in evl[:10]]
    b = [strategy_sequential(t, 42, rates) for t in evl[:10]]
    assert a == b


def test_risk_weights_raise_evidence_threshold():
    cal, evl = generate_vi_tasks(50, 100, 42)
    rates = calibrate_base_rates(cal, 42)
    task = next(t for t in evl if t.risk_level == "high")
    _, cost_low_risk, _ = strategy_sequential(
        task, 42, rates, risk_weights={"low": 1.0, "med": 2.0, "high": 1.0})
    _, cost_high_risk, _ = strategy_sequential(
        task, 42, rates, risk_weights={"low": 1.0, "med": 2.0, "high": 20.0})
    assert cost_high_risk >= cost_low_risk


def test_run_sea_experiment_structure():
    r = run_sea_experiment(50, 100, seed=42)
    assert "sea" in r
    assert r["sea"]["n"] == 100
    assert 0 <= r["sea"]["success_rate"] <= 1
    assert r["sea"]["cost_per_success"] is not None
    assert "_sea_priors" in r


def test_run_sea_full_and_summary():
    full = run_sea_full(seeds=[42, 123])
    s = summarize_sea(full)
    assert "sea" in s
    for name in ("always_t0", "always_t3", "fixed_cascade", "vov", "sea"):
        assert name in s


def test_verify_actions_ordering_by_cost():
    assert T0.cost < T1.cost < T2.cost < T3.cost
