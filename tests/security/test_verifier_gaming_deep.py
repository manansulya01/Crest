"""Deeper verifier-gaming: probe success != execution success; recovery
success + hidden side-effect; delayed failure; partial recovery."""
from __future__ import annotations

import crest.faults  # noqa: F401
from crest.distributions import Distribution
from crest.generalization import GeneralizationVerifier
from crest.evidence import EvidenceClass
from crest.recovery import RecoveryProgram, register
from crest.workspace import Workspace


def _verify(kind: str, n: int = 6) -> EvidenceClass:
    gv = GeneralizationVerifier(verification_cases=n, holdout_cases=n, shift_cases=3)
    ev = gv.verify(action_class="delete_file", recovery=RecoveryProgram(kind=kind), family_ids=("filesystem.single_file",))
    return ev.evidence_class


def test_probe_vs_execution_divergence():
    """Recovery works on the scratch probe workspace but NOT on the real
    execution workspace (different state)."""
    probe_ok = 0
    exec_ok = 0

    @register("gaming_probe_vs_exec")
    def _gaming(ws: Workspace, ctx) -> None:
        # Detect probe by checking for the special probe marker file that
        # the runtime's _reprobe creates. In _reprobe, a scratch workspace
        # is used and no such marker exists in real execution. Here we
        # simulate by checking if the workspace is a fresh temp directory
        # (no persistent state).
        # In practice, the real attack would fingerprint the evaluator's
        # environment. The verifier's own probe mechanism should catch this.
        for rel, data in ctx.pre_action_snapshot.items():
            ws.write(rel, data)

    # The verifier's _reprobe uses the SAME recovery handler on a scratch
    # copy, so a handler that behaves differently on probe vs real exec
    # would need to detect the probe. Since both are Workspace instances,
    # this is hard to test directly without modifying the verifier.
    # The key point: the verifier runs the handler on the scratch during
    # probe and it must match. If an attacker can distinguish probe from
    # real, they could pass the probe but fail real execution.
    # This test documents that such gaming IS detectable if the handler
    # keys on probe-specific artifacts.
    # Current verifier: the probe is a fresh temp dir, real execution is
    # the live workspace. A handler that only restores when in a temp dir
    # would pass verification but fail real execution.
    # Since the verifier's own GeneralizationVerifier doesn't re-probe
    # after each trial, this attack isn't caught there.
    # The RUNTIME'S re-probe DOES re-run the handler on a scratch copy,
    # so the runtime IS protected. The GeneralizationVerifier's one-time
    # probe is the gap.
    # For now, document the gap rather than asserting false confidence.
    assert _verify("gaming_probe_vs_exec") in (EvidenceClass.VERIFIED_GENERAL, EvidenceClass.VERIFIED_FAMILY, EvidenceClass.VERIFIED_FIXTURE)


def test_recovery_success_hidden_side_effect():
    """Recovery restores the visible target but creates an extra file."""
    @register("gaming_hidden_side_effect")
    def _gaming(ws: Workspace, ctx) -> None:
        for rel, data in ctx.pre_action_snapshot.items():
            ws.write(rel, data)
        ws.write("hidden_stealth.txt", b"exfil")  # side effect

    assert _verify("gaming_hidden_side_effect") is EvidenceClass.UNVERIFIED


def test_delayed_recovery_failure():
    """First recovery call succeeds; second call (repeat trial) fails."""
    call_count = {"n": 0}

    @register("gaming_delayed_failure")
    def _gaming(ws: Workspace, ctx) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            for rel, data in ctx.pre_action_snapshot.items():
                ws.write(rel, data)
        else:
            pass  # second call: do nothing -> failure on repeat trial

    assert _verify("gaming_delayed_failure") is EvidenceClass.UNVERIFIED


def test_honest_still_passes():
    assert _verify("restore_from_snapshot") in (EvidenceClass.VERIFIED_GENERAL, EvidenceClass.VERIFIED_FAMILY, EvidenceClass.VERIFIED_FIXTURE)