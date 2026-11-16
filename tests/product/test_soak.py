"""Bounded soak checks for daily-use reliability.

These are deliberately small (seconds, not hours) so they run in ordinary CI.
They stress the same real engine, SQLite database, and FastAPI routes used by
the packaged desktop app: repeated executions, concurrency, backup churn, and
pause/resume cycling. No external provider is contacted.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .conftest import create_task, execute


def _run_task(client, index: int):
    task = create_task(
        client,
        title=f"Soak task {index}",
        risk_class="low",
        acceptance_criteria=["CREST"],
    )
    response = execute(client, task["id"], wait=True)
    assert response.status_code == 200, response.text
    return response.json()


def test_bounded_sequential_soak(client):
    for index in range(30):
        result = _run_task(client, index)
        assert result["status"] == "completed", (index, result)
    assert client.get("/api/v1/health").json()["database"] == "ok"
    events = client.get("/api/v1/audit?limit=1000").json()
    assert events["total"] >= 30
    assert client.get("/api/v1/diagnostics").json()["database"]["integrity"]["ok"] is True


def test_bounded_concurrent_soak(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: _run_task(client, i), range(12)))
    assert len(results) == 12
    assert all(result["status"] == "completed" for result in results)
    tasks = client.get("/api/v1/tasks?limit=100").json()
    assert len({task["id"] for task in tasks["items"]}) == 12
    assert client.get("/api/v1/diagnostics").json()["database"]["integrity"]["ok"] is True


def test_backup_create_verify_and_retention_soak(client):
    client.put("/api/v1/settings", json={"backup_keep": 3})
    for index in range(8):
        created = client.post("/api/v1/backups", json={"note": f"soak {index}"})
        assert created.status_code == 200, created.text
        manifest = created.json()
        assert manifest["verified"] is True
        verified = client.post("/api/v1/backups/verify", json={"name": manifest["backup"]})
        assert verified.json()["valid"] is True
    backups = client.get("/api/v1/backups").json()
    assert len(backups["items"]) <= 3
    assert all(item["manifest_present"] for item in backups["items"])


def test_pause_resume_cycles_do_not_deadlock(client):
    for index in range(8):
        assert client.post("/api/v1/control/pause").json()["paused"] is True
        task = create_task(client, title=f"Pause cycle {index}")
        blocked = execute(client, task["id"])
        assert blocked.status_code == 409
        assert client.post("/api/v1/control/resume").json()["paused"] is False
        completed = execute(client, task["id"], wait=True)
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
    assert client.get("/api/v1/control").json()["active_executions"] == 0
