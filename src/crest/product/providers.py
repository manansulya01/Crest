"""Model provider adapters for CREST 1.0.

Provider calls are never automatic.  The offline mock provider is the default.
External providers require (a) an environment-held API key, (b) the provider to
be enabled, (c) ``allow_external_calls`` to be enabled in settings, and
(d) a routing/task selection.  Connection tests require an explicit
``confirm=true`` request.

No API key is ever written to the database, logs, audit trail, or API response.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class ProviderError(Exception):
    """A provider failed in a way the execution engine must handle."""


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost: float
    model: str
    latency_ms: float
    provider_request_id: str | None = None
    usage_reported: bool = True
    finish_reason: str = "stop"
    raw_meta: dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _cost(row: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1000.0) * float(row.get("input_cost_per_1k") or 0.0)
        + (output_tokens / 1000.0) * float(row.get("output_cost_per_1k") or 0.0),
        8,
    )


class BaseProvider:
    def __init__(self, row: dict[str, Any]):
        self.row = row

    @property
    def id(self) -> str:
        return str(self.row["id"])

    @property
    def kind(self) -> str:
        return str(self.row["kind"])

    @property
    def name(self) -> str:
        return str(self.row["name"])

    @property
    def models(self) -> list[str]:
        raw = self.row.get("models") or []
        return [str(m) for m in raw]

    def key_present(self) -> bool:
        env = str(self.row.get("api_key_env") or "")
        return bool(env and os.environ.get(env))

    def _key(self) -> str:
        env = str(self.row.get("api_key_env") or "")
        key = os.environ.get(env) if env else None
        if not key:
            raise ProviderError(
                f"API key not configured: set the {env or 'provider'} environment variable"
            )
        return key

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        raise NotImplementedError

    def test_connection(self, *, model: str, timeout_seconds: float) -> dict[str, Any]:
        started = time.monotonic()
        response = self.generate(
            model=model,
            prompt="Reply with the single word OK.",
            max_output_tokens=8,
            timeout_seconds=timeout_seconds,
            metadata={"connection_test": True},
        )
        return {
            "ok": True,
            "message": f"{self.name} responded to an explicit connection test.",
            "model": response.model,
            "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost": response.cost,
            "response_preview": response.text[:160],
        }


class MockProvider(BaseProvider):
    """Deterministic offline provider.

    It performs no network I/O and is explicitly labelled as simulated in every
    result.  Demo scenarios exercise real engine code paths (verification
    failure, recovery, approval, budget, denial); the provider itself remains a
    deterministic test double.
    """

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        meta = metadata or {}
        task = meta.get("task") or {}
        scenario = str(meta.get("demo_scenario") or "")
        attempt = int(meta.get("attempt") or 1)
        title = str(task.get("title") or "Untitled task")
        description = str(task.get("description") or "")
        risk = str(task.get("risk_class") or "low")
        fmt = str(task.get("output_format") or "text")

        if scenario == "verification_failure":
            text = (
                "CREST offline mock result\n"
                "The requested operation could not be completed.\n"
                "This output is intentionally failing verification in the offline demo."
            )
        elif scenario == "recovery" and attempt == 1:
            text = (
                "CREST offline mock result\n"
                "The requested operation could not be completed on the first attempt.\n"
                "A recovery retry is available."
            )
        elif fmt == "json":
            text = json.dumps(
                {
                    "provider": "mock",
                    "mode": "offline-simulation",
                    "task": title,
                    "description": description,
                    "risk_class": risk,
                    "summary": f"Simulated completion of: {title}",
                    "note": "This result was produced by the offline mock provider. It is not a real model response.",
                },
                indent=2,
            )
        else:
            text = (
                "CREST offline execution\n"
                f"Task: {title}\n"
                f"Risk class: {risk}\n"
                f"Description: {description or '(none)'}\n"
                f"Summary: Simulated completion of {title}.\n"
                "Note: this result was produced by the offline mock provider; "
                "it is not a real model response and is not evidence of live reliability."
            )

        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(text)
        return ProviderResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=_cost(self.row, input_tokens, output_tokens),
            model=model,
            latency_ms=0.0,
            provider_request_id=f"mock-{uuid.uuid4().hex[:12]}",
            usage_reported=True,
            finish_reason="stop",
            raw_meta={"mode": "offline-simulation", "demo_scenario": scenario},
        )

    def test_connection(self, *, model: str, timeout_seconds: float) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Offline mock provider is available. No network call was made.",
            "model": model,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "response_preview": "OK (offline)",
        }


class GeminiProvider(BaseProvider):
    """Google Gemini generateContent adapter (real network I/O, opt-in)."""

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        key = self._key()
        base = str(self.row.get("base_url") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{base}/models/{model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": int(max_output_tokens),
                "temperature": 0.0,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            # Never include the request URL (it may contain query parameters).
            raise ProviderError(f"Gemini HTTP {exc.code}: {body[:512]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"Gemini request failed: {type(exc).__name__}") from exc
        latency_ms = (time.monotonic() - started) * 1000.0
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("Gemini returned invalid JSON") from exc
        try:
            candidate = parsed["candidates"][0]
            parts = candidate["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts)
            finish_raw = str(candidate.get("finishReason", "STOP")).upper()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Gemini response missing required fields") from exc
        usage = parsed.get("usageMetadata") or {}
        input_tokens = int(usage.get("promptTokenCount") or 0)
        output_tokens = int(usage.get("candidatesTokenCount") or 0)
        finish = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
        }.get(finish_raw, finish_raw.lower())
        if not text:
            raise ProviderError("Gemini returned an empty response")
        return ProviderResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=_cost(self.row, input_tokens, output_tokens),
            model=model,
            latency_ms=latency_ms,
            provider_request_id=parsed.get("responseId"),
            usage_reported=bool(usage),
            finish_reason=finish,
        )


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible chat-completions adapter (real network I/O, opt-in)."""

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        max_output_tokens: int,
        timeout_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        key = self._key()
        base = str(self.row.get("base_url") or "").rstrip("/")
        if not base:
            raise ProviderError("provider base_url is not configured")
        url = base + "/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": int(max_output_tokens),
            "temperature": 0.0,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Provider HTTP {exc.code}: {body[:512]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"Provider request failed: {type(exc).__name__}") from exc
        latency_ms = (time.monotonic() - started) * 1000.0
        try:
            parsed = json.loads(raw.decode("utf-8"))
            choice = parsed["choices"][0]
            text = choice["message"]["content"]
            finish = str(choice.get("finish_reason") or "stop")
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Provider response missing required fields") from exc
        if not isinstance(text, str) or not text:
            raise ProviderError("Provider returned an empty response")
        usage = parsed.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        return ProviderResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=_cost(self.row, input_tokens, output_tokens),
            model=model,
            latency_ms=latency_ms,
            provider_request_id=parsed.get("id"),
            usage_reported=bool(usage),
            finish_reason=finish,
        )


