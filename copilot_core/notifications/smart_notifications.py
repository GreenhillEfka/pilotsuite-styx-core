"""Smart Notifications — Priority, Channels, Quiet Hours, Digest."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import time

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels."""
    CRITICAL = "critical"  # Always notify, bypass quiet hours
    HIGH = "high"  # Notify immediately
    NORMAL = "normal"  # Standard notification
    LOW = "low"  # Batch in digest
    BACKGROUND = "background"  # Silent, log only


class NotificationChannel(Enum):
    """Notification delivery channels."""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    VOICE_CALL = "voice_call"
    IN_APP = "in_app"
    LOVELACE = "lovelace"


@dataclass
class Notification:
    """Notification definition."""
    id: str
    title: str
    message: str
    priority: NotificationPriority
    channel: NotificationChannel
    target: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    actions: List[Dict] = field(default_factory=list)


@dataclass
class QuietHours:
    """Quiet hours configuration."""
    enabled: bool = True
    start_time: str = "22:00"
    end_time: str = "07:00"
    allow_critical: bool = True
    allow_repeated_callers: bool = True  # Allow if same person calls twice within 15 min
    days: List[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])


@dataclass
class NotificationDigest:
    """Notification digest configuration."""
    enabled: bool = True
    frequency: str = "daily"  # hourly, daily, weekly
    delivery_time: str = "08:00"
    channels: List[NotificationChannel] = field(default_factory=lambda: [NotificationChannel.EMAIL])
    include_read: bool = False


class SmartNotificationEngine:
    """Smart notification engine with priority and quiet hours."""

    def __init__(self):
        self._notifications: Dict[str, Notification] = {}
        self._quiet_hours: QuietHours = QuietHours()
        self._digest: NotificationDigest = NotificationDigest()
        self._blocked_sources: Set[str] = set()
        self._channel_handlers: Dict[NotificationChannel, Callable] = {}
        self._notification_history: List[Notification] = []
        self._digest_queue: List[Notification] = []

    def configure_quiet_hours(self, config: QuietHours):
        """Configure quiet hours."""
        self._quiet_hours = config
        logger.info(f"Quiet hours configured: {config.start_time} - {config.end_time}")

    def configure_digest(self, config: NotificationDigest):
        """Configure notification digest."""
        self._digest = config
        logger.info(f"Digest configured: {config.frequency} at {config.delivery_time}")

    def send_notification(self, notification: Notification) -> bool:
        """Send a notification with priority handling."""
        # Check if source is blocked
        if notification.data.get("source") in self._blocked_sources:
            logger.info(f"Notification blocked from source: {notification.data.get('source')}")
            return False
        
        # Check quiet hours
        if self._is_quiet_hours() and notification.priority not in [
            NotificationPriority.CRITICAL, NotificationPriority.HIGH
        ]:
            # Queue for digest or delayed delivery
            self._digest_queue.append(notification)
            logger.info(f"Notification queued for digest: {notification.title}")
            return True
        
        # Deliver immediately
        return self._deliver_notification(notification)

    def _is_quiet_hours(self) -> bool:
        """Check if currently in quiet hours."""
        if not self._quiet_hours.enabled:
            return False
        
        # Simplified check - in production would parse times properly
        current_hour = int(time.strftime("%H"))
        start_hour = int(self._quiet_hours.start_time.split(":")[0])
        end_hour = int(self._quiet_hours.end_time.split(":")[0])
        
        if start_hour > end_hour:  # Spans midnight
            return current_hour >= start_hour or current_hour < end_hour
        else:
            return start_hour <= current_hour < end_hour

    def _deliver_notification(self, notification: Notification) -> bool:
        """Deliver notification to channel."""
        handler = self._channel_handlers.get(notification.channel)
        
        if not handler:
            # Simulated delivery
            logger.info(f"Delivering {notification.channel.value}: {notification.title}")
            notification.delivered_at = time.time()
        else:
            try:
                handler(notification)
                notification.delivered_at = time.time()
            except Exception as e:
                logger.error(f"Delivery failed: {e}")
                return False
        
        # Add to history
        self._notification_history.append(notification)
        self._notifications[notification.id] = notification
        
        return True

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        if notification_id in self._notifications:
            self._notifications[notification_id].read_at = time.time()
            return True
        return False

    def register_channel_handler(self, channel: NotificationChannel, handler: Callable):
        """Register a handler for a notification channel."""
        self._channel_handlers[channel] = handler
        logger.info(f"Channel handler registered: {channel.value}")

    def block_source(self, source: str):
        """Block notifications from a source."""
        self._blocked_sources.add(source)
        logger.info(f"Source blocked: {source}")

    def unblock_source(self, source: str):
        """Unblock a source."""
        self._blocked_sources.discard(source)
        logger.info(f"Source unblocked: {source}")

    def send_digest(self) -> Dict[str, Any]:
        """Send notification digest."""
        if not self._digest_queue:
            return {"status": "empty", "count": 0}
        
        # Group by priority
        by_priority = {}
        for notif in self._digest_queue:
            priority = notif.priority.value
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(notif)
        
        # Create digest message
        digest_content = []
        for priority, notifs in sorted(by_priority.items()):
            digest_content.append(f"**{priority.upper()}** ({len(notifs)})")
            for n in notifs[:10]:  # Limit per category
                digest_content.append(f"  • {n.title}")
        
        # Send digest
        digest_notification = Notification(
            id=f"digest_{int(time.time())}",
            title=f"Notification Digest ({len(self._digest_queue)} items)",
            message="\n".join(digest_content),
            priority=NotificationPriority.NORMAL,
            channel=self._digest.channels[0] if self._digest.channels else NotificationChannel.EMAIL,
            target="user",
            data={"digest": True, "items": len(self._digest_queue)},
        )
        
        self._deliver_notification(digest_notification)
        
        # Clear queue
        count = len(self._digest_queue)
        self._digest_queue.clear()
        
        logger.info(f"Digest sent: {count} notifications")
        return {"status": "sent", "count": count}

    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        return len([n for n in self._notifications.values() if not n.read_at])

    def get_notifications(self, limit: int = 50, unread_only: bool = False) -> List[Notification]:
        """Get notifications."""
        notifs = self._notification_history
        if unread_only:
            notifs = [n for n in notifs if not n.read_at]
        return sorted(notifs, key=lambda n: n.created_at, reverse=True)[:limit]

    def clear_old_notifications(self, max_age_days: int = 7):
        """Clear old notifications."""
        cutoff = time.time() - (max_age_days * 86400)
        self._notification_history = [
            n for n in self._notification_history
            if n.created_at >= cutoff
        ]
        logger.info(f"Old notifications cleared (>{max_age_days} days)")

    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return {
            "total_sent": len(self._notification_history),
            "unread": self.get_unread_count(),
            "queued_for_digest": len(self._digest_queue),
            "quiet_hours_enabled": self._quiet_hours.enabled,
            "digest_enabled": self._digest.enabled,
            "blocked_sources": len(self._blocked_sources),
        }


# Global default notification engine
default_notifications: Optional[SmartNotificationEngine] = None


def init_notification_engine() -> SmartNotificationEngine:
    """Initialize global notification engine."""
    global default_notifications
    default_notifications = SmartNotificationEngine()
    return default_notifications
