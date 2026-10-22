"""Validation-only recovery programs.

These are intentionally adversarial fixtures for the independent evaluation.
They are registered on import and are not used by production admission.
"""
from __future__ import annotations

from crest.recovery import RecoveryContext, register
from crest.workspace import Workspace


@register("validation_overfit_training_shape")
def _overfit_training_shape(ws: Workspace, ctx: RecoveryContext) -> None:
    """Restore only when a training-generator marker is present.

    ``crest.fixtures.generate`` writes ``d0.txt`` for the flat family. The
    V0.4 holdout generator and the validation generator do not. A policy that
    only checks the training shape therefore admits this recovery without
    evidence that it generalizes.
    """
    names = set(ws.file_set())
    if "d0.txt" in names or any(name.startswith("d0") and name.endswith(".txt") for name in names):
        ws.restore_snapshot(dict(ctx.pre_action_snapshot))
