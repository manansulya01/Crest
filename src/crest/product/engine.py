"""CREST 1.0 execution engine.

The engine is the only path that creates executions.  It enforces autonomy,
provider, budget, approval, verification, recovery, and High-Risk Gate rules
server-side.  Every decision is persisted as evidence and audit history.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..high_risk_gate import GateDecision, GateResult, evaluate_high_risk_gate
from ..redaction import redact
from .db import Database, now_iso
from .planner import build_plan
from .policy import authorize_action, level_info, validate_custom_policy
from .providers import (
    ProviderError,
    build_provider,
    estimate_tokens,
    provider_public,
    validate_provider_update,
)
from .settings import get_settings, update_settings
from .verification import (
    VerificationResult,
    build_verifier_prompt,
    parse_verifier_output,
    verify_output,
)

VERSION = "1.0.0"
TERMINAL_TASK_STATUSES = {
    "completed", "failed", "abstained", "denied", "budget_exhausted",
    "cancelled", "rejected", "interrupted", "timed_out",
}
DEMO_SCENARIOS = {None, "", "verification_failure", "recovery", "approval_required"}


class ProductError(Exception):
    """Base class for product-layer errors."""


class TaskNotFound(ProductError):
    pass


class ConflictError(ProductError):
    pass


class ValidationError(ProductError):
    pass


class PolicyDeniedError(ProductError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ProviderUnavailableError(ProductError):
    pass


def _loads(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _task_from_row(row: Any) -> dict[str, Any]:
    task = dict(row)
    task["acceptance_criteria"] = _loads(task.get("acceptance_criteria"), [])
    task["custom_policy"] = _loads(task.get("custom_policy"), None)
    return task


def _provider_from_row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    provider = dict(row)
    provider["models"] = _loads(provider.get("models_json"), [])
    return provider


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redact_text(text: str) -> str:
    return str(redact(text))


class ProductEngine:
    def __init__(self, db: Database):
        self.db = db
        self.started_at = now_iso()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="crest-exec")
        self._start_lock = threading.Lock()
        self._shutdown = threading.Event()

    # ------------------------------------------------------------------ audit
    def _audit(
        self,
        *,
        task_id: str | None,
        execution_id: str | None,
        event_type: str,
        detail: Any = None,
        actor: str = "system",
        conn: Any = None,
    ) -> None:
        payload = json.dumps(redact(detail or {}), sort_keys=True, default=str)
        params = (task_id, execution_id, event_type, actor, payload, now_iso())
        if conn is not None:
            conn.execute(
                """INSERT INTO audit_events
                   (task_id, execution_id, event_type, actor, detail, timestamp)
                   VALUES (?,?,?,?,?,?)""",
                params,
            )
            return
        with self.db.tx() as tx:
            tx.execute(
                """INSERT INTO audit_events
                   (task_id, execution_id, event_type, actor, detail, timestamp)
                   VALUES (?,?,?,?,?,?)""",
                params,
            )

    # --------------------------------------------------------------- helpers
    def _task_row(self, task_id: str, *, include_deleted: bool = False) -> dict[str, Any]:
        with self.db.read() as conn:
            if include_deleted:
                row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL", (task_id,)
                ).fetchone()
        if row is None:
            raise TaskNotFound(f"task {task_id} not found")
        return _task_from_row(row)

    def _provider_row(self, provider_id: str) -> dict[str, Any]:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        if row is None:
            raise ValidationError(f"provider {provider_id!r} does not exist")
        return _provider_from_row(row)  # type: ignore[return-value]

    def _latest_plan(self, task_id: str) -> dict[str, Any] | None:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT * FROM plans WHERE task_id=? ORDER BY version DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        plan = dict(row)
        plan["steps"] = _loads(plan.pop("steps_json"), [])
        return plan

    def _execution_row(self, execution_id: str) -> dict[str, Any]:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT * FROM executions WHERE id=?", (execution_id,)
            ).fetchone()
        if row is None:
            raise TaskNotFound(f"execution {execution_id} not found")
        execution = dict(row)
        execution["detail"] = _loads(execution.pop("detail_json"), {})
        return execution

    def _approval_row(self, approval_id: str | None) -> dict[str, Any] | None:
        if not approval_id:
            return None
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return dict(row) if row else None

    def _policy_fingerprint(self, task: dict[str, Any], settings: dict[str, Any]) -> str:
        payload = {
            "task_id": task.get("id"),
            "title": task.get("title"),
            "description": task.get("description"),
            "risk_class": task.get("risk_class"),
            "autonomy_level": task.get("autonomy_level"),
            "budget": task.get("budget"),
            "token_budget": task.get("token_budget"),
            "timeout_seconds": task.get("timeout_seconds"),
            "acceptance_criteria": task.get("acceptance_criteria"),
            "output_format": task.get("output_format"),
            "demo_scenario": task.get("demo_scenario"),
            "custom_policy": task.get("custom_policy"),
            "provider": task.get("provider"),
            "model": task.get("model"),
            "max_autonomy_level": settings.get("max_autonomy_level"),
            "allow_external_calls": settings.get("allow_external_calls"),
            "require_approval_high_risk": settings.get("require_approval_high_risk"),
            "require_approval_external": settings.get("require_approval_external"),
            "allow_custom_policies": settings.get("allow_custom_policies"),
        }
        return _sha256(json.dumps(payload, sort_keys=True, default=str))

    def _resolve_route(
        self, task: dict[str, Any], settings: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str, bool]:
        candidates: list[tuple[str, str, str]] = []
        if task.get("provider") and task.get("model"):
            candidates.append((str(task["provider"]), str(task["model"]), "task override"))
        with self.db.read() as conn:
            rules = conn.execute(
                "SELECT * FROM routing_rules WHERE enabled=1 ORDER BY priority ASC, id ASC"
            ).fetchall()
        for rule in rules:
            if rule["risk_class"] in (task.get("risk_class"), "*"):
                candidates.append((rule["provider"], rule["model"], f"routing rule #{rule['id']}"))
        candidates.append(
            (settings["default_provider"], settings["default_model"], "application default")
        )

        seen: set[tuple[str, str]] = set()
        first_error: str | None = None
        fallback_used = False
        for provider_id, model, reason in candidates:
            if (provider_id, model) in seen:
                continue
            seen.add((provider_id, model))
            try:
                provider = self._provider_row(provider_id)
                if not bool(provider.get("enabled")):
                    raise ProviderUnavailableError(f"provider {provider_id!r} is disabled")
                models = list(provider.get("models") or [])
                if not model or (models and model not in models):
                    raise ProviderUnavailableError(
                        f"model {model!r} is not configured for provider {provider_id!r}"
                    )
                if str(provider.get("kind")) != "mock" and not provider_public(provider)["key_present"]:
                    raise ProviderUnavailableError(
                        f"provider {provider_id!r} has no API key in {provider.get('api_key_env')}"
                    )
                return provider, model, reason, fallback_used
            except (ValidationError, ProviderUnavailableError) as exc:
                first_error = first_error or str(exc)
                fallback_used = True
                if not settings.get("routing_fallback_enabled", False):
                    raise ProviderUnavailableError(str(exc)) from exc
        raise ProviderUnavailableError(first_error or "no provider route is available")

    def _ensure_plan(
        self,
        task: dict[str, Any],
        provider: dict[str, Any],
        model: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._latest_plan(str(task["id"]))
        if existing is not None:
            return existing
        steps = build_plan(task, provider=provider, model=model, settings=settings)
        plan_id = uuid.uuid4().hex
        with self.db.tx() as conn:
            version = int(
                conn.execute(
                    "SELECT COALESCE(MAX(version),0) FROM plans WHERE task_id=?",
                    (task["id"],),
                ).fetchone()[0]
            ) + 1
            conn.execute(
                "INSERT INTO plans (id, task_id, version, steps_json, created_at) VALUES (?,?,?,?,?)",
                (plan_id, task["id"], version, json.dumps(steps), now_iso()),
            )
            self._audit(
                task_id=task["id"], execution_id=None, event_type="PLAN_CREATED",
                detail={"plan_id": plan_id, "version": version, "steps": len(steps)}, conn=conn,
            )
        return {
            "id": plan_id, "task_id": task["id"], "version": version,
            "steps": steps, "created_at": now_iso(),
        }

    # ------------------------------------------------------------------ tasks
    def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings(self.db)
        idem = data.get("idempotency_key")
        if idem:
            with self.db.read() as conn:
                existing = conn.execute(
                    "SELECT id FROM tasks WHERE idempotency_key=? AND deleted_at IS NULL",
                    (idem,),
                ).fetchone()
            if existing:
                return self.get_task(existing["id"])

        provider_id = str(data.get("provider") or settings["default_provider"])
        provider = self._provider_row(provider_id)
        model = str(data.get("model") or provider.get("default_model") or "")
        if not model:
            raise ValidationError("a model is required")
        if provider.get("models") and model not in provider["models"]:
            raise ValidationError(f"model {model!r} is not configured for provider {provider_id!r}")

        autonomy = int(data.get("autonomy_level") or settings["default_autonomy_level"])
        if autonomy < 1 or autonomy > 5:
            raise ValidationError("autonomy_level must be between 1 and 5")
        if autonomy > int(settings["max_autonomy_level"]):
            raise PolicyDeniedError(
                f"AUTONOMY_EXCEEDS_GLOBAL_MAX:{autonomy}>{settings['max_autonomy_level']}"
            )
        risk = str(data.get("risk_class") or settings["default_risk_class"])
        if risk not in ("low", "med", "high"):
            raise ValidationError("risk_class must be low, med, or high")

        budget = float(data.get("budget") if data.get("budget") is not None else settings["default_budget"])
        if budget <= 0 or budget > float(settings["max_task_budget"]):
            raise ValidationError(f"budget must be between 0 and {settings['max_task_budget']}")
        token_budget = int(
            data.get("token_budget") if data.get("token_budget") is not None else settings["default_token_budget"]
        )
        if token_budget <= 0 or token_budget > int(settings["max_token_budget"]):
            raise ValidationError(f"token_budget must be between 1 and {settings['max_token_budget']}")
        timeout = float(
            data.get("timeout_seconds") if data.get("timeout_seconds") is not None else settings["default_timeout_seconds"]
        )
        if timeout <= 0 or timeout > float(settings["max_execution_seconds"]):
            raise ValidationError(f"timeout_seconds must be between 0 and {settings['max_execution_seconds']}")

        criteria = data.get("acceptance_criteria") or []
        if not isinstance(criteria, list) or len(criteria) > 20:
            raise ValidationError("acceptance_criteria must be a list of up to 20 strings")
        criteria = [str(c) for c in criteria]
        if any(len(c) > 500 for c in criteria):
            raise ValidationError("each acceptance criterion must be at most 500 characters")
        output_format = str(data.get("output_format") or "text")
        if output_format not in ("text", "json"):
            raise ValidationError("output_format must be text or json")

        custom_policy = validate_custom_policy(data.get("custom_policy"))
        if autonomy == 5 and custom_policy is None:
            raise ValidationError("autonomy level 5 requires an explicit custom_policy object")
        if autonomy != 5 and custom_policy is not None:
            raise ValidationError("custom_policy is only allowed at autonomy level 5")

        demo = data.get("demo_scenario") or None
        if demo not in DEMO_SCENARIOS:
            raise ValidationError("unknown demo_scenario")
        if demo and str(provider.get("kind")) != "mock":
            raise ValidationError("demo scenarios are only available with the offline mock provider")

        task_id = uuid.uuid4().hex
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                """INSERT INTO tasks
                   (id, idempotency_key, title, description, risk_class, autonomy_level,
                    status, provider, model, budget, token_budget, timeout_seconds,
                    acceptance_criteria, output_format, demo_scenario, custom_policy,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    task_id, idem, str(data["title"]).strip(), str(data.get("description") or ""),
                    risk, autonomy, "pending", provider_id, model, budget, token_budget,
                    timeout, json.dumps(criteria), output_format, demo,
                    json.dumps(custom_policy) if custom_policy is not None else None, ts, ts,
                ),
            )
            self._audit(
                task_id=task_id, execution_id=None, event_type="TASK_CREATED",
                detail={
                    "title": data["title"], "risk_class": risk, "autonomy_level": autonomy,
                    "provider": provider_id, "model": model,
                }, conn=conn,
            )
        return self.get_task(task_id)

    def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        task = self._task_row(task_id)
        if task["status"] in ("queued", "running"):
            raise ConflictError("cannot edit a task while it is running")
        settings = get_settings(self.db)

        provider_id = str(data.get("provider", task["provider"]) or settings["default_provider"])
        provider = self._provider_row(provider_id)
        model = str(data.get("model", task["model"]) or provider.get("default_model") or "")
        if provider.get("models") and model not in provider["models"]:
            raise ValidationError(f"model {model!r} is not configured for provider {provider_id!r}")
        autonomy = int(data.get("autonomy_level", task["autonomy_level"]))
        if autonomy > int(settings["max_autonomy_level"]):
            raise PolicyDeniedError(
                f"AUTONOMY_EXCEEDS_GLOBAL_MAX:{autonomy}>{settings['max_autonomy_level']}"
            )
        risk = str(data.get("risk_class", task["risk_class"]))
        if risk not in ("low", "med", "high"):
            raise ValidationError("risk_class must be low, med, or high")
        budget = float(data.get("budget", task["budget"]))
        if budget <= 0 or budget > float(settings["max_task_budget"]):
            raise ValidationError("budget is outside the configured maximum")
        token_budget = int(data.get("token_budget", task["token_budget"]))
        if token_budget <= 0 or token_budget > int(settings["max_token_budget"]):
            raise ValidationError("token_budget is outside the configured maximum")
        timeout = float(data.get("timeout_seconds", task["timeout_seconds"]))
        if timeout <= 0 or timeout > float(settings["max_execution_seconds"]):
            raise ValidationError("timeout_seconds is outside the configured maximum")

        criteria = data.get("acceptance_criteria", task["acceptance_criteria"])
        if not isinstance(criteria, list) or len(criteria) > 20:
            raise ValidationError("acceptance_criteria must be a list of up to 20 strings")
        criteria = [str(c) for c in criteria]
        if any(len(c) > 500 for c in criteria):
            raise ValidationError("each acceptance criterion must be at most 500 characters")

        custom_policy = validate_custom_policy(
            data.get("custom_policy", task.get("custom_policy"))
        )
        if autonomy == 5 and custom_policy is None:
            raise ValidationError("autonomy level 5 requires an explicit custom_policy object")
        if autonomy != 5:
            custom_policy = None
        demo = data.get("demo_scenario", task.get("demo_scenario")) or None
        if demo not in DEMO_SCENARIOS:
            raise ValidationError("unknown demo_scenario")
        if demo and str(provider.get("kind")) != "mock":
            raise ValidationError("demo scenarios are only available with the offline mock provider")
        output_format = str(data.get("output_format", task["output_format"]))
        if output_format not in ("text", "json"):
            raise ValidationError("output_format must be text or json")

        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                """UPDATE tasks SET
                   title=?, description=?, risk_class=?, autonomy_level=?, provider=?, model=?,
                   budget=?, token_budget=?, timeout_seconds=?, acceptance_criteria=?,
                   output_format=?, demo_scenario=?, custom_policy=?,
                   status='pending', result=NULL, result_hash=NULL, verification_status=NULL,
                   gate_decision=NULL, gate_reason=NULL, error=NULL, completed_at=NULL,
                   updated_at=?
                   WHERE id=?""",
                (
                    str(data.get("title", task["title"])).strip(),
                    str(data.get("description", task["description"])),
                    risk, autonomy, provider_id, model, budget, token_budget, timeout,
                    json.dumps(criteria), output_format, demo,
                    json.dumps(custom_policy) if custom_policy is not None else None,
                    ts, task_id,
                ),
            )
            conn.execute(
                "UPDATE approvals SET status='expired' WHERE task_id=? AND status IN ('pending','approved') AND consumed_at IS NULL",
                (task_id,),
            )
            self._audit(
                task_id=task_id, execution_id=None, event_type="TASK_UPDATED",
                detail={"status_reset": "pending", "approvals_expired": True}, conn=conn,
            )
        return self.get_task(task_id)

    def delete_task(self, task_id: str, *, hard: bool = False) -> dict[str, Any]:
        task = self._task_row(task_id)
        if task["status"] in ("queued", "running"):
            raise ConflictError("cannot delete a task while it is running")
        if hard:
            with self.db.tx() as conn:
                self._audit(
                    task_id=task_id, execution_id=None, event_type="TASK_PURGED",
                    detail={"title": task["title"], "hard": True}, conn=conn,
                )
                conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return {"id": task_id, "deleted": True, "hard": True}
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE tasks SET deleted_at=?, updated_at=? WHERE id=?",
                (now_iso(), now_iso(), task_id),
            )
            conn.execute(
                "UPDATE approvals SET status='expired' WHERE task_id=? AND status='pending'",
                (task_id,),
            )
            self._audit(
                task_id=task_id, execution_id=None, event_type="TASK_DELETED",
                detail={"title": task["title"], "hard": False}, conn=conn,
            )
        return {"id": task_id, "deleted": True, "hard": False}

    def list_tasks(
        self,
        *,
        status: str | None = None,
        risk_class: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        where = ["deleted_at IS NULL"]
        params: list[Any] = []
        if status:
            where.append("status=?")
            params.append(status)
        if risk_class:
            where.append("risk_class=?")
            params.append(risk_class)
        if search:
            where.append("(title LIKE ? OR description LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        clause = " AND ".join(where)
        with self.db.read() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) FROM tasks WHERE {clause}", params).fetchone()[0])
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        items = []
        for row in rows:
            task = _task_from_row(row)
            task["result_preview"] = (task.get("result") or "")[:280]
            task.pop("result", None)
            items.append(task)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_task(self, task_id: str, *, include_children: bool = True) -> dict[str, Any]:
        task = self._task_row(task_id)
        settings = get_settings(self.db)
        try:
            provider = self._provider_row(str(task.get("provider") or ""))
        except ValidationError:
            provider = None
        task["provider_name"] = provider.get("name") if provider else None
        task["provider_kind"] = provider.get("kind") if provider else None
        task["is_mock"] = bool(provider and provider.get("kind") == "mock")
        task["budget_remaining"] = max(0.0, float(task["budget"]) - float(task.get("cost") or 0.0))
        task["token_remaining"] = max(
            0, int(task["token_budget"]) - int(task.get("input_tokens") or 0) - int(task.get("output_tokens") or 0)
        )
        task["policy_fingerprint"] = self._policy_fingerprint(task, settings)
        if not include_children:
            return task

        task["plan"] = self._latest_plan(task_id)
        with self.db.read() as conn:
            executions = [dict(r) for r in conn.execute(
                "SELECT * FROM executions WHERE task_id=? ORDER BY attempt ASC, started_at ASC",
                (task_id,),
            ).fetchall()]
            evidence = [dict(r) for r in conn.execute(
                "SELECT * FROM evidence WHERE task_id=? ORDER BY created_at ASC", (task_id,)
            ).fetchall()]
            approvals = [dict(r) for r in conn.execute(
                "SELECT * FROM approvals WHERE task_id=? ORDER BY requested_at DESC", (task_id,)
            ).fetchall()]
            events = [dict(r) for r in conn.execute(
                "SELECT * FROM audit_events WHERE task_id=? ORDER BY timestamp ASC, id ASC",
                (task_id,),
            ).fetchall()]
            steps = [dict(r) for r in conn.execute(
                """SELECT s.* FROM execution_steps s
                   JOIN executions e ON e.id=s.execution_id
                   WHERE e.task_id=? ORDER BY s.execution_id, s.seq""",
                (task_id,),
            ).fetchall()]
        steps_by_exec: dict[str, list[dict[str, Any]]] = {}
        for step in steps:
            step["detail"] = _loads(step.pop("detail_json"), {})
            steps_by_exec.setdefault(step["execution_id"], []).append(step)
        for execution in executions:
            execution["detail"] = _loads(execution.pop("detail_json"), {})
            execution["steps"] = steps_by_exec.get(execution["id"], [])
        for item in evidence:
            item["provenance"] = _loads(item.pop("provenance_json"), {})
            item["independent"] = bool(item["independent"])
        task["executions"] = executions
        task["evidence"] = evidence
        task["approvals"] = approvals
        task["events"] = events
        return task

    # --------------------------------------------------------------- planning
    def plan_task(self, task_id: str) -> dict[str, Any]:
        task = self._task_row(task_id)
        settings = get_settings(self.db)
        provider, model, reason, _fallback = self._resolve_route(task, settings)
        plan = self._ensure_plan(task, provider, model, settings)
        return {**plan, "route_reason": reason, "provider": provider["id"], "model": model}

    # -------------------------------------------------------------- execution
    def _find_valid_approval(
        self, task: dict[str, Any], action: str, settings: dict[str, Any]
    ) -> dict[str, Any] | None:
        fingerprint = self._policy_fingerprint(task, settings)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with self.db.read() as conn:
            row = conn.execute(
                """SELECT * FROM approvals
                   WHERE task_id=? AND action=? AND status='approved'
                     AND consumed_at IS NULL AND policy_fingerprint=?
                     AND decided_at>=?
                   ORDER BY decided_at DESC LIMIT 1""",
                (task["id"], action, fingerprint, cutoff),
            ).fetchone()
        return dict(row) if row else None

    def _request_approval(
        self,
        task: dict[str, Any],
        action: str,
        reason: str,
        settings: dict[str, Any],
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = self._policy_fingerprint(task, settings)
        with self.db.read() as conn:
            existing = conn.execute(
                """SELECT * FROM approvals
                   WHERE task_id=? AND action=? AND status='pending' AND policy_fingerprint=?
                   ORDER BY requested_at DESC LIMIT 1""",
                (task["id"], action, fingerprint),
            ).fetchone()
        if existing:
            return dict(existing)
        approval_id = uuid.uuid4().hex
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                """INSERT INTO approvals
                   (id, task_id, execution_id, action, status, reason, note,
                    policy_fingerprint, requested_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (approval_id, task["id"], execution_id, action, "pending", reason, "", fingerprint, ts),
            )
            conn.execute(
                "UPDATE tasks SET status='awaiting_approval', updated_at=? WHERE id=?",
                (ts, task["id"]),
            )
            self._audit(
                task_id=task["id"], execution_id=execution_id, event_type="APPROVAL_REQUESTED",
                detail={"approval_id": approval_id, "action": action, "reason": reason}, conn=conn,
            )
        return self._approval_row(approval_id) or {}

    def _mark_denied(self, task: dict[str, Any], reason: str) -> None:
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE tasks SET status='denied', error=?, completed_at=?, updated_at=? WHERE id=?",
                (_redact_text(reason), now_iso(), now_iso(), task["id"]),
            )
            self._audit(
                task_id=task["id"], execution_id=None, event_type="POLICY_DENIED",
                detail={"reason": reason}, conn=conn,
            )

    def execute_task(self, task_id: str, *, wait: bool = False) -> dict[str, Any]:
        with self._start_lock:
            task = self._task_row(task_id)
            if task["status"] in ("queued", "running"):
                raise ConflictError("task is already queued or running")
            settings = get_settings(self.db)
            if int(task["autonomy_level"]) > int(settings["max_autonomy_level"]):
                reason = f"AUTONOMY_EXCEEDS_GLOBAL_MAX:{task['autonomy_level']}>{settings['max_autonomy_level']}"
                self._mark_denied(task, reason)
                raise PolicyDeniedError(reason)
            try:
                provider, model, route_reason, fallback = self._resolve_route(task, settings)
            except ProviderUnavailableError as exc:
                self._mark_denied(task, f"PROVIDER_UNAVAILABLE:{exc}")
                raise
            decision = authorize_action(
                task=task, action="provider_call", settings=settings,
                provider=provider, model=model,
            )
            if not decision.allowed:
                self._mark_denied(task, decision.reason)
                raise PolicyDeniedError(decision.reason)

            approval = None
            if decision.requires_approval:
                approval = self._find_valid_approval(task, "provider_call", settings)
                if approval is None:
                    if task["status"] == "awaiting_approval":
                        raise ConflictError("task is awaiting approval")
                    approval = self._request_approval(
                        task, "provider_call", decision.reason, settings
                    )
                    detail = self.get_task(task_id)
                    return {"task": detail, "approval": approval, "status": "awaiting_approval"}
            elif task["status"] in ("awaiting_approval", "approved"):
                # A stale approval state must not authorize execution.
                raise ConflictError("task is awaiting a valid approval")

            execution_id = uuid.uuid4().hex
            ts = now_iso()
            with self.db.tx() as conn:
                attempt = int(conn.execute(
                    "SELECT COALESCE(MAX(attempt),0) FROM executions WHERE task_id=?",
                    (task_id,),
                ).fetchone()[0]) + 1
                conn.execute(
                    """INSERT INTO executions
                       (id, task_id, status, attempt, provider, model, detail_json)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        execution_id, task_id, "queued", attempt, provider["id"], model,
                        json.dumps({
                            "route_reason": route_reason,
                            "fallback_used": bool(fallback),
                            "approval_id": approval["id"] if approval else None,
                            "provider_kind": provider["kind"],
                        }),
                    ),
                )
                if approval:
                    conn.execute(
                        "UPDATE approvals SET consumed_at=?, execution_id=? WHERE id=?",
                        (ts, execution_id, approval["id"]),
                    )
                conn.execute(
                    """UPDATE tasks SET status='queued', provider=?, model=?,
                       result=NULL, result_hash=NULL, verification_status=NULL,
                       gate_decision=NULL, gate_reason=NULL, error=NULL,
                       completed_at=NULL, updated_at=? WHERE id=?""",
                    (provider["id"], model, ts, task_id),
                )
                self._audit(
                    task_id=task_id, execution_id=execution_id, event_type="EXECUTION_QUEUED",
                    detail={
                        "attempt": attempt, "provider": provider["id"], "model": model,
                        "route_reason": route_reason, "fallback_used": bool(fallback),
                        "approval_id": approval["id"] if approval else None,
                    }, conn=conn,
                )
            if wait:
                self._run_execution(execution_id)
            else:
                self._executor.submit(self._run_execution, execution_id)
            return self.get_task(task_id)

    def approve_task(
        self,
        task_id: str,
        *,
        decision: str,
        note: str = "",
        start_execution: bool = True,
        wait: bool = False,
    ) -> dict[str, Any]:
        task = self._task_row(task_id)
        if decision not in ("approve", "reject"):
            raise ValidationError("decision must be approve or reject")
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE task_id=? AND status='pending' ORDER BY requested_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            raise ConflictError("no pending approval for this task")
        approval = dict(row)
        ts = now_iso()
        if decision == "reject":
            with self.db.tx() as conn:
                conn.execute(
                    "UPDATE approvals SET status='rejected', note=?, decided_at=? WHERE id=?",
                    (note[:2000], ts, approval["id"]),
                )
                conn.execute(
                    "UPDATE tasks SET status='rejected', error=?, completed_at=?, updated_at=? WHERE id=?",
                    ("approval rejected by user", ts, ts, task_id),
                )
                self._audit(
                    task_id=task_id, execution_id=None, event_type="APPROVAL_REJECTED",
                    detail={"approval_id": approval["id"], "note": note}, conn=conn,
                )
            return self.get_task(task_id)
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE approvals SET status='approved', note=?, decided_at=? WHERE id=?",
                (note[:2000], ts, approval["id"]),
            )
            conn.execute(
                "UPDATE tasks SET status='approved', updated_at=? WHERE id=?",
                (ts, task_id),
            )
            self._audit(
                task_id=task_id, execution_id=None, event_type="APPROVAL_GRANTED",
                detail={"approval_id": approval["id"], "note": note}, conn=conn,
            )
        if start_execution:
            return self.execute_task(task_id, wait=wait)
        return self.get_task(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        task = self._task_row(task_id)
        if task["status"] in TERMINAL_TASK_STATUSES:
            raise ConflictError(f"task is already {task['status']}")
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE executions SET cancel_requested=1 WHERE task_id=? AND status IN ('queued','running')",
                (task_id,),
            )
            conn.execute(
                "UPDATE executions SET status='cancelled', completed_at=? WHERE task_id=? AND status='queued'",
                (ts, task_id),
            )
            conn.execute(
                "UPDATE approvals SET status='expired' WHERE task_id=? AND status='pending'",
                (task_id,),
            )
            conn.execute(
                "UPDATE tasks SET status='cancelled', error=?, completed_at=?, updated_at=? WHERE id=?",
                ("cancelled by user", ts, ts, task_id),
            )
            self._audit(
                task_id=task_id, execution_id=None, event_type="TASK_CANCELLED",
                detail={"reason": "user request"}, conn=conn,
            )
        return self.get_task(task_id)

    # ------------------------------------------------------- execution worker
    def _step_start(self, execution_id: str, seq: int, name: str, detail: Any = None) -> int:
        with self.db.tx() as conn:
            cur = conn.execute(
                """INSERT INTO execution_steps
                   (execution_id, seq, name, status, started_at, detail_json)
                   VALUES (?,?,?,?,?,?)""",
                (execution_id, seq, name, "running", now_iso(), json.dumps(redact(detail or {}), default=str)),
            )
            return int(cur.lastrowid)

    def _step_finish(self, step_id: int, status: str, detail: Any = None) -> None:
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE execution_steps SET status=?, completed_at=?, detail_json=? WHERE id=?",
                (status, now_iso(), json.dumps(redact(detail or {}), default=str), step_id),
            )

    def _record_usage(
        self, execution_id: str, task_id: str, input_tokens: int, output_tokens: int, cost: float
    ) -> dict[str, Any]:
        with self.db.tx() as conn:
            conn.execute(
                """UPDATE executions SET input_tokens=input_tokens+?, output_tokens=output_tokens+?,
                   cost=cost+? WHERE id=?""",
                (input_tokens, output_tokens, cost, execution_id),
            )
            conn.execute(
                """UPDATE tasks SET input_tokens=input_tokens+?, output_tokens=output_tokens+?,
                   cost=cost+?, updated_at=? WHERE id=?""",
                (input_tokens, output_tokens, cost, now_iso(), task_id),
            )
        return self._task_row(task_id)

    def _record_evidence(
        self,
        *,
        task_id: str,
        execution_id: str,
        kind: str,
        source_type: str,
        source_id: str,
        independent: bool,
        status: str,
        content: str,
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        evidence_id = uuid.uuid4().hex
        digest = _sha256(content)
        with self.db.tx() as conn:
            conn.execute(
                """INSERT INTO evidence
                   (id, task_id, execution_id, kind, source_type, source_id,
                    independent, status, content, content_hash, provenance_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evidence_id, task_id, execution_id, kind, source_type, source_id,
                    1 if independent else 0, status, content, digest,
                    json.dumps(redact(provenance), sort_keys=True, default=str), now_iso(),
                ),
            )
            self._audit(
                task_id=task_id, execution_id=execution_id, event_type="EVIDENCE_RECORDED",
                detail={
                    "evidence_id": evidence_id, "kind": kind, "source_type": source_type,
                    "independent": independent, "status": status, "content_hash": digest,
                }, conn=conn,
            )
        return {
            "id": evidence_id, "kind": kind, "source_type": source_type,
            "source_id": source_id, "independent": independent, "status": status,
            "content": content, "content_hash": digest, "provenance": provenance,
            "created_at": now_iso(),
        }

    def _build_prompt(self, task: dict[str, Any]) -> str:
        criteria = task.get("acceptance_criteria") or []
        criteria_text = "\n".join(f"- {c}" for c in criteria) or "- No explicit criteria."
        return (
            "You are executing a task inside CREST, an outcome-constrained inference control plane.\n"
            "Produce a complete, useful result. Do not claim actions you did not perform.\n"
            f"TITLE: {task.get('title')}\n"
            f"DESCRIPTION: {task.get('description')}\n"
            f"RISK CLASS: {task.get('risk_class')}\n"
            f"OUTPUT FORMAT: {task.get('output_format')}\n"
            f"ACCEPTANCE CRITERIA:\n{criteria_text}\n"
        )

    def _finalize(
        self,
        *,
        task_id: str,
        execution_id: str,
        status: str,
        output: str | None = None,
        verification: VerificationResult | None = None,
        gate: Any = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ts = now_iso()
        result_hash = _sha256(output) if output is not None else None
        verification_status = None
        if verification is not None:
            verification_status = "passed" if verification.passed else "failed"
        gate_decision = gate.decision.value if gate is not None else None
        gate_reason = gate.reason if gate is not None else None
        try:
            existing_detail = self._execution_row(execution_id).get("detail") or {}
        except TaskNotFound:
            existing_detail = {}
        merged_detail = {**existing_detail, **(extra or {})}
        with self.db.tx() as conn:
            conn.execute(
                """UPDATE executions SET status=?, completed_at=?, error=?, detail_json=?
                   WHERE id=?""",
                (
                    status, ts, _redact_text(error) if error else None,
                    json.dumps(redact(merged_detail), default=str), execution_id,
                ),
            )
            conn.execute(
                """UPDATE tasks SET status=?, result=?, result_hash=?, verification_status=?,
                   gate_decision=?, gate_reason=?, error=?, completed_at=?, updated_at=?
                   WHERE id=?""",
                (
                    status, output, result_hash, verification_status,
                    gate_decision, gate_reason,
                    _redact_text(error) if error else None, ts, ts, task_id,
                ),
            )
            event = {
                "completed": "EXECUTION_COMPLETED",
                "failed": "EXECUTION_FAILED",
                "abstained": "EXECUTION_ABSTAINED",
                "denied": "EXECUTION_DENIED",
                "budget_exhausted": "BUDGET_EXHAUSTED",
                "cancelled": "EXECUTION_CANCELLED",
                "timed_out": "EXECUTION_TIMED_OUT",
                "interrupted": "EXECUTION_INTERRUPTED",
            }.get(status, "EXECUTION_FINISHED")
            self._audit(
                task_id=task_id, execution_id=execution_id, event_type=event,
                detail={
                    "status": status,
                    "verification_status": verification_status,
                    "gate_decision": gate_decision,
                    "gate_reason": gate_reason,
                    "error": error,
                    "result_hash": result_hash,
                    **(extra or {}),
                }, conn=conn,
            )

    def _run_execution(self, execution_id: str) -> None:
        started_monotonic = time.monotonic()
        try:
            execution = self._execution_row(execution_id)
            task = self._task_row(execution["task_id"])
        except TaskNotFound:
            return
        if execution["status"] not in ("queued", "running"):
            return
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE executions SET status='running', started_at=COALESCE(started_at,?) WHERE id=?",
                (ts, execution_id),
            )
            conn.execute(
                "UPDATE tasks SET status='running', started_at=COALESCE(started_at,?), updated_at=? WHERE id=?",
                (ts, ts, task["id"]),
            )
            self._audit(
                task_id=task["id"], execution_id=execution_id,
                event_type="EXECUTION_STARTED",
                detail={"attempt": execution["attempt"]}, conn=conn,
            )

        seq = 0
        try:
            settings = get_settings(self.db)
            task = self._task_row(task["id"])
            provider = self._provider_row(str(execution.get("provider") or task["provider"]))
            model = str(execution.get("model") or task["model"])
            decision = authorize_action(
                task=task, action="provider_call", settings=settings,
                provider=provider, model=model,
            )
            if not decision.allowed:
                self._finalize(
                    task_id=task["id"], execution_id=execution_id, status="denied",
                    error=decision.reason,
                )
                return

            if decision.requires_approval:
                approval = self._approval_row(execution["detail"].get("approval_id"))
                current_fp = self._policy_fingerprint(task, settings)
                if (
                    not approval
                    or approval["status"] != "approved"
                    or approval["policy_fingerprint"] != current_fp
                ):
                    self._request_approval(
                        task, "provider_call", decision.reason, settings, execution_id
                    )
                    with self.db.tx() as conn:
                        conn.execute(
                            "UPDATE executions SET status='awaiting_approval', detail_json=? WHERE id=?",
                            (
                                json.dumps({
                                    **execution["detail"],
                                    "awaiting_approval": True,
                                    "reason": decision.reason,
                                }),
                                execution_id,
                            ),
                        )
                        self._audit(
                            task_id=task["id"], execution_id=execution_id,
                            event_type="EXECUTION_AWAITING_APPROVAL",
                            detail={"reason": decision.reason}, conn=conn,
                        )
                    return

            seq += 1
            step = self._step_start(execution_id, seq, "plan", {"route": execution["detail"].get("route_reason")})
            plan = self._ensure_plan(task, provider, model, settings)
            self._step_finish(step, "completed", {"plan_id": plan["id"], "steps": len(plan["steps"])})

            # Budget pre-flight: fail closed before spending anything.
            remaining_tokens = int(task["token_budget"]) - int(task["input_tokens"] or 0) - int(task["output_tokens"] or 0)
            remaining_cost = float(task["budget"]) - float(task["cost"] or 0.0)
            if remaining_tokens <= 0 or remaining_cost <= 0:
                self._finalize(
                    task_id=task["id"], execution_id=execution_id,
                    status="budget_exhausted",
                    error="budget exhausted before provider call",
                    extra={"remaining_tokens": remaining_tokens, "remaining_cost": remaining_cost},
                )
                return
            prompt = self._build_prompt(task)
            estimated_input = estimate_tokens(prompt)
            max_output = min(
                int(provider.get("max_output_tokens") or 1024),
                max(1, remaining_tokens - estimated_input),
            )
            estimated_cost = (
                (estimated_input / 1000.0) * float(provider.get("input_cost_per_1k") or 0.0)
                + (max_output / 1000.0) * float(provider.get("output_cost_per_1k") or 0.0)
            )
            if estimated_input + max_output > remaining_tokens or estimated_cost > remaining_cost:
                self._finalize(
                    task_id=task["id"], execution_id=execution_id,
                    status="budget_exhausted",
                    error="budget insufficient for the requested provider call",
                    extra={
                        "estimated_input_tokens": estimated_input,
                        "max_output_tokens": max_output,
                        "remaining_tokens": remaining_tokens,
                        "estimated_cost": estimated_cost,
                        "remaining_cost": remaining_cost,
                    },
                )
                return

            max_attempts = 1
            if int(task["autonomy_level"]) >= 3:
                max_attempts += int(settings.get("max_recovery_attempts") or 0)
            output: str | None = None
            verification: VerificationResult | None = None
            last_error: str | None = None

            for attempt in range(1, max_attempts + 1):
                execution = self._execution_row(execution_id)
                if int(execution.get("cancel_requested") or 0):
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id, status="cancelled",
                        error="cancelled by user", extra={"attempt": attempt},
                    )
                    return
                elapsed = time.monotonic() - started_monotonic
                if elapsed > float(settings["max_execution_seconds"]) or elapsed > float(task["timeout_seconds"]):
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id, status="timed_out",
                        error="execution time limit exceeded", extra={"attempt": attempt},
                    )
                    return

                # Re-check current settings and permissions before every call.
                settings = get_settings(self.db)
                task = self._task_row(task["id"])
                provider = self._provider_row(str(task["provider"]))
                decision = authorize_action(
                    task=task, action="provider_call", settings=settings,
                    provider=provider, model=model,
                )
                if not decision.allowed:
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id, status="denied",
                        error=decision.reason, extra={"attempt": attempt},
                    )
                    return

                seq += 1
                step = self._step_start(
                    execution_id, seq, f"provider_call_attempt_{attempt}",
                    {"provider": provider["id"], "model": model},
                )
                try:
                    response = build_provider(provider).generate(
                        model=model,
                        prompt=prompt,
                        max_output_tokens=max_output,
                        timeout_seconds=min(float(task["timeout_seconds"]), float(settings["max_execution_seconds"])),
                        metadata={
                            "task": task,
                            "demo_scenario": task.get("demo_scenario"),
                            "attempt": attempt,
                        },
                    )
                except ProviderError as exc:
                    last_error = str(exc)
                    self._step_finish(step, "failed", {"error": last_error})
                    self._audit(
                        task_id=task["id"], execution_id=execution_id,
                        event_type="PROVIDER_ERROR",
                        detail={"attempt": attempt, "error": last_error},
                    )
                    transient = any(
                        token in last_error.lower()
                        for token in ("timeout", "temporar", "429", "500", "502", "503", "504", "connection")
                    )
                    if transient and attempt < max_attempts:
                        seq += 1
                        recovery = self._step_start(
                            execution_id, seq, f"recovery_retry_{attempt}",
                            {"reason": "transient provider error"},
                        )
                        self._step_finish(recovery, "completed", {"retry": attempt + 1})
                        continue
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id, status="failed",
                        error=f"provider error: {last_error}", extra={"attempt": attempt},
                    )
                    return

                output = response.text
                task = self._record_usage(
                    execution_id, task["id"], response.input_tokens,
                    response.output_tokens, response.cost,
                )
                self._step_finish(
                    step, "completed",
                    {
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cost": response.cost,
                        "latency_ms": response.latency_ms,
                        "provider_request_id": response.provider_request_id,
                        "finish_reason": response.finish_reason,
                    },
                )
                self._record_evidence(
                    task_id=task["id"], execution_id=execution_id,
                    kind="provider_output", source_type="provider",
                    source_id=f"{provider['id']}/{model}", independent=False,
                    status="informational", content=output,
                    provenance={
                        "provider": provider["id"], "provider_kind": provider["kind"],
                        "model": model, "attempt": attempt,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "cost": response.cost,
                        "prompt_sha256": _sha256(prompt),
                        "provider_request_id": response.provider_request_id,
                        "authenticated_provenance": False,
                        "note": "Content-addressed provenance; not a signed attestation.",
                    },
                )

                execution = self._execution_row(execution_id)
                if int(execution.get("cancel_requested") or 0):
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id, status="cancelled",
                        output=output, error="cancelled by user",
                        extra={"attempt": attempt},
                    )
                    return

                if float(task["cost"]) > float(task["budget"]):
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id,
                        status="budget_exhausted",
                        output=output,
                        error="cost budget exceeded after provider call",
                        extra={"cost": task["cost"], "budget": task["budget"]},
                    )
                    return
                if int(task["input_tokens"]) + int(task["output_tokens"]) > int(task["token_budget"]):
                    self._finalize(
                        task_id=task["id"], execution_id=execution_id,
                        status="budget_exhausted",
                        output=output,
                        error="token budget exceeded after provider call",
                        extra={
                            "input_tokens": task["input_tokens"],
                            "output_tokens": task["output_tokens"],
                            "token_budget": task["token_budget"],
                        },
                    )
                    return

                seq += 1
                verify_step = self._step_start(execution_id, seq, f"verify_attempt_{attempt}", {})
                verification = verify_output(task, output)
                self._step_finish(
                    verify_step, "completed" if verification.passed else "failed",
                    verification.to_dict(),
                )
                self._record_evidence(
                    task_id=task["id"], execution_id=execution_id,
                    kind="deterministic_verification", source_type="deterministic",
                    source_id="builtin-checks", independent=False,
                    status="passed" if verification.passed else "failed",
                    content=json.dumps(verification.to_dict(), indent=2),
                    provenance={
                        "checks": [c["name"] for c in verification.checks],
                        "authenticated_provenance": False,
                    },
                )
                self._audit(
                    task_id=task["id"], execution_id=execution_id,
                    event_type="VERIFICATION_PASSED" if verification.passed else "VERIFICATION_FAILED",
                    detail=verification.to_dict(),
                )
                if verification.passed:
                    break
                last_error = verification.failure_reason
                if attempt < max_attempts:
                    seq += 1
                    recovery = self._step_start(
                        execution_id, seq, f"recovery_retry_{attempt}",
                        {"reason": verification.failure_reason},
                    )
                    self._step_finish(recovery, "completed", {"retry": attempt + 1})
                    self._audit(
                        task_id=task["id"], execution_id=execution_id,
                        event_type="RECOVERY_ATTEMPT",
                        detail={"attempt": attempt, "reason": verification.failure_reason},
                    )
                    continue
                break

            if output is None or verification is None:
                self._finalize(
                    task_id=task["id"], execution_id=execution_id, status="failed",
                    error=last_error or "provider produced no output",
                )
                return

            # Optional independent provider verification.
            if verification.passed and settings.get("verification_mode") == "provider":
                verifier_id = str(settings.get("verifier_provider") or "")
                verifier_model = str(settings.get("verifier_model") or "")
                verifier_result: dict[str, Any] | None = None
                try:
                    verifier_row = self._provider_row(verifier_id)
                    if str(verifier_row.get("kind")) != "mock" and not settings.get("allow_external_calls", False):
                        raise ProviderUnavailableError("EXTERNAL_CALLS_DISABLED for verifier")
                    if not verifier_row.get("enabled"):
                        raise ProviderUnavailableError("verifier provider is disabled")
                    if verifier_row.get("models") and verifier_model not in verifier_row["models"]:
                        raise ProviderUnavailableError("verifier model is not configured")
                    if str(verifier_row.get("kind")) != "mock" and not provider_public(verifier_row)["key_present"]:
                        raise ProviderUnavailableError("verifier API key is not configured")
                    seq += 1
                    vstep = self._step_start(
                        execution_id, seq, "independent_verifier",
                        {"provider": verifier_id, "model": verifier_model},
                    )
                    verifier_prompt = build_verifier_prompt(task, output)
                    vresponse = build_provider(verifier_row).generate(
                        model=verifier_model,
                        prompt=verifier_prompt,
                        max_output_tokens=256,
                        timeout_seconds=min(float(task["timeout_seconds"]), 60.0),
                        metadata={"task": task, "verification": True},
                    )
                    task = self._record_usage(
                        execution_id, task["id"], vresponse.input_tokens,
                        vresponse.output_tokens, vresponse.cost,
                    )
                    if (
                        float(task["cost"]) > float(task["budget"])
                        or int(task["input_tokens"]) + int(task["output_tokens"]) > int(task["token_budget"])
                    ):
                        self._finalize(
                            task_id=task["id"], execution_id=execution_id,
                            status="budget_exhausted", output=output,
                            error="budget exceeded during independent verification",
                            extra={"cost": task["cost"], "budget": task["budget"]},
                        )
                        return
                    parsed = parse_verifier_output(vresponse.text)
                    independent = (
                        verifier_id != str(provider["id"]) or verifier_model != model
                    )
                    verifier_result = {
                        **parsed,
                        "independent": independent,
                        "provider": verifier_id,
                        "model": verifier_model,
                    }
                    self._step_finish(vstep, "completed" if parsed.get("passed") else "failed", verifier_result)
                    self._record_evidence(
                        task_id=task["id"], execution_id=execution_id,
                        kind="independent_verifier", source_type="provider",
                        source_id=f"{verifier_id}/{verifier_model}", independent=independent,
                        status="passed" if parsed.get("passed") else "failed",
                        content=json.dumps(verifier_result, indent=2),
                        provenance={
                            "provider": verifier_id, "model": verifier_model,
                            "generator_provider": provider["id"], "generator_model": model,
                            "independent": independent,
                            "authenticated_provenance": False,
                        },
                    )
                except (ProviderError, ProviderUnavailableError, ValidationError) as exc:
                    verifier_result = {
                        "passed": False, "independent": False,
                        "reason": f"verifier unavailable: {exc}",
                    }
                    self._audit(
                        task_id=task["id"], execution_id=execution_id,
                        event_type="VERIFIER_ERROR", detail={"error": str(exc)},
                    )
                verification = verify_output(task, output, verifier_result=verifier_result)

            remaining_cost = max(0.0, float(task["budget"]) - float(task["cost"] or 0.0))
            remaining_tokens = max(
                0, int(task["token_budget"]) - int(task["input_tokens"] or 0) - int(task["output_tokens"] or 0)
            )
            budget_remaining = remaining_cost if remaining_cost > 0 else (remaining_tokens / 1000.0)
            gate = evaluate_high_risk_gate(
                risk_class=str(task["risk_class"]),
                evidence_sources=int(verification.independent_sources),
                has_deterministic_check=bool(verification.has_deterministic_check),
                budget_remaining=budget_remaining,
            )
            if not verification.passed:
                # A failed verification cannot be accepted.  Record the gate as
                # a rejection rather than the low-risk "base admission" result,
                # so the gate decision never contradicts the task outcome.
                gate = GateResult(
                    decision=GateDecision.REJECT,
                    reason=f"verification failed: {verification.failure_reason}",
                    evidence_sources=int(verification.independent_sources),
                    risk_class=str(task["risk_class"]),
                )
            self._record_evidence(
                task_id=task["id"], execution_id=execution_id,
                kind="gate_decision", source_type="policy",
                source_id="strong-high-risk-gate", independent=False,
                status=gate.decision.value, content=json.dumps({
                    "decision": gate.decision.value,
                    "reason": gate.reason,
                    "evidence_sources": gate.evidence_sources,
                    "has_deterministic_check": verification.has_deterministic_check,
                    "risk_class": gate.risk_class,
                }, indent=2),
                provenance={
                    "policy": "Strong High-Risk Gate (narrow runtime veto)",
                    "research_basis": "Cycle 3 evidence-integrity simulation",
                    "authenticated_provenance": False,
                },
            )
            self._audit(
                task_id=task["id"], execution_id=execution_id,
                event_type="GATE_DECISION",
                detail={
                    "decision": gate.decision.value, "reason": gate.reason,
                    "evidence_sources": gate.evidence_sources,
                    "has_deterministic_check": verification.has_deterministic_check,
                },
            )

            if not verification.passed:
                final_status = "failed"
                error = f"verification failed: {verification.failure_reason}"
            elif gate.decision == GateDecision.ABSTAIN:
                final_status = "abstained"
                error = f"high-risk gate abstained: {gate.reason}"
            elif gate.decision == GateDecision.REJECT:
                final_status = "denied"
                error = f"high-risk gate rejected: {gate.reason}"
            else:
                final_status = "completed"
                error = None

            self._finalize(
                task_id=task["id"], execution_id=execution_id, status=final_status,
                output=output, verification=verification, gate=gate, error=error,
                extra={
                    "provider": provider["id"], "model": model,
                    "attempts": max_attempts,
                    "input_tokens": task["input_tokens"],
                    "output_tokens": task["output_tokens"],
                    "cost": task["cost"],
                },
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            try:
                self._finalize(
                    task_id=task["id"], execution_id=execution_id, status="failed",
                    error=f"internal execution error: {type(exc).__name__}: {exc}",
                )
            except Exception:
                pass

    # ------------------------------------------------------------- providers
    def list_providers(self) -> list[dict[str, Any]]:
        with self.db.read() as conn:
            rows = conn.execute("SELECT * FROM providers ORDER BY id").fetchall()
        return [provider_public(_provider_from_row(row)) for row in rows]  # type: ignore[arg-type]

    def update_provider(self, provider_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        provider = self._provider_row(provider_id)
        clean = validate_provider_update(updates)
        if "models" in clean and not clean["models"]:
            raise ValidationError("a provider must have at least one configured model")
        ts = now_iso()
        column_map = {"models": "models_json"}
        assignments = ", ".join(f"{column_map.get(key, key)}=?" for key in clean)
        params = [json.dumps(value) if key == "models" else value for key, value in clean.items()]
        with self.db.tx() as conn:
            if assignments:
                conn.execute(
                    f"UPDATE providers SET {assignments}, updated_at=? WHERE id=?",
                    [*params, ts, provider_id],
                )
            self._audit(
                task_id=None, execution_id=None, event_type="PROVIDER_UPDATED",
                detail={"provider": provider_id, "fields": sorted(clean)}, conn=conn,
            )
        return provider_public(self._provider_row(provider_id))

    def test_provider(
        self, provider_id: str, *, confirm: bool, model: str | None = None
    ) -> dict[str, Any]:
        if not confirm:
            raise ValidationError("explicit confirmation is required before a connection test")
        provider = self._provider_row(provider_id)
        settings = get_settings(self.db)
        external = str(provider.get("kind")) != "mock"
        if external and not settings.get("allow_external_calls", False):
            raise PolicyDeniedError("EXTERNAL_CALLS_DISABLED")
        if external and not provider_public(provider)["key_present"]:
            raise ValidationError(
                f"API key is not configured in environment variable {provider.get('api_key_env')}"
            )
        chosen = model or str(provider.get("default_model") or "")
        if not chosen:
            raise ValidationError("no model selected for connection test")
        try:
            result = build_provider(provider).test_connection(
                model=chosen,
                timeout_seconds=min(float(provider.get("timeout_seconds") or 30.0), 30.0),
            )
            status = "ok"
        except ProviderError as exc:
            result = {"ok": False, "message": str(exc), "model": chosen}
            status = "error"
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE providers SET last_test_status=?, last_test_at=?, last_test_detail=?, updated_at=? WHERE id=?",
                (status, ts, json.dumps(redact(result), default=str), ts, provider_id),
            )
            self._audit(
                task_id=None, execution_id=None, event_type="PROVIDER_TESTED",
                detail={"provider": provider_id, "model": chosen, "status": status}, conn=conn,
            )
        return {"provider": provider_id, "status": status, **result}

    # --------------------------------------------------------------- routing
    def list_routing(self) -> dict[str, Any]:
        with self.db.read() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM routing_rules ORDER BY priority ASC, id ASC"
            ).fetchall()]
        for row in rows:
            row["enabled"] = bool(row["enabled"])
        return {"rules": rows, "fallback_enabled": get_settings(self.db)["routing_fallback_enabled"]}

    def update_routing(self, rules: list[dict[str, Any]], *, fallback_enabled: bool | None = None) -> dict[str, Any]:
        if not isinstance(rules, list) or not rules:
            raise ValidationError("routing rules must be a non-empty list")
        clean: list[dict[str, Any]] = []
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValidationError(f"routing rule {index} must be an object")
            unknown = set(rule) - {"priority", "risk_class", "provider", "model", "enabled"}
            if unknown:
                raise ValidationError(f"unknown routing fields: {sorted(unknown)}")
            risk = str(rule.get("risk_class") or "*")
            if risk not in ("low", "med", "high", "*"):
                raise ValidationError("routing risk_class must be low, med, high, or *")
            provider_id = str(rule.get("provider") or "")
            provider = self._provider_row(provider_id)
            model = str(rule.get("model") or "")
            if provider.get("models") and model not in provider["models"]:
                raise ValidationError(f"model {model!r} is not configured for provider {provider_id!r}")
            try:
                priority = int(rule.get("priority", 100))
            except (TypeError, ValueError) as exc:
                raise ValidationError("routing priority must be an integer") from exc
            clean.append({
                "priority": priority, "risk_class": risk, "provider": provider_id,
                "model": model, "enabled": bool(rule.get("enabled", True)),
            })
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute("DELETE FROM routing_rules")
            for rule in clean:
                conn.execute(
                    """INSERT INTO routing_rules
                       (priority, risk_class, provider, model, enabled, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (rule["priority"], rule["risk_class"], rule["provider"], rule["model"],
                     1 if rule["enabled"] else 0, ts, ts),
                )
            self._audit(
                task_id=None, execution_id=None, event_type="ROUTING_UPDATED",
                detail={"rules": len(clean)}, conn=conn,
            )
        if fallback_enabled is not None:
            update_settings(self.db, {"routing_fallback_enabled": bool(fallback_enabled)})
        return self.list_routing()

    # ---------------------------------------------------------------- audit
    def list_audit(
        self,
        *,
        task_id: str | None = None,
        event_type: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        where = ["1=1"]
        params: list[Any] = []
        if task_id:
            where.append("task_id=?")
            params.append(task_id)
        if event_type:
            where.append("event_type=?")
            params.append(event_type)
        if search:
            where.append("(detail LIKE ? OR event_type LIKE ? OR actor LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        clause = " AND ".join(where)
        with self.db.read() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) FROM audit_events WHERE {clause}", params).fetchone()[0])
            rows = [dict(r) for r in conn.execute(
                f"SELECT * FROM audit_events WHERE {clause} ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()]
        for row in rows:
            row["detail"] = _loads(row.get("detail"), {})
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    def list_evidence(
        self,
        *,
        task_id: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        where = ["1=1"]
        params: list[Any] = []
        if task_id:
            where.append("task_id=?")
            params.append(task_id)
        if kind:
            where.append("kind=?")
            params.append(kind)
        if status:
            where.append("status=?")
            params.append(status)
        if search:
            where.append("(content LIKE ? OR source_id LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        clause = " AND ".join(where)
        with self.db.read() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) FROM evidence WHERE {clause}", params).fetchone()[0])
            rows = [dict(r) for r in conn.execute(
                f"SELECT * FROM evidence WHERE {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()]
        for row in rows:
            row["provenance"] = _loads(row.pop("provenance_json"), {})
            row["independent"] = bool(row["independent"])
            if len(row.get("content") or "") > 1200:
                row["content_preview"] = row["content"][:1200]
                row.pop("content", None)
            else:
                row["content_preview"] = row.get("content") or ""
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        if row is None:
            raise TaskNotFound("evidence not found")
        item = dict(row)
        item["provenance"] = _loads(item.pop("provenance_json"), {})
        item["independent"] = bool(item["independent"])
        return item

    def list_approvals(
        self, *, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        where = ["1=1"]
        params: list[Any] = []
        if status:
            where.append("a.status=?")
            params.append(status)
        clause = " AND ".join(where)
        with self.db.read() as conn:
            total = int(conn.execute(
                f"SELECT COUNT(*) FROM approvals a WHERE {clause}", params
            ).fetchone()[0])
            rows = [dict(r) for r in conn.execute(
                f"""SELECT a.*, t.title, t.risk_class, t.autonomy_level, t.status AS task_status,
                           t.provider, t.model
                    FROM approvals a LEFT JOIN tasks t ON t.id=a.task_id
                    WHERE {clause}
                    ORDER BY a.requested_at DESC LIMIT ? OFFSET ?""",
                [*params, limit, offset],
            ).fetchall()]
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    # ------------------------------------------------------------ statistics
    def stats(self) -> dict[str, Any]:
        with self.db.read() as conn:
            total = int(conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE deleted_at IS NULL"
            ).fetchone()[0])
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks WHERE deleted_at IS NULL GROUP BY status"
            ).fetchall()
            risk_rows = conn.execute(
                "SELECT risk_class, COUNT(*) AS n FROM tasks WHERE deleted_at IS NULL GROUP BY risk_class"
            ).fetchall()
            gate_rows = conn.execute(
                "SELECT gate_decision, COUNT(*) AS n FROM tasks WHERE deleted_at IS NULL AND gate_decision IS NOT NULL GROUP BY gate_decision"
            ).fetchall()
            verified = int(conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE deleted_at IS NULL AND verification_status='passed'"
            ).fetchone()[0])
            failed_verification = int(conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE deleted_at IS NULL AND verification_status='failed'"
            ).fetchone()[0])
            totals = conn.execute(
                """SELECT COALESCE(SUM(cost),0) AS cost,
                          COALESCE(SUM(input_tokens),0) AS input_tokens,
                          COALESCE(SUM(output_tokens),0) AS output_tokens
                   FROM tasks WHERE deleted_at IS NULL"""
            ).fetchone()
            active = int(conn.execute(
                "SELECT COUNT(*) FROM executions WHERE status IN ('queued','running','awaiting_approval')"
            ).fetchone()[0])
            daily_cutoff = (datetime.now(timezone.utc) - timedelta(days=13)).isoformat()
            daily = conn.execute(
                """SELECT substr(created_at,1,10) AS day, COUNT(*) AS n
                   FROM tasks WHERE deleted_at IS NULL
                     AND created_at >= ?
                   GROUP BY day ORDER BY day ASC""",
                (daily_cutoff,),
            ).fetchall()
            recent = [dict(r) for r in conn.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC, id DESC LIMIT 12"
            ).fetchall()]
            recent_tasks = [dict(r) for r in conn.execute(
                """SELECT id, title, status, risk_class, provider, model, cost,
                          input_tokens, output_tokens, created_at, updated_at
                   FROM tasks WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 6"""
            ).fetchall()]
        statuses = {row["status"]: int(row["n"]) for row in status_rows}
        risks = {row["risk_class"]: int(row["n"]) for row in risk_rows}
        gates = {row["gate_decision"]: int(row["n"]) for row in gate_rows}
        completed = statuses.get("completed", 0)
        for row in recent:
            row["detail"] = _loads(row.get("detail"), {})
        return {
            "total_tasks": total,
            "status_counts": statuses,
            "risk_counts": risks,
            "gate_counts": gates,
            "active_executions": active,
            "completed": completed,
            "failed": statuses.get("failed", 0),
            "abstained": statuses.get("abstained", 0),
            "awaiting_approval": statuses.get("awaiting_approval", 0),
            "verification_passed": verified,
            "verification_failed": failed_verification,
            "verification_pass_rate": round(
                verified / (verified + failed_verification), 4
            ) if (verified + failed_verification) else None,
            "completion_rate": round(completed / total, 4) if total else None,
            "budget_used": round(float(totals["cost"] or 0.0), 8),
            "input_tokens": int(totals["input_tokens"] or 0),
            "output_tokens": int(totals["output_tokens"] or 0),
            "daily": [{"day": row["day"], "count": int(row["n"])} for row in daily],
            "recent_events": recent,
            "recent_tasks": recent_tasks,
        }

    def diagnostics(self) -> dict[str, Any]:
        settings = get_settings(self.db)
        integrity = self.db.integrity()
        providers = self.list_providers()
        frontend = Path(__file__).resolve().parents[3] / "web" / "dist" / "index.html"
        return {
            "status": "ok" if integrity["ok"] else "degraded",
            "version": VERSION,
            "started_at": self.started_at,
            "uptime_seconds": round(
                (datetime.now(timezone.utc) - datetime.fromisoformat(self.started_at)).total_seconds(), 1
            ),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "data_dir": str(self.db.path.parent),
            "database": {
                "path": str(self.db.path),
                "size_bytes": self.db.size_bytes(),
                "integrity": integrity,
                "counts": self.db.counts(),
            },
            "frontend_built": frontend.exists(),
            "auth_token_required": bool(__import__("os").environ.get("CREST_API_TOKEN")),
            "external_calls_enabled": bool(settings.get("allow_external_calls")),
            "providers": providers,
            "settings": {
                key: settings[key] for key in (
                    "max_autonomy_level", "default_autonomy_level", "allow_external_calls",
                    "require_approval_high_risk", "require_approval_external",
                    "verification_mode", "retention_enabled", "retention_days",
                )
            },
        }

    def levels(self) -> list[dict[str, Any]]:
        return level_info()

    # ------------------------------------------------------------- reporting
    def task_report(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        return {
            "report_version": "1.0",
            "generated_at": now_iso(),
            "application": {"name": "CREST", "version": VERSION},
            "disclaimer": (
                "Results from the offline mock provider are simulated. Evidence is "
                "content-addressed but not a signed attestation. High-risk acceptance "
                "requires independent evidence; otherwise CREST abstains."
            ),
            "task": task,
        }

    def export_all(self) -> dict[str, Any]:
        with self.db.read() as conn:
            tables = {}
            for table in (
                "tasks", "plans", "executions", "execution_steps", "evidence",
                "approvals", "audit_events", "routing_rules",
            ):
                tables[table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
        settings = get_settings(self.db)
        return {
            "export_version": "1.0",
            "generated_at": now_iso(),
            "application": {"name": "CREST", "version": VERSION},
            "settings": settings,
            "providers": self.list_providers(),
            "routing": self.list_routing(),
            "tables": tables,
            "note": "Provider credentials are not included. API keys remain in environment variables.",
        }

    def purge_old(self, *, confirm: bool, force: bool = False) -> dict[str, Any]:
        if not confirm:
            raise ValidationError("explicit confirmation is required")
        settings = get_settings(self.db)
        if not settings.get("retention_enabled") and not force:
            raise PolicyDeniedError("retention is disabled; enable it or pass force=true")
        days = int(settings.get("retention_days") or 30)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self.db.read() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, title FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at<?",
                (cutoff,),
            ).fetchall()]
        for row in rows:
            with self.db.tx() as conn:
                self._audit(
                    task_id=row["id"], execution_id=None, event_type="TASK_PURGED",
                    detail={"title": row["title"], "reason": "retention"}, conn=conn,
                )
                conn.execute("DELETE FROM tasks WHERE id=?", (row["id"],))
        return {"purged": len(rows), "cutoff": cutoff, "retention_days": days}

    def recover_interrupted(self) -> int:
        ts = now_iso()
        with self.db.read() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, task_id FROM executions WHERE status IN ('queued','running')"
            ).fetchall()]
        for row in rows:
            with self.db.tx() as conn:
                conn.execute(
                    "UPDATE executions SET status='interrupted', completed_at=?, error=? WHERE id=?",
                    (ts, "application restarted during execution", row["id"]),
                )
                conn.execute(
                    "UPDATE tasks SET status='interrupted', error=?, completed_at=?, updated_at=? WHERE id=?",
                    ("application restarted during execution; task was not completed", ts, ts, row["task_id"]),
                )
                self._audit(
                    task_id=row["task_id"], execution_id=row["id"],
                    event_type="EXECUTION_INTERRUPTED",
                    detail={"reason": "application restart"}, conn=conn,
                )
        with self.db.tx() as conn:
            stuck = conn.execute(
                "SELECT id FROM tasks WHERE status IN ('queued','running')"
            ).fetchall()
            for row in stuck:
                conn.execute(
                    "UPDATE tasks SET status='interrupted', error=?, completed_at=?, updated_at=? WHERE id=?",
                    ("no active execution after restart; task was not completed", ts, ts, row["id"]),
                )
        return len(rows)

    def shutdown(self) -> None:
        self._shutdown.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
