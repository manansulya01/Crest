"""Drift experiment: which drift classes does Crest actually detect?

Honest scope: only the implemented drift model is measured. Unimplemented
classes (git state change, symlink topology, content identity) are recorded
as UNIMPLEMENTED rather than silently ignored.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.drift import detect
from crest.recovery import RecoveryProgram
from crest.workspace import Workspace

RESULTS = Path(__file__).resolve().parents[1] / "results"


class DriftClass(str, Enum):
    TARGET_MOVED = "target_moved"
    TARGET_RENAMED = "target_renamed"
    DIRECTORY_STRUCTURE_CHANGED = "directory_structure_changed"
    ADDITIONAL_DISTRACTORS = "additional_distractors"
    SCOPE_CHANGED = "scope_changed"
    FILE_CONTENT_CHANGED = "file_content_changed"
    SYMLINK_INTRODUCED = "symlink_introduced"
    GIT_STATE_CHANGED = "git_state_changed"


IMPLEMENTED = {DriftClass.TARGET_MOVED, DriftClass.TARGET_RENAMED, DriftClass.DIRECTORY_STRUCTURE_CHANGED}
# NOTE: this set reflects what the detector actually implements today
# (target identity/type + evidence-family nesting). Content drift, scope
# drift, symlink topology and git-state drift are recorded as unimplemented.


@dataclass
class DriftOutcome:
    drift_class: str
    detected: bool | None
    detection_reason: str
    revocation_latency_ms: float | None
    implementation: str


def _scenario(tmp: Path, drift: DriftClass):
    ws = Workspace(tmp)
    ws.write("a.txt", b"data")
    ws.write("keep/b.txt", b"nested")
    ws.write("docs/a.txt", b"docs-data")
    return ws


def run(cases: int = 5) -> list[DriftOutcome]:
    outcomes: list[DriftOutcome] = []
    for drift in DriftClass:
        for i in range(cases):
            tmp = Path(tempfile.mkdtemp(prefix="crest-drift-"))
            try:
                ws = _scenario(tmp, drift)
                target = "a.txt"
                if drift is DriftClass.TARGET_MOVED:
                    ws.move("a.txt", "sub/a.txt")
                    target = "sub/a.txt"
                elif drift is DriftClass.TARGET_RENAMED:
                    ws.move("a.txt", "renamed.txt")
                    target = "renamed.txt"
                elif drift is DriftClass.DIRECTORY_STRUCTURE_CHANGED:
                    ws.write("nested/deep/file.txt", b"deep")
                    target = "nested/a.txt"
                elif drift in (DriftClass.ADDITIONAL_DISTRACTORS, DriftClass.FILE_CONTENT_CHANGED, DriftClass.SCOPE_CHANGED):
                    ws.write("extra.txt", b"extra")
                    ws.write("a.txt", b"changed content")
                elif drift is DriftClass.SYMLINK_INTRODUCED:
                    try:
                        (tmp / "link").symlink_to(Path("..").resolve() / "outside")
                    except OSError:
                        pass
                elif drift is DriftClass.GIT_STATE_CHANGED:
                    pass

                families = ("filesystem.directory_tree",) if "/" in target else ("filesystem.single_file",)
                t0 = time.perf_counter()
                report = detect(ws, families, target=target)
                dt = (time.perf_counter() - t0) * 1000
                detected: bool | None = report.detected if drift in IMPLEMENTED else None
                outcomes.append(
                    DriftOutcome(
                        drift_class=drift.value,
                        detected=detected,
                        detection_reason="; ".join(report.reasons) or "no drift detected",
                        revocation_latency_ms=round(dt, 4) if detected else None,
                        implementation="implemented" if drift in IMPLEMENTED else "unimplemented",
                    )
                )
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    return outcomes


def summarize(outcomes: list[DriftOutcome]) -> dict[str, Any]:
    implemented = [o for o in outcomes if o.implementation == "implemented"]
    unimplemented = [o for o in outcomes if o.implementation == "unimplemented"]
    return {
        "cases": len(outcomes),
        "implemented_classes": sorted({o.drift_class for o in implemented}),
        "unimplemented_classes": sorted({o.drift_class for o in unimplemented}),
        "detection_rate_implemented": round(sum(1 for o in implemented if o.detected) / len(implemented), 4) if implemented else 0.0,
        "false_negative_rate_implemented": round(sum(1 for o in implemented if not o.detected) / len(implemented), 4) if implemented else 0.0,
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=int, default=5)
    args = p.parse_args()
    outs = run(args.cases)
    for o in outs:
        print(f"{o.drift_class:32s} detected={o.detected} impl={o.implementation} reason={o.detection_reason[:60]}")
    print(json.dumps(summarize(outs), indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "drift.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "summary": summarize(outs),
                             "outcomes": [dataclasses.asdict(o) for o in outs]}, sort_keys=True) + "\n")