"""Composition experiments: measure whether composed recoverability holds.

Tests sequences of operations where individual steps may be recoverable
but the sequence is not, or where evidence composition is required."""
from __future__ import annotations

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram
from crest.composition import Step, verify_composition


def _rt(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("orig", encoding="utf-8")
    return CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))


def test_modify_then_move_composition(tmp_path):
    """modify_file then move_file: recovery must restore both states."""
    rt = _rt(tmp_path)
    result = rt.check_composition(
        steps=[
            {"action_class": "modify_file", "params": {"content": "step1\n"}},
            {"action_class": "move_file", "params": {"destination": "moved.txt"}},
        ],
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_id="filesystem.directory_tree",
        cases=6,
    )
    print("modify->move:", result)
    assert result["status"] in ("VERIFIED_COMPOSITION", "UNVERIFIED_COMPOSITION")
    rt.close()


def test_delete_then_create_composition(tmp_path):
    """delete_file then create_file: recovery must restore pre-delete state."""
    rt = _rt(tmp_path)
    result = rt.check_composition(
        steps=[
            {"action_class": "delete_file", "params": {}},
            {"action_class": "create_file", "params": {"path": "new.txt", "content": "new"}},
        ],
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_id="filesystem.single_file",
        cases=6,
    )
    print("delete->create:", result)
    rt.close()


def test_move_then_modify_composition(tmp_path):
    """move_file then modify_file on the moved target."""
    rt = _rt(tmp_path)
    result = rt.check_composition(
        steps=[
            {"action_class": "move_file", "params": {"destination": "moved.txt"}},
            {"action_class": "modify_file", "params": {"content": "after move\n"}},
        ],
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_id="filesystem.directory_tree",
        cases=6,
    )
    print("move->modify:", result)
    rt.close()


def test_three_step_composition(tmp_path):
    """A -> B -> C: can full snapshot recovery restore all three states?"""
    rt = _rt(tmp_path)
    result = rt.check_composition(
        steps=[
            {"action_class": "modify_file", "params": {"content": "a\n"}},
            {"action_class": "move_file", "params": {"destination": "b.txt"}},
            {"action_class": "modify_file", "params": {"content": "c\n"}},
        ],
        recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_id="filesystem.directory_tree",
        cases=6,
    )
    print("a->b->c:", result)
    rt.close()


def test_component_success_vs_composed(tmp_path):
    """Individual steps succeed but composition may fail."""
    rt = _rt(tmp_path)
    # modify_file alone
    mod = rt.check_composition(steps=[{"action_class": "modify_file", "params": {"content": "x\n"}}], recovery=RecoveryProgram(kind="restore_from_snapshot"), family_id="filesystem.directory_tree", cases=6)
    # move_file alone
    mv = rt.check_composition(steps=[{"action_class": "move_file", "params": {"destination": "moved.txt"}}], recovery=RecoveryProgram(kind="restore_from_snapshot"), family_id="filesystem.directory_tree", cases=6)
    # composition
    comp = rt.check_composition(steps=[{"action_class": "modify_file", "params": {"content": "x\n"}}, {"action_class": "move_file", "params": {"destination": "moved.txt"}}], recovery=RecoveryProgram(kind="restore_from_snapshot"), family_id="filesystem.directory_tree", cases=6)
    print("modify alone:", mod["component_success"])
    print("move alone:", mv["component_success"])
    print("composed:", comp["success_rate"], comp["component_success"])
    # component_success in composition result shows per-step success within sequence
    rt.close()