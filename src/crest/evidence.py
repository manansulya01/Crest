"""Evidence model (V0.3).

Evidence is content-sensitive security input: its *class* is monotonicity-
critical invariants. A stronger class may only be assigned from evidence;
never synthesized from weaker evidence.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .hashing import digest_of


class EvidenceClass(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PROPOSED = "PROPOSED"
    VERIFIED_FIXTURE = "VERIFIED_FIXTURE"
    VERIFIED_FAMILY = "VERIFIED_FAMILY"
    VERIFIED_GENERAL = "VERIFIED_GENERAL"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


_RANK = {
    EvidenceClass.UNVERIFIED: 0,
    EvidenceClass.PROPOSED: 1,
    EvidenceClass.VERIFIED_FIXTURE: 2,
    EvidenceClass.VERIFIED_FAMILY: 3,
    EvidenceClass.VERIFIED_GENERAL: 4,
    EvidenceClass.EXPIRED: 0,
    EvidenceClass.REVOKED: 0,
}


def at_least(actual: EvidenceClass, required: EvidenceClass) -> bool:
    return _RANK[actual] >= _RANK[required]


class EvidenceStatus(str, Enum):
    OK = "OK"
    WEAK = "WEAK"
    FAILED = "FAILED"


def failure_upper_bound(failures: int, n: int, z: float = 1.645) -> float:
    """One-sided Wilson upper bound on the failure rate (95% w/ z=1.645).

    Conservative: zero failures still yields bound > 0.
    """
    if n <= 0:
        return 1.0
    p = failures / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return min(1.0, center + margin)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    action_class: str
    target_scope: str
    environment_family: str
    recovery_program_digest: str
    verification_version: str
    verifier_version: str
    test_suite_digest: str

    fixtures_tested: int
    fixtures_passed: int
    fixtures_failed: int

    holdout_fixtures: int
    holdout_passed: int
    holdout_failed: int

    fault_models_tested: tuple[str, ...] = ()
    recovery_success_rate: float = 0.0
    confidence_level: float = 0.0
    upper_bound_exposure: float = 1.0
    propagation_bound: int = 0
    recovery_time_bound_ms: float = 0.0
    distribution_shift_failures: int = 0

    created_at: str = ""
    expires_at: str = ""
    evidence_class: EvidenceClass = EvidenceClass.UNVERIFIED
    status: EvidenceStatus = EvidenceStatus.WEAK
    sampling_method: str = "fixture-generated"
    population_scope: str = "single environment family"

    def digest(self) -> str:
        return digest_of({**self.__dict__, "evidence_class": self.evidence_class.value, "status": self.status.value})
