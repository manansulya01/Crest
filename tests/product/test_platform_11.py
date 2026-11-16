"""CREST 1.1 platform, security, reliability, and Windows tests.

These tests use real SQLite, the real engine, and the real API.  External
provider tests use a local loopback HTTP server only; no paid provider calls
are made.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from crest.product.credentials import CredentialStore, describe_backend
from crest.product.db import Database, _SCHEMA_SQL
from crest.product.logging_setup import configure_logging, tail_log
from crest.product.platform import app_data_dir

from .conftest import create_task, execute


def test_health_reports_1_1_schema_and_credentials(client):
    body = client.get("/api/v1/health").json()
    assert body["version"] == "1.1.0"
    assert body["schema_version"] == 2
    assert body["database"] == "ok"
    assert body["credentials"]["backend"] in ("dpapi", "aes-gcm-portable")
    assert body["control"]["operating_mode"] == "supervised"


def test_schema_migration_preserves_existing_database(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA_SQL)
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        ("legacy-task", "Preserved task", "pending", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute("PRAGMA user_version=1")
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.schema_version() == 2
    with db.read() as check:
        assert check.execute("SELECT title FROM tasks WHERE id='legacy-task'").fetchone()[0] == "Preserved task"
        columns = {row[1] for row in check.execute("PRAGMA table_info(providers)")}
        assert {"retry_max", "rate_limit_per_minute"} <= columns
        assert check.execute("SELECT COUNT(*) FROM provider_credentials").fetchone()[0] == 0


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is a Windows facility")
def test_dpapi_credentials_are_encrypted_at_rest(tmp_path):
    db = Database(tmp_path / "crest.db")
    store = CredentialStore(db, tmp_path)
    assert store.backend == "dpapi"
    secret = "sk-test-DPAPI-secret-value-123456"
    status = store.set("gemini", secret)
    assert status["method"] == "dpapi"
    assert store.get("gemini") == secret
    raw = db.path.read_bytes()
    assert secret.encode() not in raw
    store.delete("gemini")
    assert store.get("gemini") is None


def test_credential_api_never_returns_the_secret(client):
    secret = "sk-credential-api-test-secret-987654321"
    response = client.put(
        "/api/v1/credentials/gemini",
        json={"api_key": secret, "confirm": True},
    )
    assert response.status_code == 200, response.text
    assert secret not in response.text
    assert "api_key" not in response.json()

    status = client.get("/api/v1/credentials").json()
    assert status["providers"]
    gemini = next(p for p in status["providers"] if p["provider_id"] == "gemini")
    assert gemini["configured"] is True
    assert secret not in json.dumps(status)

    with client.app.state.db.read() as conn:
        blob = conn.execute(
            "SELECT ciphertext FROM provider_credentials WHERE provider_id='gemini'"
        ).fetchone()[0]
    assert secret.encode() not in bytes(blob)

    cleared = client.delete("/api/v1/credentials/gemini")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False


def test_manual_mode_routes_low_risk_execution_to_approval(client):
    assert client.put("/api/v1/settings", json={"operating_mode": "manual"}).status_code == 200
    task = create_task(client, title="Manual mode task")
    pending = execute(client, task["id"]).json()
    assert pending["status"] == "awaiting_approval"
    assert pending["approval"]["status"] == "pending"

    approved = client.post(
        f"/api/v1/tasks/{task['id']}/approve",
        json={"decision": "approve", "note": "manual approval", "start_execution": True, "wait": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "completed"


def test_supervised_mode_gates_medium_risk(client):
    task = create_task(client, title="Supervised medium", risk_class="med")
    pending = execute(client, task["id"]).json()
    assert pending["status"] == "awaiting_approval"


def test_bounded_autonomous_mode_still_gates_high_risk(client):
    assert client.put("/api/v1/settings", json={"operating_mode": "bounded_autonomous"}).status_code == 200
    task = create_task(client, title="Bounded high risk", risk_class="high")
    pending = execute(client, task["id"]).json()
    assert pending["status"] == "awaiting_approval"

    approved = client.post(
        f"/api/v1/tasks/{task['id']}/approve",
        json={"decision": "approve", "note": "still gated", "start_execution": True, "wait": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "abstained"
    assert approved.json()["gate_decision"] == "ABSTAIN"


def test_pause_blocks_new_executions_and_resume_restores_them(client):
    paused = client.post("/api/v1/control/pause")
    assert paused.status_code == 200
    assert paused.json()["paused"] is True

    task = create_task(client, title="Paused task")
    blocked = execute(client, task["id"])
    assert blocked.status_code == 409
    assert "paused" in blocked.json()["detail"].lower()

    resumed = client.post("/api/v1/control/resume")
    assert resumed.json()["paused"] is False
    completed = execute(client, task["id"])
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_stop_all_cancels_pending_tasks(client):
    first = create_task(client, title="Stop one")
    second = create_task(client, title="Stop two")
    result = client.post("/api/v1/control/stop-all").json()
    assert result["cancelled"] >= 2
    assert client.get(f"/api/v1/tasks/{first['id']}").json()["status"] == "cancelled"
    assert client.get(f"/api/v1/tasks/{second['id']}").json()["status"] == "cancelled"


def test_backup_create_verify_restore_roundtrip(client):
    original = create_task(client, title="Before backup")
    assert execute(client, original["id"]).json()["status"] == "completed"

    created = client.post("/api/v1/backups", json={"note": "pytest roundtrip"})
    assert created.status_code == 200, created.text
    manifest = created.json()
    assert manifest["verified"] is True
    assert len(manifest["sha256"]) == 64

    listed = client.get("/api/v1/backups").json()
    assert any(item["name"] == manifest["backup"] for item in listed["items"])
    verified = client.post("/api/v1/backups/verify", json={"name": manifest["backup"]})
    assert verified.status_code == 200
    assert verified.json()["valid"] is True

    later = create_task(client, title="After backup")
    assert execute(client, later["id"]).json()["status"] == "completed"

    restored = client.post(
        "/api/v1/backups/restore",
        json={"name": manifest["backup"], "confirm": True},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] == manifest["backup"]
    assert client.get(f"/api/v1/tasks/{original['id']}").status_code == 200
    assert client.get(f"/api/v1/tasks/{later['id']}").status_code == 404


def test_backup_path_traversal_is_rejected(client):
    response = client.post("/api/v1/backups/verify", json={"name": "../crest.db"})
    assert response.status_code == 422


def test_browser_csrf_protection(client):
    token = client.get("/api/v1/security/csrf").json()["token"]
    headers = {"Origin": "http://127.0.0.1:8765"}
    denied = client.put("/api/v1/settings", json={"onboarding_complete": True}, headers=headers)
    assert denied.status_code == 403

    allowed = client.put(
        "/api/v1/settings",
        json={"onboarding_complete": True},
        headers={**headers, "X-Crest-CSRF": token},
    )
    assert allowed.status_code == 200

    evil = client.put(
        "/api/v1/settings",
        json={"onboarding_complete": True},
        headers={"Origin": "https://evil.example", "X-Crest-CSRF": token},
    )
    assert evil.status_code == 403


def test_import_validation_accepts_exports_and_rejects_secrets(client):
    export = client.get("/api/v1/export").json()
    valid = client.post("/api/v1/import/validate", json={"payload": export})
    assert valid.status_code == 200, valid.text
    assert valid.json()["valid"] is True

    export["tables"]["tasks"].append({"api_key": "sk-should-not-be-imported"})
    invalid = client.post("/api/v1/import/validate", json={"payload": export})
    assert invalid.status_code == 422


def test_logs_redact_secret_material(tmp_path):
    configure_logging(tmp_path, console=False)
    import logging

    logging.getLogger("crest.test").warning(
        "Authorization: Bearer sk-super-secret-value-1234567890"
    )
    tail = tail_log(tmp_path, lines=50)
    assert "sk-super-secret-value-1234567890" not in tail
    assert "[REDACTED" in tail


class _RetryHandler(BaseHTTPRequestHandler):
    calls = 0
    fail_first = True

    def do_POST(self):  # noqa: N802
        type(self).calls += 1
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        if type(self).fail_first and type(self).calls == 1:
            body = json.dumps({"error": "rate limited"}).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps(
            {
                "id": "local-test-1",
                "choices": [
                    {"message": {"content": "CREST local mock provider response"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 4},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


@pytest.fixture
def local_provider():
    _RetryHandler.calls = 0
    _RetryHandler.fail_first = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RetryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _configure_external(client, base_url, *, retry_max=2):
    provider = client.put(
        "/api/v1/providers/openai-compatible",
        json={
            "enabled": True,
            "base_url": base_url,
            "models": ["test-model"],
            "default_model": "test-model",
            "retry_max": retry_max,
            "rate_limit_per_minute": 60,
            "timeout_seconds": 5,
        },
    )
    assert provider.status_code == 200, provider.text
    credential = client.put(
        "/api/v1/credentials/openai-compatible",
        json={"api_key": "sk-local-provider-test-key", "confirm": True},
    )
    assert credential.status_code == 200, credential.text
    settings = client.put(
        "/api/v1/settings",
        json={
            "allow_external_calls": True,
            "require_approval_external": False,
            "provider_backoff_seconds": 0,
            "provider_max_retries": 2,
            "max_recovery_attempts": 0,
            "operating_mode": "supervised",
        },
    )
    assert settings.status_code == 200, settings.text


def test_provider_retries_rate_limit_and_records_usage(client, local_provider):
    _configure_external(client, local_provider)
    task = create_task(
        client,
        title="Local provider retry",
        provider="openai-compatible",
        model="test-model",
    )
    result = execute(client, task["id"])
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "completed", body
    assert _RetryHandler.calls == 2

    usage = client.get("/api/v1/providers/openai-compatible/usage").json()
    statuses = {item["status"] for item in usage["items"]}
    assert "error" in statuses
    assert "ok" in statuses
    assert usage["totals"]["calls"] >= 2
    assert usage["totals"]["input_tokens"] >= 7


def test_invalid_provider_credential_fails_without_leaking_secret(client, local_provider):
    _RetryHandler.fail_first = False
    _configure_external(client, local_provider)

    class Unauthorized(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("content-length") or 0)
            self.rfile.read(length)
            body = b'{"error":"invalid api key"}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Unauthorized)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert client.put(
            "/api/v1/providers/openai-compatible",
            json={"base_url": f"http://127.0.0.1:{server.server_port}"},
        ).status_code == 200
        task = create_task(
            client,
            title="Invalid credential",
            provider="openai-compatible",
            model="test-model",
        )
        result = execute(client, task["id"]).json()
        assert result["status"] == "failed"
        assert "401" in (result["error"] or "")
        assert "sk-local-provider-test-key" not in json.dumps(result)
        assert "sk-local-provider-test-key" not in json.dumps(
            client.get("/api/v1/providers/openai-compatible/usage").json()
        )
    finally:
        server.shutdown()
        server.server_close()


def test_default_data_dir_is_platform_appropriate(monkeypatch, tmp_path):
    monkeypatch.delenv("CREST_DATA_DIR", raising=False)
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert app_data_dir() == (tmp_path / "CREST").resolve()
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert app_data_dir() == (tmp_path / "crest").resolve()


def test_describe_backend_is_honest_about_storage():
    info = describe_backend()
    if os.name == "nt":
        assert info["windows_dpapi"] is True
        assert info["backend"] == "dpapi"
    assert "detail" in info
