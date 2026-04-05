"""Contract tests for events_ingest deprecation.

Slice 116 — events_ingest deprecated in favor of ha_events WebSocket API.
"""

import pytest
from flask import Flask

from copilot_core.api.v1 import events_ingest as module


@pytest.fixture
def client():
    """Test client."""
    app = Flask(__name__)
    app.register_blueprint(module.bp)
    with app.test_client() as c:
        yield c


def test_events_ingest_post_returns_410(client):
    """POST /api/v1/events returns 410 Gone with deprecation notice."""
    response = client.post("/api/v1/events", json={"items": []})
    assert response.status_code == 410
    data = response.get_json()
    assert data["ok"] is False
    assert "deprecated" in data
    assert data["deprecated"] is True
    assert "WebSocket" in data["message"] or "WebSocket" in data["error"]


def test_events_ingest_get_returns_410(client):
    """GET /api/v1/events returns 410 Gone with deprecation notice."""
    response = client.get("/api/v1/events")
    assert response.status_code == 410
    data = response.get_json()
    assert data["ok"] is False
    assert "deprecated" in data
    assert data["deprecated"] is True


def test_events_ingest_stats_returns_410(client):
    """GET /api/v1/events/stats returns 410 Gone with deprecation notice."""
    response = client.get("/api/v1/events/stats")
    assert response.status_code == 410
    data = response.get_json()
    assert data["ok"] is False
    assert "deprecated" in data
    assert data["deprecated"] is True


def test_events_ingest_has_migration_guide(client):
    """All deprecation responses include migration guide and sunset date."""
    for endpoint in ["/api/v1/events", "/api/v1/events/stats"]:
        response = client.get(endpoint)
        data = response.get_json()
        assert "migration_guide" in data
        assert "sunset_date" in data
        assert data["sunset_date"] == "2026-06-01"


def test_events_ingest_maintains_backward_compatibility_structure(client):
    """Response structure maintains backward compatibility keys even when deprecated."""
    response = client.post("/api/v1/events", json={"items": []})
    data = response.get_json()
    # Backward compatible keys
    assert "ok" in data
    assert "error" in data
