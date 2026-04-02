"""Zone Presence Hold Notification Surface for Slice 43.

Enables zone presence hold state changes as notification events,
so users are informed about manual overrides and expirations.
Follows the same pattern as Action Closure and Proposal Lifecycle notifications.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List
import logging

from copilot_core.core.zone_presence_hold import ZonePresenceHold, ZoneHoldState, ZonePresenceHoldStore, get_zone_presence_hold_store

logger = logging.getLogger(__name__)


class HoldNotificationType:
    """Notification types for hold events."""
    HOLD_SET = "hold_set"
    HOLD_RELEASED = "hold_released"
    HOLD_EXPIRED = "hold_expired"
    HOLD_EXPIRING_SOON = "hold_expiring_soon"


@dataclass
class ZonePresenceHoldNotification:
    """Single zone presence hold notification record."""
    notification_id: str
    zone_id: str
    notification_type: str  # HoldNotificationType
    hold_state: ZoneHoldState
    reason: str
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hold_set_at: str | None = None
    hold_expires_at: str | None = None
    hold_released_at: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ZonePresenceHoldNotificationV1",
            "notification_id": self.notification_id,
            "zone_id": self.zone_id,
            "notification_type": self.notification_type,
            "hold_state": self.hold_state.value,
            "reason": self.reason,
            "triggered_at": self.triggered_at,
            "hold_set_at": self.hold_set_at,
            "hold_expires_at": self.hold_expires_at,
            "hold_released_at": self.hold_released_at,
            "metadata": self.metadata,
        }


@dataclass
class ZonePresenceHoldNotificationSummary:
    """Aggregated notification summary for zone presence hold."""
    notification_revision: int = 0
    latest_change_at: str | None = None
    total_notifications: int = 0
    unread_notifications: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_zone: Dict[str, int] = field(default_factory=dict)
    recent_notifications: List[ZonePresenceHoldNotification] = field(default_factory=list)
    has_changes: bool = False
    since_revision: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ZonePresenceHoldNotificationSummaryV1",
            "notification_revision": self.notification_revision,
            "latest_change_at": self.latest_change_at,
            "total_notifications": self.total_notifications,
            "unread_notifications": self.unread_notifications,
            "by_type": self.by_type,
            "by_zone": {k: v for k, v in self.by_zone.items()},
            "recent_notifications": [n.to_dict() for n in self.recent_notifications],
            "has_changes": self.has_changes,
            "since_revision": self.since_revision,
        }


class ZonePresenceHoldNotificationStore:
    """In-memory store for zone presence hold notifications."""
    
    def __init__(self) -> None:
        self._notifications: dict[str, dict[str, Any]] = {}  # notification_id -> data
        self._by_zone: dict[str, list[str]] = {}  # zone_id -> notification_ids
        self._by_type: dict[str, list[str]] = {}  # type -> notification_ids
        self._revision = 0
        self._latest_change_at: str | None = None
        self._unread_ids: set[str] = set()
    
    def clear(self) -> None:
        """Clear all store data."""
        self._notifications.clear()
        self._by_zone.clear()
        self._by_type.clear()
        self._revision = 0
        self._latest_change_at = None
        self._unread_ids.clear()
    
    def record_notification(
        self,
        zone_id: str,
        notification_type: str,
        hold_state: ZoneHoldState,
        reason: str,
        hold_set_at: str | None = None,
        hold_expires_at: str | None = None,
        hold_released_at: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> ZonePresenceHoldNotification:
        """Record a zone presence hold notification.
        
        Returns:
            The created ZonePresenceHoldNotification.
        """
        import uuid
        notification_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        notification = ZonePresenceHoldNotification(
            notification_id=notification_id,
            zone_id=zone_id,
            notification_type=notification_type,
            hold_state=hold_state,
            reason=reason,
            hold_set_at=hold_set_at,
            hold_expires_at=hold_expires_at,
            hold_released_at=hold_released_at,
            metadata=metadata or {},
        )
        
        # Store notification
        self._notifications[notification_id] = {
            "notification_id": notification_id,
            "zone_id": zone_id,
            "notification_type": notification_type,
            "hold_state": hold_state.value,
            "reason": reason,
            "triggered_at": notification.triggered_at,
            "hold_set_at": hold_set_at,
            "hold_expires_at": hold_expires_at,
            "hold_released_at": hold_released_at,
            "metadata": metadata or {},
            "read": False,
            "created_at": now.isoformat(),
        }
        
        # Index by zone
        if zone_id not in self._by_zone:
            self._by_zone[zone_id] = []
        self._by_zone[zone_id].append(notification_id)
        
        # Index by type
        if notification_type not in self._by_type:
            self._by_type[notification_type] = []
        self._by_type[notification_type].append(notification_id)
        
        # Update revision
        self._revision += 1
        self._latest_change_at = now.isoformat()
        self._unread_ids.add(notification_id)
        
        logger.debug(f"Recorded zone presence hold notification: {notification_id} for zone {zone_id} type={notification_type}")
        
        return notification
    
    def get_notification(self, notification_id: str) -> ZonePresenceHoldNotification | None:
        """Get a single notification by ID."""
        data = self._notifications.get(notification_id)
        if not data:
            return None
        
        return ZonePresenceHoldNotification(
            notification_id=data["notification_id"],
            zone_id=data["zone_id"],
            notification_type=data["notification_type"],
            hold_state=ZoneHoldState(data["hold_state"]),
            reason=data["reason"],
            triggered_at=data["triggered_at"],
            hold_set_at=data.get("hold_set_at"),
            hold_expires_at=data.get("hold_expires_at"),
            hold_released_at=data.get("hold_released_at"),
            metadata=data.get("metadata", {}),
        )
    
    def get_summary(
        self,
        zone_id: str | None = None,
        notification_type: str | None = None,
        recent_limit: int = 20,
        since_revision: int | None = None,
    ) -> ZonePresenceHoldNotificationSummary:
        """Get aggregated notification summary.
        
        Args:
            zone_id: Optional zone filter
            notification_type: Optional type filter
            recent_limit: Max recent notifications to include
            since_revision: Optional revision for delta responses
        
        Returns:
            ZonePresenceHoldNotificationSummary with filtered data.
        """
        now = datetime.now(timezone.utc)
        
        # Filter notification IDs
        notification_ids = set(self._notifications.keys())
        
        if zone_id:
            zone_ids = set(self._by_zone.get(zone_id, []))
            notification_ids &= zone_ids
        
        if notification_type:
            type_ids = set(self._by_type.get(notification_type, []))
            notification_ids &= type_ids
        
        # Sort by triggered_at descending
        sorted_ids = sorted(
            notification_ids,
            key=lambda nid: self._notifications[nid]["triggered_at"],
            reverse=True,
        )
        
        # Build recent list
        recent = []
        for nid in sorted_ids[:recent_limit]:
            data = self._notifications[nid]
            recent.append(ZonePresenceHoldNotification(
                notification_id=data["notification_id"],
                zone_id=data["zone_id"],
                notification_type=data["notification_type"],
                hold_state=ZoneHoldState(data["hold_state"]),
                reason=data["reason"],
                triggered_at=data["triggered_at"],
                hold_set_at=data.get("hold_set_at"),
                hold_expires_at=data.get("hold_expires_at"),
                hold_released_at=data.get("hold_released_at"),
                metadata=data.get("metadata", {}),
            ))
        
        # Count by type
        by_type: Dict[str, int] = {}
        for nid in notification_ids:
            ntype = self._notifications[nid]["notification_type"]
            by_type[ntype] = by_type.get(ntype, 0) + 1
        
        # Count by zone
        by_zone: Dict[str, int] = {}
        for nid in notification_ids:
            zid = self._notifications[nid]["zone_id"]
            by_zone[zid] = by_zone.get(zid, 0) + 1
        
        # Unread count
        unread_count = len(self._unread_ids & notification_ids)
        
        # Delta detection
        has_changes = since_revision is None or self._revision > since_revision
        
        return ZonePresenceHoldNotificationSummary(
            notification_revision=self._revision,
            latest_change_at=self._latest_change_at,
            total_notifications=len(notification_ids),
            unread_notifications=unread_count,
            by_type=by_type,
            by_zone=by_zone,
            recent_notifications=recent,
            has_changes=has_changes,
            since_revision=since_revision,
        )
    
    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read.
        
        Returns:
            True if marked, False if not found.
        """
        if notification_id not in self._notifications:
            return False
        
        self._notifications[notification_id]["read"] = True
        self._unread_ids.discard(notification_id)
        return True
    
    def mark_all_read(self, zone_id: str | None = None) -> int:
        """Mark all notifications as read.
        
        Args:
            zone_id: Optional zone filter
        
        Returns:
            Number of notifications marked.
        """
        if zone_id:
            notification_ids = set(self._by_zone.get(zone_id, []))
        else:
            notification_ids = set(self._notifications.keys())
        
        count = 0
        for nid in notification_ids:
            if nid in self._unread_ids:
                self._notifications[nid]["read"] = True
                self._unread_ids.discard(nid)
                count += 1
        
        return count


