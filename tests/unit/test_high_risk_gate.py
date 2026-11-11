"""Tests for the High-Risk Gate runtime integration."""
from __future__ import annotations

import pytest

from crest.high_risk_gate import GateDecision, evaluate_high_risk_gate


def test_low_risk_always_accepts():
    result = evaluate_high_risk_gate(
        risk_class="low", evidence_sources=0,
        has_deterministic_check=False, budget_remaining=1.0,
    )
    assert result.decision == GateDecision.ACCEPT


def test_med_risk_always_accepts():
    result = evaluate_high_risk_gate(
        risk_class="med", evidence_sources=0,
        has_deterministic_check=False, budget_remaining=1.0,
    )
    assert result.decision == GateDecision.ACCEPT


def test_high_risk_with_deterministic_check_accepts():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=1,
        has_deterministic_check=True, budget_remaining=1.0,
    )
    assert result.decision == GateDecision.ACCEPT


def test_high_risk_with_sufficient_sources_accepts():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=2,
        has_deterministic_check=False, budget_remaining=1.0,
    )
    assert result.decision == GateDecision.ACCEPT


def test_high_risk_insufficient_evidence_abstains():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=1,
        has_deterministic_check=False, budget_remaining=1.0,
    )
    assert result.decision == GateDecision.ABSTAIN
    assert "insufficient" in result.reason


def test_high_risk_budget_exhausted_abstains():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=1,
        has_deterministic_check=False, budget_remaining=0.0,
    )
    assert result.decision == GateDecision.ABSTAIN
    assert "budget exhausted" in result.reason


def test_high_risk_zero_sources_abstains():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=0,
        has_deterministic_check=False, budget_remaining=5.0,
    )
    assert result.decision == GateDecision.ABSTAIN


def test_gate_result_fields():
    result = evaluate_high_risk_gate(
        risk_class="high", evidence_sources=2,
        has_deterministic_check=False, budget_remaining=1.0,
    )
    assert result.risk_class == "high"
    assert result.evidence_sources == 2
    assert result.reason != ""