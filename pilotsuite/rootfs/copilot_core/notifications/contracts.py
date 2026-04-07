"""
Notification Delivery Contracts for PilotSuite Core.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List


class NotificationType(str, Enum):
    """Notification types."""
    ALERT = "alert"
    INFO = "info"
    REMINDER = "reminder"
    DIGEST = "digest"
    ACTION_REQUIRED = "action_required"
    SYSTEM = "system"


class DeliveryStatus(str, Enum):
    """Delivery status values."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    TELEGRAM = "telegram"
    PUSH = "push"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBHOOK = "webhook"


@dataclass
class NotificationV1:
    """
    Canonical notification message.
    """
    notification_id: str
    type: NotificationType
    priority: str  # critical, high, normal, low
    channel: NotificationChannel
    recipient: str
    subject: Optional[str]
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    ttl_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "priority": self.priority,
            "channel": self.channel.value,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "ttl_seconds": self.ttl_seconds,
            "idempotency_key": self.idempotency_key,
            "revision": self.revision,
        }


@dataclass
class NotificationDeliveryV1:
    """
    Delivery record for a notification.
    """
    delivery_id: str
    notification_id: str
    channel: NotificationChannel
    recipient: str
    status: DeliveryStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    response_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "delivery_id": self.delivery_id,
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "recipient": self.recipient,
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "response_data": self.response_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "revision": self.revision,
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
    pending_count: int
    sent_count: int
    delivered_count: int
    failed_count: int
    retrying_count: int
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
            "pending_count": self.pending_count,
            "sent_count": self.sent_count,
            "delivered_count": self.delivered_count,
            "failed_count": self.failed_count,
            "retrying_count": self.retrying_count,
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