# Global store instance
_notification_store: ZonePresenceHoldNotificationStore | None = None


def get_zone_presence_hold_notification_store() -> ZonePresenceHoldNotificationStore:
    """Get or create the global notification store instance."""
    global _notification_store
    if _notification_store is None:
        _notification_store = ZonePresenceHoldNotificationStore()
    return _notification_store


def reset_zone_presence_hold_notification_store() -> None:
    """Reset the global store (for testing)."""
    global _notification_store
    _notification_store = None


def record_hold_set_notification(
    zone_id: str,
    hold_state: ZoneHoldState,
    reason: str,
    hold_set_at: str,
    hold_expires_at: str | None = None,
) -> ZonePresenceHoldNotification:
    """Record a notification when a hold is set."""
    store = get_zone_presence_hold_notification_store()
    return store.record_notification(
        zone_id=zone_id,
        notification_type=HoldNotificationType.HOLD_SET,
        hold_state=hold_state,
        reason=reason,
        hold_set_at=hold_set_at,
        hold_expires_at=hold_expires_at,
        metadata={"action": "hold_set"},
    )


def record_hold_released_notification(
    zone_id: str,
    hold_state: ZoneHoldState,
    reason: str,
    hold_set_at: str,
    hold_released_at: str,
) -> ZonePresenceHoldNotification:
    """Record a notification when a hold is released."""
    store = get_zone_presence_hold_notification_store()
    return store.record_notification(
        zone_id=zone_id,
        notification_type=HoldNotificationType.HOLD_RELEASED,
        hold_state=hold_state,
        reason=reason,
        hold_set_at=hold_set_at,
        hold_released_at=hold_released_at,
        metadata={"action": "hold_released"},
    )


