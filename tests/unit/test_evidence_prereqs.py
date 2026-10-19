"""Evidence-class prerequisites: samples, holdout evidence and failures.

Required principle: more samples do not by themselves establish stronger
evidence. A class is granted only when the implemented criteria -- minimum
holdout cases, minimum total cases, zero observed failures, and a Wilson
upper bound below the policy threshold -- are actually satisfied by the
measured data.
"""
from __future__ import annotations

from crest.evidence import EvidenceClass, EvidenceStatus
from crest.generalization import GeneralizationVerifier
from crest.recovery import RecoveryProgram
from experiments.generalization import ablations, config


def test_family_class_requires_samples_and_the_wilson_bound():
    cfg = config.canonical()
    n = cfg.samples
    policy = ablations._policy_for_mode("family_evidence", n)

    # Canonical sample size with zero failures: the bound is below 0.20.
    cls, status, diag = policy.classify(
        verification_cases=n,
        verification_failures=0,
        holdout_cases=n,
        holdout_failures=0,
    )
    assert cls is EvidenceClass.VERIFIED_FAMILY
    assert status is EvidenceStatus.OK
    assert diag["failure_ucb_holdout"] <= cfg.maximum_failure_upper_bound

    # One holdout case short of the scaled minimum: not enough evidence.
    cls2, status2, _ = policy.classify(
        verification_cases=n,
        verification_failures=0,
        holdout_cases=n - 1,
        holdout_failures=0,
    )
    assert cls2 is EvidenceClass.VERIFIED_FIXTURE
    assert status2 is EvidenceStatus.WEAK


def test_reduced_sample_count_cannot_reach_family():
    """At half the canonical sample count the same zero-failure record stays
    fixture-grade because the statistical bound is not met."""
    cfg = config.canonical()
    n = cfg.samples // 2
    policy = ablations._policy_for_mode("family_evidence", n)
    cls, status, diag = policy.classify(
        verification_cases=n,
        verification_failures=0,
        holdout_cases=n,
        holdout_failures=0,
    )
    assert cls is EvidenceClass.VERIFIED_FIXTURE
    assert status is EvidenceStatus.WEAK
    assert diag["failure_ucb_holdout"] > cfg.maximum_failure_upper_bound


def test_sample_count_alone_never_promotes_with_observed_failures():
    cfg = config.canonical()
    policy = ablations._policy_for_mode("generalized_evidence", cfg.samples)
    cls, _, diag = policy.classify(
        verification_cases=cfg.samples,
        verification_failures=0,
        holdout_cases=cfg.samples,
        holdout_failures=1,
        shift_distributions=3,
        shift_failures=0,
        adversarial_checked=True,
        adversarial_failures=0,
    )
    assert cls is EvidenceClass.UNVERIFIED
    assert diag["failure_observed"] is True


def test_general_class_requires_shift_and_adversarial_evidence():
    cfg = config.canonical()
    policy = ablations._policy_for_mode("generalized_evidence", cfg.samples)
    base = dict(
        verification_cases=cfg.samples,
        verification_failures=0,
        holdout_cases=cfg.samples,
        holdout_failures=0,
        shift_failures=0,
    )
    assert (
        policy.classify(
            **base,
            shift_distributions=3,
            adversarial_checked=True,
            adversarial_failures=0,
        )[0]
        is EvidenceClass.VERIFIED_GENERAL
    )
    # Two shift distributions: below the minimum of three.
    assert (
        policy.classify(
            **base,
            shift_distributions=2,
            adversarial_checked=True,
            adversarial_failures=0,
        )[0]
        is EvidenceClass.VERIFIED_FAMILY
    )
    # No adversarial shift measured: the general prerequisite is unmet.
    assert (
        policy.classify(**base, shift_distributions=3, adversarial_checked=False)[0]
        is EvidenceClass.VERIFIED_FAMILY
    )


def test_fixture_only_evidence_is_capped_and_reports_no_holdout():
    row = ablations.evaluate_mode(
        "fixture_only", "delete_file", "restore_from_snapshot", "filesystem.single_file", n=2
    )
    assert row["evidence_class"] in ("VERIFIED_FIXTURE", "UNVERIFIED")
    assert row["holdout_cases"] == 0
    assert row["holdout_passed"] == 0


def test_canonical_family_row_reproduces_verified_family_class():
    """Integration anchor: with the canonical configuration, the honest
    recovery under family evidence classifies VERIFIED_FAMILY -- matching the
    committed tables' claim (deterministic fixed seeds; ~7 s)."""
    cfg = config.canonical()
    evidence = GeneralizationVerifier(
        policy=ablations._policy_for_mode("family_evidence", cfg.samples),
        verification_cases=cfg.samples,
        holdout_cases=cfg.samples,
        shift_cases=max(2, cfg.samples // 2),
    ).verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",),
    )
    assert evidence.evidence_class is EvidenceClass.VERIFIED_FAMILY
    assert evidence.holdout_failed == 0
    assert evidence.fixtures_passed > 0
    assert evidence.holdout_passed > 0
