"""Smallest reliable model-inference runtime for Crest.

This module is intentionally separate from the V0.4 recovery-admission runtime.
The V0.5 Phase A validation supports a synthetic filesystem recovery-admission
policy; it does not support any model-inference claim.  Consequently this
runtime has its own policy, budget, token ledger, adapter boundary, and audit
trail.  It never grants authority from recovery evidence.

The only adapter that is exercised by the test suite is ``FakeModelAdapter``.
``HttpChatAdapter`` is a concrete OpenAI-compatible transport, but live provider
calls are unverified and are not claimed to be tested.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol

from .store import SecurityStateCorrupt, Store


class InferenceError(Exception):
    """Base class for inference-runtime failures."""


class InferenceDenied(InferenceError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts must be non-negative")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    model: str
    prompt: str
    max_output_tokens: int
    agent_id: str = "anonymous"
    temperature: float = 0.0
    system: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self, policy: "InferencePolicy") -> None:
        if not self.request_id or len(self.request_id) > 128:
            raise ValueError("request_id must be 1..128 characters")
        if any(ch in self.request_id for ch in "\r\n\t\0"):
            raise ValueError("request_id contains control characters")
        if not self.model or len(self.model) > 128:
            raise ValueError("model must be 1..128 characters")
        if not self.prompt:
            raise ValueError("prompt must not be empty")
        if len(self.prompt) > policy.max_prompt_chars:
            raise ValueError("prompt exceeds max_prompt_chars")
        if len(self.system) > policy.max_prompt_chars:
            raise ValueError("system exceeds max_prompt_chars")
        if self.max_output_tokens < 1 or self.max_output_tokens > policy.max_output_tokens:
            raise ValueError("max_output_tokens outside policy bounds")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be in [0, 2]")
        if len(self.metadata) > 32:
            raise ValueError("too many metadata entries")
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("metadata keys and values must be strings")
            if len(key) > 64 or len(value) > 256:
                raise ValueError("metadata entry too large")


@dataclass(frozen=True)
class InferenceResponse:
    request_id: str
    model: str
    text: str
    usage: TokenUsage
    finish_reason: str
    provider_request_id: str | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True)
class InferencePolicy:
    allowed_models: tuple[str, ...] = ("fake-echo",)
    max_input_tokens: int = 4096
    max_output_tokens: int = 1024
    max_prompt_chars: int = 32768
    max_output_chars: int = 65536
    input_token_weight: float = 1.0
    output_token_weight: float = 1.0
    max_cost_units_per_request: float = 8192.0
    window_seconds: float = 3600.0
    window_budget_units: float = 100000.0
    request_timeout_seconds: float = 30.0
    allowed_finish_reasons: tuple[str, ...] = ("stop",)
    require_usage: bool = True
    require_nonempty_output: bool = True

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("token limits must be positive")
        if self.max_prompt_chars <= 0 or self.max_output_chars <= 0:
            raise ValueError("character limits must be positive")
        if self.input_token_weight < 0 or self.output_token_weight < 0:
            raise ValueError("token weights must be non-negative")
        if self.max_cost_units_per_request <= 0 or self.window_budget_units <= 0:
            raise ValueError("budgets must be positive")
        if self.window_seconds <= 0 or self.request_timeout_seconds <= 0:
            raise ValueError("time limits must be positive")
        if not self.allowed_models:
            raise ValueError("at least one model must be allowed")
        if not self.allowed_finish_reasons:
            raise ValueError("at least one finish reason must be allowed")

    def reserved_units(self, request: InferenceRequest) -> float:
        # Worst case: the request uses the full input and output ceilings.
        return (
            self.max_input_tokens * self.input_token_weight
            + request.max_output_tokens * self.output_token_weight
        )

    def cost_units(self, usage: TokenUsage) -> float:
        return (
            usage.input_tokens * self.input_token_weight
            + usage.output_tokens * self.output_token_weight
        )


@dataclass(frozen=True)
class InferenceResult:
    allowed: bool
    reason: str
    response: InferenceResponse | None
    request_id: str
    model: str
    reserved_units: float
    charged_units: float
    actual_units: float
    input_tokens: int
    output_tokens: int
    duration_ms: float


class ModelAdapter(Protocol):
    def complete(
        self,
        request: InferenceRequest,
        *,
        timeout_seconds: float,
    ) -> InferenceResponse:
        ...


class FakeModelAdapter:
    """Deterministic adapter used by tests and by local development.

    It performs no network I/O.  Token counts are derived from text length so
    that budget and accounting tests are deterministic.
    """

    def __init__(
        self,
        *,
        model: str = "fake-echo",
        sleep_seconds: float = 0.0,
        failure_mode: str | None = None,
        output_prefix: str = "fake:",
    ) -> None:
        if failure_mode not in (None, "timeout", "exception", "malformed", "wrong_model", "over_usage", "empty"):
            raise ValueError(f"unknown failure mode {failure_mode!r}")
        self.model = model
        self.sleep_seconds = sleep_seconds
        self.failure_mode = failure_mode
        self.output_prefix = output_prefix
        self.calls: list[InferenceRequest] = []
        self._lock = threading.Lock()

    def complete(self, request: InferenceRequest, *, timeout_seconds: float) -> InferenceResponse:
        with self._lock:
            self.calls.append(request)
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if self.failure_mode == "timeout":
            time.sleep(timeout_seconds + 1.0)
        if self.failure_mode == "exception":
            raise RuntimeError("fake adapter failure")
        if self.failure_mode == "wrong_model":
            return InferenceResponse(
                request_id=request.request_id,
                model="not-the-requested-model",
                text="wrong model",
                usage=TokenUsage(1, 1),
                finish_reason="stop",
            )
        if self.failure_mode == "empty":
            return InferenceResponse(
                request_id=request.request_id,
                model=request.model,
                text="",
                usage=TokenUsage(1, 0),
                finish_reason="stop",
            )
        if self.failure_mode == "malformed":
            return InferenceResponse(
                request_id=request.request_id,
                model=request.model,
                text="malformed",
                usage=TokenUsage(1, 1),
                finish_reason="length",
            )
        if self.failure_mode == "over_usage":
            return InferenceResponse(
                request_id=request.request_id,
                model=request.model,
                text="too much",
                usage=TokenUsage(request.max_output_tokens + 1, 1),
                finish_reason="stop",
            )
        text = f"{self.output_prefix}{request.model}:{hashlib.sha256(request.prompt.encode('utf-8')).hexdigest()[:16]}"
        input_tokens = max(1, (len(request.prompt) + len(request.system) + 3) // 4)
        output_tokens = max(1, (len(text) + 3) // 4)
        return InferenceResponse(
            request_id=request.request_id,
            model=request.model,
            text=text,
            usage=TokenUsage(input_tokens, output_tokens),
            finish_reason="stop",
            latency_ms=0.0,
        )


class HttpChatAdapter:
    """OpenAI-compatible chat-completions transport.

    This adapter performs real network I/O.  It is not exercised by the test
    suite and live-provider correctness is unverified.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key, and model are required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = dict(extra_headers or {})

    def complete(self, request: InferenceRequest, *, timeout_seconds: float) -> InferenceResponse:
        model = request.model or self.model
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        url = self.base_url + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }
        headers.update(self.extra_headers)
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise InferenceError(f"provider HTTP {exc.code}: {body[:512]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise InferenceError(f"provider request failed: {exc}") from exc
        latency_ms = (time.monotonic() - started) * 1000.0
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InferenceError("provider returned invalid JSON") from exc
        try:
            choice = parsed["choices"][0]
            message = choice["message"]
            text = message["content"]
            finish_reason = choice.get("finish_reason", "stop")
            usage = parsed.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise InferenceError("provider response missing required fields") from exc
        if not isinstance(text, str):
            raise InferenceError("provider response content is not a string")
        return InferenceResponse(
            request_id=request.request_id,
            model=model,
            text=text,
            usage=TokenUsage(input_tokens, output_tokens),
            finish_reason=str(finish_reason),
            provider_request_id=parsed.get("id"),
            latency_ms=latency_ms,
        )


class InferenceRuntime:
    def __init__(
        self,
        store: Store,
        policy: InferencePolicy,
        adapter: ModelAdapter,
        *,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.policy = policy
        self.adapter = adapter
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def infer(self, request: InferenceRequest) -> InferenceResult:
        started = self._now_fn()
        reserved = 0.0
        try:
            request.validate(self.policy)
        except ValueError as exc:
            self._audit(request, "DENY", "INVALID_REQUEST", {}, started)
            return self._denied(request, "INVALID_REQUEST", str(exc), 0.0, 0.0, started)

        if request.model not in self.policy.allowed_models:
            self._audit(request, "DENY", "MODEL_NOT_ALLOWED", {}, started)
            return self._denied(request, "MODEL_NOT_ALLOWED", request.model, 0.0, 0.0, started)

        existing = self.store.get_inference(request.request_id)
        if existing is not None:
            self._audit(request, "DENY", "DUPLICATE_REQUEST", {"status": existing["status"]}, started)
            return self._denied(
                request,
                "DUPLICATE_REQUEST",
                f"request {request.request_id} already has status {existing['status']}",
                0.0,
                0.0,
                started,
            )

        reserved = self.policy.reserved_units(request)
        if reserved > self.policy.max_cost_units_per_request:
            self._audit(request, "DENY", "REQUEST_BUDGET_EXCEEDED", {"reserved": reserved}, started)
            return self._denied(request, "REQUEST_BUDGET_EXCEEDED", str(reserved), 0.0, 0.0, started)

        now = self._now_fn()
        cutoff = (now - timedelta(seconds=self.policy.window_seconds)).isoformat()
        ok, reason = self.store.try_begin_inference(
            request.request_id,
            request.model,
            reserved,
            self.policy.window_budget_units,
            now.isoformat(),
            cutoff,
        )
        if not ok:
            self._audit(request, "DENY", reason, {"reserved": reserved}, started)
            return self._denied(request, reason, reason, 0.0, 0.0, started)

        response: InferenceResponse | None = None
        failure_reason: str | None = None
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.adapter.complete, request, timeout_seconds=self.policy.request_timeout_seconds)
                try:
                    response = future.result(timeout=self.policy.request_timeout_seconds)
                except FutureTimeout:
                    future.cancel()
                    raise InferenceDenied("TIMEOUT")
        except InferenceDenied as exc:
            failure_reason = exc.reason
        except Exception as exc:  # adapter or runtime failure
            failure_reason = "ADAPTER_ERROR"
            self._last_adapter_error = f"{type(exc).__name__}: {exc}"

        if failure_reason is not None:
            error = getattr(self, "_last_adapter_error", failure_reason)
            if failure_reason != "ADAPTER_ERROR":
                error = failure_reason
            self.store.finish_inference(
                request.request_id,
                "FAILED" if failure_reason != "TIMEOUT" else "TIMED_OUT",
                finished_at=self._now_fn().isoformat(),
                error=error,
            )
            self._audit(request, "DENY", failure_reason, {"reserved": reserved, "error": error}, started)
            return self._denied(request, failure_reason, error, reserved, reserved, started)

        assert response is not None
        try:
            self._validate_response(request, response)
        except ValueError as exc:
            self.store.finish_inference(
                request.request_id,
                "INVALID",
                finished_at=self._now_fn().isoformat(),
                error=f"INVALID_RESPONSE: {exc}",
            )
            self._audit(request, "DENY", "INVALID_RESPONSE", {"error": str(exc), "reserved": reserved}, started)
            return self._denied(request, "INVALID_RESPONSE", str(exc), reserved, reserved, started)

        actual = self.policy.cost_units(response.usage)
        if actual > reserved + 1e-9:
            self.store.finish_inference(
                request.request_id,
                "INVALID",
                finished_at=self._now_fn().isoformat(),
                error=f"USAGE_EXCEEDS_RESERVATION: {actual} > {reserved}",
            )
            self._audit(
                request,
                "DENY",
                "USAGE_EXCEEDS_RESERVATION",
                {"actual": actual, "reserved": reserved},
                started,
            )
            return self._denied(request, "USAGE_EXCEEDS_RESERVATION", str(actual), reserved, reserved, started)

        digest = self._response_digest(response)
        self.store.finish_inference(
            request.request_id,
            "COMPLETED",
            actual_units=actual,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finished_at=self._now_fn().isoformat(),
            response_digest=digest,
        )
        duration_ms = (self._now_fn() - started).total_seconds() * 1000.0
        self._audit(
            request,
            "ALLOW",
            "OK",
            {
                "model": response.model,
                "finish_reason": response.finish_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "reserved_units": reserved,
                "actual_units": actual,
                "response_digest": digest,
                "provider_request_id": response.provider_request_id,
            },
            started,
        )
        return InferenceResult(
            allowed=True,
            reason="OK",
            response=response,
            request_id=request.request_id,
            model=response.model,
            reserved_units=reserved,
            charged_units=reserved,
            actual_units=actual,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
        )

    def _validate_response(self, request: InferenceRequest, response: InferenceResponse) -> None:
        if response.request_id != request.request_id:
            raise ValueError("response request_id mismatch")
        if response.model != request.model:
            raise ValueError("response model mismatch")
        if self.policy.require_usage and response.usage is None:
            raise ValueError("missing usage")
        if response.usage.input_tokens > self.policy.max_input_tokens:
            raise ValueError("input token count exceeds policy")
        if response.usage.output_tokens > request.max_output_tokens:
            raise ValueError("output token count exceeds request limit")
        if response.usage.output_tokens > self.policy.max_output_tokens:
            raise ValueError("output token count exceeds policy")
        if len(response.text) > self.policy.max_output_chars:
            raise ValueError("response text exceeds max_output_chars")
        if self.policy.require_nonempty_output and not response.text:
            raise ValueError("empty response text")
        if response.finish_reason not in self.policy.allowed_finish_reasons:
            raise ValueError(f"finish reason {response.finish_reason!r} not allowed")

    def _response_digest(self, response: InferenceResponse) -> str:
        payload = {
            "request_id": response.request_id,
            "model": response.model,
            "text_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "finish_reason": response.finish_reason,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _audit(
        self,
        request: InferenceRequest,
        decision: str,
        reason: str,
        details: dict[str, Any],
        started: datetime,
    ) -> None:
        try:
            self.store.add_audit(
                timestamp=started.isoformat(),
                request_id=request.request_id,
                agent_id=request.agent_id,
                capability_id=None,
                tool="model",
                operation="infer",
                decision=decision,
                reason=reason,
                details=details,
            )
        except Exception:
            # Auditing must not create a second failure mode that hides the
            # original decision, but the store is expected to be available.
            pass

    def _denied(
        self,
        request: InferenceRequest,
        reason: str,
        detail: str,
        reserved: float,
        charged: float,
        started: datetime,
    ) -> InferenceResult:
        duration_ms = (self._now_fn() - started).total_seconds() * 1000.0
        return InferenceResult(
            allowed=False,
            reason=reason,
            response=None,
            request_id=request.request_id,
            model=request.model,
            reserved_units=reserved,
            charged_units=charged,
            actual_units=0.0,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
        )

    def usage_summary(self, *, window_seconds: float | None = None) -> dict[str, Any]:
        seconds = self.policy.window_seconds if window_seconds is None else window_seconds
        cutoff = (self._now_fn() - timedelta(seconds=seconds)).isoformat()
        reserved, count = self.store.inference_totals(cutoff)
        rows = self.store.list_inference(100000)
        completed = [row for row in rows if row["status"] == "COMPLETED" and row["created_at"] >= cutoff]
        return {
            "window_seconds": seconds,
            "requests": count,
            "completed": len(completed),
            "reserved_units": reserved,
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in completed),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in completed),
            "actual_units": sum(float(row.get("actual_units") or 0.0) for row in completed),
        }