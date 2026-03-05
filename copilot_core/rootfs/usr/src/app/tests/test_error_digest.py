"""Tests for Error Digest API Blueprint."""

import importlib
import json
import time
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask


def _make_test_app():
    """Create Flask app with error_digest blueprint."""
    with patch("copilot_core.api.v1.error_digest.require_token", lambda f: f):
        import copilot_core.api.v1.error_digest as mod
        importlib.reload(mod)

    app = Flask(__name__)
    app.config["TESTING"] = True
    mod.init_error_digest_api(llm_provider=None)
    app.register_blueprint(mod.error_digest_bp)
    return app, mod


# ── Pattern Matching ──────────────────────────────────────────────────────

class TestRepairPatterns:
    """Tests for error pattern matching and repair suggestions."""

    def test_match_connection_refused(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Connection refused to homeassistant.local:8123")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "connectivity"

    def test_match_timeout(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Request timeout after 30 seconds")
        assert len(repairs) >= 1
        assert any(r["category"] == "connectivity" for r in repairs)

    def test_match_entity_not_found(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Entity not found: light.nonexistent")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "configuration"

    def test_match_permission_denied(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Permission denied for token")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "security"

    def test_match_database_locked(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("database is locked")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "database"

    def test_match_automation_failed(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Automation failed: trigger error")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "automation"

    def test_match_unavailable(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Device unavailable: sensor.temp")
        assert len(repairs) >= 1
        assert repairs[0]["category"] == "device"

    def test_no_match(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Everything is working fine")
        assert len(repairs) == 0

    def test_multiple_matches(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Connection refused and timeout on ssl service")
        assert len(repairs) >= 2

    def test_repair_has_actions(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("Connection refused")
        assert repairs[0]["actions"]
        assert isinstance(repairs[0]["actions"], list)

    def test_repair_has_suggestion(self):
        from copilot_core.api.v1.error_digest import _match_repair_patterns
        repairs = _match_repair_patterns("database is locked")
        assert repairs[0]["suggestion"]
        assert len(repairs[0]["suggestion"]) > 10


# ── Categorization ────────────────────────────────────────────────────────

class TestErrorCategorization:
    """Tests for error categorization."""

    def test_categorize_connectivity(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Connection refused") == "connectivity"

    def test_categorize_security(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Authentication token invalid") == "security"

    def test_categorize_configuration(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Entity not found in config") == "configuration"

    def test_categorize_system(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Out of memory error") == "system"

    def test_categorize_database(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("SQLite database locked") == "database"

    def test_categorize_automation(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Automation trigger failed") == "automation"

    def test_categorize_device(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Device unavailable battery low") == "device"

    def test_categorize_other(self):
        from copilot_core.api.v1.error_digest import _categorize_error
        assert _categorize_error("Something random happened") == "other"


# ── API Endpoints ─────────────────────────────────────────────────────────

class TestErrorDigestAPI:
    """Tests for error digest REST endpoints."""

    def test_digest_empty(self):
        app, mod = _make_test_app()
        with patch.object(mod, "_get_dev_logs", return_value=[]):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest")
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["ok"] is True
                assert data["errors"] == []
                assert data["summary"]["total_errors"] == 0

    def test_digest_with_mock_logs(self):
        app, mod = _make_test_app()
        now = time.time()
        mock_logs = [
            {"timestamp": now - 100, "level": "ERROR", "message": "Connection refused to port 8123", "source": "core"},
            {"timestamp": now - 200, "level": "WARNING", "message": "Entity not found: light.test", "source": "api"},
            {"timestamp": now - 300, "level": "ERROR", "message": "database is locked", "source": "db"},
            {"timestamp": now - 50, "level": "INFO", "message": "Normal operation", "source": "core"},  # Should be excluded
        ]
        with patch.object(mod, "_get_dev_logs", return_value=mock_logs):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest")
                data = resp.get_json()
                assert data["ok"] is True
                assert data["summary"]["total_errors"] == 3  # INFO excluded
                assert "connectivity" in data["summary"]["by_category"]
                assert "database" in data["summary"]["by_category"]

    def test_digest_hours_filter(self):
        app, mod = _make_test_app()
        now = time.time()
        mock_logs = [
            {"timestamp": now - 100, "level": "ERROR", "message": "Recent error", "source": "core"},
            {"timestamp": now - 90000, "level": "ERROR", "message": "Old error", "source": "core"},  # >24h
        ]
        with patch.object(mod, "_get_dev_logs", return_value=mock_logs):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest?hours=1")
                data = resp.get_json()
                assert data["summary"]["total_errors"] == 1

    def test_digest_category_filter(self):
        app, mod = _make_test_app()
        now = time.time()
        mock_logs = [
            {"timestamp": now - 100, "level": "ERROR", "message": "Connection refused", "source": "core"},
            {"timestamp": now - 200, "level": "ERROR", "message": "database is locked", "source": "db"},
        ]
        with patch.object(mod, "_get_dev_logs", return_value=mock_logs):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest?category=database")
                data = resp.get_json()
                assert data["summary"]["total_errors"] == 1
                assert data["errors"][0]["category"] == "database"

    def test_digest_severity_filter(self):
        app, mod = _make_test_app()
        now = time.time()
        mock_logs = [
            {"timestamp": now - 100, "level": "ERROR", "message": "High error", "source": "core"},
            {"timestamp": now - 200, "level": "WARNING", "message": "Low warning", "source": "core"},
        ]
        with patch.object(mod, "_get_dev_logs", return_value=mock_logs):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest?severity=high")
                data = resp.get_json()
                assert data["summary"]["total_errors"] == 1

    def test_categories_endpoint(self):
        app, _ = _make_test_app()
        with app.test_client() as c:
            resp = c.get("/api/v1/errors/digest/categories")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert "connectivity" in data["categories"]
            assert "security" in data["categories"]
            assert "system" in data["categories"]

    def test_repair_suggestions_endpoint(self):
        app, _ = _make_test_app()
        with app.test_client() as c:
            resp = c.post(
                "/api/v1/errors/repair-suggestions",
                json={"message": "Connection refused to homeassistant.local:8123"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert len(data["repairs"]) >= 1
            assert data["pattern_matches"] >= 1

    def test_repair_suggestions_no_match(self):
        app, _ = _make_test_app()
        with app.test_client() as c:
            resp = c.post(
                "/api/v1/errors/repair-suggestions",
                json={"message": "Everything is fine"},
            )
            data = resp.get_json()
            assert data["ok"] is True
            assert data["pattern_matches"] == 0

    def test_repair_suggestions_empty_message(self):
        app, _ = _make_test_app()
        with app.test_client() as c:
            resp = c.post(
                "/api/v1/errors/repair-suggestions",
                json={"message": ""},
            )
            assert resp.status_code == 400

    def test_error_has_repairs(self):
        app, mod = _make_test_app()
        now = time.time()
        mock_logs = [
            {"timestamp": now - 100, "level": "ERROR", "message": "Connection refused to port 8123", "source": "core"},
        ]
        with patch.object(mod, "_get_dev_logs", return_value=mock_logs):
            with app.test_client() as c:
                resp = c.get("/api/v1/errors/digest")
                data = resp.get_json()
                err = data["errors"][0]
                assert len(err["repairs"]) >= 1
                assert err["repairs"][0]["category"] == "connectivity"
