"""
Notification Delivery Engine Contracts — Slice 68.

Canonical contracts for unified notification delivery with channel routing,
rate limiting, and delivery tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PUSH = "push"
    HA_NOTIFICATION = "ha_notification"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationType(str, Enum):
    """Notification types."""
    ALERT = "alert"
    INFO = "info"
    REMINDER = "reminder"
    DIGEST = "digest"
    ACTION_REQUIRED = "action_required"
    SYSTEM = "system"
    PROPOSAL = "proposal"
    ACTION_CLOSURE = "action_closure"
    PRESENCE_HOLD = "presence_hold"
    FOLLOW_UP = "follow_up"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryStatus(str, Enum):
    """Delivery status values."""
    PENDING = "pending"
    QUEUED = "queued"
    RATE_LIMITED = "rate_limited"
    QUIET_HOURS = "quiet_hours"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryMode(str, Enum):
    """Delivery mode for notifications."""
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    BATCHED = "batched"
    DIGEST = "digest"


@dataclass
class NotificationV1:
    """
    Canonical notification message for delivery.
    """
    notification_id: str
    type: NotificationType
    priority: NotificationPriority
    channel: NotificationChannel
    recipient_id: str
    user_id: str
    zone_id: Optional[str]
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    action_url: Optional[str] = None
    action_data: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    ttl_seconds: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "channel": self.channel.value,
            "recipient_id": self.recipient_id,
            "user_id": self.user_id,
            "zone_id": self.zone_id,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "action_url": self.action_url,
            "action_data": self.action_data,
            "idempotency_key": self.idempotency_key,
            "ttl_seconds": self.ttl_seconds,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revision": self.revision,
        }


@dataclass
class DeliveryAttemptV1:
    """
    Single delivery attempt record.
    """
    attempt_id: str
    notification_id: str
    channel: NotificationChannel
    status: DeliveryStatus
    attempted_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0
    response_data: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "attempt_id": self.attempt_id,
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "attempted_at": self.attempted_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "response_data": self.response_data,
            "latency_ms": self.latency_ms,
        }


@dataclass
class NotificationDeliveryV1:
    """
    Delivery record for a notification with full lifecycle tracking.
    """
    delivery_id: str
    notification_id: str
    user_id: str
    channel: NotificationChannel
    recipient_id: str
    status: DeliveryStatus
    priority: NotificationPriority
    delivery_mode: DeliveryMode
    attempts: List[DeliveryAttemptV1] = field(default_factory=list)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    rate_limited_at: Optional[datetime] = None
    quiet_hours_applied: bool = False
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "delivery_id": self.delivery_id,
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "channel": self.channel.value,
            "recipient_id": self.recipient_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "delivery_mode": self.delivery_mode.value,
            "attempts": [a.to_dict() for a in self.attempts],
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "rate_limited_at": self.rate_limited_at.isoformat() if self.rate_limited_at else None,
            "quiet_hours_applied": self.quiet_hours_applied,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "revision": self.revision,
        }


@dataclass
class RateLimitStateV1:
    """
    Rate limit state for a user/channel combination.
    """
    user_id: str
    channel: NotificationChannel
    window_start: datetime
    window_end: datetime
    count: int
    limit: int
    reset_at: datetime
    is_limited: bool
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "channel": self.channel.value,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "count": self.count,
            "limit": self.limit,
            "reset_at": self.reset_at.isoformat(),
            "is_limited": self.is_limited,
        }


@dataclass
class QuietHoursStateV1:
    """
    Quiet hours state for a user.
    """
    user_id: str
    is_quiet_hours: bool
    quiet_hours_start: int  # hour 0-23
    quiet_hours_end: int  # hour 0-23
    current_hour: int
    priority_override: bool
    next_quiet_hours_start: Optional[datetime]
    next_quiet_hours_end: Optional[datetime]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "is_quiet_hours": self.is_quiet_hours,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "current_hour": self.current_hour,
            "priority_override": self.priority_override,
            "next_quiet_hours_start": self.next_quiet_hours_start.isoformat() if self.next_quiet_hours_start else None,
            "next_quiet_hours_end": self.next_quiet_hours_end.isoformat() if self.next_quiet_hours_end else None,
        }


@dataclass
class DeliverySummaryV1:
    """
    Summary of notification deliveries.
    """
    total_notifications: int
    total_deliveries: int
    by_status: Dict[str, int]
    by_channel: Dict[str, int]
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    pending_count: int
    queued_count: int
    rate_limited_count: int
    sent_count: int
    delivered_count: int
    read_count: int
    acknowledged_count: int
    failed_count: int
    cancelled_count: int
    avg_delivery_latency_ms: Optional[float]
    latest_revision: int
    latest_change_at: datetime
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_notifications": self.total_notifications,
            "total_deliveries": self.total_deliveries,
            "by_status": self.by_status,
            "by_channel": self.by_channel,
            "by_type": self.by_type,
            "by_priority": self.by_priority,
            "pending_count": self.pending_count,
            "queued_count": self.queued_count,
            "rate_limited_count": self.rate_limited_count,
            "sent_count": self.sent_count,
            "delivered_count": self.delivered_count,
            "read_count": self.read_count,
            "acknowledged_count": self.acknowledged_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "avg_delivery_latency_ms": self.avg_delivery_latency_ms,
            "latest_revision": self.latest_revision,
            "latest_change_at": self.latest_change_at.isoformat(),
        }


@dataclass
class DeliveryDeltaV1:
    """
    Delta information for delivery polling.
    """
    has_changes: bool
    revision: int
    changes_since_revision: List[Dict[str, Any]]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_changes": self.has_changes,
            "revision": self.revision,
            "changes_since_revision": self.changes_since_revision,
        }
