"""Focused tests for the V0.7 benchmark slice (fake mode only — no network)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.benchmark import tasks as tasklib
from experiments.benchmark.adapters import FakeTaskModelAdapter
from experiments.benchmark.pilot import run as run_pilot, BudgetGuard, BudgetGuardExceeded
from experiments.benchmark.strategies import calibrate_crest, capability_of
from experiments.benchmark.tasks import (
    PROMPT_SYSTEM,
    SPLIT_SIZES,
    generate_tasks,
    derive_features,
    score,
    parse_response_json,
    digest,
)

ROOT = Path(__file__).resolve().parents[2]


def test_dataset_sizes_and_splits():
    tasks = generate_tasks()
    assert len(tasks) == sum(SPLIT_SIZES.values())
    assert sum(1 for t in tasks if t.split == "calibration") == SPLIT_SIZES["calibration"]
    assert sum(1 for t in tasks if t.split == "pilot") == SPLIT_SIZES["pilot"]
    assert sum(1 for t in tasks if t.split == "heldout") == SPLIT_SIZES["heldout"]
    assert SPLIT_SIZES["heldout"] >= 100


def test_dataset_digest_is_deterministic():
    assert digest(generate_tasks()) == digest(generate_tasks())


def test_feature_multi_constraint_matches_task_attribute():
    for task in generate_tasks():
        assert derive_features(task.text).multi_topic == task.multi_constraint


def test_derive_features_does_not_read_gold_labels():
    # RoutingFeatures exposes only text-derived fields; no gold answer.
    names = {f.name for f in derive_features("hello").__dataclass_fields__.values()}
    assert "gold" not in names and "answer" not in names
    assert {"first_sentence_category_hint", "multi_topic", "urgent_marker", "deadline_phrase", "refund_phrase"} == names


def test_oracle_exact_match_and_failures():
    tasks = generate_tasks()
    task = tasks[SPLIT_SIZES["calibration"] + 1]  # a pilot task
    gold_text = __import__("json").dumps(task.gold)
    assert score(task, gold_text)["correct"] is True
    wrong = dict(task.gold)
    wrong["category"] = "general_help"
    assert score(task, __import__("json").dumps(wrong))["correct"] is False
    assert score(task, "not json at all")["correct"] is False
    missing = {k: v for k, v in task.gold.items() if k != "due_date"}
    assert score(task, __import__("json").dumps(missing))["correct"] is False
    # parse helper returns None for junk
    assert parse_response_json("no braces here") is None


def test_fake_cheap_model_fails_on_some_multi_topic_tasks():
    tasks = generate_tasks()
    by_id = {t.task_id: t for t in tasks}
    cheap = FakeTaskModelAdapter(by_id, cheap=True)
    failures = 0
    for task in tasks:
        if not task.multi_constraint:
            continue
        from crest.inference import InferenceRequest

        req = InferenceRequest(
            request_id=f"probe::{task.task_id}::0",
            model="cheap",
            prompt=task.text,
            max_output_tokens=100,
        )
        resp = cheap.complete(req, timeout_seconds=1.0)
        verdict = score(task, resp.text)
        if not verdict["correct"]:
            failures += 1
    assert failures >= 1, "cheap fake model must fail on at least one multi-topic task"


def test_large_fake_model_is_always_correct():
    tasks = generate_tasks()
    by_id = {t.task_id: t for t in tasks}
    large = FakeTaskModelAdapter(by_id, cheap=False)
    for task in tasks:
        from crest.inference import InferenceRequest

        req = InferenceRequest(
            request_id=f"probe::{task.task_id}::0",
            model="large",
            prompt=task.text,
            max_output_tokens=100,
        )
        resp = large.complete(req, timeout_seconds=1.0)
        assert score(task, resp.text)["correct"] is True


def test_calibration_admission_shape_and_threshold():
    tasks = generate_tasks()
    calibration = [t for t in tasks if t.split == "calibration"]
    by_id = {t.task_id: t for t in tasks}
    from crest.store import Store
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "crest.db")
        from crest.inference import InferencePolicy, InferenceRuntime
        from experiments.benchmark.adapters import MultiModelAdapter

        policy = InferencePolicy(
            allowed_models=("gemini-3.5-flash-lite",),
            max_input_tokens=4096,
            max_output_tokens=120,
            request_timeout_seconds=10.0,
            max_attempts=1,
            retry_on_transient=False,
            retry_backoff_seconds=0.0,
            window_budget_units=1e9,
            max_cost_units_per_request=1e9,
            require_usage=True,
        )
        adapter = MultiModelAdapter({"gemini-3.5-flash-lite": FakeTaskModelAdapter(by_id, cheap=True)})
        result = calibrate_crest(
            calibration,
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            store,
            policy,
            adapter,
        )
        assert set(result["admission"].keys()) == {"single_topic", "multi_topic"}
        # With 120 calibration tasks: single-topic (0 failures in 77) is admitted
        # (upper bound 0.0339 <= 0.05); multi-topic (4 failures in 43) is not
        # (upper bound 0.1918 > 0.05).
        assert result["admission"]["single_topic"] is True
        assert result["admission"]["multi_topic"] is False
        store.close()


def test_pilot_fake_run_end_to_end():
    artifact = run_pilot(mode="fake", stage_max_attempts=300)
    assert artifact["mode"] == "fake"
    assert artifact["status"] == "COMPLETE"
    summary = artifact["summary"]
    assert set(summary.keys()) == {"cost_aware_small", "crest_policy", "fixed_large", "cascade"}
    # Fake cheap model misses some tasks; baselines differ in success.
    assert summary["cost_aware_small"]["task_success_rate"] <= summary["fixed_large"]["task_success_rate"]
    # CREST (strict admission) degenerates to fixed_large on this calibration size.
    assert summary["crest_policy"]["task_success_rate"] == summary["fixed_large"]["task_success_rate"]
    # Guard respected.
    assert artifact["guard_final"]["attempts"] <= artifact["budget_guard"]["max_request_attempts"]
    # No not-run rows in fake mode (strong model healthy).
    assert "not_run_rows" not in artifact or not artifact["not_run_rows"]


def test_pilot_fake_run_is_reproducible():
    a = run_pilot(mode="fake", stage_max_attempts=300)
    b = run_pilot(mode="fake", stage_max_attempts=300)
    assert a["summary"] == b["summary"]
    # Latency varies run-to-run; compare rows excluding latency_ms.
    def strip_latency(rows):
        return [{k: v for k, v in r.items() if k != "latency_ms"} for r in rows]
    assert strip_latency(a["pilot_rows"]) == strip_latency(b["pilot_rows"])


def test_budget_guard_caps():
    guard = BudgetGuard(max_attempts=2, usd_cap=0.01)
    # attempts cap
    with pytest.raises(BudgetGuardExceeded):
        guard.observe("gemini-3.5-flash-lite", 3, 100, 10, require_price=True)
    # unknown usage (require_price=True on a denied/unknown) is tested via run()
    guard2 = BudgetGuard(max_attempts=100, usd_cap=0.000001)
    with pytest.raises(BudgetGuardExceeded):
        guard2.observe("gemini-3.5-flash-lite", 1, 100000, 100000, require_price=True)


def test_pilot_halts_on_low_caps():
    artifact = run_pilot(mode="fake", stage_max_attempts=3, usd_cap=0.000001)
    assert artifact["status"] == "HALTED_BUDGET_GUARD"


def test_admission_threshold_math():
    from crest.policy import failure_upper_bound_at

    # With zero observed failures, the 95% one-sided Wilson upper bound reaches
    # the 0.05 admission threshold only at n >= 52 (mathematical floor).
    assert failure_upper_bound_at(0, 51, 0.95) > 0.05
    assert failure_upper_bound_at(0, 52, 0.95) <= 0.05
    # A class with a real failure rate (26/120) must not be admitted.
    assert failure_upper_bound_at(26, 120, 0.95) > 0.05
    # Small samples with zero failures are still not admitted (wide bounds).
    assert failure_upper_bound_at(0, 22, 0.95) > 0.05


def test_pilot_artifact_written_separately(tmp_path):
    out = tmp_path / "x.json"
    import subprocess, sys

    subprocess.run(
        [sys.executable, "-m", "experiments.benchmark.pilot", "--mode", "fake", "--max-attempts", "300", "--out", str(out)],
        check=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src") + ";" + str(ROOT)},
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mode"] == "fake"
    assert data["status"] == "COMPLETE"
