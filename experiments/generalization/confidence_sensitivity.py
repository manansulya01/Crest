"""Confidence sensitivity: does system behaviour depend on the chosen
confidence level, or only on one lucky threshold?

Sweeps 90/95/99/99.9% confidence over the same recovery programs and reports
coverage, false admission, false rejection per setting.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import crest.faults  # noqa: F401
from crest.distributions import Distribution
from crest.env_family import FAMILIES
from crest.generalization import GeneralizationVerifier, _trial
from crest.policy import EvidencePolicy
from crest.recovery import RecoveryProgram

from .config import canonical

RESULTS = Path(__file__).resolve().parents[1] / "results"
CONFIDENCES = (0.90, 0.95, 0.99, 0.999)
RECOVERIES = ("restore_from_snapshot", "overfit_distractor_gate")
FAMILIES_TESTED = ("filesystem.single_file", "filesystem.directory_tree")


def _policy(confidence: float, n: int) -> EvidencePolicy:
    base = EvidencePolicy()
    bound = canonical().maximum_failure_upper_bound
    return dataclasses.replace(
        base,
        family=dataclasses.replace(base.family, minimum_holdout_cases=n, minimum_verification_cases=n, maximum_failure_upper_bound=bound),
        general=dataclasses.replace(base.general, minimum_holdout_cases=n, minimum_shift_distributions=3, maximum_failure_upper_bound=bound),
        statistics=dataclasses.replace(base.statistics, confidence=confidence, minimum_samples_family=2 * n, minimum_samples_general=2 * n),
    )


def evaluate(confidence: float, action: str, family_id: str, recovery_kind: str, n: int | None = None) -> dict[str, Any]:
    if n is None:
        n = canonical().confidence_samples
    recovery = RecoveryProgram(kind=recovery_kind)
    verifier = GeneralizationVerifier(policy=_policy(confidence, n), verification_cases=n, holdout_cases=n, shift_cases=max(2, n // 2))
    ev = verifier.verify(action_class=action, recovery=recovery, family_ids=(family_id,))
    admitted = ev.evidence_class.value in ("VERIFIED_FIXTURE", "VERIFIED_FAMILY", "VERIFIED_GENERAL")
    eval_ok = 0
    eval_n = 0
    for i in range(n):
        eval_n += 1
        eval_ok += int(_trial(action, FAMILIES[family_id], recovery, 60000 + i, Distribution.IN_DISTRIBUTION, True))
    for i in range(n):
        for d in list(Distribution):
            if d is Distribution.IN_DISTRIBUTION:
                continue
            eval_n += 1
            eval_ok += int(_trial(action, FAMILIES[family_id], recovery, 61000 + i, d, True))
    success = eval_ok / eval_n if eval_n else 0.0
    return {
        "confidence": confidence,
        "action": action,
        "family": family_id,
        "recovery": recovery_kind,
        "evidence_class": ev.evidence_class.value,
        "admitted": admitted,
        "evaluation_success": round(success, 4),
        "false_admission": bool(admitted and success < 0.999),
        "false_rejection": bool((not admitted) and success >= 0.999),
        "ucb_all": ev.upper_bound_exposure,
    }


def run_all(actions=None, n: int | None = None) -> list[dict[str, Any]]:
    cfg = canonical()
    if actions is None:
        actions = cfg.confidence_actions
    if n is None:
        n = cfg.confidence_samples
    rows: list[dict[str, Any]] = []
    for conf in cfg.confidence_levels:
        for action in actions:
            for family in cfg.families:
                for kind in cfg.recoveries:
                    r = evaluate(conf, action, family, kind, n=n)
                    rows.append(r)
                    print(f"conf={conf:<6} {action:12s} {family:26s} {kind:24s} class={r['evidence_class']:18s} "
                          f"admitted={r['admitted']} success={r['evaluation_success']:.2f} false_adm={r['false_admission']}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    is_canonical = (
        tuple(actions) == cfg.confidence_actions
        and n == cfg.confidence_samples
    )
    with (RESULTS / "confidence_sensitivity.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n": n,
            "actions": list(actions),
            "families": list(cfg.families),
            "recoveries": list(cfg.recoveries),
            "maximum_failure_upper_bound": cfg.maximum_failure_upper_bound,
            "canonical": is_canonical,
            "config_digest": cfg.digest(),
            "rows": rows,
        }, sort_keys=True) + "\n")
    return rows


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=None, help="per-arm sample count (default: canonical configuration)")
    args = p.parse_args()
    run_all(n=args.n)