"""Composition verifier: does recoverability compose?

Each step of a sequence may be individually recoverable while the *sequence*
is not, e.g. modify-then-move: a recovery program that only restores the
final target path cannot restore the intermediate modification history.

Nothing here assumes compositionality; the whole point is to measure it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .actions import ACTIONS
from .env_family import FAMILIES
from .fixtures import generate
from .recovery import RecoveryContext, RecoveryProgram, get_handler
from .workspace import Workspace


class CompositionStatus(str, Enum):
    VERIFIED_COMPOSITION = "VERIFIED_COMPOSITION"
    UNVERIFIED_COMPOSITION = "UNVERIFIED_COMPOSITION"


@dataclass
class Step:
    action_class: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompositionResult:
    status: CompositionStatus
    cases: int
    recovered: int
    success_rate: float
    component_success: dict[str, float]
    failure_mode: str = ""


def _params_for(step: Step, target: str, case_index: int) -> dict[str, Any]:
    args = dict(step.params)
    if step.action_class == "modify_file":
        args = {"content": f"step-{case_index}\n"}
    elif step.action_class == "move_file":
        args = {"destination": f"moved-{case_index}.txt"}
    return args


def _run_sequence(family_id: str, seed: int, steps: tuple[Step, ...], recovery: RecoveryProgram) -> tuple[bool, str]:
    ws = Workspace.temporary()
    try:
        family = FAMILIES[family_id]
        fixture = generate(ws, family=family, seed=seed)
        pre = ws.snapshot()
        for i, step in enumerate(steps):
            try:
                ACTIONS[step.action_class](ws, fixture.target, _params_for(step, fixture.target, seed + i))
            except Exception:
                return False, "step_failed"
        handler = get_handler(recovery.kind)
        if handler is None:
            return False, "no_recovery_handler"
        try:
            handler(ws, RecoveryContext("composition", fixture.target, {}, pre))
        except Exception:
            return False, "recovery_exception"
        return (ws.state_matches(pre), "" if ws.state_matches(pre) else "state_not_restored")
    finally:
        ws.cleanup()


def verify_composition(
    *,
    steps: tuple[Step, ...],
    recovery: RecoveryProgram,
    family_id: str = "filesystem.single_file",
    cases: int = 10,
    seed_base: int = 40000,
    measure_components: bool = True,
) -> CompositionResult:
    recovered = 0
    failure_mode = ""
    for i in range(cases):
        ok, mode = _run_sequence(family_id, seed_base + i, steps, recovery)
        if ok:
            recovered += 1
        elif not failure_mode:
            failure_mode = mode

    component: dict[str, float] = {}
    if measure_components:
        for step in steps:
            ok_count = 0
            for i in range(cases):
                ok, _ = _run_sequence(family_id, seed_base + i, (step,), recovery)
                ok_count += int(ok)
            component[step.action_class] = round(ok_count / cases, 4) if cases else 0.0

    rate = recovered / cases if cases else 0.0
    status = CompositionStatus.VERIFIED_COMPOSITION if rate >= 1.0 else CompositionStatus.UNVERIFIED_COMPOSITION
    return CompositionResult(
        status=status,
        cases=cases,
        recovered=recovered,
        success_rate=round(rate, 4),
        component_success=component,
        failure_mode=failure_mode,
    )