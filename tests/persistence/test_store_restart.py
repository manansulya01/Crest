from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.recovery import RecoveryProgram


def test_restart_preserves_state(workspace):
    rt = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    out = rt.verify_and_admit(action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    assert out["admitted"] is True
    ok = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert ok.ok
    before = rt.store.total_exposure()
    audit_count = len(rt.audit())
    rt.close()

    # simulate restart: fresh runtime object over the same config/db
    rt2 = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    assert rt2.store.total_exposure() == before
    assert len(rt2.audit()) >= audit_count
    caps = rt2.store.list_capabilities()
    assert caps and caps[0].state == "ACTIVE"
    rt2.close()


def test_revoke_persists(workspace):
    rt = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    rt.verify_and_admit(action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="a.txt", trials=3)
    rt.revoke("delete_file:*", "test")
    rt.close()
    rt2 = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    res = rt2.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason == "CAPABILITY_REVOKED"
    rt2.close()
