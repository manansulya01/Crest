"""Coverage and efficiency metrics (V0.4).

Definitions used throughout Crest research artifacts:

AAC (Autonomous Action Coverage)
    fraction of *eligible* action classes for which autonomous execution is
    currently permitted by the runtime (capability in ADMITTED/ACTIVE with a
    valid receipt).

GAC (Generalized Autonomous Coverage)
    fraction of eligible action classes permitted *and* backed by evidence
    whose class is at least VERIFIED_FAMILY (evidence that survived the
    independent holdout generator and distribution shifts).

AAC - GAC is the autonomy Crest granted without generalized evidence.

EvidenceEfficiency
    GAC delta per verification second spent producing evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class CoverageSnapshot:
    eligible: int
    admitted: set[str] = field(default_factory=set)
    family_backed: set[str] = field(default_factory=set)
    general_backed: set[str] = field(default_factory=set)
    revoked: set[str] = field(default_factory=set)

    @property
    def aac(self) -> float:
        return len(self.admitted) / self.eligible if self.eligible else 0.0

    @property
    def gac(self) -> float:
        return len(self.family_backed) / self.eligible if self.eligible else 0.0

    @property
    def gac_general(self) -> float:
        return len(self.general_backed) / self.eligible if self.eligible else 0.0

    @property
    def fixture_only_autonomy(self) -> set[str]:
        return self.admitted - self.family_backed

    def to_dict(self) -> dict[str, float | int]:
        return {
            "eligible": self.eligible,
            "aac": round(self.aac, 4),
            "gac": round(self.gac, 4),
            "gac_general": round(self.gac_general, 4),
            "admitted": len(self.admitted),
            "family_backed": len(self.family_backed),
            "general_backed": len(self.general_backed),
            "revoked": len(self.revoked),
            "fixture_only_autonomy": len(self.fixture_only_autonomy),
        }


def evidence_efficiency(coverage_gain: float, verification_seconds: float) -> float:
    """Generalized coverage gained per second of verification cost."""
    if verification_seconds <= 0:
        return float("inf")
    return coverage_gain / verification_seconds


def summarize(records: Iterable[dict]) -> dict[str, float]:
    """Aggregate ablation-like records into research summary numbers."""
    rows = list(records)
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "admission_rate": round(sum(1 for r in rows if r.get("admitted")) / len(rows), 4),
        "false_admission_rate": round(sum(1 for r in rows if r.get("false_admission")) / len(rows), 4),
        "false_rejection_rate": round(sum(1 for r in rows if r.get("false_rejection")) / len(rows), 4),
        "mean_evaluation_success": round(sum(r.get("evaluation_success", 0.0) for r in rows) / len(rows), 4),
        "mean_verification_seconds": round(sum(r.get("verification_seconds", 0.0) for r in rows) / len(rows), 4),
    }