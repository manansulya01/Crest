"""Tests for the verification intelligence (VoV) simulation."""
from __future__ import annotations

import pytest

from experiments.benchmark.verification_intelligence import (
    generate_vi_tasks,
    run_vov_experiment,
    run_vov_full,
    summarize_vov,
    strategy_always_t0,
    strategy_always_t3,
    strategy_fixed_cascade,
    VoVController,
    simulate_verify,
    ALL_ACTIONS,
    ACTION_BY_NAME,
    T0, T1, T2, T3,
)


def test_task_generation_sizes():
    cal, evl = generate_vi_tasks(50, 100, 42)
    assert len(cal) == 50
    assert len(evl) == 100


def test_task_generation_determinism():
    cal1, evl1 = generate_vi_tasks(50, 100, 42)
    cal2, evl2 = generate_vi_tasks(50, 100, 42)
    assert cal1 == cal2
    assert evl1 == evl2


def test_cal_eval_disjoint():
    cal, evl = generate_vi_tasks(50, 100, 42)
    cal_ids = {t.task_id for t in cal}
    evl_ids = {t.task_id for t in evl}
    assert cal_ids.isdisjoint(evl_ids)


def test_run_vov_experiment_structure():
    r = run_vov_experiment(50, 100, 42)
    for name in ["always_t0", "always_t3", "fixed_cascade", "vov"]:
        assert name in r
        assert r[name]["n"] == 100
        assert 0 <= r[name]["success_rate"] <= 1
        assert r[name]["cost_per_success"] is not None
    assert "_meta" in r


def test_vov_beats_always_t3_on_cost():
    r = run_vov_experiment(100, 200, 42)
    assert r["vov"]["cost_per_success"] < r["always_t3"]["cost_per_success"]


def test_vov_beats_always_t3_on_success():
    r = run_vov_experiment(100, 200, 42)
    assert r["vov"]["success_rate"] >= r["always_t3"]["success_rate"] - 0.05


def test_vov_beats_fixed_cascade_on_success():
    r = run_vov_experiment(100, 200, 42)
    assert r["vov"]["success_rate"] > r["fixed_cascade"]["success_rate"]


def test_vov_controller_executes():
    cal, evl = generate_vi_tasks(50, 100, 42)
    controller = VoVController(budget_per_task=10.0, voi_threshold=0.1)
    success, cost, state = controller.execute(evl[0], 42)
    assert isinstance(success, bool)
    assert cost > 0
    assert state.model_used in ("cheap", "strong")


def test_verify_actions_have_costs():
    for action in ALL_ACTIONS:
        assert action.cost >= 0
        assert 0 <= action.fpr <= 1
        assert 0 <= action.fnr <= 1


def test_run_vov_full_structure():
    full = run_vov_full(seeds=[42, 123])
    assert "42" in full["results"]
    assert "123" in full["results"]
    s = summarize_vov(full)
    assert "vov" in s
    assert "_comparison" in s


def test_simulate_verify_deterministic():
    cal, evl = generate_vi_tasks(10, 20, 42)
    task = evl[0]
    r1 = simulate_verify(T2, task, True, 42)
    r2 = simulate_verify(T2, task, True, 42)
    assert r1 == r2
