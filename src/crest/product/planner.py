"""Deterministic task planner for CREST 1.0.

The planner is intentionally deterministic and local.  It does not call a model
to decide what it is allowed to do.  Plans describe the steps the engine will
execute; the engine re-checks policy before every step.
"""
from __future__ import annotations

from typing import Any


def build_plan(
    task: dict[str, Any],
    *,
    provider: dict[str, Any] | None,
    model: str,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    level = int(task.get("autonomy_level") or 2)
    risk = str(task.get("risk_class") or "low")
    steps: list[dict[str, Any]] = [
        {
            "id": "interpret",
            "name": "Interpret task",
            "action": "plan",
            "description": "Read the task, constraints, risk class, and acceptance criteria.",
        },
        {
            "id": "route",
            "name": "Resolve provider and model",
            "action": "plan",
            "description": f"Resolve {provider.get('name') if provider else 'provider'} / {model} through routing policy.",
        },
        {
            "id": "generate",
            "name": "Generate output",
            "action": "provider_call",
            "description": f"Call the selected provider within {task.get('token_budget')} tokens and {task.get('timeout_seconds')}s.",
        },
        {
            "id": "verify",
            "name": "Verify output",
            "action": "verify",
            "description": "Run deterministic checks and acceptance criteria; record evidence.",
        },
    ]
    if level >= 4:
        steps.append(
            {
                "id": "adapt",
                "name": "Adapt on failure",
                "action": "adapt_model",
                "description": "Adaptive mode may adjust the model or plan within granted permissions.",
            }
        )
    steps.append(
        {
            "id": "gate",
            "name": "Evaluate High-Risk Gate",
            "action": "verify",
            "description": "Apply the Strong High-Risk Gate to applicable acceptance decisions.",
        }
    )
    if int(settings.get("max_recovery_attempts") or 0) > 0 and level >= 3:
        steps.append(
            {
                "id": "recover",
                "name": "Recover on verification failure",
                "action": "recover",
                "description": "Retry within budget; otherwise fail closed without accepting the result.",
            }
        )
    steps.append(
        {
            "id": "finalize",
            "name": "Finalize and audit",
            "action": "plan",
            "description": "Persist status, evidence, gate decision, and audit events.",
        }
    )
    if risk == "high":
        steps.insert(
            4,
            {
                "id": "risk-review",
                "name": "Confirm high-risk evidence sufficiency",
                "action": "verify",
                "description": "High-risk acceptance requires independent evidence; otherwise abstain.",
            },
        )
    return steps
