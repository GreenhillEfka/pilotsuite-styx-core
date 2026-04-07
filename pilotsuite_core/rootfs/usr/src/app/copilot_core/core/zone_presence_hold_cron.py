"""Zone Presence Hold Expiration Cron Service for Slice 44.

Automatically checks for expiring/expired holds, triggers notifications,
and performs auto-release after expiration. Follows the same pattern as
other Core cron services.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Dict, List
import logging

from copilot_core.core.zone_presence_hold import (
    ZonePresenceHold,
    ZoneHoldState,
    get_zone_presence_hold_store,
)
from copilot_core.core.zone_presence_hold_notifications import (
    HoldNotificationType,
    record_hold_expired_notification,
    record_hold_expiring_soon_notification,
    get_zone_presence_hold_notification_store,
)

logger = logging.getLogger(__name__)


class HoldExpirationCheckResult:
    """Result of a single hold expiration check."""
    
    def __init__(
        self,
        hold_id: str,
        zone_id: str,
        action_taken: str,  # "notified_expiring", "notified_expired", "auto_released", "none"
        hold_state: ZoneHoldState,
        minutes_until_expiry: int | None = None,
        notification_id: str | None = None,
    ):
        self.hold_id = hold_id
        self.zone_id = zone_id
        self.action_taken = action_taken
        self.hold_state = hold_state
        self.minutes_until_expiry = minutes_until_expiry
        self.notification_id = notification_id
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "HoldExpirationCheckResultV1",
            "hold_id": self.hold_id,
            "zone_id": self.zone_id,
            "action_taken": self.action_taken,
            "hold_state": self.hold_state.value,
            "minutes_until_expiry": self.minutes_until_expiry,
            "notification_id": self.notification_id,
        }


class HoldExpirationCronSummary:
    """Summary of a cron run."""
    
    def __init__(
        self,
        run_at: str,
        total_holds_checked: int,
        expiring_soon_count: int,
        expired_count: int,
        auto_released_count: int,
        results: List[HoldExpirationCheckResult],
        cron_revision: int = 0,
    ):
        self.run_at = run_at
        self.total_holds_checked = total_holds_checked
        self.expiring_soon_count = expiring_soon_count
        self.expired_count = expired_count
        self.auto_released_count = auto_released_count
        self.results = results
        self.cron_revision = cron_revision
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "HoldExpirationCronSummaryV1",
            "run_at": self.run_at,
            "total_holds_checked": self.total_holds_checked,
            "expiring_soon_count": self.expiring_soon_count,
            "expired_count": self.expired_count,
            "auto_released_count": self.auto_released_count,
            "results": [r.to_dict() for r in self.results],
            "cron_revision": self.cron_revision,
        }


class ZonePresenceHoldCronService:
    """Cron service for zone presence hold expiration checking.
    
    Periodically checks all active holds for:
    1. Holds expiring soon (within warning window) → send expiring_soon notification
    2. Holds that just expired → send expired notification + auto-release
    3. Already expired holds → ensure released
    """
    
    def __init__(
        self,
        expiring_soon_window_minutes: int = 15,
        auto_release_on_expire: bool = True,
    ):
        self.expiring_soon_window_minutes = expiring_soon_window_minutes
        self.auto_release_on_expire = auto_release_on_expire
        self._cron_revision = 0
        self._last_run_at: str | None = None
        self._last_summary: HoldExpirationCronSummary | None = None
    
    def check_and_process_holds(self) -> HoldExpirationCronSummary:
        """Check all holds and process expirations.
        
        Returns:
            HoldExpirationCronSummary with all actions taken.
        """
        now = datetime.now(timezone.utc)
        run_at = now.isoformat()
        
        hold_store = get_zone_presence_hold_store()
        notification_store = get_zone_presence_hold_notification_store()
        
        # Get all holds (including released/expired for completeness)
        all_holds = hold_store.get_all_holds(limit=1000)
        
        results: List[HoldExpirationCheckResult] = []
        expiring_soon_count = 0
        expired_count = 0
        auto_released_count = 0
        
        for hold in all_holds:
            # Skip already released holds
            if hold.released:
                continue
            
            # Skip AUTO holds (no expiration needed)
            if hold.hold_state == ZoneHoldState.AUTO:
                continue
            
            # Check if hold has expiration
            if not hold.expires_at:
                continue
            
            expires_at = datetime.fromisoformat(hold.expires_at.replace("Z", "+00:00"))
            time_until_expiry = expires_at - now
            minutes_until_expiry = int(time_until_expiry.total_seconds() / 60)
            
            result: HoldExpirationCheckResult | None = None
            
            # Case 1: Hold just expired (within last check interval)
            if time_until_expiry.total_seconds() <= 0:
                expired_count += 1
                
                # Record expired notification
                notification = record_hold_expired_notification(
                    zone_id=hold.zone_id,
                    hold_state=hold.hold_state,
                    reason="auto_expiration",
                    hold_set_at=hold.set_at,
                    hold_expires_at=hold.expires_at,
                )
                
                # Auto-release if enabled
                if self.auto_release_on_expire:
                    released = hold_store.release_hold(
                        zone_id=hold.zone_id,
                        reason="auto_release_on_expiration",
                    )
                    if released:
                        auto_released_count += 1
                        logger.info(
                            f"Auto-released expired hold {hold.hold_id} for zone {hold.zone_id}"
                        )
                
                result = HoldExpirationCheckResult(
                    hold_id=hold.hold_id,
                    zone_id=hold.zone_id,
                    action_taken="notified_expired" + ("+auto_released" if auto_released_count > 0 else ""),
                    hold_state=hold.hold_state,
                    notification_id=notification.notification_id,
                )
            
            # Case 2: Hold expiring soon (within warning window)
            elif minutes_until_expiry <= self.expiring_soon_window_minutes:
                expiring_soon_count += 1
                
                # Record expiring soon notification
                notification = record_hold_expiring_soon_notification(
                    zone_id=hold.zone_id,
                    hold_state=hold.hold_state,
                    reason="approaching_expiration",
                    hold_set_at=hold.set_at,
                    hold_expires_at=hold.expires_at,
                    minutes_until_expiry=minutes_until_expiry,
                )
                
                result = HoldExpirationCheckResult(
                    hold_id=hold.hold_id,
                    zone_id=hold.zone_id,
                    action_taken="notified_expiring",
                    hold_state=hold.hold_state,
                    minutes_until_expiry=minutes_until_expiry,
                    notification_id=notification.notification_id,
                )
            
            if result:
                results.append(result)
                logger.debug(
                    f"Hold {hold.hold_id} zone={hold.zone_id} action={result.action_taken}"
                )
        
        self._cron_revision += 1
        self._last_run_at = run_at
        
        summary = HoldExpirationCronSummary(
            run_at=run_at,
            total_holds_checked=len(all_holds),
            expiring_soon_count=expiring_soon_count,
            expired_count=expired_count,
            auto_released_count=auto_released_count,
            results=results,
            cron_revision=self._cron_revision,
        )
        
        self._last_summary = summary
        
        logger.info(
            f"Hold expiration cron run: checked={len(all_holds)} "
            f"expiring_soon={expiring_soon_count} expired={expired_count} "
            f"auto_released={auto_released_count}"
        )
        
        return summary
    
    def get_last_summary(self) -> HoldExpirationCronSummary | None:
        """Get the last cron run summary."""
        return self._last_summary
    
    def get_cron_revision(self) -> int:
        """Get current cron revision."""
        return self._cron_revision
    
    def get_next_check_time(self) -> str | None:
        """Get the next scheduled check time (if known)."""
        # This would be set by the scheduler integration
        return None


# Global service instance
_hold_cron_service: ZonePresenceHoldCronService | None = None


def get_hold_cron_service() -> ZonePresenceHoldCronService:
    """Get or create the global hold cron service."""
    global _hold_cron_service
    if _hold_cron_service is None:
        _hold_cron_service = ZonePresenceHoldCronService()
    return _hold_cron_service


def reset_hold_cron_service() -> None:
    """Reset the global service (for testing)."""
    global _hold_cron_service
    _hold_cron_service = None


def run_hold_expiration_check() -> HoldExpirationCronSummary:
    """Convenience function to run a single expiration check."""
    service = get_hold_cron_service()
    return service.check_and_process_holds()
