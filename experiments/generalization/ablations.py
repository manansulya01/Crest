"""Ablation + coverage experiment.

Measures, per evidence mode:
  - admitted coverage (AAC at admission time)
  - generalized coverage (GAC: coverage backed by evidence that survived the
    cross-distribution evaluation)
  - false admissions (admitted under policy but recovery failed on the
    independent evaluation distribution)
  - false rejections (recovery reliable on evaluation but denied)
  - verification cost (seconds)

Everything is measured on real runs; nothing is simulated.
"""
from __future__ import annotations

import dataclasses
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import crest
import crest.faults  # noqa: F401
from crest.distributions import Distribution
from crest.env_family import FAMILIES
from crest.fixtures import generate as train_generate
from crest.generalization import GeneralizationVerifier
from crest.holdout_gen import build as holdout_build
from crest.policy import EvidencePolicy
from crest.recovery import RecoveryProgram, get_handler
from crest.generalization import _trial

from .config import canonical

RESULTS = Path(__file__).resolve().parents[1] / "results"

MODES = ("fixture_only", "family_evidence", "generalized_evidence")
RECOVERIES = ("restore_from_snapshot", "overfit_distractor_gate")


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _policy_for_mode(mode: str, n: int | None = None) -> EvidencePolicy:
    cfg = canonical()
    if n is None:
        n = cfg.samples
    base = EvidencePolicy()
    # Minimum samples and bounds are scaled to the experiment sample size so
    # the three modes are comparable at this n. The *default* production
    # policy is far stricter; this is an experimental configuration whose
    # parameters are declared in experiments/configs/experiment.yaml.
    family = dataclasses.replace(base.family, minimum_holdout_cases=n, minimum_verification_cases=n, maximum_failure_upper_bound=cfg.maximum_failure_upper_bound)
    general = dataclasses.replace(base.general, minimum_holdout_cases=n, minimum_shift_distributions=3, maximum_failure_upper_bound=cfg.maximum_failure_upper_bound)
    stats = dataclasses.replace(base.statistics, minimum_samples_family=2 * n, minimum_samples_general=2 * n)
    if mode == "fixture_only":
        return dataclasses.replace(base, family=dataclasses.replace(family, minimum_holdout_cases=0, minimum_verification_cases=0),
                                   general=dataclasses.replace(general, minimum_holdout_cases=0, minimum_shift_distributions=0),
                                   statistics=dataclasses.replace(stats, minimum_samples_family=0, minimum_samples_general=0))
    if mode == "family_evidence":
        return dataclasses.replace(base, family=family, general=dataclasses.replace(general, minimum_shift_distributions=10 ** 6), statistics=stats)
    return dataclasses.replace(base, family=family, general=general, statistics=stats)


