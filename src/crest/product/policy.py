"""Server-side autonomy and permission policy for CREST 1.0.

The frontend is never the authority.  Every execution step calls
``authorize_action`` against current task state and current application
settings.  Unknown actions fail closed, task-level custom policies can only
narrow permissions, and higher autonomy never means unrestricted access.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KNOWN_ACTIONS = {
    "plan",
    "provider_call",
    "verify",
    "recover",
    "adapt_plan",
    "adapt_model",
    "export",
}

LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "name": "Observe",
        "summary": "Interpret tasks, generate plans, and recommend actions. No execution.",
        "can_execute": False,
        "default_actions": ["plan"],
        "approval": "No provider call is permitted.",
    },
    2: {
        "level": 2,
        "name": "Assisted",
        "summary": "Prepare execution and require approval before provider actions.",
        "can_execute": True,
        "default_actions": ["plan", "provider_call", "verify", "recover"],
        "approval": "Every provider call requires a fresh approval.",
    },
    3: {
        "level": 3,
        "name": "Bounded",
        "summary": "Execute permitted actions inside task scopes and budgets.",
        "can_execute": True,
        "default_actions": ["plan", "provider_call", "verify", "recover"],
        "approval": "High-risk tasks and external providers require approval.",
    },
    4: {
        "level": 4,
        "name": "Adaptive",
        "summary": "Adapt plans and model selection within explicitly granted permissions.",
        "can_execute": True,
        "default_actions": ["plan", "provider_call", "verify", "recover", "adapt_plan", "adapt_model"],
        "approval": "High-risk and privileged actions still require approval.",
    },
    5: {
        "level": 5,
        "name": "Custom",
        "summary": "Task-specific permissions, restrictions, approval rules, budgets, and timeouts.",
        "can_execute": True,
        "default_actions": ["plan", "provider_call", "verify", "recover"],
        "approval": "Custom rules apply; global limits and high-risk approval still apply.",
    },
}

_CUSTOM_KEYS = {
    "allowed_actions",
    "allowed_providers",
    "allowed_models",
    "allowed_risk_classes",
    "require_approval",
    "max_cost",
    "max_tokens",
    "timeout_seconds",
    "notes",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False


def validate_custom_policy(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("custom_policy must be an object")
    unknown = set(raw) - _CUSTOM_KEYS
    if unknown:
        raise ValueError(f"unknown custom_policy keys: {sorted(unknown)}")
    out: dict[str, Any] = {}
    if "allowed_actions" in raw:
        actions = raw["allowed_actions"]
        if not isinstance(actions, list) or not actions:
            raise ValueError("allowed_actions must be a non-empty list")
        clean = sorted({str(a) for a in actions})
        unknown_actions = set(clean) - KNOWN_ACTIONS
        if unknown_actions:
            raise ValueError(f"unknown actions fail closed: {sorted(unknown_actions)}")
        out["allowed_actions"] = clean
    if "allowed_providers" in raw:
        providers = raw["allowed_providers"]
        if not isinstance(providers, list):
            raise ValueError("allowed_providers must be a list")
        out["allowed_providers"] = sorted({str(p) for p in providers})
    if "allowed_models" in raw:
        models = raw["allowed_models"]
        if not isinstance(models, list):
            raise ValueError("allowed_models must be a list")
        out["allowed_models"] = sorted({str(m) for m in models})
    if "allowed_risk_classes" in raw:
        risks = raw["allowed_risk_classes"]
        if not isinstance(risks, list):
            raise ValueError("allowed_risk_classes must be a list")
        clean_risks = sorted({str(r) for r in risks})
        if set(clean_risks) - {"low", "med", "high"}:
            raise ValueError("allowed_risk_classes must contain low, med, or high")
        out["allowed_risk_classes"] = clean_risks
    if "require_approval" in raw:
        if not isinstance(raw["require_approval"], bool):
            raise ValueError("require_approval must be a boolean")
        out["require_approval"] = raw["require_approval"]
    if "max_cost" in raw:
        try:
            value = float(raw["max_cost"])
        except (TypeError, ValueError) as exc:
            raise ValueError("max_cost must be a number") from exc
        if value <= 0:
            raise ValueError("max_cost must be positive")
        out["max_cost"] = value
    if "max_tokens" in raw:
        try:
            value = int(raw["max_tokens"])
        except (TypeError, ValueError) as exc:
            raise ValueError("max_tokens must be an integer") from exc
        if value <= 0:
            raise ValueError("max_tokens must be positive")
        out["max_tokens"] = value
    if "timeout_seconds" in raw:
        try:
            value = float(raw["timeout_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValueError("timeout_seconds must be a number") from exc
        if value <= 0:
            raise ValueError("timeout_seconds must be positive")
        out["timeout_seconds"] = value
    if "notes" in raw:
        if not isinstance(raw["notes"], str) or len(raw["notes"]) > 2000:
            raise ValueError("notes must be a string up to 2000 characters")
        out["notes"] = raw["notes"]
    return out


def level_info() -> list[dict[str, Any]]:
    return [LEVELS[i] for i in sorted(LEVELS)]


def authorize_action(
    *,
    task: dict[str, Any],
    action: str,
    settings: dict[str, Any],
    provider: dict[str, Any] | None = None,
    model: str | None = None,
) -> PolicyDecision:
    if action not in KNOWN_ACTIONS:
        return PolicyDecision(False, f"UNKNOWN_ACTION:{action}")

    level = int(task.get("autonomy_level") or 0)
    max_level = int(settings.get("max_autonomy_level") or 0)
    if level < 1 or level > 5:
        return PolicyDecision(False, "INVALID_AUTONOMY_LEVEL")
    if level > max_level:
        return PolicyDecision(False, f"AUTONOMY_EXCEEDS_GLOBAL_MAX:{level}>{max_level}")

    risk = str(task.get("risk_class") or "low")
    custom = task.get("custom_policy") or None

    if level == 1 and action != "plan":
        return PolicyDecision(False, "OBSERVE_MODE_NO_EXECUTION")
    if level == 2 and action in ("adapt_plan", "adapt_model"):
        return PolicyDecision(False, "ASSISTED_MODE_NO_ADAPTATION")
    if level == 3 and action in ("adapt_plan", "adapt_model"):
        return PolicyDecision(False, "BOUNDED_MODE_NO_ADAPTATION")

    if level == 5:
        if not settings.get("allow_custom_policies", False):
            return PolicyDecision(False, "CUSTOM_POLICIES_DISABLED")
        if not isinstance(custom, dict):
            return PolicyDecision(False, "CUSTOM_POLICY_REQUIRED")
        allowed_actions = custom.get("allowed_actions") or LEVELS[5]["default_actions"]
        if action not in allowed_actions:
            return PolicyDecision(False, f"ACTION_NOT_IN_CUSTOM_POLICY:{action}")
        allowed_providers = custom.get("allowed_providers")
        if allowed_providers is not None and provider is not None:
            if str(provider.get("id")) not in allowed_providers:
                return PolicyDecision(False, f"PROVIDER_NOT_IN_CUSTOM_POLICY:{provider.get('id')}")
        allowed_models = custom.get("allowed_models")
        if allowed_models is not None and model is not None:
            if model not in allowed_models:
                return PolicyDecision(False, f"MODEL_NOT_IN_CUSTOM_POLICY:{model}")
        allowed_risks = custom.get("allowed_risk_classes")
        if allowed_risks is not None and risk not in allowed_risks:
            return PolicyDecision(False, f"RISK_CLASS_NOT_IN_CUSTOM_POLICY:{risk}")
        if float(task.get("budget") or 0) > float(custom.get("max_cost") or float("inf")):
            return PolicyDecision(False, "TASK_BUDGET_EXCEEDS_CUSTOM_POLICY")
        if int(task.get("token_budget") or 0) > int(custom.get("max_tokens") or 10**18):
            return PolicyDecision(False, "TASK_TOKEN_BUDGET_EXCEEDS_CUSTOM_POLICY")
        if float(task.get("timeout_seconds") or 0) > float(custom.get("timeout_seconds") or float("inf")):
            return PolicyDecision(False, "TASK_TIMEOUT_EXCEEDS_CUSTOM_POLICY")

    requires_approval = False
    reasons: list[str] = []

    if level == 2 and action == "provider_call":
        requires_approval = True
        reasons.append("assisted mode requires approval")

    if action == "provider_call" and provider is not None:
        if not bool(provider.get("enabled")):
            return PolicyDecision(False, f"PROVIDER_DISABLED:{provider.get('id')}")
        models = list(provider.get("models") or [])
        if model is not None and models and model not in models:
            return PolicyDecision(False, f"MODEL_NOT_AVAILABLE:{model}")
        if str(provider.get("kind")) != "mock":
            if not settings.get("allow_external_calls", False):
                return PolicyDecision(False, "EXTERNAL_CALLS_DISABLED")
            if settings.get("require_approval_external", True):
                requires_approval = True
                reasons.append("external provider requires approval")

    if risk == "high" and action in ("provider_call", "verify"):
        if settings.get("require_approval_high_risk", True):
            requires_approval = True
            reasons.append("high-risk task requires approval")

    if str(task.get("demo_scenario") or "") == "approval_required" and action == "provider_call":
        requires_approval = True
        reasons.append("offline approval demo")

    if isinstance(custom, dict) and custom.get("require_approval") and action == "provider_call":
        requires_approval = True
        reasons.append("custom policy requires approval")

    return PolicyDecision(
        True,
        "allowed" + (": " + "; ".join(reasons) if reasons else ""),
        requires_approval=requires_approval,
    )


def permissions_matrix(settings: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for info in level_info():
        out.append(
            {
                **info,
                "enabled": int(info["level"]) <= int(settings.get("max_autonomy_level") or 0),
                "global_high_risk_approval": bool(settings.get("require_approval_high_risk")),
                "global_external_approval": bool(settings.get("require_approval_external")),
                "external_calls_enabled": bool(settings.get("allow_external_calls")),
            }
        )
    return out
