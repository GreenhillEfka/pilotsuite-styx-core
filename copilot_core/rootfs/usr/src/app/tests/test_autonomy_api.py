"""Tests for Autonomy REST API endpoints."""

import json
from unittest.mock import MagicMock

import pytest
from flask import Flask

from copilot_core.api.v1.autonomy import autonomy_bp, init_autonomy_api


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.get_dashboard.return_value = {
        "zones": [{"zone_id": "wohnbereich", "automation_mode": "autonomy"}],
        "stats": {"total_events": 10, "executed": 5},
        "log": {"doc_count": 3},
        "rate_limit_seconds": 30,
    }
    executor._stats = {"total_events": 10, "executed": 5, "suggested": 3, "skipped": 2, "errors": 0}
    executor._zone_automation = MagicMock()
    executor._zone_automation.get_automation_mode.return_value = "autonomy"
    executor._behavioral_log = MagicMock()
    executor._behavioral_log.get_zone_history.return_value = []
    executor._behavioral_log.get_stats.return_value = {"doc_count": 3}

    mapper_mock = MagicMock()
    mapper_mock.get_all_actions.return_value = {
        "relax": {"mood": "relax", "brightness_pct": 50, "overridden": False},
    }
    from copilot_core.autonomy.mood_actions import MoodActionSet
    mapper_mock.set_override.return_value = MoodActionSet(mood="relax", brightness_pct=70)
    executor._get_mood_mapper.return_value = mapper_mock

    return executor


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.get_zone_states.return_value = {"licht": "active", "musik": "learning"}
    registry.set_zone_state.return_value = True
    return registry


@pytest.fixture
def client(mock_executor, mock_registry):
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_autonomy_api(mock_executor, mock_registry)
    app.register_blueprint(autonomy_bp)
    with app.test_client() as c:
        yield c


class TestDashboard:
    def test_get_dashboard(self, client, mock_executor):
        resp = client.get("/api/v1/autonomy/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "zones" in data
        assert "stats" in data
        mock_executor.get_dashboard.assert_called_once()


class TestZoneStatus:
    def test_get_zone_status(self, client, mock_registry):
        resp = client.get("/api/v1/autonomy/zones/wohnbereich")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["zone_id"] == "wohnbereich"
        assert data["automation_mode"] == "autonomy"
        assert data["module_states"] == {"licht": "active", "musik": "learning"}

    def test_set_zone_module_state(self, client, mock_registry):
        resp = client.post(
            "/api/v1/autonomy/zones/wohnbereich/module",
            json={"module_id": "licht", "state": "off"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        mock_registry.set_zone_state.assert_called_with("wohnbereich", "licht", "off")

    def test_set_zone_module_missing_fields(self, client):
        resp = client.post(
            "/api/v1/autonomy/zones/wohnbereich/module",
            json={},
        )
        assert resp.status_code == 400

    def test_set_zone_module_invalid_state(self, client, mock_registry):
        mock_registry.set_zone_state.return_value = False
        resp = client.post(
            "/api/v1/autonomy/zones/wohnbereich/module",
            json={"module_id": "licht", "state": "invalid"},
        )
        assert resp.status_code == 400


class TestZoneHistory:
    def test_get_zone_history(self, client, mock_executor):
        resp = client.get("/api/v1/autonomy/zones/wohnbereich/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["zone_id"] == "wohnbereich"
        assert "history" in data


class TestMoodActions:
    def test_get_mood_actions(self, client, mock_executor):
        resp = client.get("/api/v1/autonomy/mood-actions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "relax" in data["actions"]

    def test_set_mood_override(self, client, mock_executor):
        resp = client.post(
            "/api/v1/autonomy/mood-actions/relax/override",
            json={"brightness_pct": 70},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mood"] == "relax"

    def test_set_mood_override_empty_body(self, client):
        resp = client.post(
            "/api/v1/autonomy/mood-actions/relax/override",
            data="",
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestStats:
    def test_get_stats(self, client, mock_executor):
        resp = client.get("/api/v1/autonomy/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_events" in data
        assert "executed" in data


class TestNoExecutor:
    def test_dashboard_503(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        init_autonomy_api(None, None)
        app.register_blueprint(autonomy_bp)
        with app.test_client() as c:
            resp = c.get("/api/v1/autonomy/dashboard")
            assert resp.status_code == 503
