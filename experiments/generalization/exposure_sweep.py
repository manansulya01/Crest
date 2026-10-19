"""Exposure sweep: autonomy/coverage vs exposure budget.

For each E_max, run a fixed action schedule against a real Crest runtime and
record admitted/denied actions, realized exposure, certified exposure, AAC
and GAC.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import crest.faults  # noqa: F401
from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.evidence import EvidenceClass
from crest.metrics_v04 import CoverageSnapshot
from crest.recovery import RecoveryProgram

from .config import canonical

RESULTS = Path(__file__).resolve().parents[1] / "results"

BUDGETS = (0.1, 0.25, 0.5, 1.0)
SCHEDULE = (
    ("filesystem", "modify_file", {"path": "a.txt", "content": "1"}),
    ("filesystem", "modify_file", {"path": "a.txt", "content": "2"}),
    ("filesystem", "delete_file", {"path": "a.txt"}),
    ("filesystem", "delete_file", {"path": "b.txt"}),
)
ELIGIBLE_ACTIONS = ("modify_file", "delete_file")


def run_budget(e_max: float, agent: str = "sweep-agent") -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="crest-sweep-"))
    try:
        (tmp / "a.txt").write_text("x", encoding="utf-8")
        (tmp / "b.txt").write_text("y", encoding="utf-8")
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest", e_max=e_max))
        for action in ELIGIBLE_ACTIONS:
            rt.verify_generalized(
                action_class=action, scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
                family_ids=("filesystem.single_file",), verification_cases=4, holdout_cases=4, shift_cases=2,
            )
        admitted = set()
        family_backed = set()
        general_backed = set()
        executed = denied = 0
        for tool, operation, args in SCHEDULE:
            r = rt.execute(agent_id=agent, tool=tool, operation=operation, arguments=dict(args))
            if r.ok:
                executed += 1
                admitted.add(operation)
                payload = rt.store.get_receipt_payload(rt.get_capability(f"{operation}:*")["receipt_id"]) or {}
                cls = payload.get("evidence_classification", "VERIFIED_FIXTURE")
                if cls in (EvidenceClass.VERIFIED_FAMILY.value, EvidenceClass.VERIFIED_GENERAL.value):
                    family_backed.add(operation)
                if cls == EvidenceClass.VERIFIED_GENERAL.value:
                    general_backed.add(operation)
            else:
                denied += 1
        snapshot = CoverageSnapshot(eligible=len(ELIGIBLE_ACTIONS), admitted=admitted, family_backed=family_backed, general_backed=general_backed)
        return {
            "e_max": e_max,
            "executed": executed,
            "denied": denied,
            "certified_exposure": round(rt.store.total_exposure(), 4),
            "realized_actions": executed,
            **snapshot.to_dict(),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_all(budgets=None) -> list[dict[str, Any]]:
    cfg = canonical()
    if budgets is None:
        budgets = cfg.e_max_values
    out = []
    for e_max in budgets:
        row = run_budget(e_max)
        out.append(row)
        print(f"e_max={e_max:<5} executed={row['executed']} denied={row['denied']} "
              f"certified={row['certified_exposure']} aac={row['aac']} gac={row['gac']}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    is_canonical = tuple(budgets) == cfg.e_max_values
    with (RESULTS / "exposure_sweep.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "schedule": len(SCHEDULE),
            "e_max_values": list(budgets),
            "canonical": is_canonical,
            "config_digest": cfg.digest(),
            "rows": out,
        }, sort_keys=True) + "\n")
    return out


if __name__ == "__main__":
    run_all()