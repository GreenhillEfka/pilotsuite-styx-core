"""Notifications — Slice 52 (Analytics) + Slice 68 (Delivery Engine)."""

from .analytics import (
    NotificationDeliveryEntryV1,
    NotificationDeliveryHistoryV1,
    NotificationChannelPatternEntryV1,
    NotificationChannelPatternsV1,
    NotificationEffectivenessMetricsV1,
    NotificationAnalyticsSummaryV1,
    NotificationChannel,
    NotificationType,
    DeliveryStatus,
)
from .analytics_store import NotificationAnalyticsStore, get_notification_analytics_store

from .delivery_contracts import (
    NotificationV1,
    NotificationDeliveryV1,
    DeliveryAttemptV1,
    DeliverySummaryV1,
    DeliveryDeltaV1,
    RateLimitStateV1,
    QuietHoursStateV1,
    NotificationChannel as DeliveryChannel,
    NotificationPriority,
    DeliveryMode,
)
from .delivery_engine import DeliveryEngine, ChannelHandler
from .delivery_store import NotificationDeliveryStore, get_notification_delivery_store

__all__ = [
    # Analytics (Slice 52)
    "NotificationDeliveryEntryV1",
    "NotificationDeliveryHistoryV1",
    "NotificationChannelPatternEntryV1",
    "NotificationChannelPatternsV1",
    "NotificationEffectivenessMetricsV1",
    "NotificationAnalyticsSummaryV1",
    "NotificationChannel",
    "NotificationType",
    "DeliveryStatus",
    "NotificationAnalyticsStore",
    "get_notification_analytics_store",
    # Delivery Engine (Slice 68)
    "NotificationV1",
    "NotificationDeliveryV1",
    "DeliveryAttemptV1",
    "DeliverySummaryV1",
    "DeliveryDeltaV1",
    "RateLimitStateV1",
    "QuietHoursStateV1",
    "DeliveryChannel",
    "NotificationPriority",
    "DeliveryMode",
    "DeliveryEngine",
    "ChannelHandler",
    "NotificationDeliveryStore",
    "get_notification_delivery_store",
]
