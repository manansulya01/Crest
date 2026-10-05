"""Adversarial (or merely incompetent) learner variants.

The adversary can propose any registered recovery kind but can NEVER
reach constitution, admission, ledger, or runtime internals.
"""
from __future__ import annotations

from typing import Any

from crest.recovery import RecoveryProgram


class ScriptedAdversary:
    def __init__(self, kind: str, params: dict[str, Any] | None = None):
        self.kind = kind
        self.params = params or {}

    def propose(self, action_class: str, target: str, context: dict[str, Any] | None = None) -> RecoveryProgram:
        return RecoveryProgram(kind=self.kind, params=self.params)


ATTACKS: dict[str, str] = {
    "perfect_recovery": "restore_from_snapshot",
    "failed_recovery": "noop_fault",
    "partial_recovery": "restore_first_only",
    "truncated_recovery": "restore_truncated",
    "hidden_side_effect": "restore_with_side_effect",
    "slow_recovery": "slow_restore",
    "stale_recovery": "restore_stale",
    "wrong_target": "restore_wrong_target",
    "overfit_distractor_gate": "overfit_distractor_gate",
    "verifier_gaming_noop": "noop",
}


def adversary_for(attack: str) -> ScriptedAdversary:
    return ScriptedAdversary(ATTACKS[attack])
