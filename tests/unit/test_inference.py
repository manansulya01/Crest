"""Tests for the V0.5 model-inference runtime."""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import pytest

from crest.config import CrestConfig, default_yaml, load
from crest.inference import (
    FakeModelAdapter,
    HttpChatAdapter,
    InferenceDenied,
    InferencePolicy,
    InferenceRequest,
    InferenceRuntime,
)
from crest.store import Store


def _store(tmp_path: Path) -> Store:
    return Store(tmp_path / ".crest" / "crest.db")


def _policy(**overrides) -> InferencePolicy:
    values = {
        "allowed_models": ("fake-echo",),
        "max_input_tokens": 64,
        "max_output_tokens": 64,
        "max_prompt_chars": 1000,
        "max_output_chars": 1000,
        "max_cost_units_per_request": 1000.0,
        "window_seconds": 3600.0,
        "window_budget_units": 1000.0,
        "request_timeout_seconds": 1.0,
    }
    values.update(overrides)
    return InferencePolicy(**values)


def _request(**overrides) -> InferenceRequest:
    values = {
        "request_id": "req-00000001",
        "model": "fake-echo",
        "prompt": "hello inference runtime",
        "max_output_tokens": 16,
        "agent_id": "agent-a",
    }
    values.update(overrides)
    return InferenceRequest(**values)


def test_inference_policy_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        InferencePolicy(max_input_tokens=0)
    with pytest.raises(ValueError):
        InferencePolicy(window_budget_units=0)
    with pytest.raises(ValueError):
        InferencePolicy(allowed_models=())


def test_request_validation_rejects_bad_input():
    policy = _policy()
    with pytest.raises(ValueError):
        InferenceRequest(request_id="", model="fake-echo", prompt="x", max_output_tokens=4).validate(policy)
    with pytest.raises(ValueError):
        InferenceRequest(request_id="req", model="fake-echo", prompt="", max_output_tokens=4).validate(policy)
    with pytest.raises(ValueError):
        InferenceRequest(request_id="req", model="fake-echo", prompt="x", max_output_tokens=1000).validate(policy)


def test_fake_adapter_is_deterministic():
    adapter = FakeModelAdapter()
    request = _request()
    policy = _policy()
    first = adapter.complete(request, timeout_seconds=1.0)
    second = adapter.complete(request, timeout_seconds=1.0)
    assert first.text == second.text
    assert first.usage == second.usage
    assert first.finish_reason == "stop"


