"""Model adapters for the benchmark slice.

A tiny multi-model dispatcher that satisfies the adapter protocol expected by
`crest.inference.InferenceRuntime` (a `.complete(request, *, timeout_seconds)`
callable). In fake mode nothing touches the network.

Request-id contract (fake and live): ``{strategy}::{task_id}::{unique}`;
the fake adapters recover ``task_id`` from it. Live requests keep the same
shape so request identity is auditable in the ledger either way.
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

from crest.inference import InferenceRequest, InferenceResponse, TokenUsage


def make_request_id(strategy: str, task_id: str, unique: str) -> str:
    return f"{strategy}::{task_id}::{unique}"


def extract_task_id(request_id: str) -> str:
    return request_id.split("::")[1]


class MultiModelAdapter:
    """Dispatch each request to the adapter registered for ``request.model``."""

    def __init__(self, adapters: Mapping[str, object]) -> None:
        self._adapters = dict(adapters)

    def register(self, model: str, adapter: object) -> None:
        self._adapters[model] = adapter

    def complete(self, request: InferenceRequest, *, timeout_seconds: float):
        adapter = self._adapters.get(request.model)
        if adapter is None:
            raise KeyError(f"no adapter registered for model {request.model!r}")
        return adapter.complete(request, timeout_seconds=timeout_seconds)


def response_for_text(request: InferenceRequest, text: str, in_tokens: int, out_tokens: int, latency_ms: float = 1.0) -> InferenceResponse:
    return InferenceResponse(
        request_id=request.request_id,
        model=request.model,
        text=text,
        usage=TokenUsage(in_tokens, out_tokens),
        finish_reason="stop",
        usage_reported=True,
        latency_ms=latency_ms,
    )


class FakeTaskModelAdapter:
    """Deterministic fake model for the extraction workload (test mode only).

    Contract (documented in docs/v0.7-benchmark-plan.md):
    - strong model: always emits the exactly-correct gold JSON for the task;
    - cheap model: correct on single-topic tasks; deterministic 20% failure
      rate on multi-topic tasks (fails when sha256(task_id) % 5 == 0) by
      flipping the category field to the distractor value.
    Usage counts are synthetic and deterministic; usage_reported always True.
    """

    def __init__(
        self,
        tasks_by_id: Mapping[str, object],
        *,
        cheap: bool,
        distractor_category: str = "general_help",
    ) -> None:
        self._tasks = dict(tasks_by_id)
        self._cheap = cheap
        self._distractor = distractor_category
        self.calls = 0

    def complete(self, request: InferenceRequest, *, timeout_seconds: float) -> InferenceResponse:
        self.calls += 1
        task = self._tasks.get(extract_task_id(request.request_id))
        if task is None:
            return response_for_text(request, "not found", 10, 2)
        gold = dict(task.gold)
        text = json.dumps(gold)
        if self._cheap and task.multi_constraint:
            if int(hashlib.sha256(task.task_id.encode()).hexdigest()[:8], 16) % 5 == 0:
                wrong = dict(gold)
                wrong["category"] = self._distractor
                text = json.dumps(wrong)
        in_tokens = 45 + min(160, len(request.prompt) // 3)
        return response_for_text(request, text, in_tokens, max(12, len(text) // 4))
