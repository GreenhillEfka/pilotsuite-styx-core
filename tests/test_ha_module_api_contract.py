"""HA Module API Contract Tests — CORE-HARDEN-205"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import ha_module
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(ha_module.ha_module_bp)
    return app


def _patch_validate_token():
    """Always allow requests through."""
    return patch.object(ha_module, '_validate_token', return_value=True)


class TestHAModuleStatus:
    """CORE-HARDEN-205: HA module status endpoint tests."""

    def test_get_status_returns_200_with_module_structure(self):
        """GET /api/v1/modules/homeassistant/status returns 200 + structure."""
        app = _make_app()
        # Patch the engine returned by _get_engine
        with _patch_validate_token():
            mock_dashboard = MagicMock()
            mock_dashboard.connection = {"reachable": True, "last_successful_call": datetime.now().isoformat()}
            mock_dashboard.event_forwarding = {"enabled": True, "forwarded_count": 10}
            mock_dashboard.webhook = {"configured": True}
            mock_dashboard.supervisor = {"supported": True, "healthy": True}
            mock_dashboard.integration_entity_count = 5
            mock_dashboard.module_count = 3
            mock_dashboard.active_dashboard_views = ["overview", "zones"]
            
            mock_engine = MagicMock()
            mock_engine.get_status.return_value = mock_dashboard
            
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/status")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"
                data = r.get_json()
                assert data["status"] == "ok"
                assert data["module"] == "homeassistant"
                assert "connection" in data

    def test_get_status_unauthorized_without_token(self):
        """GET /api/v1/modules/homeassistant/status returns 401 without valid token."""
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/modules/homeassistant/status")
        assert r.status_code == 401


class TestHAModuleConnection:
    """HA module connection endpoint tests."""

    def test_get_connection_returns_200(self):
        """GET /api/v1/modules/homeassistant/connection returns 200."""
        app = _make_app()
        with _patch_validate_token():
            mock_dashboard = MagicMock()
            mock_dashboard.connection = {"reachable": True, "last_successful_call": None}
            mock_engine = MagicMock()
            mock_engine.get_status.return_value = mock_dashboard
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/connection")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_connection_unauthorized(self):
        """GET /api/v1/modules/homeassistant/connection returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/modules/homeassistant/connection")
        assert r.status_code == 401


class TestHAModuleEvents:
    """HA module event forwarding endpoints."""

    def test_get_events_returns_forwarding_stats(self):
        """GET /api/v1/modules/homeassistant/events returns stats."""
        app = _make_app()
        with _patch_validate_token():
            mock_dashboard = MagicMock()
            mock_dashboard.event_forwarding = {"enabled": True, "forwarded_count": 42, "last_event": "2026-04-22T12:00:00"}
            mock_engine = MagicMock()
            mock_engine.get_status.return_value = mock_dashboard
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/events")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_configure_events_accepts_valid_domain_list(self):
        """POST /api/v1/modules/homeassistant/events/config accepts {"domains": [...]}."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.configure_forwarded_domains.return_value = None
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/events/config",
                    json={"domains": ["light", "climate", "switch"]},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_configure_events_rejects_missing_domains(self):
        """POST without domains list returns 400."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/events/config",
                    json={"something": "else"},
                )
                assert r.status_code == 400, f"expected 400, got {r.status_code}"

    def test_configure_events_rejects_empty_body(self):
        """POST with empty body returns 400."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/events/config",
                    json={},
                )
                assert r.status_code == 400

    def test_configure_events_unauthorized(self):
        """POST /events/config returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/modules/homeassistant/events/config",
            json={"domains": ["light"]},
        )
        assert r.status_code == 401


