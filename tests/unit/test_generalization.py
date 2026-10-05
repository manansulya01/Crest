"""Generalized evidence: classification, holdout, no silent upgrades."""
from __future__ import annotations

from crest.evidence import EvidenceClass, failure_upper_bound
import crest.faults  # noqa: F401
from crest.generalization import GeneralizationVerifier, _classify
from crest.recovery import RecoveryProgram


def test_failure_upper_bound_bounds_observed_rate():
    # zero failures in 100 -> nonzero upper bound, documented as weak sample
    assert 0 < failure_upper_bound(0, 100) < 1
    assert failure_upper_bound(50, 100) > 0.4
    assert failure_upper_bound(0, 0) == 1.0


def test_perfect_recovery_family_classifies_family():
    ev = GeneralizationVerifier().verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class is EvidenceClass.VERIFIED_FAMILY
    assert ev.holdout_failed == 0
    assert ev.evidence_class is not EvidenceClass.VERIFIED_GENERAL


def test_perfect_recovery_cross_family_classifies_general():
    ev = GeneralizationVerifier().verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file", "filesystem.directory_tree"),
    )
    assert ev.evidence_class is EvidenceClass.VERIFIED_GENERAL
    assert ev.holdout_failed == 0
    assert ev.fixtures_failed == 0


def test_overfit_recovery_cannot_upgrade():
    # single_file fixtures name distractors differently from trial-time
    # distractors, so the overfit gate no-ops and every fixture fails.
    ev = GeneralizationVerifier().verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="overfit_distractor_gate"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class in (EvidenceClass.UNVERIFIED, EvidenceClass.VERIFIED_FIXTURE)
    assert ev.holdout_failed == ev.holdout_fixtures


def test_unknown_handler_yields_unverified():
    ev = GeneralizationVerifier().verify(
        action_class="delete_file",
        recovery=RecoveryProgram(kind="does_not_exist"),
        family_ids=("filesystem.single_file",),
    )
    assert ev.evidence_class is EvidenceClass.UNVERIFIED
    assert ev.fixtures_passed == 0


def test_classify_requires_holdout_and_cross_family():
    assert _classify(holdout_total=0, holdout_failures=0, actual_failures=0, total=4, cross_family=True) is EvidenceClass.VERIFIED_FIXTURE
    assert _classify(holdout_total=8, holdout_failures=0, actual_failures=0, total=16, cross_family=True) is EvidenceClass.VERIFIED_GENERAL
    assert _classify(holdout_total=8, holdout_failures=1, actual_failures=1, total=16, cross_family=True) is not EvidenceClass.VERIFIED_GENERAL
    assert _classify(holdout_total=4, holdout_failures=0, actual_failures=0, total=8, cross_family=False) is EvidenceClass.VERIFIED_FAMILY
    assert _classify(holdout_total=4, holdout_failures=0, actual_failures=1, total=8, cross_family=False) is EvidenceClass.VERIFIED_FIXTURE


def test_evidence_is_not_upgraded_after_creation():
    ev = GeneralizationVerifier().verify(action_class="delete_file", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.single_file",))
    import dataclasses

    assert dataclasses.replace(ev, evidence_class=EvidenceClass.VERIFIED_GENERAL).evidence_class is EvidenceClass.VERIFIED_GENERAL
    # but the ORIGINAL object — the basis for admission — stays family-level
    assert ev.evidence_class is EvidenceClass.VERIFIED_FAMILY
