"""API contract and end-to-end product tests.

These tests exercise real FastAPI routes, real SQLite persistence, the real
execution engine, and the real High-Risk Gate.  The only simulated component is
the explicitly labelled offline mock provider.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from crest.product.api import create_app

from .conftest import create_task, execute


def test_health_reports_version_and_database(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
    assert body["database"] == "ok"


def test_offline_task_completes_with_evidence_and_gate(client):
    task = create_task(client, title="Offline CREST task")
    assert task["status"] == "pending"

    response = execute(client, task["id"])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed"
    assert result["verification_status"] == "passed"
    assert result["gate_decision"] == "ACCEPT"
    assert "CREST" in result["result"]
    kinds = {item["kind"] for item in result["evidence"]}
    assert {"provider_output", "deterministic_verification", "gate_decision"} <= kinds
    assert result["is_mock"] is True

    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert events["total"] >= 5
    event_types = {item["event_type"] for item in events["items"]}
    assert "EXECUTION_COMPLETED" in event_types
    assert "GATE_DECISION" in event_types


def test_high_risk_requires_approval_then_abstains(client):
    task = create_task(client, title="High risk task", risk_class="high")
    response = execute(client, task["id"])
    assert response.status_code == 200
    pending = response.json()
    assert pending["status"] == "awaiting_approval"
    assert pending["approval"]["status"] == "pending"

    approved = client.post(
        f"/api/v1/tasks/{task['id']}/approve",
        json={"decision": "approve", "wait": True},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "abstained"
    assert body["gate_decision"] == "ABSTAIN"
    assert "insufficient independent evidence" in body["gate_reason"]
    assert body["result"]  # output is retained for inspection, but not accepted


def test_assisted_mode_requires_fresh_approval(client):
    task = create_task(client, title="Assisted task", autonomy_level=2)
    response = execute(client, task["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"

    approved = client.post(
        f"/api/v1/tasks/{task['id']}/approve",
        json={"decision": "approve", "start_execution": False},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    result = execute(client, task["id"]).json()
    assert result["status"] == "completed"


def test_observe_mode_cannot_execute(client):
    task = create_task(client, title="Observe task", autonomy_level=1)
    response = execute(client, task["id"])
    assert response.status_code == 403
    assert "OBSERVE_MODE_NO_EXECUTION" in response.json()["detail"]
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["status"] == "denied"


def test_budget_exhaustion_fails_closed(client):
    task = create_task(client, title="Budget task", token_budget=5)
    result = execute(client, task["id"]).json()
    assert result["status"] == "budget_exhausted"
    assert result["result"] is None
    assert "budget" in result["error"].lower()
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert any(e["event_type"] == "BUDGET_EXHAUSTED" for e in events["items"])


def test_verification_failure_is_not_reported_as_success(client):
    task = create_task(
        client, title="Verification failure", demo_scenario="verification_failure"
    )
    result = execute(client, task["id"]).json()
    assert result["status"] == "failed"
    assert result["verification_status"] == "failed"
    assert result["gate_decision"] == "REJECT"
    assert "verification failed" in result["gate_reason"]
    assert "verification failed" in result["error"]


def test_recovery_retry_completes(client):
    task = create_task(client, title="Recovery demo", demo_scenario="recovery")
    result = execute(client, task["id"]).json()
    assert result["status"] == "completed"
    assert result["verification_status"] == "passed"
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    assert any(e["event_type"] == "RECOVERY_ATTEMPT" for e in events["items"])


def test_persistence_across_application_restart(tmp_path):
    db_path = tmp_path / "persistent.db"
    first = create_app(db_path=db_path)
    with TestClient(first) as client:
        task = create_task(client, title="Persistent task")
        execute(client, task["id"])
        task_id = task["id"]

    second = create_app(db_path=db_path)
    with TestClient(second) as client:
        detail = client.get(f"/api/v1/tasks/{task_id}").json()
        assert detail["status"] == "completed"
        assert detail["result"]
        assert len(detail["executions"]) == 1
        assert len(detail["evidence"]) >= 3


def test_idempotency_key_returns_same_task(client):
    first = create_task(client, title="Idempotent", idempotency_key="same-key")
    second = create_task(client, title="Idempotent", idempotency_key="same-key")
    assert first["id"] == second["id"]
    listing = client.get("/api/v1/tasks").json()
    assert listing["total"] == 1


def test_task_cannot_raise_own_autonomy(client):
    response = client.post(
        "/api/v1/tasks",
        json={"title": "Too much autonomy", "autonomy_level": 5},
    )
    assert response.status_code == 403
    assert "AUTONOMY_EXCEEDS_GLOBAL_MAX" in response.json()["detail"]

    task = create_task(client, title="Editable", autonomy_level=3)
    response = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"autonomy_level": 5}
    )
    assert response.status_code == 403


def test_custom_policy_denies_unlisted_action(client):
    client.put("/api/v1/settings", json={"max_autonomy_level": 5})
    task = create_task(
        client,
        title="Custom denied",
        autonomy_level=5,
        custom_policy={"allowed_actions": ["plan"]},
    )
    response = execute(client, task["id"])
    assert response.status_code == 403
    assert "ACTION_NOT_IN_CUSTOM_POLICY" in response.json()["detail"]
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["status"] == "denied"


def test_external_calls_disabled_blocks_provider_without_network(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-not-a-real-key")
    updated = client.put(
        "/api/v1/providers/gemini",
        json={"enabled": True, "models": ["gemini-2.5-flash"], "default_model": "gemini-2.5-flash"},
    )
    assert updated.status_code == 200, updated.text
    task = create_task(
        client,
        title="External disabled",
        provider="gemini",
        model="gemini-2.5-flash",
    )
    response = execute(client, task["id"])
    assert response.status_code == 403
    assert "EXTERNAL_CALLS_DISABLED" in response.json()["detail"]
    detail = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert detail["status"] == "denied"
    assert not detail["evidence"]


def test_provider_connection_test_requires_confirmation(client):
    response = client.post("/api/v1/providers/mock/test", json={"confirm": False})
    assert response.status_code == 422
    response = client.post(
        "/api/v1/providers/mock/test", json={"confirm": True, "model": "mock-fast"}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_settings_validation_and_audit(client):
    response = client.put("/api/v1/settings", json={"max_autonomy_level": 2})
    assert response.status_code == 200
    assert response.json()["max_autonomy_level"] == 2
    response = client.put("/api/v1/settings", json={"unknown": True})
    assert response.status_code == 422
    response = client.put("/api/v1/settings", json={"default_budget": 999999})
    assert response.status_code == 422
    audit = client.get("/api/v1/audit", params={"event_type": "SETTINGS_UPDATED"}).json()
    assert audit["total"] >= 1


def test_api_token_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("CREST_API_TOKEN", "test-token-123")
    app = create_app(db_path=tmp_path / "auth.db")
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/tasks").status_code == 401
        authorized = client.get(
            "/api/v1/tasks", headers={"Authorization": "Bearer test-token-123"}
        )
        assert authorized.status_code == 200
        wrong = client.get(
            "/api/v1/tasks", headers={"Authorization": "Bearer wrong"}
        )
        assert wrong.status_code == 401


def test_task_report_and_backup_export(client):
    task = create_task(client, title="Report task")
    execute(client, task["id"])
    report = client.get(f"/api/v1/tasks/{task['id']}/report")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert report.json()["task"]["id"] == task["id"]

    backup = client.get("/api/v1/export")
    assert backup.status_code == 200
    body = backup.json()
    assert body["application"]["version"] == "1.0.0"
    assert len(body["tables"]["tasks"]) == 1
    assert "providers" in body
    serialized = json.dumps(body).lower()
    assert "placeholder-not-a-real-key" not in serialized
    assert '"api_key":' not in serialized


def test_task_deletion_is_soft_by_default(client):
    task = create_task(client, title="Delete me")
    response = client.delete(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    audit = client.get("/api/v1/audit", params={"task_id": task["id"]}).json()
    assert any(e["event_type"] == "TASK_DELETED" for e in audit["items"])


def test_routing_update_and_models_listing(client):
    routing = client.get("/api/v1/routing").json()
    assert routing["rules"]
    payload = {
        "rules": [
            {"priority": 10, "risk_class": "*", "provider": "mock", "model": "mock-fast", "enabled": True}
        ],
        "fallback_enabled": False,
    }
    response = client.put("/api/v1/routing", json=payload)
    assert response.status_code == 200
    assert len(response.json()["rules"]) == 1
    models = client.get("/api/v1/models").json()
    assert any(m["provider"] == "mock" and m["model"] == "mock-fast" for m in models)


def test_interrupted_execution_is_not_reported_as_complete(tmp_path):
    db_path = tmp_path / "interrupted.db"
    first = create_app(db_path=db_path)
    with TestClient(first) as client:
        task = create_task(client, title="Interrupted task")
        # Simulate a process death after the execution row was created.
        with first.state.db.tx() as conn:
            conn.execute(
                "UPDATE tasks SET status='running' WHERE id=?", (task["id"],)
            )
            conn.execute(
                "INSERT INTO executions (id, task_id, status, attempt, provider, model) VALUES (?,?,?,?,?,?)",
                ("exec-interrupted", task["id"], "running", 1, "mock", "mock-fast"),
            )

    second = create_app(db_path=db_path)
    with TestClient(second) as client:
        detail = client.get(f"/api/v1/tasks/{task['id']}").json()
        assert detail["status"] == "interrupted"
        assert "not completed" in detail["error"]
        execution = detail["executions"][0]
        assert execution["status"] == "interrupted"
