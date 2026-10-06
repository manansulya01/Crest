"""Generalized evidence: policy-driven classification, holdout, small samples."""
from __future__ import annotations

import dataclasses

import pytest

import crest.faults  # noqa: F401
from crest.evidence import EvidenceClass, EvidenceStatus, failure_upper_bound
from crest.generalization import GeneralizationVerifier
from crest.policy import EvidencePolicy, failure_upper_bound_at, z_for_confidence
from crest.recovery import RecoveryProgram


def test_failure_upper_bound_bounds_observed_rate():
    assert 0 < failure_upper_bound(0, 100) < 1
    assert failure_upper_bound(50, 100) > 0.4
    assert failure_upper_bound(0, 0) == 1.0


def test_upper_bound_is_monotone_in_failures_and_n():
    assert failure_upper_bound_at(0, 10) > failure_upper_bound_at(0, 100)
    assert failure_upper_bound_at(1, 10) > failure_upper_bound_at(0, 10)


def test_z_for_confidence_known_values():
    assert z_for_confidence(0.95) == pytest.approx(1.6449, abs=1e-4)
    assert z_for_confidence(0.99) == pytest.approx(2.3263, abs=1e-4)
    assert z_for_confidence(0.999) == pytest.approx(3.0902, abs=1e-4)
    assert z_for_confidence(0.975) > z_for_confidence(0.95)


def test_perfect_recovery_reaches_general_evidence():
    # 30 verification + 30 independent-holdout cases are needed before the
    # Wilson bound on a zero-failure run drops below the general threshold.
    ev = GeneralizationVerifier(
        policy=EvidencePolicy(
            general=dataclasses.replace(EvidencePolicy().general, minimum_holdout_cases=20, minimum_shift_distributions=3, maximum_failure_upper_bound=0.15),
            family=dataclasses.replace(EvidencePolicy().family, minimum_holdout_cases=20, maximum_failure_upper_bound=0.15),
            statistics=dataclasses.replace(EvidencePolicy().statistics, minimum_samples_general=50, minimum_samples_family=50),
        ),
        verification_cases=30,
        holdout_cases=30,
        shift_cases=10,
    ).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class is EvidenceClass.VERIFIED_GENERAL
    assert ev.holdout_failed == 0
    assert ev.distribution_shift_failures == 0


def test_single_family_cannot_reach_general_without_shift_evidence():
    ev = GeneralizationVerifier(verification_cases=4, holdout_cases=4, shift_cases=2).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",),
    )
    # shifts were measured, but the sample is far below the general minimum
    assert ev.evidence_class in (EvidenceClass.VERIFIED_FIXTURE, EvidenceClass.VERIFIED_FAMILY)


def test_small_sample_never_reaches_strong_class():
    policy = EvidencePolicy()
    cls, status, diag = policy.classify(verification_cases=1, verification_failures=0, holdout_cases=1, holdout_failures=0, shift_distributions=3, shift_failures=0, adversarial_checked=True, adversarial_failures=0)
    assert cls is EvidenceClass.VERIFIED_FIXTURE
    assert status is EvidenceStatus.WEAK


def test_observed_failure_never_yields_authority():
    """Failures anywhere in verification/holdout/shift => UNVERIFIED.

    V0.3 classified failing runs as VERIFIED_FIXTURE, which kept them
    admissible at min_evidence_class=FIXTURE. That conflation is fixed here.
    """
    policy = EvidencePolicy()
    cls, status, diag = policy.classify(verification_cases=100, verification_failures=0, holdout_cases=100, holdout_failures=1, shift_distributions=3, shift_failures=0, adversarial_checked=True)
    assert cls is EvidenceClass.UNVERIFIED
    assert status is EvidenceStatus.WEAK
    assert diag["failure_observed"] is True

    cls2, _, _ = policy.classify(verification_cases=100, verification_failures=0, holdout_cases=100, holdout_failures=0, shift_distributions=3, shift_failures=2, adversarial_checked=True, adversarial_failures=0)
    assert cls2 is EvidenceClass.UNVERIFIED


def test_zero_holdout_is_unverified():
    policy = EvidencePolicy()
    cls, _, _ = policy.classify(verification_cases=50, verification_failures=0, holdout_cases=0, holdout_failures=0)
    assert cls is EvidenceClass.UNVERIFIED


def test_adversarial_shift_requirement_can_block_general():
    policy = EvidencePolicy(
        general=dataclasses.replace(EvidencePolicy().general, minimum_holdout_cases=10, minimum_shift_distributions=1, maximum_failure_upper_bound=1.0, require_adversarial_shift=True),
        statistics=dataclasses.replace(EvidencePolicy().statistics, minimum_samples_general=5),
    )
    cls, _, _ = policy.classify(verification_cases=10, verification_failures=0, holdout_cases=10, holdout_failures=0, shift_distributions=1, shift_failures=0, adversarial_checked=False)
    assert cls is not EvidenceClass.VERIFIED_GENERAL
    cls2, _, _ = policy.classify(verification_cases=10, verification_failures=0, holdout_cases=10, holdout_failures=0, shift_distributions=1, shift_failures=0, adversarial_checked=True, adversarial_failures=0)
    assert cls2 is EvidenceClass.VERIFIED_GENERAL


def test_overfit_recovery_cannot_upgrade_on_holdout():
    ev = GeneralizationVerifier(verification_cases=4, holdout_cases=6, shift_cases=3).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="overfit_distractor_gate"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class in (EvidenceClass.UNVERIFIED, EvidenceClass.VERIFIED_FIXTURE)


def test_overfit_on_tree_family_passes_in_distribution_but_fails_holdout():
    """The V0.3 false-confidence case: in-distribution success, holdout failure."""
    ev = GeneralizationVerifier(verification_cases=4, holdout_cases=6, shift_cases=3).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="overfit_distractor_gate"),
        family_ids=("filesystem.directory_tree",),
    )
    assert ev.fixtures_passed > 0          # training/verification fixtures pass
    assert ev.holdout_failed > 0            # independent generator exposes it
    assert ev.evidence_class is EvidenceClass.UNVERIFIED


def test_unknown_handler_yields_unverified():
    ev = GeneralizationVerifier(verification_cases=2, holdout_cases=2, shift_cases=2).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="does_not_exist"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class is EvidenceClass.UNVERIFIED
    assert ev.fixtures_passed == 0


def test_policy_validation_rejects_illegal_combinations():
    with pytest.raises(ValueError):
        EvidencePolicy(general=dataclasses.replace(EvidencePolicy().general, minimum_holdout_cases=0)).validate()
    with pytest.raises(ValueError):
        EvidencePolicy(statistics=dataclasses.replace(EvidencePolicy().statistics, confidence=0.2)).validate()


def test_evidence_class_not_mutable_after_creation():
    ev = GeneralizationVerifier(verification_cases=2, holdout_cases=2, shift_cases=1).verify(
        action_class="delete_file", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.single_file",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.evidence_class = EvidenceClass.VERIFIED_GENERAL  # type: ignore[misc]