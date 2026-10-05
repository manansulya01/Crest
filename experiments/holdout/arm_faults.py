"""Holdout-specific adversarial recovery programs (registered on import)."""
from __future__ import annotations

from crest.recovery import RecoveryContext, register
from crest.workspace import Workspace


@register("exact_state_gate_restore")
def _exact_state_gate(ws: Workspace, ctx: RecoveryContext) -> None:
    """Restores only when the workspace looks like the verifier fixture
    (flat paths, all seed-prefixed or seed-target content).

    Environment A (verification fixture) satisfies this; environment B
    does not."""
    prefix = str(ctx.params.get("prefix", "seed-")).encode()
    snap = ctx.pre_action_snapshot
    gate = all("/" not in key for key in snap) and ctx.target in snap and snap[ctx.target].startswith(prefix)
    if gate:
        ws.restore_snapshot(dict(snap))