def record_hold_expired_notification(
    zone_id: str,
    hold_state: ZoneHoldState,
    reason: str,
    hold_set_at: str,
    hold_expires_at: str,
) -> ZonePresenceHoldNotification:
    """Record a notification when a hold expires."""
    store = get_zone_presence_hold_notification_store()
    return store.record_notification(
        zone_id=zone_id,
        notification_type=HoldNotificationType.HOLD_EXPIRED,
        hold_state=hold_state,
        reason=reason,
        hold_set_at=hold_set_at,
        hold_expires_at=hold_expires_at,
        metadata={"action": "hold_expired"},
    )


def record_hold_expiring_soon_notification(
    zone_id: str,
    hold_state: ZoneHoldState,
    reason: str,
    hold_set_at: str,
    hold_expires_at: str,
    minutes_until_expiry: int,
) -> ZonePresenceHoldNotification:
    """Record a notification when a hold is expiring soon."""
    store = get_zone_presence_hold_notification_store()
    return store.record_notification(
        zone_id=zone_id,
        notification_type=HoldNotificationType.HOLD_EXPIRING_SOON,
        hold_state=hold_state,
        reason=reason,
        hold_set_at=hold_set_at,
        hold_expires_at=hold_expires_at,
        metadata={"action": "hold_expiring_soon", "minutes_until_expiry": minutes_until_expiry},
    )
