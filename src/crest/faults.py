"""Fault-injection recovery programs.

These deliberately misbehave and exist ONLY for experiments and tests.
They are registered on import; importing this module is an explicit act.
The default honest kinds live in `crest.recovery`.
"""
from __future__ import annotations

import time

from .recovery import RecoveryContext, register
from .workspace import Workspace

SIDE_EFFECT_PATH = "innocent.txt"
STALE_CONTENT = b"STALE CONTENT"


@register("noop_fault")
def _noop_fault(ws: Workspace, ctx: RecoveryContext) -> None:
    return None


@register("restore_truncated")
def _truncated(ws: Workspace, ctx: RecoveryContext) -> None:
    snap = ctx.pre_action_snapshot
    if ctx.target in snap:
        data = snap[ctx.target]
        ws.write(ctx.target, data[: max(1, len(data) // 2)])


@register("restore_with_side_effect")
def _side_effect(ws: Workspace, ctx: RecoveryContext) -> None:
    snap = ctx.pre_action_snapshot
    if ctx.target in snap:
        ws.write(ctx.target, snap[ctx.target])
    existing = b""
    try:
        existing = ws.read(SIDE_EFFECT_PATH)
    except Exception:
        pass
    ws.write(SIDE_EFFECT_PATH, existing + b"\nTAMPERED")


@register("slow_restore")
def _slow(ws: Workspace, ctx: RecoveryContext) -> None:
    time.sleep(1.0)
    ws.restore_snapshot(dict(ctx.pre_action_snapshot))


@register("restore_stale")
def _stale(ws: Workspace, ctx: RecoveryContext) -> None:
    ws.write(ctx.target, STALE_CONTENT)


@register("restore_first_only")
def _first_only(ws: Workspace, ctx: RecoveryContext) -> None:
    """Partially recovers: only the first child fully, plus only a
    truncated copy of the primary file."""
    target_norm = ctx.target.rstrip("/")
    under = sorted(k for k in ctx.pre_action_snapshot if k == target_norm or k.startswith(target_norm + "/"))
    for rel in under[:1]:
        data = ctx.pre_action_snapshot[rel]
        if rel == target_norm:
            ws.write(rel, data[: max(1, len(data) // 2)])
        else:
            ws.write(rel, data)


@register("overfit_distractor_gate")
def _overfit(ws: Workspace, ctx: RecoveryContext) -> None:
    """Passes verifier trials (which create distractor files); no-op otherwise."""
    looks_like_trial = any(name.startswith("distractor-") for name in ws.file_set())
    if looks_like_trial:
        ws.restore_snapshot(dict(ctx.pre_action_snapshot))


@register("restore_wrong_target")
def _wrong_target(ws: Workspace, ctx: RecoveryContext) -> None:
    snap = ctx.pre_action_snapshot
    other = next((k for k in snap if k != ctx.target), None)
    if other is not None:
        ws.write(ctx.target, snap[other])
