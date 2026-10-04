"""Capability state machine.

Legal path to capability:
    FORBIDDEN -> PROPOSED -> VERIFYING -> VERIFIED -> ADMITTED -> ACTIVE
Revocation (ASYMMETRIC: only negative evidence / expiry / drift needed):
    ACTIVE/ADMITTED -> REVOKED
Re-admission after revocation requires fresh verification:
    REVOKED -> VERIFYING
"""
from __future__ import annotations

from enum import Enum


class CapabilityState(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    PROPOSED = "PROPOSED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    ADMITTED = "ADMITTED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


_TRANSITIONS: dict[CapabilityState, frozenset[CapabilityState]] = {
    CapabilityState.FORBIDDEN: frozenset({CapabilityState.PROPOSED}),
    CapabilityState.PROPOSED: frozenset({CapabilityState.VERIFYING, CapabilityState.FORBIDDEN}),
    CapabilityState.VERIFYING: frozenset({CapabilityState.VERIFIED, CapabilityState.FORBIDDEN}),
    CapabilityState.VERIFIED: frozenset({CapabilityState.ADMITTED, CapabilityState.FORBIDDEN}),
    CapabilityState.ADMITTED: frozenset({CapabilityState.ACTIVE, CapabilityState.REVOKED, CapabilityState.EXPIRED}),
    CapabilityState.ACTIVE: frozenset({CapabilityState.REVOKED, CapabilityState.EXPIRED}),
    CapabilityState.REVOKED: frozenset({CapabilityState.VERIFYING, CapabilityState.FORBIDDEN}),
    CapabilityState.EXPIRED: frozenset({CapabilityState.PROPOSED, CapabilityState.FORBIDDEN}),
}


class IllegalTransition(Exception):
    pass


class Capability:
    def __init__(self, action_class: str, scope: str = "*"):
        self.action_class = action_class
        self.scope = scope
        self.state = CapabilityState.FORBIDDEN
        self.receipt_digest: str | None = None

    def transition(self, to: CapabilityState) -> None:
        if to not in _TRANSITIONS[self.state]:
            raise IllegalTransition(f"{self.state} -> {to} is not allowed")
        self.state = to

    @property
    def executable(self) -> bool:
        return self.state in (CapabilityState.ADMITTED, CapabilityState.ACTIVE)
