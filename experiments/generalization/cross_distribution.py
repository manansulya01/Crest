"""Cross-distribution generalization experiment.

Question: does an evidence class predict recovery success on environments
the training generator never produced?

For each (action, family, recovery kind) we measure success on:
  - training fixtures (training generator)
  - verification fixtures (training generator, unseen seeds)
  - IID holdout (training generator, unseen seeds)
  - Level-2 holdout (holdout generator = same family, unseen seeds)
  - Level-3 holdout + distribution shifts (independent generator)

Everything is deterministic given the seed; nothing is fabricated.
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
from crest.distributions import Distribution, apply_distribution
from crest.env_family import FAMILIES
from crest.evidence import failure_upper_bound
from crest.fixtures import generate as train_generate
from crest.generalization import VERIFIER_VERSION
from crest.holdout_gen import build as holdout_build
from crest.actions import ACTIONS
from crest.recovery import RecoveryContext, RecoveryProgram, get_handler
from crest.workspace import Workspace

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _trial(action_class: str, recovery: RecoveryProgram, build_fixture, family_id: str, seed: int, distribution: Distribution, params: dict | None = None) -> bool:
    ws = Workspace.temporary()
    try:
        family = FAMILIES[family_id]
        fixture = build_fixture(ws, family=family, seed=seed)
        apply_distribution(ws, fixture.target, distribution, seed=seed)
        pre = ws.snapshot()
        target = fixture.target
        action_params = dict(params or {})
        if action_class == "modify_file":
            action_params = {"content": "modified\n"}
        elif action_class == "move_file":
            action_params = {"destination": "moved-" + target.rsplit("/", 1)[-1]}
        try:
            ACTIONS[action_class](ws, target, action_params)
        except Exception:
            return False
        handler = get_handler(recovery.kind)
        if handler is None:
            return False
        try:
            handler(ws, RecoveryContext(action_class, target, action_params, pre))
        except Exception:
            return False
        return ws.state_matches(pre)
    finally:
        ws.cleanup()


def measure(action_class: str, family_id: str, recovery_kind: str, *, train_n=10, verify_n=10, iid_n=10, level2_n=10, level3_n=10, shift_n=10, seed_base=0) -> dict[str, Any]:
    recovery = RecoveryProgram(kind=recovery_kind)
    metrics: dict[str, Any] = {}
    for name, n, builder, dist in (
        ("training", train_n, train_generate, Distribution.IN_DISTRIBUTION),
        ("verification", verify_n, train_generate, Distribution.IN_DISTRIBUTION),
        ("iid_holdout", iid_n, train_generate, Distribution.IN_DISTRIBUTION),
        ("level2_holdout", level2_n, holdout_build, Distribution.IN_DISTRIBUTION),
        ("level3_holdout", level3_n, holdout_build, Distribution.IN_DISTRIBUTION),
        ("structural_shift", shift_n, holdout_build, Distribution.STRUCTURAL_SHIFT),
        ("parameter_shift", shift_n, holdout_build, Distribution.PARAMETER_SHIFT),
        ("adversarial_shift", shift_n, holdout_build, Distribution.ADVERSARIAL_SHIFT),
    ):
        base = seed_base + {"training": 0, "verification": 1000, "iid_holdout": 2000, "level2_holdout": 3000,
                            "level3_holdout": 4000, "structural_shift": 5000, "parameter_shift": 6000,
                            "adversarial_shift": 7000}[name]
        t0 = time.perf_counter()
        ok = sum(1 for i in range(n) if _trial(action_class, recovery, builder, family_id, base + i, dist))
        metrics[name] = {
            "passed": ok,
            "n": n,
            "success_rate": round(ok / n, 4) if n else 0.0,
            "failure_ucb": round(failure_upper_bound(n - ok, n), 4),
            "seconds": round(time.perf_counter() - t0, 3),
        }
    return metrics


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: str
    git_commit: str
    branch: str
    crest_version: str
    python_version: str
    os: str
    verifier_version: str
    seed_base: int
    action: str
    family: str
    recovery_kind: str
    distributions: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def run_grid(actions=("delete_file", "modify_file"), families=("filesystem.single_file", "filesystem.directory_tree"),
             recoveries=("restore_from_snapshot", "overfit_distractor_gate", "noop_fault"), **kw) -> list[ExperimentRecord]:
    records: list[ExperimentRecord] = []
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for action in actions:
        for family in families:
            for kind in recoveries:
                dist = measure(action, family, kind, **kw)
                rec = ExperimentRecord(
                    experiment_id="",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    git_commit=_git(["rev-parse", "HEAD"]),
                    branch=_git(["rev-parse", "--abbrev-ref", "HEAD"]),
                    crest_version=crest.__version__,
                    python_version=sys.version.split()[0],
                    os=f"{platform.system()} {platform.release()}",
                    verifier_version=VERIFIER_VERSION,
                    seed_base=kw.get("seed_base", 0),
                    action=action,
                    family=family,
                    recovery_kind=kind,
                    distributions=dist,
                    config={"generators": ["train:fixtures.generate", "holdout:holdout_gen.build"]},
                )
                records.append(rec)
                print(f"{action:12s} {family:28s} {kind:24s} " +
                      " ".join(f"{k}={v['success_rate']:.2f}" for k, v in dist.items()))
    out = RESULTS_DIR / "cross_distribution.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(r.to_json() + "\n")
    print(f"wrote {out}")
    return records


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n", type=int, default=10)
    args = p.parse_args()
    run_grid(train_n=args.n, verify_n=args.n, iid_n=args.n, level2_n=args.n, level3_n=args.n, shift_n=args.n, seed_base=args.seed)