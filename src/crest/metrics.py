"""Metric helpers. Raw experiment data is recorded in session results;
this module provides derived, reproducible computations over it."""
from __future__ import annotations

from .capabilities import CapabilityState

EXECUTABLE = (CapabilityState.ADMITTED, CapabilityState.ACTIVE)


def aac(capability_states: dict[str, CapabilityState], eligible: int) -> float:
    if eligible <= 0:
        return 0.0
    return sum(1 for s in capability_states.values() if s in EXECUTABLE) / eligible


def exposure_never_refunded(ledger_totals: list[float]) -> bool:
    """Ledger totals over a session must be non-decreasing."""
    return all(b >= a for a, b in zip(ledger_totals, ledger_totals[1:]))
