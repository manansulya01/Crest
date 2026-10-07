"""Adversarial learner attacks against the verifier.

Every attack below must end in UNVERIFIED or failure to admit. None of them
may be granted authority.
"""
from __future__ import annotations

import crest.faults  # noqa: F401  (registers attack recovery kinds)
from crest.generalization import GeneralizationVerifier
from crest.evidence import EvidenceClass
from crest.recovery import RecoveryProgram, register
from crest.workspace import Workspace


def _verify(kind: str, n: int = 6) -> EvidenceClass:
    gv = GeneralizationVerifier(verification_cases=n, holdout_cases=n, shift_cases=3)
    ev = gv.verify(action_class="delete_file", recovery=RecoveryProgram(kind=kind), family_ids=("filesystem.single_file",))
    return ev.evidence_class


def test_noop_recovery_never_certified():
    assert _verify("noop") is EvidenceClass.UNVERIFIED


def test_fixture_keyed_recovery_never_certified():
    # works on the training generator (distractor artifacts present) but
    # not on independent holdouts
    assert _verify("overfit_distractor_gate") is EvidenceClass.UNVERIFIED


def test_name_keyed_recovery_fails():
    @register("gaming_name_key")
    def _gaming(ws: Workspace, ctx) -> None:
        # "succeeds" only when it recognizes the fixture's distractor files
        if any("distractor" in name for name in _list_names(ws)):
            for rel, data in ctx.pre_action_snapshot.items():
                ws.write(rel, data)
        # else: do nothing -> observed failure on holdout

    assert _verify("gaming_name_key") is EvidenceClass.UNVERIFIED


def test_wrong_target_recovery_fails():
    @register("gaming_wrong_target")
    def _gaming(ws: Workspace, ctx) -> None:
        for rel, data in ctx.pre_action_snapshot.items():
            ws.write("wrong-" + rel, data)  # restore into wrong paths

    assert _verify("gaming_wrong_target") is EvidenceClass.UNVERIFIED


def test_honest_recovery_can_be_certified():
    # sanity: the honest program still passes independence checks
    assert _verify("restore_from_snapshot") in (EvidenceClass.VERIFIED_GENERAL, EvidenceClass.VERIFIED_FAMILY, EvidenceClass.VERIFIED_FIXTURE)


def _list_names(ws: Workspace):
    for p in ws.root.rglob("*"):
        yield p.name
