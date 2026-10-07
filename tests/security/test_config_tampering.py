"""Configuration tampering must not silently broaden authority."""
from __future__ import annotations

import pytest

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig, default_yaml, load
from crest.recovery import RecoveryProgram


def test_malformed_config_fails_closed(tmp_path):
    (tmp_path / "crest.yaml").write_text("exposure: [not, a, mapping]\n", encoding="utf-8")
    with pytest.raises(Exception):
        load(tmp_path / "crest.yaml")


def test_unknown_section_rejected(tmp_path):
    (tmp_path / "crest.yaml").write_text("admit_everything: true\nexposure:\n  max_window_exposure: 100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config sections"):
        load(tmp_path / "crest.yaml")


def test_invalid_budget_rejected(tmp_path):
    (tmp_path / "crest.yaml").write_text("exposure:\n  max_window_exposure: -5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load(tmp_path / "crest.yaml")


def test_impossible_evidence_policy_rejected(tmp_path):
    (tmp_path / "crest.yaml").write_text("evidence:\n  general:\n    minimum_holdout_cases: 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load(tmp_path / "crest.yaml")


def test_policy_version_bump_invalidates_old_receipts(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    cfg_text = default_yaml(tmp_path)
    (tmp_path / "crest.yaml").write_text(cfg_text, encoding="utf-8")
    rt = CrestRuntime.from_config(tmp_path / "crest.yaml")
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    # operator rotates the policy version underneath the live state
    (tmp_path / "crest.yaml").write_text(cfg_text.replace("policy-v1", "policy-v2"), encoding="utf-8")
    rt2 = CrestRuntime.from_config(tmp_path / "crest.yaml")
    res = rt2.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "y"})
    assert not res.ok
    assert res.reason.startswith("POLICY_DENIED")
    rt.close()
    rt2.close()


def test_running_runtime_does_not_reload_config(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "crest.yaml").write_text(default_yaml(tmp_path), encoding="utf-8")
    rt = CrestRuntime.from_config(tmp_path / "crest.yaml")
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    # attacker raises the exposure budget on disk mid-session
    (tmp_path / "crest.yaml").write_text(default_yaml(tmp_path).replace("max_window_exposure: 1.0", "max_window_exposure: 1000000.0"), encoding="utf-8")
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "y"})
    # running runtime keeps its parsed constitutional budget
    assert res.ok
    assert rt.config.e_max == 1.0
    rt.close()
