"""Pinned-target content/identity drift must revoke before execution."""
from __future__ import annotations

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def _rt(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("original", encoding="utf-8")
    return CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))


def test_content_modification_triggers_content_drift(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_generalized(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.directory_tree",), verification_cases=2, holdout_cases=2, shift_cases=1, pinned_target="sub/a.txt")
    (tmp_path / "sub" / "a.txt").write_text("tampered externally", encoding="utf-8")
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "sub/a.txt", "content": "x"})
    assert not res.ok and res.reason.startswith("DRIFT_DETECTED:CONTENT_DRIFT")
    assert rt.get_capability("modify_file:*")["state"] == "REVOKED"
    rt.close()


def test_target_replacement_triggers_identity_drift(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_generalized(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.directory_tree",), verification_cases=2, holdout_cases=2, shift_cases=1, pinned_target="sub/a.txt")
    (tmp_path / "sub" / "a.txt").unlink()
    (tmp_path / "sub" / "a.txt").write_text("replacement", encoding="utf-8")
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "sub/a.txt", "content": "x"})
    assert not res.ok and res.reason.startswith("DRIFT_DETECTED")
    rt.close()


def test_missing_pinned_target_triggers_identity_drift(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_generalized(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.directory_tree",), verification_cases=2, holdout_cases=2, shift_cases=1, pinned_target="sub/a.txt")
    (tmp_path / "sub" / "a.txt").unlink()
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "sub/a.txt", "content": "x"})
    assert not res.ok and "IDENTITY_DRIFT" in res.reason
    rt.close()


def test_permission_change_triggers_permission_drift(tmp_path):
    import os, stat

    rt = _rt(tmp_path)
    rt.verify_generalized(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.directory_tree",), verification_cases=2, holdout_cases=2, shift_cases=1, pinned_target="sub/a.txt")
    os.chmod(tmp_path / "sub" / "a.txt", stat.S_IREAD)  # remove write bit
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "sub/a.txt", "content": "x"})
    assert not res.ok and "PERMISSION_DRIFT" in res.reason
    rt.close()


def test_unmodified_pinned_target_admits(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_generalized(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), family_ids=("filesystem.directory_tree",), verification_cases=2, holdout_cases=2, shift_cases=1, pinned_target="sub/a.txt")
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "sub/a.txt", "content": "x"})
    assert res.ok, res.reason
    rt.close()
