"""Target pinning: evidence for one concrete path does not authorize another."""
from __future__ import annotations

from crest.recovery import RecoveryProgram

from tests.conftest import make_runtime


def test_pinned_capability_denies_other_target(workspace):
    (workspace / "other.txt").write_text("o", encoding="utf-8")
    rt = make_runtime(workspace)
    out = rt.verify_generalized(
        action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",), verification_cases=3, holdout_cases=3, shift_cases=1,
        pinned_target="data/a.txt",
    )
    assert out["admitted"] is True
    # pinned to data/a.txt; a different flat target must be refused
    res2 = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "other.txt"})
    assert not res2.ok and res2.reason == "TARGET_IDENTITY_MISMATCH"
    assert (workspace / "other.txt").exists()
    rt.close()


def test_unpinned_capability_still_allows_other_targets(workspace):
    (workspace / "b.txt").write_text("b", encoding="utf-8")
    rt = make_runtime(workspace)
    out = rt.verify_generalized(
        action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",), verification_cases=3, holdout_cases=3, shift_cases=1,
    )
    assert out["admitted"] is True
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "b.txt"})
    assert res.ok, res.reason
    rt.close()


def test_nested_target_under_single_file_evidence_is_drift(workspace):
    rt = make_runtime(workspace)
    out = rt.verify_generalized(
        action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
        family_ids=("filesystem.single_file",), verification_cases=3, holdout_cases=3, shift_cases=1,
    )
    assert out["admitted"] is True
    res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "data/a.txt"})
    assert not res.ok and res.reason.startswith("DRIFT_DETECTED")
    rt.close()