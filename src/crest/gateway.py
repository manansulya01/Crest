"""ToolRequest / ToolResult / ToolGateway integration surface.

An agent framework plugs in by constructing ToolRequests and calling
gateway.execute(). The gateway never trusts the requester with authority:
all decisions are made by the CrestRuntime.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolRequest:
    agent_id: str
    tool: str
    operation: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_request_id: str | None = None


@dataclass
class ToolResult:
    ok: bool
    request_id: str
    agent_id: str
    tool: str
    operation: str
    reason: str
    target: str | None = None
    exposure_before: float | None = None
    exposure_after: float | None = None
    output: Any = None
    duration_ms: float | None = None


class ToolGateway:
    def __init__(self, runtime):
        self._runtime = runtime

    def execute(self, request: ToolRequest) -> ToolResult:
        return self._runtime.execute(
            agent_id=request.agent_id,
            tool=request.tool,
            operation=request.operation,
            arguments=request.arguments,
            request_id=request.request_id,
        )
