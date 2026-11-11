"""Verification Intelligence experiment — Cycle 2.

Implements Value-of-Verification (VoV) controller: selects verification actions
based on expected reduction in decision risk per unit cost.

See docs/v1.2-verification-intelligence.md for the protocol.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _stable_seed(*parts: object) -> int:
    """Process-independent seed for deterministic pseudo-random generation.

    Python's built-in hash() on strings is randomized per interpreter session,
    so anything derived from it differs between runs.  We hash explicitly with
    SHA-256 instead, giving byte-identical results across processes and machines.
    """
    return int(hashlib.sha256("::".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8], 16)

# ---------------------------------------------------------------------------
# Verification actions and their properties
# ---------------------------------------------------------------------------

@dataclass
class VerifyAction:
    name: str
    cost: float
    # False positive rate: probability of accepting a bad output
    fpr: float
    # False negative rate: probability of rejecting a good output
    fnr: float


# Default verification actions (tiers)
T0 = VerifyAction("T0_structural", cost=0.0, fpr=0.3, fnr=0.05)
T1 = VerifyAction("T1_consistency", cost=0.1, fpr=0.2, fnr=0.05)
T2 = VerifyAction("T2_semantic_cheap", cost=0.5, fpr=0.1, fnr=0.1)
T3 = VerifyAction("T3_semantic_strong", cost=2.0, fpr=0.02, fnr=0.02)

ALL_ACTIONS = [T0, T1, T2, T3]
ACTION_BY_NAME = {a.name: a for a in ALL_ACTIONS}

# Model costs
CHEAP_MODEL_COST = 1.0
STRONG_MODEL_COST = 5.0

# Verification tier costs
T0_COST = 0.0
T1_COST = 0.1
T2_COST = 0.5
T3_COST = 2.0

# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------

@dataclass
class VITask:
    task_id: str
    split: str
    # Observed features
    feature_a: int  # 0 or 1
    feature_b: int
    text_length_bucket: str  # "low", "med", "high"
    risk_level: str  # "low", "med", "high" (observable task risk)
    # Latent (hidden from policy)
    latent_difficulty: float  # [0, 1]
    hidden_correct: bool  # whether cheap model would be correct
    # Truth (evaluator only)
    truth: str


def generate_vi_tasks(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    seed: int = 42,
) -> Tuple[List[VITask], List[VITask]]:
    """Generate tasks with observed features, hidden difficulty, and risk levels."""
    rng = random.Random(seed)
    tasks = []
    total = n_calibration + n_evaluation

    for i in range(total):
        split = "calibration" if i < n_calibration else "evaluation"
        task_id = f"vi-{split}-{seed}-{i:04d}"

        # Latent difficulty
        base_difficulty = rng.random()

        # Observed features (imperfectly correlated with difficulty)
        noise = rng.gauss(0, 0.3)
        feature_a = 1 if (base_difficulty + noise) > 0.5 else 0
        feature_b = 1 if rng.random() < (0.3 + 0.4 * base_difficulty) else 0

        if base_difficulty < 0.33:
            text_length_bucket = "low"
        elif base_difficulty < 0.67:
            text_length_bucket = "med"
        else:
            text_length_bucket = "high"

        # Risk level (observable, correlated with difficulty but noisy)
        if base_difficulty < 0.3 and rng.random() < 0.8:
            risk_level = "low"
        elif base_difficulty > 0.7 and rng.random() < 0.8:
            risk_level = "high"
        else:
            risk_level = "med"

        # Hidden correctness: cheap model correct with prob based on difficulty
        cheap_rng = random.Random(_stable_seed(task_id, "cheap", seed))
        p_fail_cheap = 0.05 + 0.4 * base_difficulty
        hidden_correct = cheap_rng.random() > p_fail_cheap

        truth = f"answer-{i}"

        tasks.append(VITask(
            task_id=task_id,
            split=split,
            feature_a=feature_a,
            feature_b=feature_b,
            text_length_bucket=text_length_bucket,
            risk_level=risk_level,
            latent_difficulty=base_difficulty,
            hidden_correct=hidden_correct,
            truth=truth,
        ))

    cal = [t for t in tasks if t.split == "calibration"]
    evl = [t for t in tasks if t.split == "evaluation"]
    return cal, evl


# ---------------------------------------------------------------------------
# Verifier simulation
# ---------------------------------------------------------------------------

def simulate_verify(action: VerifyAction, task: VITask, model_correct: bool, seed: int) -> bool:
    """Simulate a verification action. Returns True if verifier accepts.

    Verifier has false positive (accepts bad) and false negative (rejects good)
    rates. Verifier errors may be correlated with model errors.
    """
    rng = random.Random(_stable_seed(task.task_id, action.name, seed))
    if model_correct:
        # Good output: verifier rejects with probability fnr
        return rng.random() > action.fnr
    else:
        # Bad output: verifier accepts with probability fpr
        return rng.random() < action.fpr


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def strategy_always_t0(task: VITask, seed: int) -> Tuple[bool, float]:
    """Always run cheap model + T0 only. Cheapest, least safe."""
    model_correct = task.hidden_correct
    verify_pass = simulate_verify(T0, task, model_correct, seed)
    # T0 passes → accept; T0 fails → still accept (no escalation in always-T0)
    accepted = verify_pass or True  # always accept
    cost = CHEAP_MODEL_COST + T0_COST
    return model_correct and accepted, cost


def strategy_always_t3(task: VITask, seed: int) -> Tuple[bool, float]:
    """Always run strong model + T3. Most expensive, safest."""
    strong_correct = random.Random(_stable_seed(task.task_id, "strong", seed)).random() > (0.01 + 0.05 * task.latent_difficulty)
    verify_pass = simulate_verify(T3, task, strong_correct, seed)
    accepted = verify_pass
    if not accepted:
        # Re-run (retry) — simplified: just accept
        accepted = True
    cost = STRONG_MODEL_COST + T3_COST
    return strong_correct, cost


def strategy_fixed_cascade(task: VITask, seed: int) -> Tuple[bool, float]:
    """Fixed cascade: T0 on cheap; if T0 fails, escalate to strong + T3."""
    model_correct = task.hidden_correct
    verify_pass = simulate_verify(T0, task, model_correct, seed)
    if not verify_pass:
        # Escalate
        strong_correct = random.Random(_stable_seed(task.task_id, "strong", seed)).random() > (0.01 + 0.05 * task.latent_difficulty)
        v3_pass = simulate_verify(T3, task, strong_correct, seed)
        return strong_correct and v3_pass, CHEAP_MODEL_COST + STRONG_MODEL_COST + T0_COST + T3_COST
    return model_correct, CHEAP_MODEL_COST + T0_COST


# ---------------------------------------------------------------------------
# Value-of-Verification (VoV) Controller
# ---------------------------------------------------------------------------

@dataclass
class VoVState:
    """State of the VoV controller for a single task."""
    task: VITask
    model_used: str = "cheap"
    model_correct: bool = False
    verifications_run: List[str] = field(default_factory=list)
    verifications_passed: List[bool] = field(default_factory=list)
    total_verify_cost: float = 0.0
    accepted: bool = False
    rejected: bool = False


class VoVController:
    """Value-of-Verification controller.

    Selects verification actions based on expected reduction in decision risk
    per unit cost. Uses a simple value-of-information heuristic:

    For each candidate action, compute:
      VoI = P(action changes decision) * (cost of wrong decision) / action_cost

    Select the action with highest VoI. Stop when VoI < threshold or budget
    exhausted.
    """

    def __init__(
        self,
        budget_per_task: float = 10.0,
        voi_threshold: float = 0.1,
        risk_weights: Dict[str, float] = None,
    ):
        self.budget_per_task = budget_per_task
        self.voi_threshold = voi_threshold
        self.risk_weights = risk_weights or {"low": 1.0, "med": 2.0, "high": 5.0}

    def _estimate_uncertainty(self, state: VoVState) -> float:
        """Estimate uncertainty about whether the current output is correct.

        Based on how many verifications have passed/failed and their reliability.
        Higher uncertainty → more verification needed.
        """
        if not state.verifications_run:
            return 1.0  # maximum uncertainty
        # Uncertainty decreases as more verifications pass
        # Uncertainty decreases as more verifications pass, but never below
        # the residual uncertainty from verifier error rates.
        n_pass = sum(1 for p in state.verifications_passed if p)
        n_total = len(state.verifications_passed)
        if n_total == 0:
            return 1.0
        pass_rate = n_pass / n_total
        # Residual uncertainty: even if all verifiers pass, the output might
        # still be wrong due to verifier false positive rates.
        residual = 1.0
        for action_name in state.verifications_run:
            action = ACTION_BY_NAME.get(action_name)
            if action:
                residual *= action.fpr  # probability all verifiers falsely accept
        # Uncertainty = max(residual, pass_rate-based uncertainty)
        base_uncertainty = 1.0 - abs(pass_rate - 0.5) * 2
        uncertainty = max(residual, base_uncertainty * 0.5)
        return min(1.0, max(0.0, uncertainty))

    def _compute_voi(self, action: VerifyAction, state: VoVState, task: VITask) -> float:
        """Compute Value of Information for a candidate action.

        VoI = P(action changes decision) * cost_of_wrong_decision / action_cost
        """
        if action.cost <= 0:
            # Free actions always have infinite VoI (run them first)
            return float("inf")

        uncertainty = self._estimate_uncertainty(state)
        risk_weight = self.risk_weights.get(task.risk_level, 1.0)

        # Probability that this action changes the decision
        # Higher uncertainty → higher probability of changing decision
        p_change = uncertainty * 0.5

        # Cost of wrong decision: if we accept a bad output, downstream cost
        # is proportional to risk level
        cost_of_wrong = risk_weight * 10.0  # base cost of a wrong acceptance

        # VoI = expected benefit / cost
        voi = (p_change * cost_of_wrong) / action.cost
        return voi

    def _select_next_action(self, state: VoVState, task: VITask,
                            remaining_budget: float) -> Optional[VerifyAction]:
        """Select the next verification action with highest VoI."""
        run_names = set(state.verifications_run)
        candidates = []
        for action in ALL_ACTIONS:
            if action.name in run_names:
                continue
            if action.cost > remaining_budget:
                continue
            voi = self._compute_voi(action, state, task)
            if voi >= self.voi_threshold:
                candidates.append((action, voi))

        if not candidates:
            return None
        # Select highest VoI
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def execute(self, task: VITask, seed: int) -> Tuple[bool, float, VoVState]:
        """Execute the VoV controller on a task. Returns (success, total_cost, state)."""
        state = VoVState(task=task)
        remaining_budget = self.budget_per_task

        # Step 1: Run the cheap model
        model_correct = task.hidden_correct if hasattr(task, 'hidden_correct') else None
        # Simulate model correctness based on hidden difficulty
        rng = random.Random(_stable_seed(task.task_id, "cheap", seed))
        p_fail = 0.05 + 0.4 * task.latent_difficulty
        model_correct = rng.random() > p_fail

        state.model_used = "cheap"
        state.model_correct = model_correct
        remaining_budget -= CHEAP_MODEL_COST

        # Step 2: Adaptive verification loop
        while remaining_budget > 0:
            action = self._select_next_action(state, task, remaining_budget)
            if action is None:
                break

            # Execute the verification action
            verify_pass = simulate_verify(action, task, model_correct, seed)
            state.verifications_run.append(action.name)
            state.verifications_passed.append(verify_pass)
            state.total_verify_cost += action.cost
            remaining_budget -= action.cost

            # Update acceptance/rejection
            uncertainty = self._estimate_uncertainty(state)
            if uncertainty < 0.15 and all(state.verifications_passed) and len(state.verifications_run) >= 2:
                state.accepted = True
                break
            if not verify_pass and action.name in ("T2_semantic_cheap", "T3_semantic_strong"):
                state.rejected = True
                break

        # Step 3: Decide
        if state.rejected:
            # Escalate to strong model
            strong_rng = random.Random(_stable_seed(task.task_id, "strong", seed))
            strong_correct = strong_rng.random() > (0.01 + 0.05 * task.latent_difficulty)
            v3_pass = simulate_verify(T3, task, strong_correct, seed)
            state.model_used = "strong"
            total_cost = (CHEAP_MODEL_COST + state.total_verify_cost +
                          STRONG_MODEL_COST + T3_COST)
            return strong_correct and v3_pass, total_cost, state

        if state.accepted or (state.verifications_run and all(state.verifications_passed)):
            return model_correct, CHEAP_MODEL_COST + state.total_verify_cost, state

        # Default: accept (no verification rejected)
        return model_correct, CHEAP_MODEL_COST + state.total_verify_cost, state


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def run_vov_experiment(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    seed: int = 42,
    budget_per_task: float = 10.0,
    voi_threshold: float = 0.1,
) -> dict:
    """Run the VoV experiment for one seed."""
    cal_tasks, eval_tasks = generate_vi_tasks(n_calibration, n_evaluation, seed)

    # Baselines
    results = {
        "always_t0": [],
        "always_t3": [],
        "fixed_cascade": [],
        "vov": [],
    }

    for task in eval_tasks:
        # Always T0
        mc = task.hidden_correct if hasattr(task, 'hidden_correct') else None
        rng = random.Random(_stable_seed(task.task_id, "cheap", seed))
        mc = rng.random() > (0.05 + 0.4 * task.latent_difficulty)
        v0 = simulate_verify(T0, task, mc, seed)
        accepted = v0 or True  # always accept
        results["always_t0"].append((mc and accepted, CHEAP_MODEL_COST + T0_COST))

        # Always T3
        srng = random.Random(_stable_seed(task.task_id, "strong", seed))
        sc = srng.random() > (0.01 + 0.05 * task.latent_difficulty)
        v3 = simulate_verify(T3, task, sc, seed)
        results["always_t3"].append((sc and v3, STRONG_MODEL_COST + T3_COST))

        # Fixed cascade
        v0_pass = simulate_verify(T0, task, mc, seed)
        if not v0_pass:
            srng2 = random.Random(_stable_seed(task.task_id, "strong", seed))
            sc2 = srng2.random() > (0.01 + 0.05 * task.latent_difficulty)
            v3p = simulate_verify(T3, task, sc2, seed)
            results["fixed_cascade"].append((sc2 and v3p, CHEAP_MODEL_COST + STRONG_MODEL_COST + T0_COST + T3_COST))
        else:
            results["fixed_cascade"].append((mc, CHEAP_MODEL_COST + T0_COST))

        # VoV
        controller = VoVController(budget_per_task=budget_per_task, voi_threshold=voi_threshold)
        success, cost, state = controller.execute(task, seed)
        results["vov"].append((success, cost))

    # Aggregate
    summary = {}
    for name, outcomes in results.items():
        successes = sum(1 for s, _ in outcomes if s)
        total_cost = sum(c for _, c in outcomes)
        n = len(outcomes)
        summary[name] = {
            "n": n,
            "successes": successes,
            "success_rate": round(successes / n, 4) if n > 0 else 0.0,
            "total_cost": round(total_cost, 2),
            "avg_cost_per_task": round(total_cost / n, 4) if n > 0 else 0.0,
            "cost_per_success": round(total_cost / successes, 4) if successes > 0 else None,
        }

    summary["_meta"] = {"seed": seed, "n_calibration": n_calibration,
                        "n_evaluation": n_evaluation, "budget_per_task": budget_per_task,
                        "voi_threshold": voi_threshold}
    return summary


def run_vov_full(seeds=None, **kwargs):
    if seeds is None:
        seeds = [42, 123, 456, 789, 1024]
    results = {}
    for seed in seeds:
        results[str(seed)] = run_vov_experiment(seed=seed, **kwargs)
    return {"seeds": seeds, "results": results}


def summarize_vov(full_results):
    seeds = full_results["seeds"]
    summary = {}
    for name in ["always_t0", "always_t3", "fixed_cascade", "vov"]:
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
    vov_cps = summary["vov"]["mean_cost_per_success"]
    cascade_cps = summary["fixed_cascade"]["mean_cost_per_success"]
    vov_sr = summary["vov"]["mean_success_rate"]
    cascade_sr = summary["fixed_cascade"]["mean_success_rate"]
    t3_cps = summary["always_t3"]["mean_cost_per_success"]
    summary["_comparison"] = {
        "vov_vs_cascade_cps_ratio": round(vov_cps / cascade_cps, 4) if cascade_cps and vov_cps else None,
        "vov_vs_cascade_success_diff": round(vov_sr - cascade_sr, 4),
        "vov_vs_always_t3_cps_ratio": round(vov_cps / t3_cps, 4) if t3_cps and vov_cps else None,
        "vov_vs_always_t3_success_diff": round(vov_sr - summary["always_t3"]["mean_success_rate"], 4),
    }
    return summary
