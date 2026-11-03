"""Tests for the adaptive verification simulation."""
from __future__ import annotations

import pytest

from experiments.benchmark.adaptive_verification import (
    generate_av_tasks,
    run_av_experiment,
    run_av_full,
    summarize_av,
    strategy_always_t0,
    strategy_always_t3,
    strategy_fixed_cascade,
    strategy_adaptive,
    verify_t0,
    verify_t1,
    calibrate,
    CHEAP_MODEL_COST,
    STRONG_MODEL_COST,
)


def test_task_generation_sizes():
    cal, evl = generate_av_tasks(50, 100, 42)
    assert len(cal) == 50
    assert len(evl) == 100


def test_task_generation_determinism():
    cal1, evl1 = generate_av_tasks(50, 100, 42)
    cal2, evl2 = generate_av_tasks(50, 100, 42)
    assert cal1 == cal2
    assert evl1 == evl2


def test_task_generation_different_seeds():
    cal1, _ = generate_av_tasks(50, 100, 42)
    cal2, _ = generate_av_tasks(50, 100, 999)
    assert cal1 != cal2


def test_cal_eval_disjoint():
    cal, evl = generate_av_tasks(50, 100, 42)
    cal_ids = {t.task_id for t in cal}
    evl_ids = {t.task_id for t in evl}
    assert cal_ids.isdisjoint(evl_ids)


def test_verify_t0_valid_json():
    assert verify_t0('{"a": 1, "b": 2}', ("a", "b")) is True


def test_verify_t0_invalid_json():
    assert verify_t0("not json", ("a", "b")) is False


def test_verify_t0_missing_key():
    assert verify_t0('{"a": 1}', ("a", "b")) is False


def test_run_av_experiment_structure():
    r = run_av_experiment(50, 100, 42)
    for name in ["always_t0", "always_t3", "fixed_cascade", "adaptive"]:
        assert name in r
        assert r[name]["n"] == 100
        assert 0 <= r[name]["success_rate"] <= 1
        assert r[name]["cost_per_success"] is not None
    assert "_calibration" in r
    assert "_meta" in r


def test_adaptive_beats_always_t3_on_cost():
    """Adaptive should be cheaper than always-T3."""
    r = run_av_experiment(100, 200, 42)
    assert r["adaptive"]["cost_per_success"] < r["always_t3"]["cost_per_success"]


def test_adaptive_beats_fixed_cascade_on_success():
    """Adaptive should have higher success than fixed cascade."""
    r = run_av_experiment(100, 200, 42)
    assert r["adaptive"]["success_rate"] >= r["fixed_cascade"]["success_rate"]


def test_run_av_full_structure():
    full = run_av_full(seeds=[42, 123])
    assert "42" in full["results"]
    assert "123" in full["results"]
    s = summarize_av(full)
    assert "adaptive" in s
    assert "_comparison" in s


def test_hidden_difficulty_not_in_routing():
    """Verify that the routing class uses only observed features."""
    cal, evl = generate_av_tasks(50, 100, 42)
    for task in cal:
        cls = "multi" if task.multi_constraint else "single"
        assert "hidden" not in cls
        assert "difficulty" not in cls
        assert "truth" not in cls
