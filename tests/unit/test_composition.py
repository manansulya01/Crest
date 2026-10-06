"""Composition tests: recoverability does not automatically compose."""
from __future__ import annotations

from crest.composition import CompositionStatus, Step, verify_composition
from crest.recovery import RecoveryProgram

SNAPSHOT = RecoveryProgram(kind="restore_from_snapshot")
PARTIAL = RecoveryProgram(kind="restore_first_only")


def test_single_step_composition_is_verified():
    res = verify_composition(steps=(Step("delete_file"),), recovery=SNAPSHOT, cases=6)
    assert res.status is CompositionStatus.VERIFIED_COMPOSITION
    assert res.success_rate == 1.0


def test_modify_then_move_sequence_recovers_with_full_snapshot_recovery():
    res = verify_composition(steps=(Step("modify_file"), Step("move_file")), recovery=SNAPSHOT, cases=6)
    assert res.status is CompositionStatus.VERIFIED_COMPOSITION
    assert res.success_rate == 1.0


def test_composition_is_not_assumed_for_partial_recovery():
    """Component steps pass individually; the sequence may still fail."""
    res = verify_composition(steps=(Step("modify_file"), Step("delete_file")), recovery=PARTIAL, cases=6)
    assert res.component_success.get("modify_file", 0) >= 0.0
    assert res.status in (CompositionStatus.VERIFIED_COMPOSITION, CompositionStatus.UNVERIFIED_COMPOSITION)


def test_composition_with_no_recovery_is_unverified():
    res = verify_composition(steps=(Step("delete_file"),), recovery=RecoveryProgram(kind="noop_fault"), cases=4)
    assert res.status is CompositionStatus.UNVERIFIED_COMPOSITION
    assert res.success_rate == 0.0
    assert res.component_success["delete_file"] == 0.0