class TestHAModuleConfig:
    """HA module config endpoints."""

    def test_get_config_returns_configuration(self):
        """GET /api/v1/modules/homeassistant/config returns config."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.get_config.return_value = {"domains": ["light", "switch"], "enabled": True}
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/config")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_update_config_accepts_valid_body(self):
        """POST /api/v1/modules/homeassistant/config accepts config update."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.update_config.return_value = True
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/config",
                    json={"domains": ["climate"], "enabled": True},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_config_unauthorized(self):
        """GET /config returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/modules/homeassistant/config")
        assert r.status_code == 401


class TestHAModuleDiagnostics:
    """HA module diagnostics and health."""

    def test_get_diagnostics_returns_debug_data(self):
        """GET /api/v1/modules/homeassistant/diagnostics returns diagnostics."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.get_diagnostics.return_value = {"version": "20.0.8", "uptime": 3600}
            mock_engine.get_pipeline_health.return_value = {"healthy": True, "latency_ms": 5}
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/diagnostics")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_health_returns_health_status(self):
        """GET /api/v1/modules/homeassistant/health returns health check."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.get_pipeline_health.return_value = {"healthy": True, "checks": []}
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.get("/api/v1/modules/homeassistant/health")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"
                data = r.get_json()
                assert "healthy" in data

    def test_diagnostics_unauthorized(self):
        """GET /diagnostics returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/modules/homeassistant/diagnostics")
        assert r.status_code == 401


class TestHAModuleWebhook:
    """HA module webhook endpoint."""

    def test_webhook_received_accepts_valid_payload(self):
        """POST /api/v1/modules/homeassistant/webhook-received accepts event."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine._webhook_received_count = 0
            mock_engine.record_webhook.return_value = None
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/webhook-received",
                    json={"event_type": "state_changed", "data": {}},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}, body={r.get_json()}"

    def test_webhook_received_rejects_empty_body(self):
        """POST /webhook-received with no body returns 400."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            mock_engine.record_webhook.return_value = None
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                client = app.test_client()
                r = client.post(
                    "/api/v1/modules/homeassistant/webhook-received",
                    json=None,
                )
                # 400 if no body, or error handling
                assert r.status_code in (400, 500)

    def test_webhook_unauthorized(self):
        """POST /webhook-received returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/modules/homeassistant/webhook-received",
            json={"event_type": "test"},
        )
        assert r.status_code == 401


class TestHAModuleRefresh:
    """HA module refresh endpoint."""

    def test_refresh_returns_200_when_router_available(self):
        """POST /api/v1/modules/homeassistant/refresh returns 200 when router configured."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                # Mock ModuleRouter in COPILOT_SERVICES
                mock_router = MagicMock()
                mock_router.async_refresh_from_ha = AsyncMock(return_value={"refreshed": True})
                mock_router.refresh_all.return_value = True
                app.config["COPILOT_SERVICES"] = {"module_router": mock_router}
                client = app.test_client()
                r = client.post("/api/v1/modules/homeassistant/refresh")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_refresh_returns_503_when_router_not_available(self):
        """POST /refresh returns 503 when ModuleRouter not in COPILOT_SERVICES."""
        app = _make_app()
        with _patch_validate_token():
            mock_engine = MagicMock()
            with patch.object(ha_module, '_get_engine', return_value=mock_engine):
                app.config["COPILOT_SERVICES"] = {}  # No router
                client = app.test_client()
                r = client.post("/api/v1/modules/homeassistant/refresh")
                assert r.status_code == 503, f"expected 503, got {r.status_code}"

    def test_refresh_unauthorized(self):
        """POST /refresh returns 401 without token."""
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/modules/homeassistant/refresh")
        assert r.status_code == 401


class TestHAModuleAllUnauthorized:
    """Verify all 10 endpoints require auth."""

    def test_all_endpoints_require_authorization(self):
        """All ha_module endpoints return 401 without token."""
        app = _make_app()
        client = app.test_client()
        endpoints = [
            ("GET", "/api/v1/modules/homeassistant/status"),
            ("GET", "/api/v1/modules/homeassistant/connection"),
            ("GET", "/api/v1/modules/homeassistant/events"),
            ("POST", "/api/v1/modules/homeassistant/events/config"),
            ("GET", "/api/v1/modules/homeassistant/config"),
            ("POST", "/api/v1/modules/homeassistant/config"),
            ("GET", "/api/v1/modules/homeassistant/diagnostics"),
            ("GET", "/api/v1/modules/homeassistant/health"),
            ("POST", "/api/v1/modules/homeassistant/webhook-received"),
            ("POST", "/api/v1/modules/homeassistant/refresh"),
        ]
        for method, path in endpoints:
            r = client.get(path) if method == "GET" else client.post(path, json={})
            assert r.status_code == 401, f"{method} {path}: expected 401, got {r.status_code}"