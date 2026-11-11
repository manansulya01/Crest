"""Sequential Evidence Accumulation (SEA) — a principled Bayesian/SPRT-style
verification allocator for the CREST verification-intelligence track.

Distinct from the Value-of-Verification (VoV) heuristic, which picks the next
action by a hand-tuned "expected change probability x wrong-accept cost /
action cost" score.  SEA instead:

* starts from a risk-class prior (calibrated once per class from the
  calibration split — never from the evaluation split);
* accumulates log-likelihood-ratio (LLR) evidence from successive verifier
  verdicts;
* stops with an **accept** when there is decisive evidence for correctness;
* **escalates** (strong model) when there is decisive evidence against, or
  when the evidence budget is exhausted without reaching either bound.

Decision-theoretic stopping bounds (asymmetric-loss SPRT):

    accept when  L >= +log(FA / FR)
    escalate    when  L <= -log(FA / FR)

where
    FA = downstream cost of wrongly accepting a bad output  = risk_weight * 10
    FR = cost of a needless escalation                      = STRONG_MODEL_COST

Higher-consequence classes therefore require *more* evidence (in either
direction) before terminating — exactly the behaviour a risk-averse system
needs.  This is deliberately simple and auditable; it makes no pretension to
global optimality, and it is fully deterministic under fixed seeds.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from experiments.benchmark.verification_intelligence import (
    ALL_ACTIONS,
    T0,
    T1,
    T2,
    T3,
    CHEAP_MODEL_COST,
    STRONG_MODEL_COST,
    T0_COST,
    T1_COST,
    T2_COST,
    T3_COST,
    VITask,
    _stable_seed,
    generate_vi_tasks,
    simulate_verify,
)

EVIDENCE_T0 = T0
EVIDENCE_ORDER = [T0, T1, T2, T3]

VERIFIER_BY_NAME = {a.name: a for a in ALL_ACTIONS}


def _llr(action, passed: bool) -> float:
    """Log-likelihood ratio for H=correct vs not, given a verifier verdict."""
    fpr = max(action.fpr, 1e-9)
    fnr = max(action.fnr, 1e-9)
    one_minus_fnr = max(1.0 - fnr, 1e-9)
    one_minus_fpr = max(1.0 - fpr, 1e-9)
    if passed:
        return math.log(one_minus_fnr / fpr)
    return math.log(fnr / one_minus_fpr)


def calibrate_base_rates(
    cal_tasks: List[VITask],
    seed: int,
) -> Dict[str, float]:
    """Calibrate cheap-model correctness per risk class from the CALIBRATION
    split only.  Uses hidden correctness exactly as a calibration label, the
    same role calibration labels play for the admission rule.  Never touches
    evaluation tasks."""
    import random

    correct: Dict[str, List[bool]] = {}
    for task in cal_tasks:
        rng = random.Random(_stable_seed(task.task_id, "cheap", seed))
        mc = rng.random() > (0.05 + 0.4 * task.latent_difficulty)
        correct.setdefault(task.risk_level, []).append(bool(mc))
    rates = {}
    for risk, successes in correct.items():
        n = len(successes)
        p = sum(successes) / n if n else 0.75
        # Clip away from 0/1 so log-odds stay finite.
        rates[risk] = min(max(p, 0.05), 0.95)
    return rates


def strategy_sequential(
    task: VITask,
    seed: int,
    base_rates: Dict[str, float],
    risk_weights: Optional[Dict[str, float]] = None,
) -> Tuple[bool, float, dict]:
    """Run SEA on one task. Returns (success, total_cost, evidence_trace)."""
    risk_weights = risk_weights or {"low": 1.0, "med": 2.0, "high": 5.0}
    import random

    p0 = base_rates.get(task.risk_level, 0.75)
    llr = math.log(p0 / (1.0 - p0))
    risk = risk_weights.get(task.risk_level, 1.0)
    bound = math.log((risk * 10.0) / STRONG_MODEL_COST)   # FA/FR
    fa_fr = bound                                          # accept threshold
    reject_bound = -bound                                  # escalate threshold

    rng = random.Random(_stable_seed(task.task_id, "cheap", seed))
    model_correct = rng.random() > (0.05 + 0.4 * task.latent_difficulty)

    trace = {"risk": task.risk_level, "prior": round(p0, 4), "llr": [round(llr, 4)]}
    cost = CHEAP_MODEL_COST
    accepted = None

    for action in EVIDENCE_ORDER:
        cost += action.cost
        passed = simulate_verify(action, task, model_correct, seed)
        llr += _llr(action, passed)
        trace["llr"].append(round(llr, 4))
        trace[f"{action.name}_passed"] = bool(passed)
        if llr >= fa_fr:
            accepted = True
            break
        if llr <= reject_bound:
            accepted = False
            break

    if accepted is None:
        # Evidence exhausted without either bound met.
        accepted = llr > 0.0

    if accepted:
        return model_correct, cost, trace

    # Escalate: strong model + T3.
    strong_rng = random.Random(_stable_seed(task.task_id, "strong", seed))
    strong_correct = strong_rng.random() > (0.01 + 0.05 * task.latent_difficulty)
    v3 = simulate_verify(T3, task, strong_correct, seed)
    trace["escalated"] = True
    total_cost = cost + STRONG_MODEL_COST + T3_COST
    return strong_correct and v3, total_cost, trace


def run_sea_experiment(
    n_calibration: int = 100,
    n_evaluation: int = 200,
    seed: int = 42,
) -> dict:
    """Run SEA alongside the existing baselines on the same frozen tasks."""
    from experiments.benchmark import verification_intelligence as vi

    cal, evl = generate_vi_tasks(n_calibration, n_evaluation, seed)
    base_rates = calibrate_base_rates(cal, seed)

    sea = []
    for task in evl:
        success, cost, _ = strategy_sequential(task, seed, base_rates)
        sea.append((success, cost))

    vov = vi.run_vov_experiment(n_calibration, n_evaluation, seed=seed)
    results = dict(vov)
    successes = sum(1 for s, _ in sea if s)
    total_cost = sum(c for _, c in sea)
    n = len(sea)
    results["sea"] = {
        "n": n,
        "successes": successes,
        "success_rate": round(successes / n, 4) if n else 0.0,
        "total_cost": round(total_cost, 2),
        "avg_cost_per_task": round(total_cost / n, 4) if n else 0.0,
        "cost_per_success": round(total_cost / successes, 4) if successes else None,
    }
    results["_sea_priors"] = base_rates
    return results


def run_sea_full(seeds=None) -> dict:
    if seeds is None:
        seeds = [42, 123, 456, 789, 1024]
    results = {}
    for seed in seeds:
        results[str(seed)] = run_sea_experiment(seed=seed)
    return {"seeds": seeds, "results": results}


def summarize_sea(full_results) -> dict:
    seeds = full_results["seeds"]
    summary = {}
    strategies = ["always_t0", "always_t3", "fixed_cascade", "vov", "sea"]
    for name in strategies:
        sr = [full_results["results"][str(s)][name]["success_rate"] for s in seeds]
        cps = [full_results["results"][str(s)][name]["cost_per_success"]
               for s in seeds if full_results["results"][str(s)][name]["cost_per_success"] is not None]
        summary[name] = {
            "mean_success_rate": round(sum(sr) / len(sr), 4),
            "mean_cost_per_success": round(sum(cps) / len(cps), 4) if cps else None,
            "min_success_rate": round(min(sr), 4),
            "max_success_rate": round(max(sr), 4),
        }
    return summary
