"""Zone Presence Hold Scheduler Integration — Slice 45.

Integrates the Hold Expiration Cron Service into the Core Scheduler Engine.
Provides automatic periodic checking with configurable intervals.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from copilot_core.core.zone_presence_hold_cron import (
    get_hold_cron_service,
    run_hold_expiration_check,
    HoldExpirationCronSummary,
)

logger = logging.getLogger(__name__)


class ZonePresenceHoldSchedulerIntegration:
    """Scheduler integration for hold expiration checking.
    
    Registers a scheduler action and manages the periodic job
    for automatic hold expiration checks.
    """
    
    def __init__(self):
        self._scheduler_engine = None
        self._job_id: Optional[str] = None
        self._check_interval_seconds = 300  # Default: 5 minutes
        self._enabled = True
    
    def attach_scheduler(self, scheduler_engine: Any | None) -> None:
        """Attach scheduler engine and register hold expiration job.
        
        Args:
            scheduler_engine: The core scheduler engine instance.
        """
        self._scheduler_engine = scheduler_engine
        
        if scheduler_engine is None:
            logger.info("Hold scheduler: no scheduler engine provided")
            return
        
        # Register the action handler
        register_action = getattr(scheduler_engine, "register_action", None)
        if callable(register_action):
            register_action(
                "presence.hold_expiration_check",
                self._scheduler_hold_expiration_check,
            )
            logger.info("Hold scheduler: action registered")
        
        # Create or update the periodic job
        self._ensure_job()
    
    def _scheduler_hold_expiration_check(self, **kwargs) -> Dict[str, Any]:
        """Scheduler action handler for hold expiration check.
        
        This is called by the scheduler engine at the configured interval.
        
        Returns:
            Dict with summary of actions taken.
        """
        try:
            summary = run_hold_expiration_check()
            return {
                "success": True,
                "summary": summary.to_dict(),
            }
        except Exception as e:
            logger.exception("Hold expiration check failed in scheduler")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _ensure_job(self) -> None:
        """Ensure the periodic job exists in the scheduler."""
        if self._scheduler_engine is None:
            return
        
        # Check if job already exists
        if self._job_id:
            existing = self._scheduler_engine.get_job(self._job_id)
            if existing:
                # Job exists, just ensure it's enabled
                if not self._enabled:
                    self._scheduler_engine.disable_job(self._job_id)
                return
        
        # Create new job
        create_job = getattr(self._scheduler_engine, "create_job", None)
        if not callable(create_job):
            logger.warning("Hold scheduler: scheduler engine has no create_job method")
            return
        
        self._job_id = create_job(
            name="zone_presence_hold_expiration",
            description="Periodic check for zone presence hold expiration",
            schedule_type="interval",
            schedule_expression=str(self._check_interval_seconds),
            action_name="presence.hold_expiration_check",
            parameters={},
            priority=5,
            tags=["presence", "holds", "maintenance"],
            max_retries=1,
            timeout_seconds=60,
        )
        
        if not self._enabled:
            self._scheduler_engine.disable_job(self._job_id)
        
        logger.info(
            f"Hold scheduler: job created {self._job_id} interval={self._check_interval_seconds}s"
        )
    
    def set_interval(self, interval_seconds: int) -> None:
        """Update the check interval.
        
        Args:
            interval_seconds: New interval in seconds (minimum 30).
        """
        if interval_seconds < 30:
            interval_seconds = 30
        
        self._check_interval_seconds = interval_seconds
        
        # Recreate job with new interval
        if self._job_id and self._scheduler_engine:
            self._scheduler_engine.delete_job(self._job_id)
            self._job_id = None
            self._ensure_job()
        
        logger.info(f"Hold scheduler: interval updated to {interval_seconds}s")
    
    def get_interval(self) -> int:
        """Get current check interval in seconds."""
        return self._check_interval_seconds
    
    def enable(self) -> None:
        """Enable the scheduler job."""
        self._enabled = True
        
        if self._scheduler_engine and self._job_id:
            self._scheduler_engine.enable_job(self._job_id)
        
        logger.info("Hold scheduler: enabled")
    
    def disable(self) -> None:
        """Disable the scheduler job."""
        self._enabled = False
        
        if self._scheduler_engine and self._job_id:
            self._scheduler_engine.disable_job(self._job_id)
        
        logger.info("Hold scheduler: disabled")
    
    def is_enabled(self) -> bool:
        """Check if scheduler is enabled."""
        return self._enabled
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get current job status."""
        if not self._scheduler_engine or not self._job_id:
            return {
                "status": "not_configured",
                "job_id": None,
            }
        
        job = self._scheduler_engine.get_job(self._job_id)
        if not job:
            return {
                "status": "not_found",
                "job_id": self._job_id,
            }
        
        return {
            "status": "active",
            "job_id": self._job_id,
            "job": job,
            "interval_seconds": self._check_interval_seconds,
            "enabled": self._enabled,
        }
    
    def run_now(self) -> Dict[str, Any]:
        """Manually trigger a hold expiration check.
        
        Returns:
            Result of the check.
        """
        return self._scheduler_hold_expiration_check()


# Global integration instance
_hold_scheduler_integration: ZonePresenceHoldSchedulerIntegration | None = None


def get_hold_scheduler_integration() -> ZonePresenceHoldSchedulerIntegration:
    """Get or create the global hold scheduler integration."""
    global _hold_scheduler_integration
    if _hold_scheduler_integration is None:
        _hold_scheduler_integration = ZonePresenceHoldSchedulerIntegration()
    return _hold_scheduler_integration


def reset_hold_scheduler_integration() -> None:
    """Reset the global integration (for testing)."""
    global _hold_scheduler_integration
    _hold_scheduler_integration = None


def attach_hold_scheduler_to_engine(scheduler_engine: Any | None) -> None:
    """Convenience function to attach hold scheduler to a scheduler engine."""
    integration = get_hold_scheduler_integration()
    integration.attach_scheduler(scheduler_engine)
