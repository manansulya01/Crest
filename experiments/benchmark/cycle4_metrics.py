"""Metrics for Cycle 4 offline validation.

Pure functions. No network. No side effects.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def compute_metrics(
    decisions: List[Dict[str, Any]],
    *,
    cost_budget: Optional[float] = None,
) -> Dict[str, float]:
    """Compute standard metrics from a list of decision records.

    Each record: {task_id, decision, cost, confidence, ground_truth}.
    ground_truth in {correct, incorrect, indeterminate}.
    """
    n = len(decisions)
    if n == 0:
        return {"n": 0}

    accepts = [d for d in decisions if d["decision"] == "ACCEPT"]
    rejects = [d for d in decisions if d["decision"] == "REJECT"]
    indeterminates = [d for d in decisions if d["decision"] == "INDETERMINATE"]

    bad = [d for d in decisions if d["ground_truth"] == "incorrect"]
    good = [d for d in decisions if d["ground_truth"] == "correct"]

    false_accepts = [d for d in accepts if d["ground_truth"] == "incorrect"]
    false_rejects = [d for d in rejects if d["ground_truth"] == "correct"]
    correct_decisions = [
        d for d in decisions
        if (d["decision"] == "ACCEPT" and d["ground_truth"] == "correct")
        or (d["decision"] == "REJECT" and d["ground_truth"] == "incorrect")
    ]
    accepted_and_correct = [
        d for d in accepts if d["ground_truth"] == "correct"
    ]

    far = len(false_accepts) / len(bad) if bad else 0.0
    frr = len(false_rejects) / len(good) if good else 0.0
    coverage = (len(accepts) + len(rejects)) / n
    success_rate = len(correct_decisions) / n
    accepted_correct_rate = len(accepted_and_correct) / n

    total_cost = sum(d.get("cost", 0.0) for d in decisions)
    cost_per_task = total_cost / n
    cost_per_success = total_cost / len(correct_decisions) if correct_decisions else None

    # Risk-weighted loss (requires risk_class in record; default med weight).
    loss = 0.0
    for d in decisions:
        risk = d.get("risk_class", "med")
        weights = {"low": (4.0, 2.0, 1.0), "med": (12.0, 4.0, 1.5), "high": (50.0, 8.0, 2.0)}
        fa_w, fr_w, ind_w = weights.get(risk, weights["med"])
        if d["decision"] == "ACCEPT" and d["ground_truth"] == "incorrect":
            loss += fa_w
        elif d["decision"] == "REJECT" and d["ground_truth"] == "correct":
            loss += fr_w
        elif d["decision"] == "INDETERMINATE":
            loss += ind_w

    return {
        "n": n,
        "n_good": len(good),
        "n_bad": len(bad),
        "accepts": len(accepts),
        "rejects": len(rejects),
        "indeterminate": len(indeterminates),
        "false_accepts": len(false_accepts),
        "false_rejects": len(false_rejects),
        "far": round(far, 4),
        "far_wilson": wilson_interval(len(false_accepts), len(bad)),
        "frr": round(frr, 4),
        "frr_wilson": wilson_interval(len(false_rejects), len(good)),
        "success_rate": round(success_rate, 4),
        "accepted_and_correct_rate": round(accepted_correct_rate, 4),
        "coverage": round(coverage, 4),
        "selective_risk": round(far, 4),
        "cost_per_task": round(cost_per_task, 4),
        "cost_per_success": round(cost_per_success, 4) if cost_per_success is not None else None,
        "risk_weighted_loss": round(loss, 4),
        "risk_weighted_loss_per_task": round(loss / n, 4),
    }


def paired_loss_difference(
    decisions_a: List[Dict[str, Any]],
    decisions_b: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Paired per-task loss difference (a - b). Returns mean and bootstrap CI."""
    if len(decisions_a) != len(decisions_b):
        raise ValueError("Paired comparison requires equal lengths")
    # Per-task loss using the same weights as compute_metrics.
    def per_task_loss(d):
        risk = d.get("risk_class", "med")
        weights = {"low": (4.0, 2.0, 1.0), "med": (12.0, 4.0, 1.5), "high": (50.0, 8.0, 2.0)}
        fa_w, fr_w, ind_w = weights.get(risk, weights["med"])
        if d["decision"] == "ACCEPT" and d["ground_truth"] == "incorrect":
            return fa_w
        if d["decision"] == "REJECT" and d["ground_truth"] == "correct":
            return fr_w
        if d["decision"] == "INDETERMINATE":
            return ind_w
        return 0.0

    diffs = [per_task_loss(a) - per_task_loss(b) for a, b in zip(decisions_a, decisions_b)]
    mean_diff = sum(diffs) / len(diffs)
    # Bootstrap CI
    import random
    rng = random.Random(42)
    boot_means = []
    for _ in range(1000):
        sample = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        boot_means.append(sum(sample) / len(sample))
    boot_means.sort()
    ci_low = boot_means[int(0.025 * len(boot_means))]
    ci_high = boot_means[int(0.975 * len(boot_means))]
    return {
        "mean_difference_a_minus_b": round(mean_diff, 4),
        "ci_95_low": round(ci_low, 4),
        "ci_95_high": round(ci_high, 4),
        "n": len(diffs),
    }