"""Drift detection unit tests."""
from __future__ import annotations

from crest.drift import detect
from crest.workspace import Workspace


def test_flat_workspace_matches_single_file_family():
    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"1")
        report = detect(ws, ("filesystem.single_file",), target="a.txt")
        assert not report.detected
    finally:
        ws.cleanup()


def test_missing_target_is_identity_drift():
    ws = Workspace.temporary()
    try:
        ws.write("keep.txt", b"1")
        report = detect(ws, ("filesystem.single_file",), target="a.txt")
        assert report.detected
        assert any("moved_or_renamed" in r for r in report.reasons)
    finally:
        ws.cleanup()


def test_path_type_change_detected():
    ws = Workspace.temporary()
    try:
        ws.write("thing/inner.txt", b"1")
        report = detect(ws, ("filesystem.directory_tree",), target="thing", expected_path_type="file")
        assert report.detected
        assert any("path_type_changed" in r for r in report.reasons)
    finally:
        ws.cleanup()


def test_create_target_absence_is_not_drift_when_not_required():
    ws = Workspace.temporary()
    try:
        report = detect(ws, ("filesystem.single_file",), target="new.txt", require_existing=False)
        assert not report.detected
    finally:
        ws.cleanup()


def test_nested_target_mismatches_single_file_family():
    ws = Workspace.temporary()
    try:
        ws.write("a/b/c.txt", b"1")
        report = detect(ws, ("filesystem.single_file",), target="a/b/c.txt")
        assert report.detected
        assert "flat" in report.reasons[0] or "invariant" in report.reasons[0]
    finally:
        ws.cleanup()


def test_nested_workspace_matches_tree_family():
    ws = Workspace.temporary()
    try:
        ws.write("docs/a.txt", b"1")
        report = detect(ws, ("filesystem.directory_tree",), target="docs/a.txt")
        assert not report.detected
    finally:
        ws.cleanup()


def test_unknown_family_is_silent():
    ws = Workspace.temporary()
    try:
        ws.write("a.txt", b"1")
        report = detect(ws, ("filesystem.quantum",), target="a.txt")
        assert not report.detected
    finally:
        ws.cleanup()


def test_drift_denies_execution_when_family_invariants_break():
    """End-to-end: capability admitted with single_file evidence; workspace
    then develops a nested directory -> drift revokes authority."""
    from datetime import datetime, timezone

    from crest.agent_runtime import CrestRuntime
    from crest.config import CrestConfig
    from crest.recovery import RecoveryProgram

    import tempfile, pathlib, shutil

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="crest-drift-"))
    try:
        (tmp / "a.txt").write_text("x", encoding="utf-8")
        rt = CrestRuntime(CrestConfig(workspace_root=tmp, state_dir=tmp / ".crest"))
        # Generalized evidence expects single_file; admissible because family is satisfied.
        out = rt.verify_generalized(
            action_class="delete_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"),
            family_ids=("filesystem.single_file",),
        )
        assert out["admitted"] is True
        # introduce a nested target while evidence family says single_file
        (tmp / "nested").mkdir()
        (tmp / "nested" / "a.txt").write_text("y", encoding="utf-8")
        res = rt.execute(agent_id="a", tool="filesystem", operation="delete_file", arguments={"path": "nested/a.txt"})
        assert not res.ok
        assert res.reason.startswith("DRIFT_DETECTED")
        assert rt.store.list_capabilities()[0].state == "REVOKED"
        rt.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
