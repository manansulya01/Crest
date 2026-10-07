"""Key provider: rotation keeps old receipts verifiable; revoked keys
cannot authorize; unknown keys fail closed; test provider is deterministic."""
from __future__ import annotations

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram
from crest.signing import DeterministicKeyProvider, DevKeyProvider


def _rt(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    return CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))


def test_rotation_preserves_old_receipts(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    old_kid = rt.get_receipt(rt.store.list_receipts()[0]["receipt_id"])["key_id"]
    new_kid = rt._key_provider.rotate()
    assert new_kid != old_kid
    # old receipt still verifies under the archived public key
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "y"})
    assert res.ok, res.reason
    rt.close()


def test_revoked_key_invalidates(tmp_path):
    rt = _rt(tmp_path)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    kid = rt.get_receipt(rt.store.list_receipts()[0]["receipt_id"])["key_id"]
    rt._key_provider.revoke(kid)
    res = rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "a.txt", "content": "y"})
    assert not res.ok and res.reason == "RECEIPT_KEY_REVOKED"
    rt.close()


def test_deterministic_provider_is_fixed_per_instance():
    p = DeterministicKeyProvider()
    kid, sig1 = p.sign("00" * 32)
    _, sig2 = p.sign("00" * 32)
    assert sig1 == sig2
    assert p.get_public_key(kid) is not None
    p.revoke(kid)
    assert p.is_revoked(kid)


def test_dev_provider_archives_public_keys(tmp_path):
    p = DevKeyProvider(tmp_path / ".crest")
    kid = p.get_active_key_id()
    assert p.get_public_key(kid) is not None
    assert p.get_public_key("deadbeef" * 2) is None
