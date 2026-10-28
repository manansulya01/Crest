"""Non-circular simulation for testing CREST routing under imperfect features.

Separates observed routing features from latent task difficulty. The routing
feature is an imperfect (noisy) predictor of difficulty, which determines
model failure probability. This tests whether the controller adds value when
features are imperfect predictors of failure.

See docs/v1.0-noncircular-experiment.md for the full protocol.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Task and outcome data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimTask:
    task_id: str
    split: str  # "calibration" or "evaluation"
    # Observed features (available to routing)
    feature_a: int  # 0 or 1
    feature_b: int  # 0 or 1
    text_length_bucket: str  # "low", "med", "high"
    # Latent difficulty (hidden from all deployable strategies)
    latent_difficulty: float  # [0, 1]
    # Truth (evaluator only)
    truth: str
    # Signal strength used to generate this task (for reporting)
    signal_strength: float


@dataclass
class SimOutcome:
    task_id: str
    strategy: str
    model_used: str  # "cheap" or "strong"
    success: bool
    cost: float
    escalated: bool = False


# ---------------------------------------------------------------------------
# Task generation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def generate_tasks(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    signal_strength: float = 0.5,
    seed: int = 42,
) -> Tuple[List[SimTask], List[SimTask]]:
    """Generate calibration and evaluation tasks with the given signal strength.

    The routing feature is an imperfect predictor of latent difficulty.
    signal_strength=0: no predictive signal.
    signal_strength=1: perfect prediction (unrealistic upper bound).
    """
    rng = random.Random(seed)
    tasks = []

    for split, n in [("calibration", n_calibration), ("evaluation", n_evaluation)]:
        for i in range(n):
            task_id = f"sim-{split}-{seed}-{i:04d}"

            # Latent difficulty: uniform base, then modulated
            base_difficulty = rng.random()

            # Observed features: derived from difficulty with controlled noise
            noise_std = (1 - signal_strength) ** 2 + 0.1
            # z_feature correlates with difficulty
            z_feature = (base_difficulty - 0.5) * 2 * signal_strength + rng.gauss(0, noise_std)
            feature_a = 1 if z_feature > 0 else 0
            feature_b = 1 if rng.random() < (0.3 + 0.4 * signal_strength * (1 if z_feature > 0 else 0)) else 0

            # text_length_bucket: weakly correlated with difficulty
            if base_difficulty < 0.33:
                text_length_bucket = "low"
            elif base_difficulty < 0.67:
                text_length_bucket = "med"
            else:
                text_length_bucket = "high"

            # Latent difficulty (hidden from router)
            latent_difficulty = base_difficulty

            # Truth (evaluator only)
            truth = f"answer-{i}"

            tasks.append(SimTask(
                task_id=task_id,
                split=split,
                feature_a=feature_a,
                feature_b=feature_b,
                text_length_bucket=text_length_bucket,
                latent_difficulty=latent_difficulty,
                truth=truth,
                signal_strength=signal_strength,
            ))

    cal = [t for t in tasks if t.split == "calibration"]
    evl = [t for t in tasks if t.split == "evaluation"]
    return cal, evl


# ---------------------------------------------------------------------------
# Model outcome simulation
# ---------------------------------------------------------------------------

def simulate_outcome(task: SimTask, model: str, seed: int) -> bool:
    """Simulate whether a model succeeds on a task.

    Returns True if success. Uses latent difficulty (hidden from router).
    """
    rng = random.Random(hash((task.task_id, model, seed)) & 0xFFFFFFFF)
    d = task.latent_difficulty
    if model == "cheap":
        p_fail = min(0.95, 0.05 + 0.4 * d + 0.1 * (1 - task.signal_strength))
    else:  # strong
        p_fail = min(0.5, 0.01 + 0.05 * d)
    return rng.random() > p_fail


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

CHEAP_COST = 1.0
STRONG_COST = 5.0
VERIFY_COST = 0.1


def strategy_fixed_cheap(task: SimTask, seed: int) -> SimOutcome:
    success = simulate_outcome(task, "cheap", seed)
    return SimOutcome(task.task_id, "fixed_cheap", "cheap", success, CHEAP_COST + VERIFY_COST)


def strategy_fixed_strong(task: SimTask, seed: int) -> SimOutcome:
    success = simulate_outcome(task, "strong", seed)
    return SimOutcome(task.task_id, "fixed_strong", "strong", success, STRONG_COST + VERIFY_COST)


def strategy_cost_aware(task: SimTask, seed: int) -> SimOutcome:
    # Simple heuristic: route to cheap if feature_a == 0, else strong
    if task.feature_a == 0:
        success = simulate_outcome(task, "cheap", seed)
        return SimOutcome(task.task_id, "cost_aware", "cheap", success, CHEAP_COST + VERIFY_COST)
    else:
        success = simulate_outcome(task, "strong", seed)
        return SimOutcome(task.task_id, "cost_aware", "strong", success, STRONG_COST + VERIFY_COST)


def _wilson_upper(failures: int, n: int, z: float = 1.645) -> float:
    """One-sided Wilson upper bound on failure rate."""
    if n <= 0:
        return 1.0
    p = failures / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return min(1.0, center + margin)


class CrestAdmission:
    """CREST admission policy: admit cheap model per capability class if
    Wilson upper bound on failure rate <= threshold."""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.admitted_classes: Dict[str, bool] = {}
        self.calibration_data: Dict[str, List[bool]] = {}

    def capability_class(self, task: SimTask) -> str:
        # Routing uses only observed features
        return f"a{task.feature_a}_b{task.feature_b}"

    def calibrate(self, cal_tasks: List[SimTask], seed: int) -> None:
        """Calibrate on calibration set. Uses task truth for scoring (allowed
        during calibration; not during evaluation)."""
        classes: Dict[str, List[bool]] = {}
        for task in cal_tasks:
            cls = self.capability_class(task)
            success = simulate_outcome(task, "cheap", seed)
            classes.setdefault(cls, []).append(success)

        for cls, successes in classes.items():
            n = len(successes)
            failures = sum(1 for s in successes if not s)
            upper = _wilson_upper(failures, n)
            self.admitted_classes[cls] = upper <= self.threshold
            self.calibration_data[cls] = successes

    def route(self, task: SimTask) -> str:
        cls = self.capability_class(task)
        if self.admitted_classes.get(cls, False):
            return "cheap"
        return "strong"

    def strategy(self, task: SimTask, seed: int) -> SimOutcome:
        model_choice = self.route(task)
        success = simulate_outcome(task, model_choice, seed)
        cost = (CHEAP_COST if model_choice == "cheap" else STRONG_COST) + VERIFY_COST
        return SimOutcome(task.task_id, "crest", model_choice, success, cost)


def strategy_oracle(task: SimTask, seed: int) -> SimOutcome:
    """Oracle: uses latent difficulty (diagnostic only, never deployable)."""
    if task.latent_difficulty < 0.5:
        success = simulate_outcome(task, "cheap", seed)
        return SimOutcome(task.task_id, "oracle", "cheap", success, CHEAP_COST + VERIFY_COST)
    else:
        success = simulate_outcome(task, "strong", seed)
        return SimOutcome(task.task_id, "oracle", "strong", success, STRONG_COST + VERIFY_COST)


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

STRATEGY_NAMES = ["fixed_cheap", "fixed_strong", "cost_aware", "crest", "oracle"]
DEPLOYABLE_STRATEGIES = ["fixed_cheap", "fixed_strong", "cost_aware", "crest"]


def run_experiment(
    signal_strength: float = 0.5,
    seed: int = 42,
    n_calibration: int = 100,
    n_evaluation: int = 200,
) -> Dict:
    """Run the full experiment for one signal strength and seed.

    Returns a dict with per-strategy metrics.
    """
    cal_tasks, eval_tasks = generate_tasks(n_calibration, n_evaluation, signal_strength, seed)

    # Calibrate CREST
    crest = CrestAdmission(threshold=0.05)
    crest.calibrate(cal_tasks, seed)

    # Run all strategies on evaluation set
    outcomes: Dict[str, List[SimOutcome]] = {s: [] for s in STRATEGY_NAMES}
    for task in eval_tasks:
        outcomes["fixed_cheap"].append(strategy_fixed_cheap(task, seed))
        outcomes["fixed_strong"].append(strategy_fixed_strong(task, seed))
        outcomes["cost_aware"].append(strategy_cost_aware(task, seed))
        outcomes["crest"].append(crest.strategy(task, seed))
        outcomes["oracle"].append(strategy_oracle(task, seed))

    # Compute metrics
    results = {}
    for strategy in STRATEGY_NAMES:
        outs = outcomes[strategy]
        successes = sum(1 for o in outs if o.success)
        total_cost = sum(o.cost for o in outs)
        n = len(outs)
        success_rate = successes / n if n > 0 else 0.0
        cost_per_success = total_cost / successes if successes > 0 else float("inf")
        escalation_rate = sum(1 for o in outs if o.model_used == "strong") / n
        results[strategy] = {
            "n": n,
            "successes": successes,
            "success_rate": round(success_rate, 4),
            "total_cost": round(total_cost, 2),
            "avg_cost_per_task": round(total_cost / n, 4),
            "cost_per_success": round(cost_per_success, 4) if cost_per_success != float("inf") else None,
            "escalation_rate": round(escalation_rate, 4),
        }

    # Calibration info
    admitted = sum(1 for v in crest.admitted_classes.values() if v)
    total_classes = len(crest.admitted_classes)
    results["_calibration"] = {
        "classes": total_classes,
        "admitted": admitted,
        "class_details": {
            cls: {"n": len(succ), "failures": sum(1 for s in succ if not s),
                  "admitted": crest.admitted_classes.get(cls, False)}
            for cls, succ in crest.calibration_data.items()
        },
    }

    results["_meta"] = {
        "signal_strength": signal_strength,
        "seed": seed,
        "n_calibration": n_calibration,
        "n_evaluation": n_evaluation,
    }

    return results


def run_full_experiment(
    signal_strengths: List[float] = None,
    seeds: List[int] = None,
    n_calibration: int = 100,
    n_evaluation: int = 200,
) -> Dict:
    """Run the experiment across all signal strengths and seeds."""
    if signal_strengths is None:
        signal_strengths = [0.0, 0.2, 0.5, 0.8, 1.0]
    if seeds is None:
        seeds = [42, 123, 456, 789, 1024]

    all_results = {}
    for ss in signal_strengths:
        seed_results = []
        for seed in seeds:
            r = run_experiment(ss, seed, n_calibration, n_evaluation)
            seed_results.append(r)
        all_results[str(ss)] = seed_results

    return {
        "signal_strengths": signal_strengths,
        "seeds": seeds,
        "n_calibration": n_calibration,
        "n_evaluation": n_evaluation,
        "results": all_results,
    }


def summarize_by_signal(full_results: Dict) -> Dict:
    """Aggregate results across seeds for each signal strength."""
    summary = {}
    for ss_str, seed_results in full_results["results"].items():
        ss = float(ss_str)
        agg = {}
        for strategy in DEPLOYABLE_STRATEGIES + ["oracle"]:
            cps_values = [r[strategy]["cost_per_success"] for r in seed_results
                          if r[strategy]["cost_per_success"] is not None]
            sr_values = [r[strategy]["success_rate"] for r in seed_results]
            agg[strategy] = {
                "mean_success_rate": round(sum(sr_values) / len(sr_values), 4),
                "mean_cost_per_success": round(sum(cps_values) / len(cps_values), 4) if cps_values else None,
                "min_success_rate": round(min(sr_values), 4),
                "max_success_rate": round(max(sr_values), 4),
                "mean_escalation_rate": round(
                    sum(r[strategy]["escalation_rate"] for r in seed_results) / len(seed_results), 4),
            }
        # Oracle advantage
        oracle_sr = agg["oracle"]["mean_success_rate"]
        crest_sr = agg["crest"]["mean_success_rate"]
        cost_aware_sr = agg["cost_aware"]["mean_success_rate"]
        crest_cps = agg["crest"]["mean_cost_per_success"]
        cost_aware_cps = agg["cost_aware"]["mean_cost_per_success"]
        agg["_comparison"] = {
            "crest_vs_cost_aware_success_diff": round(crest_sr - cost_aware_sr, 4),
            "crest_vs_cost_aware_cps_ratio": (
                round(crest_cps / cost_aware_cps, 4) if cost_aware_cps and crest_cps else None),
            "oracle_vs_crest_success_diff": round(oracle_sr - crest_sr, 4),
        }
        summary[ss_str] = agg
    return summary
