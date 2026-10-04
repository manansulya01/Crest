"""The learner is untrusted. It can only PROPOSE recovery programs.

It receives no reference to the constitution, ledger, admission
controller, capability store, or verifier. Its outputs are opaque,
arbitrary input to the rest of the system.
"""
from __future__ import annotations

from typing import Any

from .recovery import RecoveryProgram


class HeuristicProposer:
    """Deterministic V0 learner stand-in."""

    def propose(self, action_class: str, target: str, context: dict[str, Any] | None = None) -> RecoveryProgram:
        if action_class in ("delete_file", "modify_file", "delete_record", "modify_record", "move_file"):
            return RecoveryProgram(kind="restore_file_from_snapshot", params={})
        if action_class in ("create_file", "create_record"):
            return RecoveryProgram(kind="delete_target", params={})
        return RecoveryProgram(kind="noop", params={})


class BrokenProposer:
    """Learner that proposes inadequate recovery — verification must fail."""

    def propose(self, action_class: str, target: str, context: dict[str, Any] | None = None) -> RecoveryProgram:
        return RecoveryProgram(kind="noop", params={})


class OverfittingProposer:
    """Learner that proposes recovery tuned to pass shallow checks."""

    def propose(self, action_class: str, target: str, context: dict[str, Any] | None = None) -> RecoveryProgram:
        return RecoveryProgram(kind="restore_file_from_snapshot", params={})
