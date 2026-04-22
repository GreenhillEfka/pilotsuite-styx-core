"""Autonomy API Contract Tests — CORE-HARDEN-207"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import autonomy
from unittest.mock import patch, MagicMock
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(autonomy.autonomy_bp)
    return app


def _make_mock_executor():
    """Create a fully populated mock executor with nested mock chains."""
    e = MagicMock()
    e.get_dashboard.return_value = {"active_rules": 4, "pending_actions": 1, "mood": "balanced"}
    e.get_zone_status.return_value = {"zone_id": "living-room", "mood": "comfort", "active_rules": 2}
    e.set_zone_module_state.return_value = True
    e.get_zone_history.return_value = [{"timestamp": "2026-04-22T10:00:00", "event": "mood_change"}]
    e.get_mood_actions.return_value = [{"mood": "focused", "actions": [{"type": "dim_lights", "params": {"level": 50}}]}]
    e.set_mood_override.return_value = True
    e.get_stats.return_value = {"total_rules": 10, "active_rules": 4, "triggered_today": 23}
    # Nested mock chain: _executor._zone_automation.get_automation_mode()
    e._zone_automation.get_automation_mode.return_value = "active"
    # Nested: _module_registry.get_zone_states() and set_zone_state()
    e._module_registry.get_zone_states.return_value = {"climate": "on", "lights": "off"}
    e._module_registry.set_zone_state.return_value = True
    # Nested: _behavioral_log.get_zone_history()
    e._behavioral_log.get_zone_history.return_value = [{"timestamp": "2026-04-22T10:00:00", "event": "mood_change"}]
    e._behavioral_log.get_stats.return_value = {"total_events": 42}
    # _stats dict
    e._stats = {}
    # _get_mood_mapper chain
    e._get_mood_mapper.return_value.get_all_actions.return_value = []
    e._get_mood_mapper.return_value.set_override.return_value.to_dict.return_value = {"ok": True}
    return e


def _patch_auth():
    return patch.object(security, 'validate_token', return_value=True)


# Real routes from Flask URL map:
# GET  /api/v1/autonomy/dashboard
# GET  /api/v1/autonomy/mood-actions
# POST /api/v1/autonomy/mood-actions/<mood>/override
# GET  /api/v1/autonomy/stats
# GET  /api/v1/autonomy/zones/<zone_id>
# GET  /api/v1/autonomy/zones/<zone_id>/history
# POST /api/v1/autonomy/zones/<zone_id>/module


class TestAutonomyDashboard:
    def test_get_dashboard_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/dashboard")
            assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_get_dashboard_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/autonomy/dashboard")
        assert r.status_code in (401, 403)

    def test_get_dashboard_no_executor_returns_503(self):
        app = _make_app()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=None, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/dashboard")
            assert r.status_code == 503, f"expected 503, got {r.status_code}"


class TestAutonomyZoneStatus:
    def test_get_zone_status_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/zones/living-room")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_zone_status_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/autonomy/zones/living-room")
        assert r.status_code in (401, 403)


class TestAutonomyZoneModuleState:
    def test_set_zone_module_state_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=mock_executor._module_registry)
            client = app.test_client()
            r = client.post(
                "/api/v1/autonomy/zones/living-room/module",
                json={"module_id": "climate", "state": "on"},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_set_zone_module_state_rejects_missing_module_id(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=mock_executor._module_registry)
            client = app.test_client()
            r = client.post(
                "/api/v1/autonomy/zones/living-room/module",
                json={"state": "on"},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code}"

    def test_set_zone_module_state_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/autonomy/zones/living-room/module",
            json={"module_id": "climate", "state": {"power": "on"}},
        )
        assert r.status_code in (401, 403)


class TestAutonomyZoneHistory:
    def test_get_zone_history_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/zones/living-room/history")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_zone_history_with_limit(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/zones/living-room/history?limit=5")
            assert r.status_code == 200

    def test_get_zone_history_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/autonomy/zones/living-room/history")
        assert r.status_code in (401, 403)


class TestAutonomyMoodActions:
    def test_get_mood_actions_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/mood-actions")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_mood_actions_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/autonomy/mood-actions")
        assert r.status_code in (401, 403)


class TestAutonomyMoodOverride:
    def test_set_mood_override_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.post(
                "/api/v1/autonomy/mood-actions/focused/override",
                json={"actions": [{"type": "dim_lights", "params": {"level": 30}}]},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_set_mood_override_rejects_empty_body(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.post("/api/v1/autonomy/mood-actions/focused/override", json=None)
            assert r.status_code == 400

    def test_set_mood_override_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/autonomy/mood-actions/focused/override", json={})
        assert r.status_code in (401, 403)


class TestAutonomyStats:
    def test_get_stats_returns_200(self):
        app = _make_app()
        mock_executor = _make_mock_executor()
        with _patch_auth():
            autonomy.init_autonomy_api(executor=mock_executor, module_registry=None)
            client = app.test_client()
            r = client.get("/api/v1/autonomy/stats")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_stats_unauthorized(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/autonomy/stats")
        assert r.status_code in (401, 403)


class TestAutonomyAllAuth:
    def test_all_endpoints_require_authorization(self):
        app = _make_app()
        client = app.test_client()
        endpoints = [
            ("GET", "/api/v1/autonomy/dashboard"),
            ("GET", "/api/v1/autonomy/zones/living-room"),
            ("POST", "/api/v1/autonomy/zones/living-room/module", {"module_id": "x", "state": {}}),
            ("GET", "/api/v1/autonomy/zones/living-room/history"),
            ("GET", "/api/v1/autonomy/mood-actions"),
            ("POST", "/api/v1/autonomy/mood-actions/focused/override", {}),
            ("GET", "/api/v1/autonomy/stats"),
        ]
        for method, path, *rest in endpoints:
            body = rest[0] if rest else None
            r = client.open(path, method=method, json=body)
            assert r.status_code in (401, 403), f"{method} {path}: expected 401/403, got {r.status_code}"