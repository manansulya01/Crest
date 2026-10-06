"""Agent integration surfaces.

- ToolGateway (crest.gateway): in-process agent integration.
- McpStyleGateway: the smallest interoperable layer for MCP-like clients
  (tool / operation / arguments) without implementing an MCP server.
- external process gateway: agents that cannot import Crest can call
  `python -m crest.cli exec ...` and are still subject to the same policy.
"""
from __future__ import annotations

import json
from typing import Any

from .agent_runtime import CrestRuntime
from .gateway import ToolResult


class McpStyleGateway:
    """MCP-compatible shape: call(tool, operation, arguments) -> result dict.

    Deliberately small: Crest acts as a policy gateway in front of tool calls.
    """

    def __init__(self, runtime: CrestRuntime, agent_id: str = "mcp-client"):
        self._runtime = runtime
        self._agent_id = agent_id

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"tool": "filesystem", "operations": ["create_file", "modify_file", "move_file", "delete_file", "delete_directory"]},
            {"tool": "git", "operations": ["create_branch", "modify_file", "commit"]},
            {"tool": "shell", "operations": ["command"]},
        ]

    def call(self, tool: str, operation: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._runtime.execute(agent_id=self._agent_id, tool=tool, operation=operation, arguments=dict(arguments or {}))
        return {
            "ok": result.ok,
            "reason": result.reason,
            "request_id": result.request_id,
            "content": result.output,
            "isError": not result.ok,
        }

    def check(self, tool: str, operation: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        d = self._runtime.check(agent_id=self._agent_id, tool=tool, operation=operation, arguments=dict(arguments or {}))
        return d.to_audit()
