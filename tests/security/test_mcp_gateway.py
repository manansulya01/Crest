"""MCP-style gateway must fail closed on every malformed/unknown request."""
from __future__ import annotations

import pytest

from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.mcp import McpStyleGateway


@pytest.fixture
def gw(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    rt = CrestRuntime(CrestConfig(workspace_root=tmp_path, state_dir=tmp_path / ".crest"))
    yield McpStyleGateway(rt), rt
    rt.close()


def test_unknown_tool_denied(gw):
    g, _ = gw
    out = g.call("kernel", "root", {})
    assert out["ok"] is False and out["isError"] is True
    assert "UNKNOWN_TOOL" in out["reason"]


def test_unknown_operation_denied(gw):
    g, _ = gw
    out = g.call("filesystem", "chmod_777", {"path": "a.txt"})
    assert out["ok"] is False and "UNKNOWN_OPERATION" in out["reason"]


def test_missing_capability_denied(gw):
    g, _ = gw
    out = g.call("filesystem", "delete_file", {"path": "a.txt"})
    assert out["ok"] is False and out["reason"] == "CAPABILITY_NOT_FOUND"


def test_malformed_arguments_type_does_not_crash(gw):
    g, _ = gw
    out = g.call("filesystem", "modify_file", None)
    assert out["ok"] is False


def test_check_returns_structured_decision(gw):
    g, _ = gw
    out = g.check("filesystem", "modify_file", {"path": "a.txt", "content": "y"})
    assert "allowed" in out and "reason" in out


def test_errors_do_not_leak_stack_traces(gw):
    g, _ = gw
    out = g.call("shell", "command", {"command": "rm -rf /"})
    assert "Traceback" not in str(out)
    assert out["ok"] is False
