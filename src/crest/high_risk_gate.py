"""High-Risk Gate — runtime integration of the Strong High-Risk Gate.

This module provides a runtime-level gate that applies provenance-aware
evidence sufficiency checking to high-risk acceptance decisions.

The gate is a narrow veto: it does not replace the base verifier or the
admission controller. It adds an additional check for high-risk actions:
the evidence supporting the action must come from sufficiently independent
sources. If not, the action is abstained (not executed).

Design:
- Low/medium risk: base admission (no additional check).
- High risk: require evidence sufficiency (≥ 2 independent evidence sources
  or a single deterministic check with scope coverage).
- Budget: if the gate cannot acquire sufficient evidence within budget,
  abstain (INDETERMINATE), never accept on insufficient evidence.

This is the runtime integration of the research finding from Cycle 3:
the Strong High-Risk Gate reduces risk-weighted loss by 25.9% in simulation
by abstaining on high-risk tasks where evidence is insufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"  # INDETERMINATE — insufficient evidence


@dataclass(frozen=True)
class GateResult:
    decision: GateDecision
    reason: str
    evidence_sources: int
    risk_class: str


def evaluate_high_risk_gate(
    *,
    risk_class: str,
    evidence_sources: int,
    has_deterministic_check: bool,
    budget_remaining: float,
    min_sources_high_risk: int = 2,
) -> GateResult:
    """Evaluate whether a high-risk action should be admitted.

    Parameters
    ----------
    risk_class : str
        "low", "med", or "high".
    evidence_sources : int
        Number of independent evidence sources supporting the action.
    has_deterministic_check : bool
        Whether a deterministic (scope-covered) check passed.
    budget_remaining : float
        Remaining budget for additional verification.
    min_sources_high_risk : int
        Minimum independent sources required for high-risk acceptance.

    Returns
    -------
    GateResult with decision ACCEPT/REJECT/ABSTAIN.
    """
    if risk_class != "high":
        # Low/medium risk: base admission, no additional gate.
        return GateResult(
            decision=GateDecision.ACCEPT,
            reason="low/medium risk: base admission",
            evidence_sources=evidence_sources,
            risk_class=risk_class,
        )

    # High risk: require sufficient independent evidence.
    if has_deterministic_check and evidence_sources >= 1:
        return GateResult(
            decision=GateDecision.ACCEPT,
            reason="high risk: deterministic check + independent evidence",
            evidence_sources=evidence_sources,
            risk_class=risk_class,
        )

    if evidence_sources >= min_sources_high_risk:
        return GateResult(
            decision=GateDecision.ACCEPT,
            reason="high risk: sufficient independent evidence",
            evidence_sources=evidence_sources,
            risk_class=risk_class,
        )

    if budget_remaining <= 0:
        return GateResult(
            decision=GateDecision.ABSTAIN,
            reason="high risk: insufficient evidence, budget exhausted",
            evidence_sources=evidence_sources,
            risk_class=risk_class,
        )

    # Budget available but evidence insufficient — abstain rather than accept.
    return GateResult(
        decision=GateDecision.ABSTAIN,
        reason="high risk: insufficient independent evidence",
        evidence_sources=evidence_sources,
        risk_class=risk_class,
    )
