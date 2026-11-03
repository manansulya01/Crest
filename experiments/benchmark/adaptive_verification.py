"""Adaptive Verification experiment.

Tests whether allocating verification effort based on task uncertainty reduces
total cost without reducing task success.

See docs/v1.1-adaptive-verification-experiment.md for the protocol.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Verification tiers
# ---------------------------------------------------------------------------

T0_COST = 0.0   # structural: JSON parse + required fields + types
T1_COST = 0.1   # consistency: T0 + cross-field invariants
T2_COST = 0.5   # semantic-cheap: T1 + cheap model judge
T3_COST = 2.0   # semantic-strong: T1 + strong model judge

CHEAP_MODEL_COST = 1.0
STRONG_MODEL_COST = 5.0


def verify_t0(response_text: str, required_keys: tuple) -> bool:
    """Tier 0: structural check."""
    try:
        parsed = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(parsed, dict):
        return False
    return all(k in parsed for k in required_keys)


def verify_t1(response_text: str, required_keys: tuple, invariant_fn=None) -> bool:
    """Tier 1: T0 + cross-field consistency."""
    if not verify_t0(response_text, required_keys):
        return False
    if invariant_fn is None:
        return True
    try:
        parsed = json.loads(response_text)
        return invariant_fn(parsed)
    except (json.JSONDecodeError, ValueError, Exception):
        return False


# ---------------------------------------------------------------------------
# Task generation (reuse support-ticket workload concept)
# ---------------------------------------------------------------------------

@dataclass
class AVTask:
    task_id: str
    split: str  # "calibration" or "evaluation"
    text: str
    gold: dict
    multi_constraint: bool  # observed feature (routing feature)
    hidden_difficulty: float  # latent, not available to router


def generate_av_tasks(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    seed: int = 42,
) -> Tuple[List[AVTask], List[AVTask]]:
    """Generate tasks with observed features and hidden difficulty."""
    rng = random.Random(seed)
    tasks = []
    total = n_calibration + n_evaluation

    for i in range(total):
        split = "calibration" if i < n_calibration else "evaluation"
        task_id = f"av-{split}-{seed}-{i:04d}"

        # Observed feature: multi_constraint (text-derived, available to router)
        multi = rng.random() < 0.3

        # Hidden difficulty: independent of observed feature (noisy)
        hidden_difficulty = rng.random()

        # Gold answer (4 fields for support ticket)
        categories = ["billing_refund", "access_request", "data_fix", "report_bug",
                      "account_update", "general_help"]
        category = categories[rng.randrange(len(categories))]
        urgency = "urgent" if rng.random() < 0.3 else "routine"
        refund = "yes" if category == "billing_refund" and rng.random() < 0.8 else "no"
        due = f"2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}" if rng.random() < 0.4 else "none"

        gold = {
            "category": category,
            "urgency": urgency,
            "refund_requested": refund,
            "due_date": due,
        }

        text = f"Ticket {i}: {category} request, urgency {urgency}."
        if multi:
            text += " Also mentions a secondary topic for context."

        tasks.append(AVTask(
            task_id=task_id,
            split=split,
            text=text,
            gold=gold,
            multi_constraint=multi,
            hidden_difficulty=hidden_difficulty,
        ))

    cal = [t for t in tasks if t.split == "calibration"]
    evl = [t for t in tasks if t.split == "evaluation"]
    return cal, evl


# ---------------------------------------------------------------------------
# Model simulation
# ---------------------------------------------------------------------------

def cheap_model_correct(task: AVTask, seed: int) -> bool:
    """Cheap model: fails with probability driven by hidden difficulty.
    Structural validity is always maintained (valid JSON, correct schema).
    Semantic error: wrong category value (but valid JSON)."""
    rng = random.Random(hash((task.task_id, "cheap", seed)) & 0xFFFFFFFF)
    # Failure probability driven by hidden difficulty
    p_fail = 0.05 + 0.4 * task.hidden_difficulty
    if rng.random() < p_fail:
        return False  # semantic error (wrong category in valid JSON)
    return True


def strong_model_correct(task: AVTask, seed: int) -> bool:
    """Strong model: much more reliable."""
    rng = random.Random(hash((task.task_id, "strong", seed)) & 0xFFFFFFFF)
    p_fail = 0.01 + 0.05 * task.hidden_difficulty
    return rng.random() > p_fail


def make_response(task: AVTask, correct: bool) -> str:
    """Generate a response. If correct, return gold JSON. If incorrect,
    return valid JSON with wrong category (semantic error that passes T0/T1)."""
    import copy
    gold = dict(task.gold)
    if not correct:
        # Semantic error: flip category to a wrong value, but keep valid JSON
        wrong_cats = [c for c in ["billing_refund", "access_request", "data_fix",
                                  "report_bug", "account_update", "general_help"]
                      if c != gold["category"]]
        gold["category"] = wrong_cats[0] if wrong_cats else "general_help"
    return json.dumps(gold)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

REQUIRED_KEYS = ("category", "urgency", "refund_requested", "due_date")


def strategy_always_t0(task: AVTask, seed: int) -> Tuple[bool, float]:
    """Always run cheap model + T0 verification only."""
    correct = cheap_model_correct(task, seed)
    response = make_response(task, correct)
    t0_pass = verify_t0(response, REQUIRED_KEYS)
    if not t0_pass:
        # Escalate to strong + T3
        sc = strong_model_correct(task, seed)
        sr = make_response(task, sc)
        return sc, STRONG_MODEL_COST + CHEAP_MODEL_COST + T0_COST + T3_COST
    return correct, CHEAP_MODEL_COST + T0_COST


def strategy_always_t3(task: AVTask, seed: int) -> Tuple[bool, float]:
    """Always run strong model + T3 verification."""
    sc = strong_model_correct(task, seed)
    response = make_response(task, sc)
    return sc, STRONG_MODEL_COST + T3_COST


def strategy_fixed_cascade(task: AVTask, seed: int) -> Tuple[bool, float]:
    """Fixed cascade: T0 on cheap; if T0 fails, escalate to strong + T3."""
    correct = cheap_model_correct(task, seed)
    response = make_response(task, correct)
    t0_pass = verify_t0(response, REQUIRED_KEYS)
    if not t0_pass:
        sc = strong_model_correct(task, seed)
        sr = make_response(task, sc)
        return sc, STRONG_MODEL_COST + CHEAP_MODEL_COST + T0_COST + T3_COST
    return correct, CHEAP_MODEL_COST + T0_COST


def strategy_adaptive(task: AVTask, seed: int, calibration: dict) -> Tuple[bool, float]:
    """Adaptive Verification: allocate verification tier based on task class
    historical failure rate and budget."""
    correct = cheap_model_correct(task, seed)
    response = make_response(task, correct)

    # Determine capability class (observed feature only)
    cls = "multi" if task.multi_constraint else "single"

    # Historical failure rate from calibration
    hist_fail_rate = calibration.get(cls, {}).get("fail_rate", 0.5)

    # T0 (always)
    t0_pass = verify_t0(response, REQUIRED_KEYS)
    if not t0_pass:
        # Escalate to strong + T3
        sc = strong_model_correct(task, seed)
        sr = make_response(task, sc)
        return sc, STRONG_MODEL_COST + CHEAP_MODEL_COST + T0_COST + T3_COST

    # T0 passed. Decide verification tier based on uncertainty.
    if hist_fail_rate > 0.1:
        # High-uncertainty class: run T2 (cheap model judge)
        # T2 simulates a cheap model checking the answer
        t2_pass = (not correct) is False  # T2 catches if the answer is wrong
        # Actually T2 is a cheap model judge — it has its own error rate
        t2_rng = random.Random(hash((task.task_id, "t2", seed)) & 0xFFFFFFFF)
        t2_correct = t2_rng.random() > 0.1  # T2 has 10% error rate
        t2_result = t2_correct and (not correct) is False
        # T2 passes if it thinks the answer is correct
        t2_thinks_ok = t2_correct if correct else (not t2_correct)
        if not t2_thinks_ok:
            # T2 rejected → escalate to strong + T3
            sc = strong_model_correct(task, seed)
            sr = make_response(task, sc)
            return sc, STRONG_MODEL_COST + CHEAP_MODEL_COST + T0_COST + T2_COST + T3_COST
        return correct, CHEAP_MODEL_COST + T0_COST + T2_COST
    else:
        # Low-uncertainty class: accept after T0
        return correct, CHEAP_MODEL_COST + T0_COST


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def calibrate(cal_tasks: List[AVTask], seed: int) -> dict:
    """Calibrate: run cheap model on calibration set, compute failure rates
    per capability class (observed feature only)."""
    classes: dict = {}
    for task in cal_tasks:
        cls = "multi" if task.multi_constraint else "single"
        correct = cheap_model_correct(task, seed)
        classes.setdefault(cls, []).append(correct)

    result = {}
    for cls, successes in classes.items():
        n = len(successes)
        failures = sum(1 for s in successes if not s)
        fail_rate = failures / n if n > 0 else 0.5
        result[cls] = {"n": n, "failures": failures, "fail_rate": round(fail_rate, 4)}
    return result


def run_av_experiment(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    seed: int = 42,
) -> dict:
    """Run the adaptive verification experiment for one seed."""
    cal_tasks, eval_tasks = generate_av_tasks(n_calibration, n_evaluation, seed)

    calibration = calibrate(cal_tasks, seed)

    strategies = {
        "always_t0": [],
        "always_t3": [],
        "fixed_cascade": [],
        "adaptive": [],
    }

    for task in eval_tasks:
        s, c = strategy_always_t0(task, seed)
        strategies["always_t0"].append((s, c))
        s, c = strategy_always_t3(task, seed)
        strategies["always_t3"].append((s, c))
        s, c = strategy_fixed_cascade(task, seed)
        strategies["fixed_cascade"].append((s, c))
        s, c = strategy_adaptive(task, seed, calibration)
        strategies["adaptive"].append((s, c))

    results = {}
    for name, outcomes in strategies.items():
        successes = sum(1 for s, _ in outcomes if s)
        total_cost = sum(c for _, c in outcomes)
        n = len(outcomes)
        results[name] = {
            "n": n,
            "successes": successes,
            "success_rate": round(successes / n, 4) if n > 0 else 0.0,
            "total_cost": round(total_cost, 2),
            "avg_cost_per_task": round(total_cost / n, 4) if n > 0 else 0.0,
            "cost_per_success": round(total_cost / successes, 4) if successes > 0 else None,
        }

    results["_calibration"] = calibration
    results["_meta"] = {"seed": seed, "n_calibration": n_calibration,
                        "n_evaluation": n_evaluation}
    return results


def run_av_full(seeds: List[int] = None) -> dict:
    """Run across multiple seeds."""
    if seeds is None:
        seeds = [42, 123, 456, 789, 1024]
    all_results = {}
    for seed in seeds:
        all_results[str(seed)] = run_av_experiment(seed=seed)
    return {"seeds": seeds, "results": all_results}


def summarize_av(full_results: dict) -> dict:
    """Aggregate across seeds."""
    seeds = full_results["seeds"]
    summary = {}
    for name in ["always_t0", "always_t3", "fixed_cascade", "adaptive"]:
        sr_vals = [full_results["results"][str(s)][name]["success_rate"] for s in seeds]
        cps_vals = [full_results["results"][str(s)][name]["cost_per_success"]
                    for s in seeds if full_results["results"][str(s)][name]["cost_per_success"] is not None]
        cost_vals = [full_results["results"][str(s)][name]["avg_cost_per_task"] for s in seeds]
        summary[name] = {
            "mean_success_rate": round(sum(sr_vals) / len(sr_vals), 4),
            "mean_cost_per_success": round(sum(cps_vals) / len(cps_vals), 4) if cps_vals else None,
            "mean_cost_per_task": round(sum(cost_vals) / len(cost_vals), 4),
            "min_success_rate": round(min(sr_vals), 4),
            "max_success_rate": round(max(sr_vals), 4),
        }
    # Comparisons
    adaptive_cps = summary["adaptive"]["mean_cost_per_success"]
    cascade_cps = summary["fixed_cascade"]["mean_cost_per_success"]
    adaptive_sr = summary["adaptive"]["mean_success_rate"]
    cascade_sr = summary["fixed_cascade"]["mean_success_rate"]
    summary["_comparison"] = {
        "adaptive_vs_cascade_cps_ratio": (
            round(adaptive_cps / cascade_cps, 4) if cascade_cps and adaptive_cps else None),
        "adaptive_vs_cascade_success_diff": round(adaptive_sr - cascade_sr, 4),
        "adaptive_vs_always_t3_cps_ratio": (
            round(adaptive_cps / summary["always_t3"]["mean_cost_per_success"], 4)
            if summary["always_t3"]["mean_cost_per_success"] and adaptive_cps else None),
    }
    return summary
