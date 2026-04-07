"""Notifications Analytics — Delivery History, Channel Patterns, Effectiveness Metrics — Slice 52."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class NotificationChannel(str, Enum):
    """Notification Channels für Analytics."""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PUSH = "push"
    HA_NOTIFICATION = "ha_notification"
    SMS = "sms"


class NotificationType(str, Enum):
    """Notification-Typen für Analytics."""
    ALERT = "alert"
    REMINDER = "reminder"
    PROPOSAL = "proposal"
    ACTION_CLOSURE = "action_closure"
    PRESENCE_HOLD = "presence_hold"
    SYSTEM = "system"
    DIGEST = "digest"
    FOLLOW_UP = "follow_up"


class DeliveryStatus(str, Enum):
    """Delivery-Status für Notifications."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"


@dataclass(frozen=True)
class NotificationDeliveryEntryV1:
    """Einzelner Notification-Delivery-Eintrag für Historie."""

    entry_id: str
    notification_id: str
    channel: str  # NotificationChannel
    notification_type: str  # NotificationType
    recipient_id: str
    zone_id: Optional[str]
    zone_name: Optional[str]
    title: str
    body: str
    priority: str  # low/normal/high/urgent
    status: str  # DeliveryStatus
    sent_at: Optional[str]  # ISO-8601
    delivered_at: Optional[str]  # ISO-8601
    read_at: Optional[str]  # ISO-8601
    acknowledged_at: Optional[str]  # ISO-8601
    failed_reason: Optional[str]
    retry_count: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class NotificationDeliveryHistoryV1:
    """Aggregierte Notification-Delivery-Historie über alle Channels."""

    entries: List[NotificationDeliveryEntryV1]
    total_notifications: int
    total_sent: int
    total_delivered: int
    total_failed: int
    total_read: int
    total_acknowledged: int
    avg_delivery_time_seconds: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class NotificationChannelPatternEntryV1:
    """Notification-Pattern für einen einzelnen Channel."""

    channel: str
    total_notifications: int
    sent_count: int
    delivered_count: int
    failed_count: int
    read_count: int
    acknowledged_count: int
    avg_delivery_time_seconds: Optional[float]
    failure_rate: float  # 0.0–1.0
    most_common_type: Optional[str]
    peak_delivery_hour: Optional[int]  # 0-23
    notifications_last_24_hours: int
    notifications_last_7_days: int
    unique_recipients: int


@dataclass(frozen=True)
class NotificationChannelPatternsV1:
    """Channel-spezifische Notification-Patterns."""

    patterns: List[NotificationChannelPatternEntryV1]
    total_channels: int
    channels_with_activity: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class NotificationEffectivenessMetricsV1:
    """Notification-Effectiveness-Metriken."""

    total_notifications_analyzed: int
    notifications_by_type: Dict[str, int]  # type → count
    notifications_by_channel: Dict[str, int]  # channel → count
    overall_delivery_rate: float  # 0.0–1.0
    overall_read_rate: float  # 0.0–1.0
    overall_ack_rate: float  # 0.0–1.0
    avg_delivery_time_by_channel: Dict[str, float]  # channel → avg seconds
    failure_rate_by_type: Dict[str, float]  # type → failure rate
    zones_with_notifications: int
    peak_notification_time: Optional[str]  # morning/day/evening/night
    engagement_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class NotificationAnalyticsSummaryV1:
    """Zusammenfassung aller Notification-Analytics."""

    usage: NotificationDeliveryHistoryV1
    patterns: NotificationChannelPatternsV1
    effectiveness: NotificationEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
