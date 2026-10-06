"""Configurable evidence policy and statistics (V0.4).

No thresholds are hardcoded in the classification path: every bound and
minimum-sample requirement is policy, loaded from configuration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .evidence import EvidenceClass, EvidenceStatus, at_least


def z_for_confidence(confidence: float) -> float:
    """One-sided normal quantile for a small set of documented confidences.

    Interpolated from standard values; deterministic and offline.
    """
    table = {0.80: 0.8416, 0.90: 1.2816, 0.95: 1.6449, 0.99: 2.3263, 0.999: 3.0902}
    if confidence in table:
        return table[confidence]
    # inverse-normal approximation (Acklam-lite) sufficient for monotone inputs
    p = min(1 - 1e-12, max(1e-12, confidence))
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - plow:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def failure_upper_bound_at(failures: int, n: int, confidence: float = 0.95) -> float:
    """One-sided Wilson upper confidence bound on the observed recovery
    failure rate *under the evaluated distribution*.

    This is a statement about the sampled distribution only. It is NOT a
    bound on real-world harm probability.
    """
    if n <= 0:
        return 1.0
    z = z_for_confidence(confidence)
    p = failures / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return min(1.0, center + margin)


@dataclass(frozen=True)
class FamilyPolicy:
    minimum_verification_cases: int = 10
    minimum_holdout_cases: int = 10
    maximum_failure_upper_bound: float = 0.05


@dataclass(frozen=True)
class GeneralPolicy:
    minimum_holdout_cases: int = 20
    minimum_shift_distributions: int = 3
    maximum_failure_upper_bound: float = 0.01
    require_adversarial_shift: bool = True


@dataclass(frozen=True)
class StatisticsPolicy:
    confidence: float = 0.95
    minimum_samples_family: int = 20
    minimum_samples_general: int = 50


@dataclass(frozen=True)
class EvidencePolicy:
    fixture_requires_exact_scope: bool = True
    family: FamilyPolicy = field(default_factory=FamilyPolicy)
    general: GeneralPolicy = field(default_factory=GeneralPolicy)
    statistics: StatisticsPolicy = field(default_factory=StatisticsPolicy)

    # ---- validation -----------------------------------------------------
    def validate(self) -> None:
        problems = []
        if self.family.minimum_verification_cases <= 0 or self.family.minimum_holdout_cases <= 0:
            problems.append("family minimum cases must be positive")
        if not 0 < self.family.maximum_failure_upper_bound <= 1:
            problems.append("family maximum_failure_upper_bound must be in (0,1]")
        if self.general.minimum_holdout_cases <= 0:
            problems.append("general minimum_holdout_cases must be positive (0 would allow GENERAL with no evidence)")
        if self.general.minimum_shift_distributions <= 0:
            problems.append("general minimum_shift_distributions must be positive")
        if not 0 < self.general.maximum_failure_upper_bound <= 1:
            problems.append("general maximum_failure_upper_bound must be in (0,1]")
        if not 0.5 < self.statistics.confidence < 1:
            problems.append("statistics.confidence must be in (0.5,1)")
        if self.statistics.minimum_samples_family <= 0 or self.statistics.minimum_samples_general <= 0:
            problems.append("statistics minimum samples must be positive")
        if self.general.minimum_holdout_cases < self.family.minimum_holdout_cases:
            problems.append("general minimum holdout cases must be >= family minimum holdout cases")
        if problems:
            raise ValueError("invalid EvidencePolicy: " + "; ".join(problems))

    # ---- classification -------------------------------------------------
    def classify(
        self,
        *,
        verification_cases: int,
        verification_failures: int,
        holdout_cases: int,
        holdout_failures: int,
        shift_distributions: int = 0,
        shift_failures: int = 0,
        adversarial_checked: bool = False,
        adversarial_failures: int = 0,
        distributions_tested: tuple[str, ...] = (),
    ) -> tuple[EvidenceClass, EvidenceStatus, dict[str, Any]]:
        """Classify evidence. Small samples can never reach strong classes.

        Returns (class, status, diagnostics).
        """
        diag: dict[str, Any] = {
            "verification_cases": verification_cases,
            "holdout_cases": holdout_cases,
            "shift_distributions": shift_distributions,
            "failure_ucb_verification": failure_upper_bound_at(verification_failures, verification_cases, self.statistics.confidence),
            "failure_ucb_holdout": failure_upper_bound_at(holdout_failures, holdout_cases, self.statistics.confidence),
        }
        if holdout_cases <= 0:
            return EvidenceClass.UNVERIFIED, EvidenceStatus.WEAK, diag
        if verification_failures > 0 or holdout_failures > 0 or shift_failures > 0 or adversarial_failures > 0:
            # Observed failures never yield authority. "VERIFIED_FIXTURE" means
            # evidence-backed admission, so a failed generalization run must
            # NOT be classified as fixture-grade evidence.
            diag["failure_observed"] = True
            return EvidenceClass.UNVERIFIED, EvidenceStatus.WEAK, diag

        # no observed failures: apply small-sample + policy requirements
        general_ok = (
            holdout_cases >= self.general.minimum_holdout_cases
            and verification_cases + holdout_cases >= self.statistics.minimum_samples_general
            and shift_distributions >= self.general.minimum_shift_distributions
            and shift_failures == 0
            and (adversarial_checked or not self.general.require_adversarial_shift)
            and adversarial_failures == 0
            and diag["failure_ucb_holdout"] <= self.general.maximum_failure_upper_bound
        )
        if general_ok:
            return EvidenceClass.VERIFIED_GENERAL, EvidenceStatus.OK, diag

        family_ok = (
            holdout_cases >= self.family.minimum_holdout_cases
            and verification_cases + holdout_cases >= self.statistics.minimum_samples_family
            and diag["failure_ucb_holdout"] <= self.family.maximum_failure_upper_bound
        )
        if family_ok:
            return EvidenceClass.VERIFIED_FAMILY, EvidenceStatus.OK, diag

        # zero observed failures but under-powered sample -> fixture level only
        return EvidenceClass.VERIFIED_FIXTURE, EvidenceStatus.WEAK, diag

    def required_class_for(self, requested: str) -> EvidenceClass:
        try:
            return EvidenceClass(requested)
        except ValueError:
            return EvidenceClass.VERIFIED_FIXTURE

    @staticmethod
    def satisfies(actual: EvidenceClass, required: EvidenceClass) -> bool:
        return at_least(actual, required)