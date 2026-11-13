import os
import tempfile

# Keep the module-level FastAPI app from writing into the user's home directory
# when tests import the API module.
os.environ.setdefault("CREST_DATA_DIR", tempfile.mkdtemp(prefix="crest-test-data-"))

import pytest
from fastapi.testclient import TestClient

from crest.product.api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=tmp_path / "crest.db")


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def create_task(client, **overrides):
    payload = {
        "title": "Test task",
        "description": "A deterministic offline test task",
        "risk_class": "low",
        "autonomy_level": 3,
        "provider": "mock",
        "model": "mock-fast",
        "budget": 1.0,
        "token_budget": 4096,
        "timeout_seconds": 30,
        "acceptance_criteria": ["CREST"],
    }
    payload.update(overrides)
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def execute(client, task_id, wait=True):
    suffix = "?wait=true" if wait else ""
    return client.post(f"/api/v1/tasks/{task_id}/execute{suffix}")
