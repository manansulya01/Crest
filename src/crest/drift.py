"""Drift detection: evidence scope/family vs actual workspace topology.

Deterministic and narrow on purpose: V0.3 drift detection compares the
*declared evidence family* against the structural invariants the current
workspace satisfies. It does not claim to detect all drift.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .workspace import Workspace

def _target_lives_flat(ws: Workspace, target: str) -> bool:
    # the evidence family's flat-layout invariant is reported when the target
    # file sits directly under the workspace root (no nesting).
    return "/" not in target


def _target_lives_nested(ws: Workspace, target: str) -> bool:
    return "/" in target


EXPECTED_INVARIANTS = {
    "filesystem.single_file": (_target_lives_flat, "target lives in a flat directory (no nesting)"),
    "filesystem.directory_tree": (_target_lives_nested, "target lives in a nested directory"),
    "git.repository": (lambda ws, t: (ws.root / ".git").exists(), "git repository present"),
}


@dataclass(frozen=True)
class DriftReport:
    detected: bool
    reasons: tuple[str, ...] = ()
    declared_families: tuple[str, ...] = ()


def detect(workspace: Workspace, declared_families: tuple[str, ...], target: str | None = None) -> DriftReport:
    reasons = []
    t = target or ""
    for fam in declared_families:
        check = EXPECTED_INVARIANTS.get(fam)
        if check is None:
            continue
        ok, desc = check
        try:
            if not ok(workspace, t):
                reasons.append(f"workspace no longer satisfies invariant '{desc}' for family {fam}")
        except Exception:
            reasons.append(f"could not evaluate invariant for family {fam}")
    return DriftReport(detected=bool(reasons), reasons=tuple(reasons), declared_families=declared_families)
