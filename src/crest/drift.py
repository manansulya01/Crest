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


def detect_identity(workspace: Workspace, target: str, expected_path_type: str = "file") -> DriftReport:
    """Topology/identity drift for a single target path.

    Implemented classes (V0.4): target_moved (missing),
    target_renamed (missing), path_type_changed (file<->dir),
    symlink_introduced.
    """
    reasons: list[str] = []
    abs_target = workspace.resolve(target)
    try:
        is_symlink = abs_target.is_symlink()
    except OSError:
        is_symlink = False
    if is_symlink:
        reasons.append("symlink_introduced at target")
    if not abs_target.exists():
        reasons.append(f"target_moved_or_renamed: {target} no longer exists")
    else:
        actual_type = "dir" if abs_target.is_dir() else "file"
        if actual_type != expected_path_type:
            reasons.append(f"path_type_changed: expected {expected_path_type}, found {actual_type}")
    return DriftReport(detected=bool(reasons), reasons=tuple(reasons), declared_families=("filesystem.identity",))


def detect(workspace: Workspace, declared_families: tuple[str, ...], target: str | None = None, require_existing: bool = True, expected_path_type: str = "file") -> DriftReport:
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
    if target and require_existing:
        identity = detect_identity(workspace, target, expected_path_type=expected_path_type)
        reasons.extend(identity.reasons)
    return DriftReport(detected=bool(reasons), reasons=tuple(reasons), declared_families=declared_families)
