"""Policy, verification, provider, and settings unit tests."""
from __future__ import annotations

import os

import pytest

from crest.product.policy import (
    authorize_action,
    permissions_matrix,
    validate_custom_policy,
)
from crest.product.providers import MockProvider, ProviderError, build_provider, provider_public
from crest.product.settings import DEFAULT_SETTINGS, validate_settings
from crest.product.verification import parse_verifier_output, verify_output


def task(overrides=None, **kwargs):
    base = {
        "id": "t1",
        "title": "Task",
        "description": "Description",
        "risk_class": "low",
        "autonomy_level": 3,
        "budget": 1.0,
        "token_budget": 4096,
        "timeout_seconds": 30.0,
        "custom_policy": None,
        "demo_scenario": None,
    }
    base.update(overrides or {})
    base.update(kwargs)
    return base


def settings(**overrides):
    base = dict(DEFAULT_SETTINGS)
    base.update(overrides)
    return base


MOCK = {
    "id": "mock", "kind": "mock", "enabled": 1,
    "models": ["mock-fast"], "name": "Mock",
}


def test_unknown_action_fails_closed():
    decision = authorize_action(task=task(), action="launch_missiles", settings=settings())
    assert not decision.allowed
    assert decision.reason.startswith("UNKNOWN_ACTION")


def test_observe_mode_has_no_execution():
    decision = authorize_action(
        task=task(autonomy_level=1), action="provider_call",
        settings=settings(), provider=MOCK, model="mock-fast",
    )
    assert not decision.allowed
    assert decision.reason == "OBSERVE_MODE_NO_EXECUTION"


def test_assisted_mode_requires_approval():
    decision = authorize_action(
        task=task(autonomy_level=2), action="provider_call",
        settings=settings(), provider=MOCK, model="mock-fast",
    )
    assert decision.allowed
    assert decision.requires_approval


def test_task_cannot_exceed_global_autonomy():
    decision = authorize_action(
        task=task(autonomy_level=5), action="plan",
        settings=settings(max_autonomy_level=3),
    )
    assert not decision.allowed
    assert "AUTONOMY_EXCEEDS_GLOBAL_MAX" in decision.reason


def test_custom_policy_can_only_narrow_permissions():
    policy = {"allowed_actions": ["plan"]}
    decision = authorize_action(
        task=task(autonomy_level=5, custom_policy=policy), action="provider_call",
        settings=settings(max_autonomy_level=5, allow_custom_policies=True),
        provider=MOCK, model="mock-fast",
    )
    assert not decision.allowed
    assert "ACTION_NOT_IN_CUSTOM_POLICY" in decision.reason


def test_custom_policy_rejects_unknown_actions():
    with pytest.raises(ValueError):
        validate_custom_policy({"allowed_actions": ["plan", "root_shell"]})
    with pytest.raises(ValueError):
        validate_custom_policy({"unexpected": True})


def test_custom_policy_provider_and_risk_restrictions():
    policy = {
        "allowed_actions": ["plan", "provider_call", "verify"],
        "allowed_providers": ["other"],
        "allowed_risk_classes": ["low"],
    }
    decision = authorize_action(
        task=task(autonomy_level=5, custom_policy=policy), action="provider_call",
        settings=settings(max_autonomy_level=5, allow_custom_policies=True),
        provider=MOCK, model="mock-fast",
    )
    assert not decision.allowed
    assert "PROVIDER_NOT_IN_CUSTOM_POLICY" in decision.reason


def test_external_calls_disabled_by_default():
    external = {
        "id": "gemini", "kind": "gemini", "enabled": 1,
        "models": ["gemini-2.5-flash"], "name": "Gemini",
    }
    decision = authorize_action(
        task=task(), action="provider_call", settings=settings(),
        provider=external, model="gemini-2.5-flash",
    )
    assert not decision.allowed
    assert decision.reason == "EXTERNAL_CALLS_DISABLED"


def test_high_risk_requires_approval_by_default():
    decision = authorize_action(
        task=task(risk_class="high"), action="provider_call",
        settings=settings(), provider=MOCK, model="mock-fast",
    )
    assert decision.allowed
    assert decision.requires_approval


def test_permissions_matrix_marks_disabled_levels():
    matrix = permissions_matrix(settings(max_autonomy_level=3))
    assert [row["enabled"] for row in matrix] == [True, True, True, False, False]


def test_verification_detects_failure_phrase_and_criteria():
    result = verify_output(
        task({"acceptance_criteria": ["contains:CREST"]}),
        "The requested operation could not be completed.",
    )
    assert not result.passed
    assert any(c["name"] == "failure_phrase" and c["status"] == "fail" for c in result.checks)

    result = verify_output(
        task({"acceptance_criteria": ["contains:CREST"]}), "CREST completed the task."
    )
    assert result.passed
    assert result.has_deterministic_check
    assert result.independent_sources == 0


def test_json_output_format_is_enforced():
    result = verify_output(task({"output_format": "json"}), "not json")
    assert not result.passed
    result = verify_output(task({"output_format": "json"}), '{"ok": true}')
    assert result.passed


def test_provider_verifier_independence_is_explicit():
    result = verify_output(
        task({"acceptance_criteria": []}),
        "A useful result",
        verifier_result={"passed": True, "independent": False, "reason": "same model"},
    )
    assert result.passed
    assert result.independent_sources == 0

    result = verify_output(
        task({"acceptance_criteria": []}),
        "A useful result",
        verifier_result={"passed": True, "independent": True, "reason": "different model"},
    )
    assert result.passed
    assert result.independent_sources == 1


def test_verifier_parser_fails_closed():
    assert parse_verifier_output("not json")["passed"] is False
    assert parse_verifier_output('{"verdict":"PASS","reason":"ok"}')["passed"] is True
    assert parse_verifier_output('```json\n{"verdict":"FAIL","reason":"bad"}\n```')["passed"] is False


def test_mock_provider_is_offline_and_labelled():
    provider = MockProvider({
        "id": "mock", "kind": "mock", "name": "Mock",
        "models": ["mock-fast"], "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
    })
    response = provider.generate(
        model="mock-fast", prompt="prompt", max_output_tokens=64,
        timeout_seconds=1, metadata={"task": {"title": "CREST", "description": "d"}},
    )
    assert "offline mock provider" in response.text.lower()
    assert response.cost == 0.0
    assert response.input_tokens > 0


def test_unknown_provider_kind_fails_closed():
    with pytest.raises(ProviderError):
        build_provider({"id": "x", "kind": "unknown", "name": "x", "models": []})


def test_provider_public_never_exposes_key_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    public = provider_public({
        "id": "gemini", "kind": "gemini", "name": "Gemini", "enabled": 1,
        "api_key_env": "GEMINI_API_KEY", "models": ["m"], "default_model": "m",
    })
    assert public["key_present"] is True
    assert "secret-value" not in str(public)


def test_settings_validation_rejects_inconsistent_limits():
    assert validate_settings({"max_autonomy_level": 4})["max_autonomy_level"] == 4
    with pytest.raises(ValueError):
        validate_settings({"max_autonomy_level": 9})
    with pytest.raises(ValueError):
        validate_settings({"unknown_setting": 1})


def test_provider_mode_requires_verifier_identity():
    with pytest.raises(ValueError):
        from crest.product.settings import _cross_validate

        _cross_validate({
            **DEFAULT_SETTINGS,
            "verification_mode": "provider",
            "verifier_provider": "",
            "verifier_model": "",
        })
