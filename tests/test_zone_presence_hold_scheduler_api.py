"""Zone Presence Hold Scheduler API Tests — Slice 45.

Tests for scheduler API endpoints including:
- GET /status
- GET/PUT /config
- POST /run
- POST /enable
- POST /disable
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


@pytest.fixture
def app():
    """Create test Flask app."""
    from flask import Flask
    from copilot_core.api.v1.zone_presence_hold_scheduler import blueprint
    
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(blueprint)
    
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_integration():
    """Reset integration before each test."""
    from copilot_core.core.zone_presence_hold_scheduler import reset_hold_scheduler_integration
    reset_hold_scheduler_integration()
    yield
    reset_hold_scheduler_integration()


class TestSchedulerStatusEndpoint:
    """Test GET /status endpoint."""

    def test_status_not_configured(self, client):
        """Test status when scheduler not attached."""
        response = client.get("/api/v1/presence/holds/scheduler/status")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "not_configured"
        assert data["job_id"] is None

    def test_status_active(self, client):
        """Test status when scheduler is attached."""
        from copilot_core.scheduler.engine import create_scheduler_engine
        from copilot_core.core.zone_presence_hold_scheduler import attach_hold_scheduler_to_engine
        
        scheduler = create_scheduler_engine()
        attach_hold_scheduler_to_engine(scheduler)
        
        response = client.get("/api/v1/presence/holds/scheduler/status")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "active"
        assert data["job_id"] is not None
        assert data["interval_seconds"] == 300
        assert data["enabled"] is True
        assert "job" in data


class TestSchedulerConfigEndpoint:
    """Test GET/PUT /config endpoints."""

    def test_get_config_default(self, client):
        """Test getting default config."""
        response = client.get("/api/v1/presence/holds/scheduler/config")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 300
        assert data["enabled"] is True

    def test_get_config_after_change(self, client):
        """Test getting config after modification."""
        from copilot_core.core.zone_presence_hold_scheduler import get_hold_scheduler_integration
        
        integration = get_hold_scheduler_integration()
        integration.set_interval(600)
        integration.disable()
        
        response = client.get("/api/v1/presence/holds/scheduler/config")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 600
        assert data["enabled"] is False

    def test_update_config_interval(self, client):
        """Test updating interval via config endpoint."""
        response = client.put(
            "/api/v1/presence/holds/scheduler/config",
            json={"interval_seconds": 600},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 600
        assert data["enabled"] is True
        
        # Verify change persisted
        response2 = client.get("/api/v1/presence/holds/scheduler/config")
        data2 = response2.get_json()
        assert data2["interval_seconds"] == 600

    def test_update_config_enabled(self, client):
        """Test updating enabled state via config endpoint."""
        response = client.put(
            "/api/v1/presence/holds/scheduler/config",
            json={"enabled": False},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is False
        
        # Verify change persisted
        response2 = client.get("/api/v1/presence/holds/scheduler/config")
        data2 = response2.get_json()
        assert data2["enabled"] is False

    def test_update_config_both(self, client):
        """Test updating both interval and enabled."""
        response = client.put(
            "/api/v1/presence/holds/scheduler/config",
            json={
                "interval_seconds": 900,
                "enabled": False
            },
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 900
        assert data["enabled"] is False

    def test_update_config_minimum_interval(self, client):
        """Test that minimum interval is enforced."""
        response = client.put(
            "/api/v1/presence/holds/scheduler/config",
            json={"interval_seconds": 10},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 30  # Minimum enforced

    def test_update_config_empty_body(self, client):
        """Test updating with empty body."""
        response = client.put(
            "/api/v1/presence/holds/scheduler/config",
            json={},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["interval_seconds"] == 300
        assert data["enabled"] is True


class TestRunEndpoint:
    """Test POST /run endpoint."""

    def test_run_success(self, client):
        """Test successful manual run."""
        with patch("copilot_core.core.zone_presence_hold_scheduler.run_hold_expiration_check") as mock_run:
            mock_summary = Mock()
            mock_summary.to_dict.return_value = {
                "run_at": "2026-04-02T12:00:00Z",
                "total_holds_checked": 5,
                "expiring_soon_count": 1,
                "expired_count": 0,
                "auto_released_count": 0,
                "cron_revision": 1,
            }
            mock_run.return_value = mock_summary
            
            response = client.post("/api/v1/presence/holds/scheduler/run")
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "summary" in data
            mock_run.assert_called_once()

    def test_run_failure(self, client):
        """Test failed manual run."""
        with patch("copilot_core.core.zone_presence_hold_scheduler.run_hold_expiration_check") as mock_run:
            mock_run.side_effect = Exception("Test error")
            
            response = client.post("/api/v1/presence/holds/scheduler/run")
            
            assert response.status_code == 500
            data = response.get_json()
            assert data["success"] is False
            assert "error" in data


class TestEnableEndpoint:
    """Test POST /enable endpoint."""

    def test_enable(self, client):
        """Test enabling scheduler."""
        from copilot_core.core.zone_presence_hold_scheduler import get_hold_scheduler_integration
        from copilot_core.scheduler.engine import create_scheduler_engine
        
        integration = get_hold_scheduler_integration()
        scheduler = create_scheduler_engine()
        integration.attach_scheduler(scheduler)
        integration.disable()
        
        response = client.post("/api/v1/presence/holds/scheduler/enable")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is True
        assert data["status"]["enabled"] is True
        
        # Verify job is enabled in scheduler
        job = scheduler.get_job(integration._job_id)
        assert job["enabled"] is True


class TestDisableEndpoint:
    """Test POST /disable endpoint."""

    def test_disable(self, client):
        """Test disabling scheduler."""
        from copilot_core.core.zone_presence_hold_scheduler import get_hold_scheduler_integration
        from copilot_core.scheduler.engine import create_scheduler_engine
        
        integration = get_hold_scheduler_integration()
        scheduler = create_scheduler_engine()
        integration.attach_scheduler(scheduler)
        
        response = client.post("/api/v1/presence/holds/scheduler/disable")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["enabled"] is False
        assert data["status"]["enabled"] is False
        
        # Verify job is disabled in scheduler
        job = scheduler.get_job(integration._job_id)
        assert job["enabled"] is False


class TestAttachEndpoint:
    """Test POST /attach endpoint."""

    def test_attach_noop(self, client):
        """Test attach endpoint (documentation only)."""
        response = client.post(
            "/api/v1/presence/holds/scheduler/attach",
            json={},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "attach_requested"
        assert "note" in data
        assert "core_setup.py" in data["note"]

    def test_attach_with_interval(self, client):
        """Test attach with interval override."""
        response = client.post(
            "/api/v1/presence/holds/scheduler/attach",
            json={"interval_seconds": 600},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "attach_requested"
        
        # Verify interval was updated
        from copilot_core.core.zone_presence_hold_scheduler import get_hold_scheduler_integration
        integration = get_hold_scheduler_integration()
        assert integration.get_interval() == 600


class TestErrorHandling:
    """Test error handling."""

    def test_status_error(self, client):
        """Test status endpoint handles errors gracefully."""
        # Status should always return something, even if not configured
        response = client.get("/api/v1/presence/holds/scheduler/status")
        
        # Even without configuration, endpoint should return 200 with status info
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data or "error" in data

    def test_config_error(self, client):
        """Test config endpoint handles errors gracefully."""
        # Config should always return something, even if not configured
        response = client.get("/api/v1/presence/holds/scheduler/config")
        
        # Even without configuration, endpoint should return 200 with config info
        assert response.status_code == 200
        data = response.get_json()
        assert "interval_seconds" in data or "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
