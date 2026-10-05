"""End-to-end: agent tool call -> crest admission -> execution -> audit."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import crest.cli as cli
from crest.agent_runtime import CrestRuntime
from crest.config import CrestConfig
from crest.gateway import ToolGateway, ToolRequest
from crest.recovery import RecoveryProgram


@dataclass
class MockAgent:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def ask(self, gateway, tool, operation, arguments):
        req = ToolRequest(agent_id="mock-agent", tool=tool, operation=operation, arguments=arguments)
        self.calls.append({"tool": tool, "operation": operation, "arguments": arguments})
        return gateway.execute(req)


def test_end_to_end(workspace):
    rt = CrestRuntime(CrestConfig(workspace_root=workspace, state_dir=workspace / ".crest"))
    gw = ToolGateway(rt)
    agent = MockAgent()

    rt.verify_and_admit(
        action_class="create_file", scope="*", recovery=RecoveryProgram(kind="restore_from_snapshot"), target="new.txt", trials=3
    )
    r = agent.ask(gw, "filesystem", "create_file", {"path": "new.txt", "content": "hello"})
    assert r.ok, r.reason
    assert (workspace / "new.txt").read_text() == "hello"

    r = agent.ask(gw, "filesystem", "modify_file", {"path": "new.txt", "content": "updated"})
    assert not r.ok and r.reason == "CAPABILITY_NOT_FOUND"

    r = agent.ask(gw, "shell", "command", {"command": "rm -rf /"})
    assert not r.ok  # unknown tool target scope: no capability

    audit_events = [e["decision"] for e in rt.audit()]
    assert "ADMISSION_DENIED" in audit_events and "EXECUTION_SUCCEEDED" in audit_events
    rt.close()