def build_provider(row: dict[str, Any]) -> BaseProvider:
    kind = str(row.get("kind") or "")
    if kind == "mock":
        return MockProvider(row)
    if kind == "gemini":
        return GeminiProvider(row)
    if kind == "openai_compatible":
        return OpenAICompatibleProvider(row)
    raise ProviderError(f"unknown provider kind: {kind or '(empty)'}")


def provider_public(row: dict[str, Any]) -> dict[str, Any]:
    kind = str(row.get("kind") or "")
    external = kind != "mock"
    env = str(row.get("api_key_env") or "")
    key_present = bool(env and os.environ.get(env))
    if not bool(row.get("enabled")):
        status = "disabled"
    elif external and not key_present:
        status = "key_missing"
    else:
        status = "ready"
    return {
        "id": row["id"],
        "kind": kind,
        "name": row["name"],
        "enabled": bool(row.get("enabled")),
        "external": external,
        "base_url": row.get("base_url") or "",
        "api_key_env": env,
        "key_present": key_present,
        "default_model": row.get("default_model") or "",
        "models": list(row.get("models") or []),
        "input_cost_per_1k": float(row.get("input_cost_per_1k") or 0.0),
        "output_cost_per_1k": float(row.get("output_cost_per_1k") or 0.0),
        "max_output_tokens": int(row.get("max_output_tokens") or 1024),
        "timeout_seconds": float(row.get("timeout_seconds") or 60.0),
        "status": status,
        "last_test_status": row.get("last_test_status"),
        "last_test_at": row.get("last_test_at"),
        "last_test_detail": row.get("last_test_detail"),
        "cost_configured": bool(
            float(row.get("input_cost_per_1k") or 0.0)
            or float(row.get("output_cost_per_1k") or 0.0)
        ),
    }


def validate_provider_update(updates: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "name", "enabled", "base_url", "api_key_env", "default_model",
        "models", "input_cost_per_1k", "output_cost_per_1k",
        "max_output_tokens", "timeout_seconds",
    }
    unknown = set(updates) - allowed
    if unknown:
        raise ValueError(f"unknown provider fields: {sorted(unknown)}")
    out: dict[str, Any] = {}
    for key, value in updates.items():
        if key == "name":
            if not isinstance(value, str) or not (1 <= len(value) <= 120):
                raise ValueError("name must be 1..120 characters")
            out[key] = value
        elif key == "enabled":
            if not isinstance(value, bool):
                raise ValueError("enabled must be a boolean")
            out[key] = value
        elif key == "base_url":
            if not isinstance(value, str) or len(value) > 500:
                raise ValueError("base_url must be a string up to 500 characters")
            if value and not (value.startswith("https://") or value.startswith("http://127.0.0.1") or value.startswith("http://localhost")):
                raise ValueError("base_url must use https:// (or a local http:// endpoint)")
            out[key] = value.rstrip("/")
        elif key == "api_key_env":
            if not isinstance(value, str) or (value and not _ENV_NAME.match(value)):
                raise ValueError("api_key_env must be an environment variable name such as GEMINI_API_KEY")
            out[key] = value
        elif key == "default_model":
            if not isinstance(value, str) or not (0 <= len(value) <= 200):
                raise ValueError("default_model must be a string up to 200 characters")
            out[key] = value
        elif key == "models":
            if not isinstance(value, list) or len(value) > 50:
                raise ValueError("models must be a list of up to 50 names")
            clean = []
            for item in value:
                if not isinstance(item, str) or not (1 <= len(item) <= 200):
                    raise ValueError("each model name must be 1..200 characters")
                clean.append(item)
            out[key] = sorted(set(clean))
        elif key in ("input_cost_per_1k", "output_cost_per_1k"):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be a number") from exc
            if number < 0 or number > 1_000_000:
                raise ValueError(f"{key} is out of range")
            out[key] = number
        elif key == "max_output_tokens":
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("max_output_tokens must be an integer") from exc
            if not (1 <= number <= 1_000_000):
                raise ValueError("max_output_tokens is out of range")
            out[key] = number
        elif key == "timeout_seconds":
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("timeout_seconds must be a number") from exc
            if not (1.0 <= number <= 600.0):
                raise ValueError("timeout_seconds must be between 1 and 600")
            out[key] = number
    return out
