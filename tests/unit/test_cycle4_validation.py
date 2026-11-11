"""Tests for the Cycle 4 offline validation harness."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiments.benchmark.cycle4_metrics import compute_metrics, paired_loss_difference, wilson_interval
from experiments.benchmark.cycle4_validation import (
    POLICY_REGISTRY,
    RecordedExample,
    example_to_task,
    load_recorded_dataset,
    run_offline,
)


def test_wilson_interval_bounds() -> None:
    lo, hi = wilson_interval(5, 50)
    assert 0.0 <= lo <= hi <= 1.0
    lo2, hi2 = wilson_interval(0, 50)
    assert lo2 == 0.0


def test_compute_metrics_basic() -> None:
    decisions = [
        {"task_id": "t1", "decision": "ACCEPT", "cost": 1.0, "confidence": 0.9, "ground_truth": "correct", "risk_class": "high"},
        {"task_id": "t2", "decision": "ACCEPT", "cost": 1.0, "confidence": 0.8, "ground_truth": "incorrect", "risk_class": "high"},
        {"task_id": "t3", "decision": "REJECT", "cost": 1.0, "confidence": 0.2, "ground_truth": "incorrect", "risk_class": "med"},
        {"task_id": "t4", "decision": "INDETERMINATE", "cost": 0.5, "confidence": 0.5, "ground_truth": "correct", "risk_class": "low"},
    ]
    m = compute_metrics(decisions)
    assert m["n"] == 4
    assert m["false_accepts"] == 1
    assert m["false_rejects"] == 0
    assert m["accepts"] == 2
    assert m["indeterminate"] == 1
    assert m["coverage"] == 0.75
    assert m["success_rate"] == 0.5  # t1, t3 correct; t2 false accept; t4 indeterminate
    assert m["far"] == 0.5  # 1 false accept / 2 bad
    assert m["risk_weighted_loss"] == 50.0 + 0.0 + 0.0 + 1.0  # FA high=50, indet low=1


def test_paired_loss_difference_length_mismatch() -> None:
    a = [{"decision": "ACCEPT", "ground_truth": "correct", "risk_class": "low"}]
    b = []
    try:
        paired_loss_difference(a, b)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_load_recorded_dataset_json_and_jsonl() -> None:
    examples = [
        {"task_id": "t1", "risk_class": "high", "ground_truth_label": "correct",
         "generator_output": "42", "verifier_output": "CORRECT", "provenance": {"source_family": "llm"}, "category": "A"},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "data.json"
        json_path.write_text(json.dumps(examples), encoding="utf-8")
        loaded = load_recorded_dataset(json_path)
        assert len(loaded) == 1
        assert loaded[0].task_id == "t1"
        assert loaded[0].truth is True

        jsonl_path = Path(tmpdir) / "data.jsonl"
        jsonl_path.write_text("\n".join(json.dumps(e) for e in examples), encoding="utf-8")
        loaded2 = load_recorded_dataset(jsonl_path)
        assert len(loaded2) == 1


def test_example_to_task_maps_verifier_output() -> None:
    ex = RecordedExample(
        task_id="t1", risk_class="high", ground_truth_label="incorrect",
        generator_output="wrong", verifier_output="CORRECT",
        provenance={"source_family": "llm"},
    )
    task = example_to_task(ex, 0)
    assert task.risk == "high"
    assert task.evidence[0].verdicts == (True, True)  # verifier said correct
    assert task.evidence[0].ancestry == ("llm",)


def test_run_offline_produces_decisions() -> None:
    examples = [
        RecordedExample(task_id="t1", risk_class="low", ground_truth_label="correct",
                        generator_output="42", verifier_output="CORRECT",
                        provenance={"source_family": "llm"}),
        RecordedExample(task_id="t2", risk_class="high", ground_truth_label="incorrect",
                        generator_output="wrong", verifier_output="CORRECT",
                        provenance={"source_family": "llm"}),
    ]
    results = run_offline(examples, policy_names=["single_strong", "strong_high_risk_gate"])
    assert "single_strong" in results
    assert "strong_high_risk_gate" in results
    assert len(results["single_strong"]) == 2
    assert all("decision" in r for r in results["single_strong"])


def test_policy_registry_contains_gate() -> None:
    assert "strong_high_risk_gate" in POLICY_REGISTRY
    assert "single_strong" in POLICY_REGISTRY