def evaluate_mode(mode: str, action: str, recovery_kind: str, family_id: str, *, n: int | None = None) -> dict[str, Any]:
    if n is None:
        n = canonical().samples
    recovery = RecoveryProgram(kind=recovery_kind)
    policy = _policy_for_mode(mode, n)
    if mode == "fixture_only":
        # V0.3-style: admit on in-distribution fixture evidence only.
        # No holdout generator, no distribution shifts are consulted.
        verifier = GeneralizationVerifier(policy=policy, verification_cases=n, holdout_cases=0, shift_cases=0)
        t0 = time.perf_counter()
        in_dist_ok = sum(
            1 for i in range(n)
            if _trial(action, FAMILIES[family_id], recovery, 1000 + i, Distribution.IN_DISTRIBUTION, False)
        )
        evidence = verifier.verify(action_class=action, recovery=recovery, family_ids=(family_id,))
        cost = time.perf_counter() - t0
        admitted = in_dist_ok == n and get_handler(recovery.kind) is not None
        evidence_class = "VERIFIED_FIXTURE" if admitted else "UNVERIFIED"
    else:
        verifier = GeneralizationVerifier(policy=policy, verification_cases=n, holdout_cases=n, shift_cases=max(2, n // 2))
        t0 = time.perf_counter()
        evidence = verifier.verify(action_class=action, recovery=recovery, family_ids=(family_id,))
        cost = time.perf_counter() - t0
        evidence_class = evidence.evidence_class.value
        admitted = evidence_class in ("VERIFIED_FIXTURE", "VERIFIED_FAMILY", "VERIFIED_GENERAL")

    # independent evaluation: what actually happens on unseen environments
    ev_pass = 0
    for i in range(n):
        if _trial(action, FAMILIES[family_id], RecoveryProgram(kind=recovery_kind), 70000 + i, Distribution.IN_DISTRIBUTION, True):
            ev_pass += 1
    shift_pass = 0
    shift_n = 0
    for i in range(n):
        for d in (Distribution.PARAMETER_SHIFT, Distribution.STRUCTURAL_SHIFT, Distribution.ADVERSARIAL_SHIFT):
            shift_n += 1
            shift_pass += int(_trial(action, FAMILIES[family_id], RecoveryProgram(kind=recovery_kind), 80000 + i, d, True))
    eval_total = n + shift_n
    eval_success = (ev_pass + shift_pass) / eval_total if eval_total else 0.0

    false_admission = admitted and eval_success < 0.999
    false_rejection = (not admitted) and eval_success >= 0.999

    return {
        "mode": mode,
        "action": action,
        "family": family_id,
        "recovery": recovery_kind,
        "evidence_class": evidence_class,
        "admitted": admitted,
        "evaluation_success": round(eval_success, 4),
        "false_admission": false_admission,
        "false_rejection": false_rejection,
        "verification_seconds": round(cost, 3),
        "fixture_success": round(evidence.recovery_success_rate, 4),
        "holdout_passed": evidence.holdout_passed,
        "holdout_cases": evidence.holdout_fixtures,
        "shift_failures": evidence.distribution_shift_failures,
    }


@dataclass
class AblationRecord:
    timestamp: str
    git_commit: str
    branch: str
    crest_version: str
    python: str
    os: str
    results: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def run_all(actions=None, families=None, recoveries=None, n: int | None = None) -> AblationRecord:
    cfg = canonical()
    if actions is None:
        actions = cfg.actions
    if families is None:
        families = cfg.families
    if recoveries is None:
        recoveries = cfg.recoveries
    if n is None:
        n = cfg.samples
    results: list[dict[str, Any]] = []
    for mode in MODES:
        for action in actions:
            for family in families:
                for kind in recoveries:
                    r = evaluate_mode(mode, action, kind, family, n=n)
                    results.append(r)
                    print(f"{mode:20s} {action:12s} {family:24s} {kind:24s} class={r['evidence_class']:18s} "
                          f"admitted={r['admitted']} eval_success={r['evaluation_success']:.2f} "
                          f"false_adm={r['false_admission']} false_rej={r['false_rejection']} cost={r['verification_seconds']}s")
    rec = AblationRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_commit=_git(["rev-parse", "HEAD"]),
        branch=_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        crest_version=crest.__version__,
        python=sys.version.split()[0],
        os=f"{platform.system()} {platform.release()}",
        results=results,
        config={
            "cases_per_measurement": n,
            "maximum_failure_upper_bound": cfg.maximum_failure_upper_bound,
            "modes": list(MODES),
            "actions": list(actions),
            "families": list(families),
            "recoveries": list(recoveries),
            "seed_bases": {"verification_fixtures": 1000, "evaluation": 70000, "shift": 80000},
            "canonical": (
                tuple(actions) == cfg.actions
                and tuple(families) == cfg.families
                and tuple(recoveries) == cfg.recoveries
                and n == cfg.samples
            ),
            "config_digest": cfg.digest(),
        },
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "ablations.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        fh.write(rec.to_json() + "\n")
    print(f"wrote {out}")
    return rec


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=None, help="per-arm sample count (default: canonical configuration)")
    p.add_argument("--seed", type=str, default="0", help="numeric seed or 'random'")
    args = p.parse_args()
    if args.seed == "random":
        print("NOTE: random-seed stress mode is not implemented; fixed seeds are used and recorded in the results.")
    run_all(n=args.n)