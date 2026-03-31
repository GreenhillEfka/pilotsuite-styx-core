"""Unified Notification Engine — Slice 18.

Centralized notification and alerting for PilotSuite Core.

Features:
- Multi-channel notifications (Telegram, HA, Email, Push)
- Notification prioritization and routing
- Digest mode (batched notifications)
- Quiet hours support
- Notification templates and localization
- Delivery tracking and retry
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification delivery channel."""
    TELEGRAM = "telegram"
    HOME_ASSISTANT = "home_assistant"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priority level."""
    LOW = "low"  # Informational, can be batched
    MEDIUM = "medium"  # Normal priority
    HIGH = "high"  # Important, send immediately
    URGENT = "urgent"  # Critical, bypass quiet hours


class NotificationStatus(Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Notification:
    """Notification message."""
    notification_id: str
    channel: NotificationChannel
    priority: NotificationPriority
    title: str
    message: str
    recipient: str
    data: Dict[str, Any] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "recipient": self.recipient,
            "data": self.data,
            "status": self.status.value,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "failed_at": self.failed_at,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


@dataclass
class NotificationPreferences:
    """User notification preferences."""
    user_id: str
    enabled_channels: Set[NotificationChannel] = field(default_factory=set)
    quiet_hours_start: int = 22  # 22:00
    quiet_hours_end: int = 7  # 07:00
    digest_enabled: bool = False
    digest_interval_minutes: int = 60
    priority_override_quiet_hours: bool = True  # HIGH/URGENT bypass quiet hours
    channel_priorities: Dict[NotificationChannel, NotificationPriority] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "enabled_channels": [c.value for c in self.enabled_channels],
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "digest_enabled": self.digest_enabled,
            "digest_interval_minutes": self.digest_interval_minutes,
            "priority_override_quiet_hours": self.priority_override_quiet_hours,
        }


class NotificationEngine:
    """Unified notification engine."""
    
    def __init__(self):
        self._notifications: Dict[str, Notification] = {}
        self._preferences: Dict[str, NotificationPreferences] = {}
        self._notification_counter = 0
        self._digest_queue: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self._quiet_hours_active: Dict[str, bool] = {}
        
        # Delivery statistics
        self._stats = {
            "sent": 0,
            "delivered": 0,
            "failed": 0,
            "retried": 0,
        }
    
    def register_user(self, user_id: str, preferences: Optional[Dict[str, Any]] = None) -> str:
        """Register a user with notification preferences."""
        default_channels = {NotificationChannel.TELEGRAM, NotificationChannel.HOME_ASSISTANT}
        
        prefs = NotificationPreferences(
            user_id=user_id,
            enabled_channels=default_channels,
        )
        
        if preferences:
            if "enabled_channels" in preferences:
                prefs.enabled_channels = {
                    NotificationChannel(c) for c in preferences["enabled_channels"]
                }
            if "quiet_hours_start" in preferences:
                prefs.quiet_hours_start = preferences["quiet_hours_start"]
            if "quiet_hours_end" in preferences:
                prefs.quiet_hours_end = preferences["quiet_hours_end"]
            if "digest_enabled" in preferences:
                prefs.digest_enabled = preferences["digest_enabled"]
            if "priority_override_quiet_hours" in preferences:
                prefs.priority_override_quiet_hours = preferences["priority_override_quiet_hours"]
        
        self._preferences[user_id] = prefs
        return user_id
    
    def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        channel: Optional[NotificationChannel] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Send a notification to a user."""
        if user_id not in self._preferences:
            logger.warning("User %s not registered for notifications", user_id)
            return None
        
        prefs = self._preferences[user_id]
        
        # Check quiet hours
        if self._is_quiet_hours(prefs) and priority not in (NotificationPriority.HIGH, NotificationPriority.URGENT):
            if prefs.priority_override_quiet_hours:
                # Upgrade priority to bypass quiet hours
                priority = NotificationPriority.HIGH
            else:
                # Queue for later
                logger.info("Notification queued for quiet hours end")
                return self._queue_for_quiet_hours_end(user_id, title, message, channel, priority, data)
        
        # Check digest mode
        if prefs.digest_enabled and priority == NotificationPriority.LOW:
            return self._add_to_digest(user_id, title, message, channel, data)
        
        # Determine channel
        if channel is None:
            channel = self._select_best_channel(prefs, priority)
        
        if channel not in prefs.enabled_channels:
            logger.warning("Channel %s not enabled for user %s", channel, user_id)
            return None
        
        # Create notification
        self._notification_counter += 1
        notification = Notification(
            notification_id=f"notif_{self._notification_counter}",
            channel=channel,
            priority=priority,
            title=title,
            message=message,
            recipient=user_id,
            data=data or {},
        )
        
        self._notifications[notification.notification_id] = notification
        
        # Simulate sending (in production, this would call actual delivery services)
        self._deliver_notification(notification)
        
        return notification.notification_id
    
    def _is_quiet_hours(self, prefs: NotificationPreferences) -> bool:
        """Check if current time is within quiet hours."""
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        
        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if prefs.quiet_hours_start > prefs.quiet_hours_end:
            return current_hour >= prefs.quiet_hours_start or current_hour < prefs.quiet_hours_end
        else:
            return prefs.quiet_hours_start <= current_hour < prefs.quiet_hours_end
    
    def _select_best_channel(self, prefs: NotificationPreferences, priority: NotificationPriority) -> NotificationChannel:
        """Select best channel based on priority and user preferences."""
        # Urgent notifications prefer immediate channels
        if priority == NotificationPriority.URGENT:
            if NotificationChannel.PUSH in prefs.enabled_channels:
                return NotificationChannel.PUSH
            if NotificationChannel.SMS in prefs.enabled_channels:
                return NotificationChannel.SMS
        
        # Default to Telegram if available
        if NotificationChannel.TELEGRAM in prefs.enabled_channels:
            return NotificationChannel.TELEGRAM
        
        # Fallback to Home Assistant
        if NotificationChannel.HOME_ASSISTANT in prefs.enabled_channels:
            return NotificationChannel.HOME_ASSISTANT
        
        # Last resort: any enabled channel
        if prefs.enabled_channels:
            return next(iter(prefs.enabled_channels))
        
        raise ValueError("No enabled channels for user")
    
    def _deliver_notification(self, notification: Notification) -> None:
        """Deliver notification (simulated)."""
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(timezone.utc).isoformat()
        self._stats["sent"] += 1
        
        # Simulate delivery success
        notification.status = NotificationStatus.DELIVERED
        notification.delivered_at = datetime.now(timezone.utc).isoformat()
        self._stats["delivered"] += 1
        
        logger.info("Notification %s delivered to %s via %s",
                   notification.notification_id, notification.recipient, notification.channel.value)
    
    def _add_to_digest(self, user_id: str, title: str, message: str,
                       channel: Optional[NotificationChannel], data: Optional[Dict[str, Any]]) -> str:
        """Add notification to digest queue."""
        self._notification_counter += 1
        notification = Notification(
            notification_id=f"notif_{self._notification_counter}",
            channel=channel or NotificationChannel.TELEGRAM,
            priority=NotificationPriority.LOW,
            title=title,
            message=message,
            recipient=user_id,
            data=data or {},
        )
        
        self._notifications[notification.notification_id] = notification
        
        if user_id not in self._digest_queue:
            self._digest_queue[user_id] = []
        
        self._digest_queue[user_id].append(notification)
        
        return notification.notification_id
    
    def _queue_for_quiet_hours_end(self, user_id: str, title: str, message: str,
                                   channel: Optional[NotificationChannel],
                                   priority: NotificationPriority,
                                   data: Optional[Dict[str, Any]]) -> str:
        """Queue notification for quiet hours end."""
        # Similar to digest, but triggered when quiet hours end
        return self._add_to_digest(user_id, title, message, channel, data)
    
    def flush_digest(self, user_id: str) -> List[str]:
        """Flush digest queue and send batched notification."""
        if user_id not in self._digest_queue or not self._digest_queue[user_id]:
            return []
        
        notifications = self._digest_queue[user_id]
        
        if not notifications:
            return []
        
        # Create digest summary
        titles = [n.title for n in notifications]
        digest_title = f"{len(notifications)} Benachrichtigungen"
        digest_message = "\n".join(f"• {t}" for t in titles)
        
        # Send digest
        prefs = self._preferences.get(user_id)
        channel = NotificationChannel.TELEGRAM
        if prefs and prefs.enabled_channels:
            channel = next(iter(prefs.enabled_channels))
        
        self._notification_counter += 1
        digest_notification = Notification(
            notification_id=f"notif_{self._notification_counter}",
            channel=channel,
            priority=NotificationPriority.MEDIUM,
            title=digest_title,
            message=digest_message,
            recipient=user_id,
            data={"digest": True, "notification_count": len(notifications)},
        )
        
        self._notifications[digest_notification.notification_id] = digest_notification
        self._deliver_notification(digest_notification)
        
        # Clear digest queue
        self._digest_queue[user_id] = []
        
        return [n.notification_id for n in notifications]
    
    def acknowledge_notification(self, notification_id: str) -> bool:
        """Acknowledge notification receipt."""
        if notification_id not in self._notifications:
            return False
        
        notification = self._notifications[notification_id]
        if notification.status == NotificationStatus.DELIVERED:
            return True
        
        notification.status = NotificationStatus.DELIVERED
        notification.delivered_at = datetime.now(timezone.utc).isoformat()
        return True
    
    def retry_notification(self, notification_id: str) -> bool:
        """Retry failed notification."""
        if notification_id not in self._notifications:
            return False
        
        notification = self._notifications[notification_id]
        
        if notification.retry_count >= notification.max_retries:
            logger.warning("Notification %s exceeded max retries", notification_id)
            return False
        
        notification.status = NotificationStatus.RETRYING
        notification.retry_count += 1
        self._stats["retried"] += 1
        
        # Attempt redelivery
        self._deliver_notification(notification)
        
        return notification.status == NotificationStatus.DELIVERED
    
    def get_notifications(self, user_id: Optional[str] = None, status: Optional[NotificationStatus] = None,
                         limit: int = 50) -> List[Dict[str, Any]]:
        """Get notifications, optionally filtered."""
        notifications = list(self._notifications.values())
        
        if user_id:
            notifications = [n for n in notifications if n.recipient == user_id]
        
        if status:
            notifications = [n for n in notifications if n.status == status]
        
        # Sort by created_at (newest first)
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        
        return [n.to_dict() for n in notifications[:limit]]
    
    def get_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user notification preferences."""
        if user_id not in self._preferences:
            return None
        
        return self._preferences[user_id].to_dict()
    
    def update_preferences(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user notification preferences."""
        if user_id not in self._preferences:
            return False
        
        prefs = self._preferences[user_id]
        
        if "enabled_channels" in updates:
            prefs.enabled_channels = {
                NotificationChannel(c) for c in updates["enabled_channels"]
            }
        if "quiet_hours_start" in updates:
            prefs.quiet_hours_start = updates["quiet_hours_start"]
        if "quiet_hours_end" in updates:
            prefs.quiet_hours_end = updates["quiet_hours_end"]
        if "digest_enabled" in updates:
            prefs.digest_enabled = updates["digest_enabled"]
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification delivery statistics."""
        return {
            **self._stats,
            "total_notifications": len(self._notifications),
            "pending_notifications": len([n for n in self._notifications.values() 
                                         if n.status == NotificationStatus.PENDING]),
            "failed_notifications": len([n for n in self._notifications.values() 
                                        if n.status == NotificationStatus.FAILED]),
        }


def create_notification_engine() -> NotificationEngine:
    """Factory function to create notification engine."""
    return NotificationEngine()
