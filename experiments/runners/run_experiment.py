"""Reproducible experiment runner.

Records: experiment_id, git commit, branch, configuration, seed,
environment version, verifier version, test configuration, timestamp,
action class, attack type, system, per-step results, and metrics.

Output: JSONL records in experiments/results/.
"""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crest import __version__ as CREST_VERSION
from crest.verifier import Verifier

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


@dataclass
class ExperimentConfig:
    attack: str
    system: str  # "uncontrolled" | "self_grading" | "crest"
    seed: int = 7
    latency_bound_ms: float = 10000.0
    notes: str = ""


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: str
    git_commit: str
    branch: str
    configuration: dict[str, Any]
    random_seed: int
    environment_version: str
    verifier_version: str
    test_version: str
    attack_type: str
    system: str
    result: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        import dataclasses

        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def run_experiment(config: ExperimentConfig) -> ExperimentRecord:
    from experiments.baselines.session import run_crest, run_self_grading, run_uncontrolled

    if config.system == "uncontrolled":
        session = run_uncontrolled(config.attack)
    elif config.system == "self_grading":
        session = run_self_grading(config.attack)
    elif config.system == "crest":
        session = run_crest(config.attack, latency_bound_ms=config.latency_bound_ms)
    else:
        raise ValueError(config.system)

    metrics = {
        "realized_harm_events": session.realized_harm_events,
        "certified_exposure": session.certified_exposure,
        "aac_final": session.aac_final,
        "revoked": session.revoked,
        "steps": len(session.steps),
        "denied_steps": sum(1 for s in session.steps if not s.admitted),
        "aac_admitted": session.aac_admitted,
        "aac_executed": session.aac_executed,
        "unsafe_admission": session.unsafe_admission,
        "harm_before_revocation": session.harm_before_revocation,
        "revocation_latency_ms": session.revocation_latency_ms,
    }
    record = ExperimentRecord(
        experiment_id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_commit=_git(["rev-parse", "HEAD"]),
        branch=_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        configuration=dataclasses_config(config),
        random_seed=config.seed,
        environment_version=Verifier.ENVIRONMENT,
        verifier_version=Verifier.VERSION,
        test_version="milestone2-v1",
        attack_type=config.attack,
        system=config.system,
        result=session.to_dict(),
        metrics=metrics,
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{record.experiment_id}.jsonl"
    out.write_text(record.to_jsonl() + "\n", encoding="utf-8")
    return record


def dataclasses_config(config: ExperimentConfig) -> dict[str, Any]:
    import dataclasses

    return dataclasses.asdict(config)


def run_matrix(attacks: list[str], systems: list[str], latency_bound_ms: float = 10000.0) -> list[ExperimentRecord]:
    records = []
    for attack in attacks:
        for system in systems:
            t0 = time.perf_counter()
            bound = latency_bound_ms
            rec = run_experiment(ExperimentConfig(attack=attack, system=system, latency_bound_ms=bound))
            records.append(rec)
            print(f"{system:12s} {attack:28s} harm={rec.metrics['realized_harm_events']} denied={rec.metrics['denied_steps']} revoked={rec.metrics['revoked']} ({time.perf_counter()-t0:.1f}s)")
    return records


if __name__ == "__main__":
    import argparse

    from experiments.attacks.adversary import ATTACKS

    p = argparse.ArgumentParser()
    p.add_argument("--attack", default=None, choices=sorted(ATTACKS))
    p.add_argument("--system", default=None, choices=["uncontrolled", "self_grading", "crest"])
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--latency-bound-ms", type=float, default=10000.0)
    args = p.parse_args()
    if args.matrix:
        run_matrix(sorted(ATTACKS), ["uncontrolled", "self_grading", "crest"], latency_bound_ms=args.latency_bound_ms)
    else:
        print(run_experiment(ExperimentConfig(attack=args.attack, system=args.system, latency_bound_ms=args.latency_bound_ms)).to_jsonl()[:400])
