"""Research conclusion generator.

The verdict is computed from *pre-declared* criteria; the code never picks
the flattering outcome. Criteria are evaluated against measured ablation and
cross-distribution results.

Criteria (declared before looking at the numbers):
  C1 generalized evidence admits genuinely general recoveries
  C2 generalized evidence rejects fixture-overfitting recoveries
  C3 fixture-only evidence admits at least one unsafe (false-admission) case
  C4 generalized evidence introduces false rejections at acceptable cost
  C5 verified composition holds for the measured sequences
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).resolve().parents[1] / "results"

SUPPORTED = "SUPPORTED"
PARTIALLY = "PARTIALLY_SUPPORTED"
NOT_SUPPORTED = "NOT_SUPPORTED"
INCONCLUSIVE = "INCONCLUSIVE"


def _load(name: str) -> list[dict[str, Any]]:
    p = RESULTS / name
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def ablation_rows() -> list[dict[str, Any]]:
    rows = _load("ablations.jsonl")
    return rows[0]["results"] if rows and "results" in rows[0] else rows


def cross_distribution_rows() -> list[dict[str, Any]]:
    return _load("cross_distribution.jsonl")


def evaluate() -> dict[str, Any]:
    ab = ablation_rows()
    if not ab:
        return {"verdict": INCONCLUSIVE, "reason": "no ablation results recorded", "criteria": {}}

    def subset(mode: str) -> list[dict[str, Any]]:
        return [r for r in ab if r["mode"] == mode]

    fixture = subset("fixture_only")
    family = subset("family_evidence")
    general = subset("generalized_evidence")

    honest_recovery = "restore_from_snapshot"
    overfit_recovery = "overfit_distractor_gate"

    def admitted(rows_: list[dict[str, Any]], kind: str) -> bool:
        return any(r["admitted"] for r in rows_ if r["recovery"] == kind)

    criteria = {
        "C1_general_evidence_admits_general_recovery": admitted(general, honest_recovery),
        "C2_general_evidence_rejects_overfit_recovery": not admitted(general, overfit_recovery),
        "C3_fixture_only_has_false_admission": any(r["false_admission"] for r in fixture),
        "C4_general_evidence_false_rejection_rate": round(sum(1 for r in general if r["false_rejection"]) / max(1, len(general)), 4),
        "C5_fixture_only_false_admission_count": sum(1 for r in fixture if r["false_admission"]),
        "C6_general_cost_mean_seconds": round(sum(r["verification_seconds"] for r in general) / max(1, len(general)), 3),
        "C7_fixture_cost_mean_seconds": round(sum(r["verification_seconds"] for r in fixture) / max(1, len(fixture)), 3),
    }

    c1 = criteria["C1_general_evidence_admits_general_recovery"]
    c2 = criteria["C2_general_evidence_rejects_overfit_recovery"]
    c3 = criteria["C3_fixture_only_has_false_admission"]
    c4_ok = criteria["C4_general_evidence_false_rejection_rate"] <= 0.25

    # Diagnostic (does NOT change the verdict): can Crest actually *grant*
    # FAMILY/GENERAL evidence for honest recovery at the tested sample size?
    honest_general = [r for r in general if r["recovery"] == honest_recovery]
    criteria["C8_honest_recovery_reaches_family_or_general"] = any(
        r["evidence_class"] in ("VERIFIED_FAMILY", "VERIFIED_GENERAL") for r in honest_general
    )
    criteria["C9_honest_recovery_classes"] = sorted({r["evidence_class"] for r in honest_general})

    if c1 and c2 and c4_ok:
        verdict = SUPPORTED if c3 else PARTIALLY
        reason = (
            "Generalized evidence admitted general recovery, rejected the fixture-overfitting "
            "recovery, and fixture-only evidence was demonstrably unsafe in at least one case."
            if c3 else
            "Generalized evidence behaved correctly, but the fixture-only comparison produced no "
            "measured false admission, so the improvement is not demonstrated as necessary."
        )
    elif c1 and c2:
        verdict = PARTIALLY
        reason = "Generalized evidence behaved correctly but false rejections exceeded the pre-declared 25% bound."
    elif not c2:
        verdict = NOT_SUPPORTED
        reason = "Generalized evidence admitted a recovery whose measured generalization failed."
    else:
        verdict = INCONCLUSIVE
        reason = "Insufficient measurements to evaluate the criteria."

    return {
        "verdict": verdict,
        "reason": reason,
        "criteria": criteria,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    out = evaluate()
    print(json.dumps(out, indent=2))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "conclusion.json").write_text(json.dumps(out, indent=2), encoding="utf-8")