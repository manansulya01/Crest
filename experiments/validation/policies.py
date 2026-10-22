"""Deployable admission-policy baselines for independent validation.

Only this module decides whether a candidate is admitted. It does not import
the validation generator, evaluation seeds, evaluation labels, or the oracle.
"""
from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from crest.distributions import Distribution
from crest.env_family import FAMILIES
from crest.evidence import EvidenceClass
from crest.generalization import GeneralizationVerifier, _trial
from crest.policy import EvidencePolicy
from crest.recovery import RecoveryProgram, get_handler

N_CASES = 12
SHIFT_CASES = 6
EXPERIMENTAL_FAILURE_BOUND = 0.20


@dataclass(frozen=True)
class Candidate:
    action_class: str
    family_id: str
    recovery_kind: str

    @property
    def candidate_id(self) -> str:
        return f"{self.action_class}|{self.family_id}|{self.recovery_kind}"


@dataclass(frozen=True)
class PolicyResult:
    admitted: bool
    evidence_class: str
    reason: str
    verification_seconds: float
    details: dict[str, Any]


class Policy(Protocol):
    name: str
    deployable: bool

    def decide(self, candidate: Candidate) -> PolicyResult:
        ...


def _scaled_policy(n: int, *, family_only: bool) -> EvidencePolicy:
    base = EvidencePolicy()
    family = dataclasses.replace(
        base.family,
        minimum_verification_cases=n,
        minimum_holdout_cases=n,
        maximum_failure_upper_bound=EXPERIMENTAL_FAILURE_BOUND,
    )
    general = dataclasses.replace(
        base.general,
        minimum_holdout_cases=n,
        minimum_shift_distributions=10**6 if family_only else 3,
        maximum_failure_upper_bound=EXPERIMENTAL_FAILURE_BOUND,
    )
    stats = dataclasses.replace(
        base.statistics,
        minimum_samples_family=2 * n,
        minimum_samples_general=2 * n,
    )
    return dataclasses.replace(
        base, family=family, general=general, statistics=stats
    )


class AlwaysDeny:
    name = "deny_all"
    deployable = True

    def decide(self, candidate: Candidate) -> PolicyResult:
        return PolicyResult(False, "UNVERIFIED", "baseline: deny", 0.0, {})


class AlwaysAdmit:
    name = "admit_all"
    deployable = True

    def decide(self, candidate: Candidate) -> PolicyResult:
        return PolicyResult(True, "UNVERIFIED", "baseline: admit", 0.0, {})


class FixtureOnly:
    name = "fixture_only"
    deployable = True

    def __init__(self, n: int = N_CASES, seed_base: int = 1000):
        self.n = n
        self.seed_base = seed_base

    def decide(self, candidate: Candidate) -> PolicyResult:
        started = time.perf_counter()
        if get_handler(candidate.recovery_kind) is None:
            return PolicyResult(
                False,
                "UNVERIFIED",
                "no executable recovery handler",
                round(time.perf_counter() - started, 6),
                {"passed": 0, "n": self.n},
            )
        passed = 0
        for index in range(self.n):
            if _trial(
                candidate.action_class,
                FAMILIES[candidate.family_id],
                RecoveryProgram(kind=candidate.recovery_kind),
                self.seed_base + index,
                Distribution.IN_DISTRIBUTION,
                False,
            ):
                passed += 1
        admitted = passed == self.n
        return PolicyResult(
            admitted,
            "VERIFIED_FIXTURE" if admitted else "UNVERIFIED",
            "fixture-only all-pass rule" if admitted else "fixture trial failed",
            round(time.perf_counter() - started, 6),
            {"passed": passed, "n": self.n},
        )


class FamilyEvidence:
    name = "family_only"
    deployable = True

    def __init__(self, n: int = N_CASES):
        self.n = n

    def decide(self, candidate: Candidate) -> PolicyResult:
        started = time.perf_counter()
        policy = _scaled_policy(self.n, family_only=True)
        verifier = GeneralizationVerifier(
            policy=policy,
            verification_cases=self.n,
            holdout_cases=self.n,
            shift_cases=0,
            verification_seed_base=1000,
            holdout_seed_base=90000,
            shift_seed_base=50000,
        )
        evidence = verifier.verify(
            action_class=candidate.action_class,
            recovery=RecoveryProgram(kind=candidate.recovery_kind),
            family_ids=(candidate.family_id,),
        )
        admitted = evidence.evidence_class in (
            EvidenceClass.VERIFIED_FAMILY,
            EvidenceClass.VERIFIED_GENERAL,
        )
        return PolicyResult(
            admitted,
            evidence.evidence_class.value,
            f"family evidence: {evidence.status.value}",
            round(time.perf_counter() - started, 6),
            dict(verifier.measurement()),
        )


class GeneralizedEvidence:
    name = "generalized"
    deployable = True

    def __init__(self, n: int = N_CASES, shift_cases: int = SHIFT_CASES):
        self.n = n
        self.shift_cases = shift_cases

    def decide(self, candidate: Candidate) -> PolicyResult:
        started = time.perf_counter()
        policy = _scaled_policy(self.n, family_only=False)
        verifier = GeneralizationVerifier(
            policy=policy,
            verification_cases=self.n,
            holdout_cases=self.n,
            shift_cases=self.shift_cases,
            verification_seed_base=1000,
            holdout_seed_base=90000,
            shift_seed_base=50000,
        )
        evidence = verifier.verify(
            action_class=candidate.action_class,
            recovery=RecoveryProgram(kind=candidate.recovery_kind),
            family_ids=(candidate.family_id,),
        )
        admitted = evidence.evidence_class is EvidenceClass.VERIFIED_GENERAL
        return PolicyResult(
            admitted,
            evidence.evidence_class.value,
            f"generalized evidence: {evidence.status.value}",
            round(time.perf_counter() - started, 6),
            dict(verifier.measurement()),
        )


class Oracle:
    """Upper-bound diagnostic. Never deployable; labels are external."""

    name = "oracle"
    deployable = False

    def __init__(self, labels: Mapping[str, bool]):
        self.labels = dict(labels)

    def decide(self, candidate: Candidate) -> PolicyResult:
        reliable = bool(self.labels.get(candidate.candidate_id, False))
        return PolicyResult(
            reliable,
            "ORACLE_RELIABLE" if reliable else "ORACLE_UNRELIABLE",
            "diagnostic: evaluation label",
            0.0,
            {},
        )


def deployable_policies(n: int = N_CASES) -> tuple[Policy, ...]:
    return (
        AlwaysDeny(),
        AlwaysAdmit(),
        FixtureOnly(n=n),
        FamilyEvidence(n=n),
        GeneralizedEvidence(n=n),
    )
