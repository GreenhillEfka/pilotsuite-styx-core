"""Zone Presence Hold Scheduler Contract Tests — Slice 45.

Tests for scheduler integration including:
- Scheduler attachment
- Interval configuration
- Enable/disable functionality
- Manual trigger
- Job status reporting
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from copilot_core.core.zone_presence_hold_scheduler import (
    ZonePresenceHoldSchedulerIntegration,
    get_hold_scheduler_integration,
    reset_hold_scheduler_integration,
    attach_hold_scheduler_to_engine,
)
from copilot_core.scheduler.engine import SchedulerEngine, create_scheduler_engine


@pytest.fixture(autouse=True)
def reset_scheduler_integration():
    """Reset scheduler integration before each test."""
    reset_hold_scheduler_integration()
    yield
    reset_hold_scheduler_integration()


@pytest.fixture
def scheduler_engine():
    """Create a fresh scheduler engine."""
    return create_scheduler_engine()


class TestZonePresenceHoldSchedulerIntegration:
    """Test scheduler integration."""

    def test_init_default_state(self):
        """Test initial state of integration."""
        integration = ZonePresenceHoldSchedulerIntegration()
        
        assert integration._scheduler_engine is None
        assert integration._job_id is None
        assert integration._check_interval_seconds == 300
        assert integration._enabled is True

    def test_attach_scheduler_without_engine(self):
        """Test attaching without scheduler engine."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(None)
        
        assert integration._scheduler_engine is None
        assert integration._job_id is None

    def test_attach_scheduler_with_engine(self, scheduler_engine):
        """Test attaching with scheduler engine."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        assert integration._scheduler_engine is scheduler_engine
        assert integration._job_id is not None
        
        # Verify job was created
        job = scheduler_engine.get_job(integration._job_id)
        assert job is not None
        assert job["name"] == "zone_presence_hold_expiration"
        assert job["schedule_type"] == "interval"
        assert job["schedule_expression"] == "300"
        assert job["action_name"] == "presence.hold_expiration_check"

    def test_attach_scheduler_registers_action(self, scheduler_engine):
        """Test that action is registered."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        # Verify action is registered
        assert "presence.hold_expiration_check" in scheduler_engine._action_registry

    def test_scheduler_action_handler_success(self, scheduler_engine):
        """Test scheduler action handler on success."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
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
            
            result = integration._scheduler_hold_expiration_check()
            
            assert result["success"] is True
            assert "summary" in result
            mock_run.assert_called_once()

    def test_scheduler_action_handler_failure(self, scheduler_engine):
        """Test scheduler action handler on failure."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        with patch("copilot_core.core.zone_presence_hold_scheduler.run_hold_expiration_check") as mock_run:
            mock_run.side_effect = Exception("Test error")
            
            result = integration._scheduler_hold_expiration_check()
            
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]

    def test_set_interval_minimum(self, scheduler_engine):
        """Test setting interval enforces minimum."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        integration.set_interval(10)  # Below minimum
        
        assert integration.get_interval() == 30

    def test_set_interval_updates_job(self, scheduler_engine):
        """Test setting interval recreates job."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        old_job_id = integration._job_id
        
        integration.set_interval(600)
        
        assert integration.get_interval() == 600
        assert integration._job_id != old_job_id
        
        # Old job should be deleted
        assert scheduler_engine.get_job(old_job_id) is None
        
        # New job should exist
        new_job = scheduler_engine.get_job(integration._job_id)
        assert new_job is not None
        assert new_job["schedule_expression"] == "600"

    def test_enable_disable(self, scheduler_engine):
        """Test enable/disable functionality."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        # Initially enabled
        assert integration.is_enabled() is True
        
        # Disable
        integration.disable()
        assert integration.is_enabled() is False
        
        job = scheduler_engine.get_job(integration._job_id)
        assert job["enabled"] is False
        
        # Enable
        integration.enable()
        assert integration.is_enabled() is True
        
        job = scheduler_engine.get_job(integration._job_id)
        assert job["enabled"] is True

    def test_get_job_status_not_configured(self):
        """Test job status when not configured."""
        integration = ZonePresenceHoldSchedulerIntegration()
        
        status = integration.get_job_status()
        
        assert status["status"] == "not_configured"
        assert status["job_id"] is None

    def test_get_job_status_active(self, scheduler_engine):
        """Test job status when active."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        status = integration.get_job_status()
        
        assert status["status"] == "active"
        assert status["job_id"] == integration._job_id
        assert status["interval_seconds"] == 300
        assert status["enabled"] is True
        assert "job" in status

    def test_run_now(self, scheduler_engine):
        """Test manual trigger."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        with patch("copilot_core.core.zone_presence_hold_scheduler.run_hold_expiration_check") as mock_run:
            mock_summary = Mock()
            mock_summary.to_dict.return_value = {"test": "summary"}
            mock_run.return_value = mock_summary
            
            result = integration.run_now()
            
            assert result["success"] is True
            mock_run.assert_called_once()

    def test_attach_scheduler_multiple_times(self, scheduler_engine):
        """Test attaching scheduler multiple times."""
        integration = ZonePresenceHoldSchedulerIntegration()
        
        # First attachment
        integration.attach_scheduler(scheduler_engine)
        first_job_id = integration._job_id
        
        # Second attachment (should not recreate job)
        integration.attach_scheduler(scheduler_engine)
        
        assert integration._job_id == first_job_id
        assert scheduler_engine.get_job(first_job_id) is not None

    def test_job_created_with_correct_tags(self, scheduler_engine):
        """Test job is created with correct tags."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        job = scheduler_engine.get_job(integration._job_id)
        
        assert "presence" in job["tags"]
        assert "holds" in job["tags"]
        assert "maintenance" in job["tags"]

    def test_job_created_with_correct_priority(self, scheduler_engine):
        """Test job is created with correct priority."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        job = scheduler_engine.get_job(integration._job_id)
        
        assert job["priority"] == 5

    def test_job_created_with_correct_timeout(self, scheduler_engine):
        """Test job is created with correct timeout."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        job = scheduler_engine.get_job(integration._job_id)
        
        assert job["timeout_seconds"] == 60

    def test_job_created_with_correct_max_retries(self, scheduler_engine):
        """Test job is created with correct max retries."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        job = scheduler_engine.get_job(integration._job_id)
        
        assert job["max_retries"] == 1


class TestGlobalIntegrationFunctions:
    """Test global integration functions."""

    def test_get_hold_scheduler_integration_singleton(self):
        """Test that get_hold_scheduler_integration returns singleton."""
        reset_hold_scheduler_integration()
        
        integration1 = get_hold_scheduler_integration()
        integration2 = get_hold_scheduler_integration()
        
        assert integration1 is integration2

    def test_reset_hold_scheduler_integration(self):
        """Test reset function."""
        integration1 = get_hold_scheduler_integration()
        reset_hold_scheduler_integration()
        integration2 = get_hold_scheduler_integration()
        
        assert integration1 is not integration2

    def test_attach_hold_scheduler_to_engine(self, scheduler_engine):
        """Test convenience attach function."""
        reset_hold_scheduler_integration()
        
        attach_hold_scheduler_to_engine(scheduler_engine)
        
        integration = get_hold_scheduler_integration()
        assert integration._scheduler_engine is scheduler_engine
        assert integration._job_id is not None

    def test_attach_hold_scheduler_to_engine_none(self):
        """Test attach with None engine."""
        reset_hold_scheduler_integration()
        
        attach_hold_scheduler_to_engine(None)
        
        integration = get_hold_scheduler_integration()
        assert integration._scheduler_engine is None
        assert integration._job_id is None


class TestSchedulerEngineIntegration:
    """Test integration with actual scheduler engine."""

    def test_action_execution_via_scheduler(self, scheduler_engine):
        """Test that action can be executed via scheduler."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        # Manually run the job via scheduler
        with patch("copilot_core.core.zone_presence_hold_scheduler.run_hold_expiration_check") as mock_run:
            mock_summary = Mock()
            mock_summary.to_dict.return_value = {"test": "data"}
            mock_run.return_value = mock_summary
            
            execution_id = scheduler_engine.run_job(integration._job_id)
            
            assert execution_id is not None
            
            execution = scheduler_engine.get_execution(execution_id)
            assert execution is not None
            assert execution["status"] == "completed"

    def test_job_persists_across_get_all_jobs(self, scheduler_engine):
        """Test that job appears in get_all_jobs."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        jobs = scheduler_engine.get_all_jobs()
        
        job_ids = [j["job_id"] for j in jobs]
        assert integration._job_id in job_ids

    def test_scheduler_summary_includes_hold_job(self, scheduler_engine):
        """Test that scheduler summary includes hold job."""
        integration = ZonePresenceHoldSchedulerIntegration()
        integration.attach_scheduler(scheduler_engine)
        
        summary = scheduler_engine.get_scheduler_summary()
        
        assert summary["total_jobs"] >= 1
        assert summary["enabled_jobs"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
