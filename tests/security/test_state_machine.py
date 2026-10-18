"""State-machine invariants over Capability transitions + runtime guards."""
from __future__ import annotations

import itertools

import pytest

from crest.capabilities import Capability, CapabilityState, IllegalTransition, _TRANSITIONS


def test_no_illegal_self_transitions():
    for state, targets in _TRANSITIONS.items():
        assert state not in targets, f"{state} may transition to itself"


def test_executable_states_are_only_admitted_active():
    for state in CapabilityState:
        c = Capability("modify_file")
        c.state = state
        assert c.executable == (state in (CapabilityState.ADMITTED, CapabilityState.ACTIVE))


def test_revoked_cannot_directly_activate():
    c = Capability("modify_file")
    c.state = CapabilityState.REVOKED
    with pytest.raises(IllegalTransition):
        c.transition(CapabilityState.ACTIVE)


def test_verified_cannot_skip_admission():
    c = Capability("modify_file")
    c.state = CapabilityState.VERIFIED
    with pytest.raises(IllegalTransition):
        c.transition(CapabilityState.ACTIVE)


def test_proposed_cannot_execute_or_skip_verify():
    c = Capability("modify_file")
    c.state = CapabilityState.PROPOSED
    with pytest.raises(IllegalTransition):
        c.transition(CapabilityState.ADMITTED)


def test_all_illegal_pairs_raise():
    for a, b in itertools.product(CapabilityState, CapabilityState):
        c = Capability("modify_file")
        c.state = a
        if b in _TRANSITIONS[a]:
            continue
        with pytest.raises(IllegalTransition):
            c.transition(b)


def test_legal_paths_cover_documented_lifecycle():
    c = Capability("modify_file")
    for s in (CapabilityState.PROPOSED, CapabilityState.VERIFYING, CapabilityState.VERIFIED, CapabilityState.ADMITTED, CapabilityState.ACTIVE):
        c.transition(s)
    assert c.state is CapabilityState.ACTIVE
    c.transition(CapabilityState.REVOKED)
    assert c.state is CapabilityState.REVOKED


def test_runtime_denies_active_row_with_revoked_receipt(tmp_path):
    from crest.agent_runtime import CrestRuntime
    from crest.config import CrestConfig
    from crest.recovery import RecoveryProgram
    from crest.capabilities import CapabilityState

    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    rt = CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    rt.revoke("modify_file:*")
    # attacker resurrects the capability row to ACTIVE without fresh evidence
    row = rt.store.get_capability("modify_file:*")
    row.state = CapabilityState.ACTIVE.value
    rt.store.upsert_capability(row)
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "y"})
    assert not res.ok
    assert res.reason in ("RECEIPT_REVOKED", "CAPABILITY_REVOKED")
    rt.close()
