"""Agent integration, redaction, doctor, and coverage-metric tests."""
from __future__ import annotations

import json
import sqlite3

import pytest

from crest.evidence import EvidenceClass
from crest.metrics_v04 import CoverageSnapshot, evidence_efficiency, summarize
from crest.mcp import McpStyleGateway
from crest.redaction import redact, redact_text
from crest.recovery import RecoveryProgram

from tests.conftest import make_runtime


# ---------------- MCP-style gateway ----------------

def test_mcp_gateway_admits_and_denies(workspace):
    rt = make_runtime(workspace)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    gw = McpStyleGateway(rt, agent_id="mcp-test")
    ok = gw.call("filesystem", "modify_file", {"path": "data/a.txt", "content": "hi"})
    assert ok["ok"] is True and ok["isError"] is False
    denied = gw.call("filesystem", "delete_file", {"path": "data/a.txt"})
    assert denied["ok"] is False and denied["isError"] is True
    rt.close()


def test_mcp_gateway_unknown_tool_fails_closed(workspace):
    rt = make_runtime(workspace)
    gw = McpStyleGateway(rt)
    out = gw.call("kernel", "reboot", {})
    assert out["ok"] is False and "UNKNOWN_TOOL" in out["reason"]
    rt.close()


def test_mcp_gateway_check_is_side_effect_free(workspace):
    rt = make_runtime(workspace)
    gw = McpStyleGateway(rt)
    decision = gw.check("filesystem", "delete_file", {"path": "data/a.txt"})
    assert decision["allowed"] is False
    assert (workspace / "data" / "a.txt").exists()
    rt.close()


def test_mcp_gateway_lists_tools(workspace):
    rt = make_runtime(workspace)
    tools = {t["tool"] for t in McpStyleGateway(rt).list_tools()}
    assert tools == {"filesystem", "git", "shell"}
    rt.close()


# ---------------- redaction ----------------

def test_redaction_masks_common_secret_shapes():
    text = "api_key=abc123secret and sk-ABCDEFGHIJKLMNOPQRST and password: hunter2"
    out = redact_text(text)
    assert "hunter2" not in out
    assert "ABCDEFGHIJKLMNOPQRST" not in out


def test_redaction_masks_dict_keys():
    out = redact({"password": "x", "nested": {"api_key": "y"}, "path": "tmp/a.txt"})
    assert out["password"] == "[REDACTED]"
    assert out["nested"]["api_key"] == "[REDACTED]"
    assert out["path"] == "tmp/a.txt"


def test_audit_does_not_store_secrets(workspace):
    rt = make_runtime(workspace)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "data/a.txt", "content": "x", "password": "hunter2"})
    blob = json.dumps(rt.audit())
    assert "hunter2" not in blob
    rt.close()


def test_audit_jsonl_mirror_is_redacted(workspace):
    rt = make_runtime(workspace)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    rt.execute(agent_id="a", tool="filesystem", operation="modify_file", arguments={"path": "data/a.txt", "api_key": "TOPSECRET"})
    mirror = workspace / ".crest" / "audit.jsonl"
    assert mirror.exists()
    assert "TOPSECRET" not in mirror.read_text(encoding="utf-8")
    rt.close()


# ---------------- doctor ----------------

def test_doctor_reports_levels_and_exit_codes(workspace):
    from crest.doctor import ERROR, INFO, WARNING, diagnose

    rt = make_runtime(workspace)
    findings, code = diagnose(rt)
    assert code == 0
    assert any(f["level"] in (INFO, WARNING, ERROR) for f in findings)
    assert not any(f["level"] == ERROR for f in findings)
    rt.close()


def test_doctor_detects_exposure_over_budget(workspace):
    """Ledger > e_max is only reachable via direct DB writes (the runtime
    prevents it), so the test injects the state a corrupted store would hold."""
    from crest.doctor import ERROR, diagnose

    rt = make_runtime(workspace, e_max=0.1)
    rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    rt.store.add_exposure(5.0, "2026-01-01T00:00:00+00:00", "modify_file", "data/a.txt", "injected")
    findings, code = diagnose(rt)
    assert any(f["code"] == "EXPOSURE_OVER_BUDGET" and f["level"] == ERROR for f in findings)
    assert code == 1
    rt.close()


def test_doctor_detects_corrupt_database(workspace):
    from crest.doctor import ERROR, diagnose
    from crest.store import SecurityStateCorrupt

    rt = make_runtime(workspace)
    rt.close()
    (workspace / ".crest" / "crest.db").write_bytes(b"definitely not sqlite")
    with pytest.raises(SecurityStateCorrupt):
        make_runtime(workspace)


def test_doctor_detects_invalid_receipt(workspace):
    from crest.doctor import ERROR, diagnose

    rt = make_runtime(workspace)
    out = rt.verify_and_admit(action_class="modify_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="data/a.txt", trials=3)
    payload = rt.store.get_receipt_payload(out["receipt_id"])
    payload["status"] = "HACKED"
    rt.store.save_receipt(out["receipt_id"], "modify_file", "*", "VERIFIED", "VERIFIED_FIXTURE", payload["issued_at"], payload["expires_at"], payload)
    findings, code = diagnose(rt)
    assert any(f["code"] == "RECEIPT_INVALID" for f in findings)
    assert code == 1
    rt.close()


# ---------------- coverage metrics ----------------

def test_coverage_snapshot_separates_aac_and_gac():
    snap = CoverageSnapshot(
        eligible=4,
        admitted={"delete_file", "modify_file"},
        family_backed={"delete_file"},
        general_backed=set(),
    )
    assert snap.aac == 0.5
    assert snap.gac == 0.25
    assert snap.gac_general == 0.0
    assert snap.fixture_only_autonomy == {"modify_file"}


def test_evidence_efficiency_is_coverage_per_second():
    assert evidence_efficiency(0.5, 2.0) == 0.25
    assert evidence_efficiency(0.0, 1.0) == 0.0


def test_summarize_computes_rates():
    rows = [
        {"admitted": True, "false_admission": False, "false_rejection": False, "evaluation_success": 1.0, "verification_seconds": 1.0},
        {"admitted": False, "false_admission": False, "false_rejection": True, "evaluation_success": 1.0, "verification_seconds": 2.0},
    ]
    out = summarize(rows)
    assert out["n"] == 2 and out["false_rejection_rate"] == 0.5 and out["mean_verification_seconds"] == 1.5


# ---------------- config policy ----------------

def test_config_rejects_illegal_evidence_policy():
    from crest.config import load

    path = write_config()
    bad = path.read_text(encoding="utf-8").replace("minimum_holdout_cases: 20", "minimum_holdout_cases: 0")
    bad_path = path.with_name("bad.yaml")
    bad_path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError):
        load(bad_path)


def test_config_accepts_valid_policy():
    from crest.config import load

    cfg = load(write_config())
    assert cfg.evidence_policy.general.minimum_holdout_cases == 20
    assert cfg.limits.max_verification_cases == 500
    assert cfg.mode == "production"


def write_config() -> "Path":
    import tempfile
    from pathlib import Path

    from crest.config import default_yaml

    tmp = Path(tempfile.mkdtemp(prefix="crest-cfg-"))
    (tmp / "f.txt").write_text("x", encoding="utf-8")
    cfg = tmp / "crest.yaml"
    cfg.write_text(default_yaml(tmp), encoding="utf-8")
    return cfg