def test_successful_inference_records_usage_and_budget(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter()
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is True
    assert result.reason == "OK"
    assert result.response is not None
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert result.actual_units <= result.reserved_units
    assert result.charged_units == result.reserved_units
    row = store.get_inference("req-00000001")
    assert row is not None
    assert row["status"] == "COMPLETED"
    assert row["input_tokens"] == result.input_tokens
    assert row["output_tokens"] == result.output_tokens
    assert store.list_inference()[0]["request_id"] == "req-00000001"
    audits = store.recent_audit(10)
    assert any(a["tool"] == "model" and a["decision"] == "ALLOW" for a in audits)
    summary = runtime.usage_summary()
    assert summary["completed"] == 1
    assert summary["input_tokens"] == result.input_tokens
    store.close()


def test_duplicate_request_is_denied_without_adapter_call(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter()
    runtime = InferenceRuntime(store, policy, adapter)
    first = runtime.infer(_request())
    assert first.allowed is True
    second = runtime.infer(_request())
    assert second.allowed is False
    assert second.reason == "DUPLICATE_REQUEST"
    assert len(adapter.calls) == 1
    store.close()


def test_model_not_allowed_does_not_reserve_budget(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter()
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request(model="not-allowed"))
    assert result.allowed is False
    assert result.reason == "MODEL_NOT_ALLOWED"
    assert store.get_inference("req-00000001") is None
    assert len(adapter.calls) == 0
    store.close()


def test_budget_exhaustion_denies_second_request(tmp_path):
    store = _store(tmp_path)
    policy = _policy(
        max_input_tokens=8,
        max_output_tokens=8,
        window_budget_units=20.0,
        max_cost_units_per_request=100.0,
    )
    adapter = FakeModelAdapter()
    runtime = InferenceRuntime(store, policy, adapter)
    first = runtime.infer(_request(request_id="req-00000001", max_output_tokens=8))
    assert first.allowed is True
    second = runtime.infer(_request(request_id="req-00000002", max_output_tokens=8))
    assert second.allowed is False
    assert second.reason == "BUDGET_EXCEEDED"
    assert len(adapter.calls) == 1
    store.close()


def test_invalid_response_marks_request_invalid(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter(failure_mode="malformed")
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is False
    assert result.reason == "INVALID_RESPONSE"
    row = store.get_inference("req-00000001")
    assert row is not None
    assert row["status"] == "INVALID"
    store.close()


def test_timeout_marks_request_timed_out(tmp_path):
    store = _store(tmp_path)
    policy = _policy(request_timeout_seconds=0.05)
    adapter = FakeModelAdapter(sleep_seconds=1.0)
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is False
    assert result.reason == "TIMEOUT"
    row = store.get_inference("req-00000001")
    assert row is not None
    assert row["status"] == "TIMED_OUT"
    store.close()


def test_adapter_exception_marks_request_failed(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter(failure_mode="exception")
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is False
    assert result.reason == "ADAPTER_ERROR"
    row = store.get_inference("req-00000001")
    assert row is not None
    assert row["status"] == "FAILED"
    store.close()


def test_empty_response_is_rejected(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter(failure_mode="empty")
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is False
    assert result.reason == "INVALID_RESPONSE"
    store.close()


def test_wrong_model_response_is_rejected(tmp_path):
    store = _store(tmp_path)
    policy = _policy()
    adapter = FakeModelAdapter(failure_mode="wrong_model")
    runtime = InferenceRuntime(store, policy, adapter)
    result = runtime.infer(_request())
    assert result.allowed is False
    assert result.reason == "INVALID_RESPONSE"
    store.close()


def test_http_adapter_parses_openai_compatible_response(monkeypatch):
    adapter = HttpChatAdapter(base_url="https://example.test/v1", api_key="secret", model="gpt-test")

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id":"chatcmpl-1","choices":[{"message":{"content":"hello"},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":2}}'

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=...: _Response())
    request = _request(model="gpt-test", prompt="hi")
    response = adapter.complete(request, timeout_seconds=1.0)
    assert response.text == "hello"
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 2
    assert response.provider_request_id == "chatcmpl-1"


def test_http_adapter_rejects_http_error(monkeypatch):
    adapter = HttpChatAdapter(base_url="https://example.test/v1", api_key="secret", model="gpt-test")

    def fail(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "rate limited", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    request = _request(model="gpt-test", prompt="hi")
    with pytest.raises(Exception):
        adapter.complete(request, timeout_seconds=1.0)


def test_store_schema_includes_inference_ledger(tmp_path):
    store = _store(tmp_path)
    assert [h[0] for h in store.migration_history()] == [1, 2, 3]
    assert store.get_inference("missing") is None
    store.close()


def test_config_default_yaml_round_trips_inference_policy(tmp_path):
    (tmp_path / "crest.yaml").write_text(default_yaml(tmp_path), encoding="utf-8")
    cfg = load(tmp_path / "crest.yaml")
    assert "fake-echo" in cfg.inference_policy.allowed_models
    assert cfg.inference_policy.max_output_tokens == 1024
    assert cfg.inference_policy.window_budget_units == 100000.0


def test_config_rejects_bad_inference_policy(tmp_path):
    (tmp_path / "crest.yaml").write_text(
        default_yaml(tmp_path).replace("window_budget_units: 100000.0", "window_budget_units: 0"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load(tmp_path / "crest.yaml")