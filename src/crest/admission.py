"""Deterministic constitutional admission controller."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .constitution import Constitution
from .receipts import STATUS_VERIFIED, CapabilityReceipt


@dataclass(frozen=True)
class AdmissionDecision:
    allow: bool
    reasons: tuple[str, ...] = ()


def admit(
    *,
    receipt: CapabilityReceipt,
    current_exposure: float,
    constitution: Constitution,
    now: datetime,
) -> AdmissionDecision:
    reasons: list[str] = []

    if not receipt.is_hash_valid():
        reasons.append("receipt hash binding invalid")
    if receipt.status != STATUS_VERIFIED:
        reasons.append(f"receipt status is {receipt.status!r}, not VERIFIED")
    if receipt.is_expired(now):
        reasons.append("receipt expired")
    if not constitution.is_action_allowed(receipt.action_class):
        reasons.append("action class constitutionally forbidden")
    if receipt.evidence.recovery_success_rate < constitution.min_recovery_success_rate:
        reasons.append("recovery success rate below threshold")
    if receipt.evidence.recovery_latency_p99_ms > constitution.max_recovery_p99_ms:
        reasons.append("recovery latency exceeds budget")
    if current_exposure + receipt.evidence.residual_exposure_ucb > constitution.e_max:
        reasons.append("residual exposure exceeds budget")

    return AdmissionDecision(allow=not reasons, reasons=tuple(reasons))
