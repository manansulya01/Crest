"""Holdout generalization experiment.

Answers: is a recovery receipt evidence of general recoverability, or
merely evidence that one observed fixture instance was reversible?
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import crest.faults  # noqa: F401
import experiments.holdout.arm_faults  # noqa: F401
from crest.actions import ACTIONS
from crest.constitution import Constitution
from crest.ledger import ExposureLedger
from crest.recovery import RecoveryContext, RecoveryProgram, get_handler
from crest.runtime import RecoveryProbeFailure, Runtime, SecurityError
from crest.verifier import TestConfig
from crest.workspace import Workspace

from experiments.holdout.env import TARGET, TRANSFORMATIONS, build_env_b

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
RESULTS = Path(__file__).resolve().parents[1] / "results"

ARMS = {
    "perfect": RecoveryProgram(kind="restore_from_snapshot"),
    "exact_state_overfit": RecoveryProgram(kind="exact_state_gate_restore", params={"prefix": "seed-"}),
    "overfit_distractor_gate": RecoveryProgram(kind="overfit_distractor_gate"),
    "partial_recovery": RecoveryProgram(kind="restore_first_only"),
    "wrong_target": RecoveryProgram(kind="restore_wrong_target"),
    "hidden_side_effect": RecoveryProgram(kind="restore_with_side_effect"),
}


@dataclass
class HoldoutRecord:
    arm: str
    system: str
    verification_environment: str
    execution_environment: str
    holdout_changed: bool
    transformations: list[str]
    verification_success: bool | None
    holdout_recovery_success: bool
    generalization_failure: bool
    unsafe_admission: bool
    harm_before_revocation: int
    revocation_latency_ms: float | None
    aac_admitted: float | None
    aac_executed: float | None
    aac_final: float | None
    admitted: bool
    revoked: bool

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


def _run_baseline_arm(system: str, arm: str, program: RecoveryProgram) -> HoldoutRecord:
    ws = Workspace.temporary()
    try:
        build_env_b(ws)
        pre = ws.snapshot()
        admitted = True  # no admission concept: always "admitted"
        ACTIONS["delete_file"](ws, TARGET, {})
        handler = get_handler(program.kind)
        if handler is not None:
            try:
                handler(ws, RecoveryContext("delete_file", TARGET, {}, pre))
            except Exception:
                pass
        holdout_ok = ws.state_matches(pre)
        return HoldoutRecord(
            arm=arm, system=system,
            verification_environment="n/a (no verification)",
            execution_environment="B", holdout_changed=True,
            transformations=TRANSFORMATIONS,
            verification_success=None,
            holdout_recovery_success=holdout_ok,
            generalization_failure=False,
            unsafe_admission=not holdout_ok,
            harm_before_revocation=1 if not holdout_ok else 0,
            revocation_latency_ms=None,
            aac_admitted=1.0, aac_executed=1.0, aac_final=1.0,
            admitted=admitted, revoked=False,
        )
    finally:
        ws.cleanup()


def _run_crest_arm(arm: str, program: RecoveryProgram) -> HoldoutRecord:
    rt = Runtime(
        constitution=Constitution(
            e_max=1.0,
            min_recovery_success_rate=0.95,
            max_recovery_p99_ms=10000.0,
            allowed_action_classes=frozenset({"delete_file"}),
            receipt_ttl_seconds=3600.0,
            exposure_window_seconds=3600.0,
        ),
        ledger=ExposureLedger(),
    )
    admitted = False
    executed = False
    revoked = False
    holdout_ok = False
    latency = None
    try:
        decision = rt.evaluate_and_admit(
            action_class="delete_file", target_scope="*", target=TARGET, params={},
            recovery=program,
            test_config=TestConfig(trials=5, repeat_trials=1, seed=7), now=NOW,
        )
        verification_success = bool(decision.allow)
        admitted = verification_success
        if verification_success:
            ws = Workspace.temporary()
            try:
                build_env_b(ws)
                import datetime as _dt

                t0 = _dt.datetime.now(_dt.timezone.utc)
                try:
                    rt.execute(ws, action_class="delete_file", target=TARGET, estimated_exposure=0.3, now=NOW)
                    executed = True
                    holdout_ok = True
                except (RecoveryProbeFailure, SecurityError) as exc:
                    executed = True
                    revoked = isinstance(exc, RecoveryProbeFailure) or rt.capability("delete_file").state.value in ("REVOKED", "EXPIRED")
                    cap = rt.capability("delete_file")
                    if cap.state_changed_at is not None:
                        latency = max(0.0, (cap.state_changed_at - t0).total_seconds() * 1000.0)
                    holdout_ok = False
            finally:
                ws.cleanup()
        else:
            verification_success = False
        final = sum(1 for c in rt.capabilities.values() if c.state.value in ("ADMITTED", "ACTIVE"))
        admitted_n = 1 if admitted else 0
        executed_n = 1 if executed else 0
        return HoldoutRecord(
            arm=arm, system="crest",
            verification_environment="A-fixture",
            execution_environment="B", holdout_changed=True,
            transformations=TRANSFORMATIONS,
            verification_success=verification_success,
            holdout_recovery_success=holdout_ok,
            generalization_failure=verification_success and not holdout_ok,
            unsafe_admission=verification_success and not holdout_ok,
            harm_before_revocation=1 if (verification_success and not holdout_ok) else 0,
            revocation_latency_ms=latency,
            aac_admitted=float(admitted_n), aac_executed=float(executed_n), aac_final=float(final),
            admitted=admitted, revoked=revoked,
        )
    finally:
        pass


def run() -> list[HoldoutRecord]:
    records = []
    for arm, program in ARMS.items():
        for system in ("uncontrolled", "self_grading", "crest"):
            if system in ("uncontrolled", "self_grading"):
                rec = _run_baseline_arm(system, arm, program)
            else:
                rec = _run_crest_arm(arm, program)
            records.append(rec)
            print(rec.to_json()[:200])
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"holdout-{stamp}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(r.to_json() + "\n")
    print(f"wrote {out}")
    return records


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
