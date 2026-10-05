"""Small structured benchmarks. No fake numbers: runs against live objects."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from .agent_runtime import CrestRuntime
from .config import CrestConfig
from .drift import detect as detect_drift
from .generalization import GeneralizationVerifier
from .recovery import RecoveryProgram
from .workspace import Workspace


def admission_overhead() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="crest-bench-admission-"))
    try:
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest", e_max=10_000.0))
        rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=4)
        n = 300
        t0 = time.perf_counter()
        for _ in range(n):
            rt.check(agent_id="bench", tool="filesystem", operation="modify_file", arguments={"path": "a.txt"})
        dt = (time.perf_counter() - t0) / n * 1000
        rt.close()
        return {"metric": "admission_check_ms_mean", "value": round(dt, 3), "samples": n}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def security_deny_overhead() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="crest-bench-sec-"))
    try:
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest"))
        n = 200
        t0 = time.perf_counter()
        for _ in range(n):
            rt.check(agent_id="bench", tool="filesystem", operation="delete_file", arguments={"path": "nope.txt"})
        dt = (time.perf_counter() - t0) / n * 1000
        rt.close()
        return {"metric": "denied_check_ms_mean", "value": round(dt, 3), "samples": n}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def generalization_cost() -> dict:
    t0 = time.perf_counter()
    ev = GeneralizationVerifier().verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",),
    )
    dt = time.perf_counter() - t0
    return {
        "metric": "generalization_verify_seconds",
        "value": round(dt, 3),
        "evidence_class": ev.evidence_class.value,
        "fixtures_tested": ev.fixtures_tested,
        "holdout_fixtures": ev.holdout_fixtures,
    }


def drift_detection_time() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="crest-bench-drift-"))
    try:
        ws = Workspace(tmp)
        ws.write("a.txt", b"1")
        t0 = time.perf_counter()
        for _ in range(100):
            detect_drift(ws, ("filesystem.single_file",), target="a.txt")
        dt = (time.perf_counter() - t0) / 100 * 1000
        return {"metric": "drift_check_ms_mean", "value": round(dt, 4), "samples": 100}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ALL = {
    "admission": admission_overhead,
    "security": security_deny_overhead,
    "generalization": generalization_cost,
    "drift": drift_detection_time,
}


def run(which: str = "all") -> list[dict]:
    names = list(ALL) if which == "all" else [which]
    return [ALL[n]() for n in names]
