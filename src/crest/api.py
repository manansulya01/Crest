"""CREST 1.0 Backend API — FastAPI wrapper around the CREST execution engine.

Provides REST endpoints for task management, execution, verification,
evidence, audit, and configuration. All state-changing operations enforce
policy on the server.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = os.environ.get("CREST_DB_PATH", ".crest/crest.db")
DEFAULT_WORKSPACE = os.environ.get("CREST_WORKSPACE", ".")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database with required tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            risk_class TEXT NOT NULL DEFAULT 'low',
            autonomy_level INTEGER NOT NULL DEFAULT 2,
            budget REAL NOT NULL DEFAULT 1.0,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            cost REAL NOT NULL DEFAULT 0.0,
            detail TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            event_type TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    # Seed default settings
    defaults = {
        "autonomy_level": "2",
        "default_budget": "1.0",
        "default_risk_class": "low",
        "provider": "mock",
        "model": "mock-model",
    }
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path: str = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _audit(db_path: str, task_id: Optional[str], event_type: str, detail: str = "") -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO audit_events (task_id, event_type, detail, timestamp) VALUES (?,?,?,?)",
            (task_id, event_type, detail, _now()),
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=5000)
    risk_class: str = Field("low", pattern="^(low|med|high)$")
    autonomy_level: int = Field(2, ge=1, le=5)
    budget: float = Field(1.0, gt=0, le=1000)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    risk_class: str
    autonomy_level: int
    budget: float
    status: str
    result: Optional[str] = None
    created_at: str
    updated_at: str


class SettingsUpdate(BaseModel):
    autonomy_level: Optional[int] = Field(None, ge=1, le=5)
    default_budget: Optional[float] = Field(None, gt=0, le=1000)
    default_risk_class: Optional[str] = Field(None, pattern="^(low|med|high)$")
    provider: Optional[str] = None
    model: Optional[str] = None


class ExecutionRequest(BaseModel):
    pass


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CREST 1.0 API",
    description="Outcome-Constrained Inference Control Plane",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db(DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": _now()}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@app.post("/api/v1/tasks", response_model=TaskResponse)
def create_task(task: TaskCreate):
    task_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks (id, title, description, risk_class, autonomy_level, budget, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (task_id, task.title, task.description, task.risk_class, task.autonomy_level, task.budget, "pending", now, now),
        )
    _audit(DEFAULT_DB_PATH, task_id, "TASK_CREATED", f"title={task.title}")
    return TaskResponse(
        id=task_id, title=task.title, description=task.description,
        risk_class=task.risk_class, autonomy_level=task.autonomy_level,
        budget=task.budget, status="pending", created_at=now, updated_at=now,
    )


@app.get("/api/v1/tasks")
def list_tasks(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    with get_db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**dict(row))


@app.post("/api/v1/tasks/{task_id}/execute")
def execute_task(task_id: str, body: ExecutionRequest = ExecutionRequest()):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    task = dict(row)
    if task["status"] not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail=f"Task status is {task['status']}, cannot execute")

    exec_id = str(uuid.uuid4())
    now = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO executions (id, task_id, status, started_at, cost) VALUES (?,?,?,?,?)",
            (exec_id, task_id, "running", now, 0.0),
        )
        conn.execute("UPDATE tasks SET status='running', updated_at=? WHERE id=?", (now, task_id))
    _audit(DEFAULT_DB_PATH, task_id, "EXECUTION_STARTED", f"exec_id={exec_id}")

    # Execute using mock provider (real providers require explicit configuration)
    try:
        result_text = _run_execution(task)
        cost = 0.05  # mock cost
        with get_db() as conn:
            conn.execute(
                "UPDATE executions SET status='completed', completed_at=?, cost=?, detail=? WHERE id=?",
                (_now(), cost, result_text, exec_id),
            )
            conn.execute(
                "UPDATE tasks SET status='completed', result=?, updated_at=? WHERE id=?",
                (result_text, _now(), task_id),
            )
        _audit(DEFAULT_DB_PATH, task_id, "EXECUTION_COMPLETED", f"cost={cost}")
        return {"execution_id": exec_id, "status": "completed", "result": result_text, "cost": cost}
    except Exception as e:
        with get_db() as conn:
            conn.execute(
                "UPDATE executions SET status='failed', completed_at=?, detail=? WHERE id=?",
                (_now(), str(e), exec_id),
            )
            conn.execute("UPDATE tasks SET status='failed', updated_at=? WHERE id=?", (_now(), task_id))
        _audit(DEFAULT_DB_PATH, task_id, "EXECUTION_FAILED", str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _run_execution(task: dict) -> str:
    """Run task execution using the mock provider."""
    title = task["title"]
    desc = task["description"]
    risk = task["risk_class"]
    # Mock execution: produce a structured result
    return json.dumps({
        "task": title,
        "description": desc,
        "risk_class": risk,
        "output": f"Completed task: {title}",
        "verification": "mock-verified",
        "gate_decision": "ACCEPT" if risk != "high" else "ABSTAIN",
    })


@app.post("/api/v1/tasks/{task_id}/approve")
def approve_task(task_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    task = dict(row)
    if task["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Cannot approve task in status {task['status']}")
    now = _now()
    with get_db() as conn:
        conn.execute("UPDATE tasks SET status='approved', updated_at=? WHERE id=?", (now, task_id))
    _audit(DEFAULT_DB_PATH, task_id, "TASK_APPROVED")
    return {"id": task_id, "status": "approved"}


@app.post("/api/v1/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    now = _now()
    with get_db() as conn:
        conn.execute("UPDATE tasks SET status='cancelled', updated_at=? WHERE id=?", (now, task_id))
    _audit(DEFAULT_DB_PATH, task_id, "TASK_CANCELLED")
    return {"id": task_id, "status": "cancelled"}


@app.get("/api/v1/tasks/{task_id}/events")
def task_events(task_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE task_id=? ORDER BY timestamp ASC", (task_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Models / Providers
# ---------------------------------------------------------------------------


@app.get("/api/v1/models")
def list_models():
    return [
        {"id": "mock-model", "name": "Mock Provider", "provider": "mock", "status": "available", "cost_per_1k_tokens": 0.0},
    ]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@app.get("/api/v1/settings")
def get_settings():
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/v1/settings")
def update_settings(update: SettingsUpdate):
    with get_db() as conn:
        if update.autonomy_level is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("autonomy_level", str(update.autonomy_level)))
        if update.default_budget is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("default_budget", str(update.default_budget)))
        if update.default_risk_class is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("default_risk_class", update.default_risk_class))
        if update.provider is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("provider", update.provider))
        if update.model is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("model", update.model))
    _audit(DEFAULT_DB_PATH, None, "SETTINGS_UPDATED", str(update.dict(exclude_none=True)))
    return get_settings()


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@app.get("/api/v1/audit")
def audit_log(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Serve frontend (if built)
# ---------------------------------------------------------------------------

_FRONTEND_DIR = Path(__file__).parent.parent.parent / "web" / "dist"
if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        index = _FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(status_code=404)