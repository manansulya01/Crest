"""Typed application settings for CREST 1.0.

Settings are stored in SQLite as JSON values.  Only declared keys are accepted;
unknown keys fail closed.  Secrets are never stored here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .db import Database

DEFAULT_SETTINGS: dict[str, Any] = {
    "default_autonomy_level": 2,
    "max_autonomy_level": 3,
    "default_risk_class": "low",
    "default_budget": 1.0,
    "max_task_budget": 10.0,
    "default_token_budget": 4096,
    "max_token_budget": 32768,
    "default_timeout_seconds": 60.0,
    "max_execution_seconds": 120.0,
    "default_provider": "mock",
    "default_model": "mock-fast",
    "allow_external_calls": False,
    "require_approval_high_risk": True,
    "require_approval_external": True,
    "allow_custom_policies": True,
    "max_recovery_attempts": 1,
    "verification_mode": "deterministic",
    "verifier_provider": "",
    "verifier_model": "",
    "routing_fallback_enabled": False,
    "retention_enabled": False,
    "retention_days": 30,
}

_ENUMS = {
    "default_risk_class": {"low", "med", "high"},
    "verification_mode": {"deterministic", "provider"},
}

_RANGES = {
    "default_autonomy_level": (1, 5),
    "max_autonomy_level": (1, 5),
    "default_budget": (0.000001, 1000000.0),
    "max_task_budget": (0.000001, 1000000.0),
    "default_token_budget": (1, 10_000_000),
    "max_token_budget": (1, 10_000_000),
    "default_timeout_seconds": (1.0, 3600.0),
    "max_execution_seconds": (1.0, 3600.0),
    "max_recovery_attempts": (0, 3),
    "retention_days": (1, 3650),
}


def _parse(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _coerce(key: str, value: Any) -> Any:
    if key in ("allow_external_calls", "require_approval_high_risk",
               "require_approval_external", "allow_custom_policies",
               "routing_fallback_enabled", "retention_enabled"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "1", "yes"):
            return True
        if isinstance(value, str) and value.lower() in ("false", "0", "no"):
            return False
        raise ValueError(f"{key} must be a boolean")
    if key in ("default_autonomy_level", "max_autonomy_level",
               "default_token_budget", "max_token_budget",
               "max_recovery_attempts", "retention_days"):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be an integer") from exc
    if key in ("default_budget", "max_task_budget",
               "default_timeout_seconds", "max_execution_seconds"):
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number") from exc
    if key in _ENUMS:
        if value not in _ENUMS[key]:
            raise ValueError(f"{key} must be one of {sorted(_ENUMS[key])}")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def validate_settings(updates: dict[str, Any]) -> dict[str, Any]:
    unknown = set(updates) - set(DEFAULT_SETTINGS)
    if unknown:
        raise ValueError(f"unknown settings: {sorted(unknown)}")
    out: dict[str, Any] = {}
    for key, value in updates.items():
        coerced = _coerce(key, value)
        if key in _RANGES:
            low, high = _RANGES[key]
            if not (low <= coerced <= high):
                raise ValueError(f"{key} must be between {low} and {high}")
        out[key] = coerced
    return out


def _cross_validate(settings: dict[str, Any]) -> None:
    if settings["default_autonomy_level"] > settings["max_autonomy_level"]:
        raise ValueError("default_autonomy_level cannot exceed max_autonomy_level")
    if settings["default_budget"] > settings["max_task_budget"]:
        raise ValueError("default_budget cannot exceed max_task_budget")
    if settings["default_token_budget"] > settings["max_token_budget"]:
        raise ValueError("default_token_budget cannot exceed max_token_budget")
    if settings["default_timeout_seconds"] > settings["max_execution_seconds"]:
        raise ValueError("default_timeout_seconds cannot exceed max_execution_seconds")
    if settings["verification_mode"] == "provider":
        if not settings["verifier_provider"] or not settings["verifier_model"]:
            raise ValueError(
                "verification_mode=provider requires verifier_provider and verifier_model"
            )


def get_settings(db: Database) -> dict[str, Any]:
    with db.read() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = dict(DEFAULT_SETTINGS)
    for row in rows:
        key = row["key"]
        if key in DEFAULT_SETTINGS:
            try:
                settings[key] = _coerce(key, _parse(row["value"]))
            except ValueError:
                # A corrupt setting must not silently widen permissions.
                settings[key] = DEFAULT_SETTINGS[key]
    return settings


def update_settings(db: Database, updates: dict[str, Any]) -> dict[str, Any]:
    clean = validate_settings(updates)
    current = get_settings(db)
    merged = {**current, **clean}
    _cross_validate(merged)
    ts = datetime.now(timezone.utc).isoformat()
    with db.tx() as conn:
        for key, value in clean.items():
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,?)",
                (key, json.dumps(value, separators=(",", ":")), ts),
            )
    return get_settings(db)


def settings_public(db: Database) -> dict[str, Any]:
    return get_settings(db)
