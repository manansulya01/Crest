"""FastAPI service for CREST 1.1.

All state-changing operations are enforced server-side.  The API binds to
loopback by default and never returns provider credentials.  Browser-originated
state-changing requests must present the per-process CSRF token.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .backup import BackupError, validate_export_payload
from .credentials import CredentialError
from .db import Database, default_data_dir, now_iso
from .engine import (
    ConflictError,
    PolicyDeniedError,
    ProductEngine,
    ProviderUnavailableError,
    TaskNotFound,
    ValidationError,
)
from .logging_setup import configure_logging
from .platform import VERSION, app_data_dir, backups_dir, logs_dir
from .policy import mode_info, permissions_matrix
from .providers import ProviderError
from .settings import get_settings, update_settings


def _dist_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for candidate in (base / "web" / "dist", base / "dist"):
            if (candidate / "index.html").exists():
                return candidate
    return Path(__file__).resolve().parents[3] / "web" / "dist"


_DIST = _dist_dir()


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=10000)
    risk_class: Literal["low", "med", "high"] = "low"
    autonomy_level: int = Field(2, ge=1, le=5)
    provider: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=200)
    budget: float | None = Field(None, gt=0, le=1_000_000)
    token_budget: int | None = Field(None, gt=0, le=10_000_000)
    timeout_seconds: float | None = Field(None, gt=0, le=3600)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)
    output_format: Literal["text", "json"] = "text"
    demo_scenario: Literal["verification_failure", "recovery", "approval_required"] | None = None
    custom_policy: dict[str, Any] | None = None
    idempotency_key: str | None = Field(None, max_length=128)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=10000)
    risk_class: Literal["low", "med", "high"] | None = None
    autonomy_level: int | None = Field(None, ge=1, le=5)
    provider: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=200)
    budget: float | None = Field(None, gt=0, le=1_000_000)
    token_budget: int | None = Field(None, gt=0, le=10_000_000)
    timeout_seconds: float | None = Field(None, gt=0, le=3600)
    acceptance_criteria: list[str] | None = Field(None, max_length=20)
    output_format: Literal["text", "json"] | None = None
    demo_scenario: Literal["verification_failure", "recovery", "approval_required"] | None = None
    custom_policy: dict[str, Any] | None = None


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_autonomy_level: int | None = Field(None, ge=1, le=5)
    max_autonomy_level: int | None = Field(None, ge=1, le=5)
    default_risk_class: Literal["low", "med", "high"] | None = None
    default_budget: float | None = Field(None, gt=0, le=1_000_000)
    max_task_budget: float | None = Field(None, gt=0, le=1_000_000)
    default_token_budget: int | None = Field(None, gt=0, le=10_000_000)
    max_token_budget: int | None = Field(None, gt=0, le=10_000_000)
    default_timeout_seconds: float | None = Field(None, gt=0, le=3600)
    max_execution_seconds: float | None = Field(None, gt=0, le=3600)
    default_provider: str | None = Field(None, max_length=100)
    default_model: str | None = Field(None, max_length=200)
    allow_external_calls: bool | None = None
    require_approval_high_risk: bool | None = None
    require_approval_external: bool | None = None
    allow_custom_policies: bool | None = None
    max_recovery_attempts: int | None = Field(None, ge=0, le=3)
    verification_mode: Literal["deterministic", "provider"] | None = None
    verifier_provider: str | None = Field(None, max_length=100)
    verifier_model: str | None = Field(None, max_length=200)
    routing_fallback_enabled: bool | None = None
    retention_enabled: bool | None = None
    retention_days: int | None = Field(None, ge=1, le=3650)
    operating_mode: Literal["manual", "supervised", "bounded_autonomous"] | None = None
    onboarding_complete: bool | None = None
    execution_paused: bool | None = None
    provider_max_retries: int | None = Field(None, ge=0, le=5)
    provider_backoff_seconds: float | None = Field(None, ge=0, le=30)
    provider_rate_limit_per_minute: int | None = Field(None, ge=1, le=600)
    backup_enabled: bool | None = None
    backup_interval_hours: int | None = Field(None, ge=1, le=168)
    backup_keep: int | None = Field(None, ge=1, le=100)
    log_retention_days: int | None = Field(None, ge=1, le=365)


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=120)
    enabled: bool | None = None
    base_url: str | None = Field(None, max_length=500)
    api_key_env: str | None = Field(None, max_length=64)
    default_model: str | None = Field(None, max_length=200)
    models: list[str] | None = Field(None, max_length=50)
    input_cost_per_1k: float | None = Field(None, ge=0, le=1_000_000)
    output_cost_per_1k: float | None = Field(None, ge=0, le=1_000_000)
    max_output_tokens: int | None = Field(None, ge=1, le=1_000_000)
    timeout_seconds: float | None = Field(None, ge=1, le=600)
    retry_max: int | None = Field(None, ge=0, le=5)
    rate_limit_per_minute: int | None = Field(None, ge=1, le=600)


class RoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: int = 100
    risk_class: Literal["low", "med", "high", "*"] = "*"
    provider: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=200)
    enabled: bool = True


class RoutingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[RoutingRule] = Field(..., min_length=1, max_length=100)
    fallback_enabled: bool | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    note: str = Field("", max_length=2000)
    start_execution: bool = True
    wait: bool = False


class ProviderTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool = False
    model: str | None = Field(None, max_length=200)


class CredentialSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr
    confirm: bool = False


class ModeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["manual", "supervised", "bounded_autonomous"]


class BackupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field("", max_length=500)


class BackupNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=200)


class BackupRestoreRequest(BackupNameRequest):
    confirm: bool = False


class ImportValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: dict[str, Any]


def _error(status: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail=detail)


def create_app(
    *,
    db_path: str | Path | None = None,
    data_dir: str | Path | None = None,
) -> FastAPI:
    if db_path is None:
        root = Path(data_dir).expanduser().resolve() if data_dir else default_data_dir()
        db_path = root / "crest.db"
    db = Database(db_path)
    engine = ProductEngine(db)
    log_info = configure_logging(db.path.parent)
    csrf_token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        engine.recover_interrupted()
        engine.logger.info("CREST %s started; data_dir=%s", VERSION, db.path.parent)
        yield
        engine.shutdown()
        engine.logger.info("CREST stopped cleanly")

    app = FastAPI(
        title="CREST 1.1 API",
        description=(
            "Outcome-Constrained Inference Control Plane. Local-first task "
            "execution with server-side autonomy, budget, approval, verification, "
            "evidence, audit, and Strong High-Risk Gate enforcement."
        ),
        version=VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.db = db
    app.state.csrf_token = csrf_token
    app.state.log_file = log_info["log_file"]

    origins = os.environ.get(
        "CREST_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000,"
        "http://tauri.localhost,tauri://localhost",
    ).split(",")
    allowed_origins = {o.strip().rstrip("/") for o in origins if o.strip()}

    def _origin_allowed(origin: str) -> bool:
        if origin in allowed_origins:
            return True
        parsed = urlparse(origin)
        return (
            parsed.scheme in ("http", "https")
            and parsed.hostname in ("127.0.0.1", "localhost", "::1")
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Crest-CSRF"],
    )
    hosts = os.environ.get("CREST_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,::1").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[h.strip() for h in hosts if h.strip()])

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        token = os.environ.get("CREST_API_TOKEN")
        path = request.url.path
        method = request.method.upper()
        if token and path.startswith("/api/") and path != "/api/v1/health":
            supplied = request.headers.get("authorization", "")
            expected = "Bearer " + token
            if not secrets.compare_digest(supplied, expected):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "API token required. Configure it in Settings."},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Local browser request protection.  Non-browser clients do not send an
        # Origin header and are not exposed to CSRF; browser requests must come
        # from an allowed loopback origin and carry the per-process token.
        if path.startswith("/api/") and method not in ("GET", "HEAD", "OPTIONS"):
            origin = (request.headers.get("origin") or "").rstrip("/")
            if origin and not _origin_allowed(origin):
                return JSONResponse(status_code=403, content={"detail": "origin not allowed"})
            if origin and os.environ.get("CREST_REQUIRE_CSRF", "1") != "0":
                supplied = request.headers.get("x-crest-csrf", "")
                if not secrets.compare_digest(supplied, csrf_token):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "missing or invalid CSRF token; reload the application"},
                    )
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(status_code=403, content={"detail": "cross-site request denied"})
            length = request.headers.get("content-length")
            if length:
                try:
                    if int(length) > 5 * 1024 * 1024:
                        return JSONResponse(status_code=413, content={"detail": "request too large"})
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "invalid content-length"})

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self' http://127.0.0.1:* http://localhost:*; "
            "frame-ancestors 'none'; base-uri 'self'",
        )
        return response

    @app.exception_handler(TaskNotFound)
    async def _not_found(_request: Request, exc: TaskNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(_request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PolicyDeniedError)
    async def _denied(_request: Request, exc: PolicyDeniedError):
        return JSONResponse(status_code=403, content={"detail": exc.reason})

    @app.exception_handler(ProviderUnavailableError)
    async def _provider_unavailable(_request: Request, exc: ProviderUnavailableError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def _provider_error(_request: Request, exc: ProviderError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(BackupError)
    async def _backup_error(_request: Request, exc: BackupError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(CredentialError)
    async def _credential_error(_request: Request, exc: CredentialError):
        return JSONResponse(
            status_code=500,
            content={"detail": f"credential storage error: {exc}"},
        )

    @app.exception_handler(sqlite3.DatabaseError)
    async def _db_error(_request: Request, exc: sqlite3.DatabaseError):
        return JSONResponse(status_code=500, content={"detail": "database error"})

    # ---------------------------------------------------------------- health
    @app.get("/api/v1/health")
    def health():
        return engine.health()

    @app.get("/api/v1/health/providers")
    def health_providers():
        providers = engine.list_providers()
        return {
            "status": "ok" if all(p["status"] in ("ready", "disabled") for p in providers) else "degraded",
            "providers": providers,
            "credentials": engine.credential_status(),
        }

    @app.get("/api/v1/security/csrf")
    def csrf(request: Request):
        return {"token": request.app.state.csrf_token, "header": "X-Crest-CSRF"}

    @app.get("/api/v1/diagnostics")
    def diagnostics():
        return engine.diagnostics()

    @app.get("/api/v1/system/info")
    def system_info():
        info = engine.diagnostics()
        return {
            "name": "CREST",
            "version": VERSION,
            "description": "Outcome-Constrained Inference Control Plane",
            "started_at": info["started_at"],
            "uptime_seconds": info["uptime_seconds"],
            "python": info["python"],
            "platform": info["platform"],
            "data_dir": info["data_dir"],
            "paths": info["paths"],
            "frontend_built": info["frontend_built"],
            "auth_token_required": info["auth_token_required"],
            "external_calls_enabled": info["external_calls_enabled"],
            "database": info["database"],
            "schema_version": info["schema_version"],
            "credentials": info["credentials"],
            "control": info["control"],
            "logs": info["logs"],
            "backups": info["backups"],
            "security_level": "Level 3 — supervised personal use",
        }

    @app.get("/api/v1/logs")
    def logs(lines: int = Query(200, ge=1, le=2000)):
        return engine.logs(lines=lines)

    # ----------------------------------------------------------------- tasks
    @app.post("/api/v1/tasks")
    def create_task(payload: TaskCreate):
        return engine.create_task(payload.model_dump())

    @app.get("/api/v1/tasks")
    def list_tasks(
        status: str | None = Query(None),
        risk_class: str | None = Query(None),
        search: str | None = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        return engine.list_tasks(
            status=status, risk_class=risk_class, search=search, limit=limit, offset=offset
        )

    @app.get("/api/v1/tasks/{task_id}")
    def get_task(task_id: str):
        return engine.get_task(task_id)

    @app.patch("/api/v1/tasks/{task_id}")
    def update_task(task_id: str, payload: TaskUpdate):
        return engine.update_task(task_id, payload.model_dump(exclude_unset=True))

    @app.delete("/api/v1/tasks/{task_id}")
    def delete_task(task_id: str, hard: bool = Query(False)):
        return engine.delete_task(task_id, hard=hard)

    @app.post("/api/v1/tasks/{task_id}/plan")
    def plan_task(task_id: str):
        return engine.plan_task(task_id)

    @app.post("/api/v1/tasks/{task_id}/execute")
    def execute_task(task_id: str, wait: bool = Query(False)):
        return engine.execute_task(task_id, wait=wait)

    @app.post("/api/v1/tasks/{task_id}/approve")
    def approve_task(task_id: str, payload: ApprovalRequest):
        return engine.approve_task(
            task_id,
            decision=payload.decision,
            note=payload.note,
            start_execution=payload.start_execution,
            wait=payload.wait,
        )

    @app.post("/api/v1/tasks/{task_id}/cancel")
    def cancel_task(task_id: str):
        return engine.cancel_task(task_id)

    @app.get("/api/v1/tasks/{task_id}/events")
    def task_events(task_id: str, limit: int = Query(500, ge=1, le=1000)):
        engine.get_task(task_id, include_children=False)
        return engine.list_audit(task_id=task_id, limit=limit)

    @app.get("/api/v1/tasks/{task_id}/evidence")
    def task_evidence(task_id: str, limit: int = Query(200, ge=1, le=500)):
        engine.get_task(task_id, include_children=False)
        return engine.list_evidence(task_id=task_id, limit=limit)

    @app.get("/api/v1/tasks/{task_id}/report")
    def task_report(task_id: str):
        report = engine.task_report(task_id)
        return JSONResponse(
            content=report,
            headers={
                "Content-Disposition": f'attachment; filename="crest-task-{task_id}.json"'
            },
        )

    # ------------------------------------------------------------- providers
    @app.get("/api/v1/providers")
    def list_providers():
        return engine.list_providers()

    @app.get("/api/v1/models")
    def list_models():
        out = []
        for provider in engine.list_providers():
            for model in provider["models"]:
                out.append({
                    "id": f"{provider['id']}/{model}",
                    "model": model,
                    "name": f"{provider['name']} — {model}",
                    "provider": provider["id"],
                    "provider_name": provider["name"],
                    "provider_kind": provider["kind"],
                    "available": provider["status"] == "ready",
                    "external": provider["external"],
                    "cost_configured": provider["cost_configured"],
                    "input_cost_per_1k": provider["input_cost_per_1k"],
                    "output_cost_per_1k": provider["output_cost_per_1k"],
                })
        return out

    @app.put("/api/v1/providers/{provider_id}")
    def update_provider(provider_id: str, payload: ProviderUpdate):
        return engine.update_provider(provider_id, payload.model_dump(exclude_unset=True))

    @app.post("/api/v1/providers/{provider_id}/test")
    def test_provider(provider_id: str, payload: ProviderTestRequest):
        return engine.test_provider(provider_id, confirm=payload.confirm, model=payload.model)

    # --------------------------------------------------------------- routing
    @app.get("/api/v1/routing")
    def get_routing():
        return engine.list_routing()

    @app.put("/api/v1/routing")
    def update_routing(payload: RoutingUpdate):
        return engine.update_routing(
            [rule.model_dump() for rule in payload.rules],
            fallback_enabled=payload.fallback_enabled,
        )

    # -------------------------------------------------------------- settings
    @app.get("/api/v1/settings")
    def read_settings():
        return get_settings(db)

    @app.put("/api/v1/settings")
    def write_settings(payload: SettingsUpdate):
        updates = payload.model_dump(exclude_unset=True)
        previous = get_settings(db)
        try:
            result = update_settings(db, updates)
        except ValueError as exc:
            raise _error(422, str(exc)) from exc
        if "operating_mode" in updates and previous["operating_mode"] != result["operating_mode"]:
            engine._audit(
                task_id=None, execution_id=None, event_type="POLICY_CHANGED",
                detail={
                    "field": "operating_mode",
                    "from": previous["operating_mode"],
                    "to": result["operating_mode"],
                },
            )
        if "execution_paused" in updates and previous["execution_paused"] != result["execution_paused"]:
            engine._audit(
                task_id=None, execution_id=None,
                event_type="EXECUTION_PAUSED" if result["execution_paused"] else "EXECUTION_RESUMED",
                detail={"scope": "global", "source": "settings"},
            )
        engine._audit(
            task_id=None, execution_id=None, event_type="SETTINGS_UPDATED",
            detail={"fields": sorted(updates)},
        )
        return result

    @app.get("/api/v1/autonomy/levels")
    def autonomy_levels():
        settings = get_settings(db)
        return {
            "levels": engine.levels(),
            "modes": mode_info(),
            "matrix": permissions_matrix(settings),
            "settings": settings,
        }

    # --------------------------------------------------------------- controls
    @app.get("/api/v1/control")
    def control():
        return engine.control_status()

    @app.post("/api/v1/control/pause")
    def pause_execution():
        return engine.set_paused(True)

    @app.post("/api/v1/control/resume")
    def resume_execution():
        return engine.set_paused(False)

    @app.post("/api/v1/control/stop-all")
    def stop_all():
        return engine.stop_all()

    @app.post("/api/v1/control/shutdown")
    def shutdown_backend(request: Request):
        expected = os.environ.get("CREST_SHUTDOWN_TOKEN")
        if not expected:
            raise _error(404, "shutdown endpoint is disabled")
        supplied = request.headers.get("x-crest-shutdown-token", "")
        if not secrets.compare_digest(supplied, expected):
            raise _error(403, "invalid shutdown token")

        def _finish() -> None:
            import time

            time.sleep(0.2)
            try:
                engine.shutdown()
            finally:
                os._exit(0)

        import threading

        threading.Thread(target=_finish, daemon=True).start()
        return {"status": "shutting_down"}

    @app.get("/api/v1/modes")
    def modes():
        settings = get_settings(db)
        return {
            "modes": mode_info(),
            "current": settings["operating_mode"],
            "matrix": permissions_matrix(settings),
        }

    @app.put("/api/v1/modes")
    def set_mode(payload: ModeUpdate):
        return engine.set_operating_mode(payload.mode)

    # ------------------------------------------------------------ credentials
    @app.get("/api/v1/credentials")
    def credential_status():
        return engine.credential_status()

    @app.put("/api/v1/credentials/{provider_id}")
    def set_credential(provider_id: str, payload: CredentialSetRequest):
        if not payload.confirm:
            raise _error(422, "explicit confirmation is required to store a credential")
        return engine.set_provider_credential(
            provider_id, payload.api_key.get_secret_value()
        )

    @app.delete("/api/v1/credentials/{provider_id}")
    def clear_credential(provider_id: str):
        return engine.clear_provider_credential(provider_id)

    @app.get("/api/v1/providers/{provider_id}/usage")
    def provider_usage(provider_id: str, limit: int = Query(100, ge=1, le=500)):
        engine._provider_row(provider_id)
        return engine.provider_usage(provider_id=provider_id, limit=limit)

    @app.post("/api/v1/providers/{provider_id}/models/discover")
    def discover_models(provider_id: str, payload: ProviderTestRequest):
        return engine.discover_models(provider_id, confirm=payload.confirm)

    # ---------------------------------------------------------------- backups
    @app.get("/api/v1/backups")
    def list_backups():
        return {"items": engine.list_backups(), "directory": str(engine.backups.directory)}

    @app.post("/api/v1/backups")
    def create_backup(payload: BackupCreateRequest):
        return engine.create_backup(note=payload.note)

    @app.post("/api/v1/backups/verify")
    def verify_backup(payload: BackupNameRequest):
        return engine.verify_backup(payload.name)

    @app.post("/api/v1/backups/restore")
    def restore_backup(payload: BackupRestoreRequest):
        return engine.restore_backup(payload.name, confirm=payload.confirm)

    @app.get("/api/v1/backups/{name}/download")
    def download_backup(name: str):
        path = engine.backup_file(name)
        return FileResponse(
            str(path), media_type="application/vnd.sqlite3",
            filename=path.name,
        )

    @app.post("/api/v1/import/validate")
    def validate_import(payload: ImportValidateRequest):
        return validate_export_payload(payload.payload)

    # ----------------------------------------------------------------- audit
    @app.get("/api/v1/audit")
    def audit(
        task_id: str | None = Query(None),
        event_type: str | None = Query(None),
        search: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        return engine.list_audit(
            task_id=task_id, event_type=event_type, search=search, limit=limit, offset=offset
        )

    @app.get("/api/v1/evidence")
    def evidence(
        task_id: str | None = Query(None),
        kind: str | None = Query(None),
        status: str | None = Query(None),
        search: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        return engine.list_evidence(
            task_id=task_id, kind=kind, status=status, search=search,
            limit=limit, offset=offset,
        )

    @app.get("/api/v1/evidence/{evidence_id}")
    def evidence_detail(evidence_id: str):
        return engine.get_evidence(evidence_id)

    @app.get("/api/v1/approvals")
    def approvals(status: str | None = Query(None), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return engine.list_approvals(status=status, limit=limit, offset=offset)

    # ------------------------------------------------------------------ stats
    @app.get("/api/v1/stats/overview")
    def overview():
        return engine.stats()

    @app.get("/api/v1/budgets/summary")
    def budgets_summary():
        settings = get_settings(db)
        stats = engine.stats()
        tasks = engine.list_tasks(limit=200)["items"]
        usage = [
            {
                "id": task["id"], "title": task["title"], "status": task["status"],
                "budget": task["budget"], "cost": task["cost"],
                "token_budget": task["token_budget"],
                "tokens": int(task["input_tokens"]) + int(task["output_tokens"]),
                "provider": task["provider"], "model": task["model"],
            }
            for task in tasks
        ]
        return {
            "limits": {
                "max_task_budget": settings["max_task_budget"],
                "max_token_budget": settings["max_token_budget"],
                "max_execution_seconds": settings["max_execution_seconds"],
                "default_budget": settings["default_budget"],
                "default_token_budget": settings["default_token_budget"],
            },
            "totals": {
                "cost": stats["budget_used"],
                "input_tokens": stats["input_tokens"],
                "output_tokens": stats["output_tokens"],
                "tokens": stats["input_tokens"] + stats["output_tokens"],
                "tasks": stats["total_tasks"],
            },
            "tasks": usage,
        }

    # --------------------------------------------------------------- exports
    @app.get("/api/v1/export")
    def export_all():
        payload = engine.export_all()
        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": f'attachment; filename="crest-backup-{now_iso()[:10]}.json"'
            },
        )

    @app.post("/api/v1/maintenance/purge")
    def purge(confirm: bool = Query(False), force: bool = Query(False)):
        return engine.purge_old(confirm=confirm, force=force)

    # ------------------------------------------------------------- frontend
    if (_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise _error(404, "not found")
        # Serve real files that live at the dist root (favicon, icons, etc.)
        # without allowing path traversal outside the build directory.
        if full_path:
            dist_root = _DIST.resolve()
            candidate = (_DIST / full_path).resolve()
            try:
                candidate.relative_to(dist_root)
            except ValueError:
                raise _error(404, "not found")
            if candidate.is_file():
                return FileResponse(str(candidate))
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse(
            """<!doctype html><html><head><meta charset="utf-8"><title>CREST 1.0</title>
            <style>body{font-family:system-ui;max-width:760px;margin:60px auto;padding:0 20px;line-height:1.6}
            code{background:#f1f5f9;padding:2px 6px;border-radius:4px}</style></head><body>
            <h1>CREST 1.0 backend is running</h1>
            <p>The web dashboard has not been built yet. From the repository root run:</p>
            <pre><code>cd web
npm install
npm run build</code></pre>
            <p>Then reload this page. API documentation: <a href="/api/docs">/api/docs</a></p>
            </body></html>""",
            status_code=200,
        )

    return app


app = create_app()
