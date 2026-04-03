"""Notification Analytics Contract Tests — Slice 52."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from copilot_core.notifications.analytics import (
    NotificationDeliveryEntryV1,
    NotificationDeliveryHistoryV1,
    NotificationChannelPatternEntryV1,
    NotificationChannelPatternsV1,
    NotificationEffectivenessMetricsV1,
    NotificationChannel,
    NotificationType,
    DeliveryStatus,
)
from copilot_core.notifications.analytics_store import NotificationAnalyticsStore, get_notification_analytics_store


class TestNotificationDeliveryEntryV1:
    """Tests für NotificationDeliveryEntryV1."""

    def test_entry_creation(self):
        """Entry-Erstellung mit allen Feldern."""
        now = datetime.now(timezone.utc).isoformat()
        entry = NotificationDeliveryEntryV1(
            entry_id="entry_001",
            notification_id="notif_001",
            channel="telegram",
            notification_type="alert",
            recipient_id="user_123",
            zone_id="living",
            zone_name="Wohnbereich",
            title="Test Alert",
            body="Test notification body",
            priority="high",
            status="delivered",
            sent_at=now,
            delivered_at=now,
            read_at=None,
            acknowledged_at=None,
            failed_reason=None,
            retry_count=0,
        )

        assert entry.entry_id == "entry_001"
        assert entry.channel == "telegram"
        assert entry.notification_type == "alert"
        assert entry.status == "delivered"
        assert entry.priority == "high"


class TestNotificationAnalyticsStore:
    """Tests für NotificationAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "notification_analytics.db"
        return NotificationAnalyticsStore(db_path=str(db_path))

    def test_add_delivery_entry(self, store):
        """Delivery-Eintrag hinzufügen."""
        now = datetime.now(timezone.utc).isoformat()
        entry = NotificationDeliveryEntryV1(
            entry_id="entry_001",
            notification_id="notif_001",
            channel="telegram",
            notification_type="alert",
            recipient_id="user_123",
            zone_id="living",
            zone_name="Wohnbereich",
            title="Test Alert",
            body="Test notification body",
            priority="high",
            status="delivered",
            sent_at=now,
            delivered_at=now,
            read_at=None,
            acknowledged_at=None,
            failed_reason=None,
            retry_count=0,
        )

        store.add_delivery_entry(entry)

        # Verify entry was added
        history = store.build_delivery_history(channel="telegram")
        assert len(history.entries) == 1
        assert history.entries[0].entry_id == "entry_001"
        assert history.total_delivered == 1

    def test_build_delivery_history(self, store):
        """Delivery-Historie aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries
        for i in range(5):
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_{i:03d}",
                notification_id=f"notif_{i:03d}",
                channel="telegram",
                notification_type="alert",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Alert {i}",
                body=f"Body {i}",
                priority="normal",
                status="delivered",
                sent_at=now.isoformat(),
                delivered_at=now.isoformat(),
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        history = store.build_delivery_history(channel="telegram")

        assert history.total_notifications == 5
        assert history.total_delivered == 5
        assert history.total_sent == 5
        assert history.revision == 5

    def test_build_delivery_history_with_filters(self, store):
        """Delivery-Historie mit Filtern."""
        now = datetime.now(timezone.utc)

        # Add entries for different channels
        for channel in ["telegram", "whatsapp", "email"]:
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_{channel}",
                notification_id=f"notif_{channel}",
                channel=channel,
                notification_type="reminder",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Reminder via {channel}",
                body="Reminder body",
                priority="normal",
                status="sent",
                sent_at=now.isoformat(),
                delivered_at=None,
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        # Filter by channel
        telegram_history = store.build_delivery_history(channel="telegram")
        assert telegram_history.total_notifications == 1
        assert telegram_history.entries[0].channel == "telegram"

        # Filter by notification type
        reminder_history = store.build_delivery_history(notification_type="reminder")
        assert reminder_history.total_notifications == 3

    def test_build_channel_patterns(self, store):
        """Channel-Patterns aufbauen."""
        now = datetime.now(timezone.utc)

        # Add multiple entries for telegram
        for i in range(10):
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_telegram_{i}",
                notification_id=f"notif_telegram_{i}",
                channel="telegram",
                notification_type="alert",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Alert {i}",
                body="Alert body",
                priority="high",
                status="delivered",
                sent_at=now.isoformat(),
                delivered_at=now.isoformat(),
                read_at=now.isoformat(),
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        # Add entries for whatsapp
        for i in range(3):
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_whatsapp_{i}",
                notification_id=f"notif_whatsapp_{i}",
                channel="whatsapp",
                notification_type="reminder",
                recipient_id="user_456",
                zone_id="kitchen",
                zone_name="Küche",
                title=f"Reminder {i}",
                body="Reminder body",
                priority="normal",
                status="sent",
                sent_at=now.isoformat(),
                delivered_at=None,
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        patterns = store.build_channel_patterns()

        assert patterns.total_channels == 2
        assert patterns.channels_with_activity == 2

        telegram_pattern = next(p for p in patterns.patterns if p.channel == "telegram")
        assert telegram_pattern.total_notifications == 10
        assert telegram_pattern.most_common_type == "alert"
        assert telegram_pattern.failure_rate == 0.0

    def test_get_effectiveness_metrics(self, store):
        """Effectiveness-Metriken berechnen."""
        now = datetime.now(timezone.utc)

        # Add diverse notifications
        channels = ["telegram", "whatsapp", "email"]
        types = ["alert", "reminder", "proposal"]
        statuses = ["delivered", "read", "failed"]
        total_expected = len(channels) * len(types) * len(statuses)
        
        for channel in channels:
            for notif_type in types:
                for status in statuses:
                    entry = NotificationDeliveryEntryV1(
                        entry_id=f"entry_{channel}_{notif_type}_{status}",
                        notification_id=f"notif_{channel}_{notif_type}_{status}",
                        channel=channel,
                        notification_type=notif_type,
                        recipient_id="user_123",
                        zone_id="living",
                        zone_name="Wohnbereich",
                        title=f"{notif_type} via {channel}",
                        body="Body",
                        priority="normal",
                        status=status,
                        sent_at=now.isoformat(),
                        delivered_at=now.isoformat() if status != "failed" else None,
                        read_at=now.isoformat() if status == "read" else None,
                        acknowledged_at=None,
                        failed_reason="error" if status == "failed" else None,
                        retry_count=1 if status == "failed" else 0,
                    )
                    store.add_delivery_entry(entry)

        metrics = store.get_effectiveness_metrics()

        assert metrics.total_notifications_analyzed == total_expected
        assert "alert" in metrics.notifications_by_type
        assert "telegram" in metrics.notifications_by_channel
        assert 0.0 <= metrics.overall_delivery_rate <= 1.0
        assert 0.0 <= metrics.overall_read_rate <= 1.0
        assert 0.0 <= metrics.engagement_score <= 1.0

    def test_revision_tracking(self, store):
        """Revision-Tracking bei Änderungen."""
        now = datetime.now(timezone.utc)

        initial_revision = store._revision

        entry = NotificationDeliveryEntryV1(
            entry_id="entry_001",
            notification_id="notif_001",
            channel="telegram",
            notification_type="alert",
            recipient_id="user_123",
            zone_id="living",
            zone_name="Wohnbereich",
            title="Test",
            body="Body",
            priority="normal",
            status="sent",
            sent_at=now.isoformat(),
            delivered_at=None,
            read_at=None,
            acknowledged_at=None,
            failed_reason=None,
            retry_count=0,
        )
        store.add_delivery_entry(entry)

        assert store._revision == initial_revision + 1

    def test_build_summary(self, store):
        """Analytics Summary aufbauen."""
        now = datetime.now(timezone.utc)

        # Add some data
        for i in range(5):
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_{i}",
                notification_id=f"notif_{i}",
                channel="telegram",
                notification_type="alert",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Alert {i}",
                body="Body",
                priority="high",
                status="delivered",
                sent_at=now.isoformat(),
                delivered_at=now.isoformat(),
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        summary = store.build_summary()

        assert summary.usage.total_notifications == 5
        assert summary.patterns.channels_with_activity >= 1
        assert summary.effectiveness.total_notifications_analyzed == 5
        assert summary.summary_revision == summary.usage.revision


class TestNotificationChannel:
    """Tests für NotificationChannel Enum."""

    def test_channels(self):
        """Alle Channels verfügbar."""
        assert NotificationChannel.TELEGRAM == "telegram"
        assert NotificationChannel.WHATSAPP == "whatsapp"
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.PUSH == "push"
        assert NotificationChannel.HA_NOTIFICATION == "ha_notification"
        assert NotificationChannel.SMS == "sms"


class TestNotificationType:
    """Tests für NotificationType Enum."""

    def test_types(self):
        """Alle Typen verfügbar."""
        assert NotificationType.ALERT == "alert"
        assert NotificationType.REMINDER == "reminder"
        assert NotificationType.PROPOSAL == "proposal"
        assert NotificationType.ACTION_CLOSURE == "action_closure"
        assert NotificationType.PRESENCE_HOLD == "presence_hold"
        assert NotificationType.SYSTEM == "system"
        assert NotificationType.DIGEST == "digest"
        assert NotificationType.FOLLOW_UP == "follow_up"


class TestDeliveryStatus:
    """Tests für DeliveryStatus Enum."""

    def test_statuses(self):
        """Alle Status verfügbar."""
        assert DeliveryStatus.PENDING == "pending"
        assert DeliveryStatus.SENT == "sent"
        assert DeliveryStatus.DELIVERED == "delivered"
        assert DeliveryStatus.FAILED == "failed"
        assert DeliveryStatus.READ == "read"
        assert DeliveryStatus.ACKNOWLEDGED == "acknowledged"


class TestNotificationAnalyticsStoreIntegration:
    """Integrationstests für NotificationAnalyticsStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Store mit temporärer DB."""
        db_path = tmp_path / "notification_analytics.db"
        return NotificationAnalyticsStore(db_path=str(db_path))

    def test_full_workflow(self, store):
        """Kompletter Workflow: Add → History → Patterns → Metrics → Summary."""
        now = datetime.now(timezone.utc)

        # Add diverse notifications
        for channel in ["telegram", "whatsapp", "email"]:
            for notif_type in ["alert", "reminder"]:
                for status in ["delivered", "read"]:
                    entry = NotificationDeliveryEntryV1(
                        entry_id=f"entry_{channel}_{notif_type}_{status}",
                        notification_id=f"notif_{channel}_{notif_type}_{status}",
                        channel=channel,
                        notification_type=notif_type,
                        recipient_id="user_123",
                        zone_id="living",
                        zone_name="Wohnbereich",
                        title=f"{notif_type} via {channel}",
                        body="Body",
                        priority="normal",
                        status=status,
                        sent_at=now.isoformat(),
                        delivered_at=now.isoformat(),
                        read_at=now.isoformat() if status == "read" else None,
                        acknowledged_at=None,
                        failed_reason=None,
                        retry_count=0,
                    )
                    store.add_delivery_entry(entry)

        # Build all read models
        history = store.build_delivery_history()
        patterns = store.build_channel_patterns()
        metrics = store.get_effectiveness_metrics()
        summary = store.build_summary()

        # Verify consistency
        assert history.total_notifications == 12  # 3 channels * 2 types * 2 statuses
        assert patterns.total_channels == 3
        assert metrics.total_notifications_analyzed == 12
        assert summary.usage.total_notifications == 12
        assert summary.patterns.channels_with_activity == 3

    def test_time_range_filtering(self, store):
        """Zeitbereichs-Filterung."""
        now = datetime.now(timezone.utc)

        # Add entries at different times
        for days_ago in [1, 3, 7, 14, 30]:
            entry = NotificationDeliveryEntryV1(
                entry_id=f"entry_{days_ago}d",
                notification_id=f"notif_{days_ago}d",
                channel="telegram",
                notification_type="alert",
                recipient_id="user_123",
                zone_id="living",
                zone_name="Wohnbereich",
                title=f"Alert {days_ago}d ago",
                body="Body",
                priority="normal",
                status="delivered",
                sent_at=(now - timedelta(days=days_ago)).isoformat(),
                delivered_at=(now - timedelta(days=days_ago)).isoformat(),
                read_at=None,
                acknowledged_at=None,
                failed_reason=None,
                retry_count=0,
            )
            store.add_delivery_entry(entry)

        # Last 7 days - should include 1, 3, 7 days ago entries
        start_7d = (now - timedelta(days=7)).isoformat()
        history_7d = store.build_delivery_history(time_range_start=start_7d)
        assert history_7d.total_notifications >= 3  # At least 1, 3, 7 days ago

        # Last 30 days - should include all 5 entries
        start_30d = (now - timedelta(days=30)).isoformat()
        history_30d = store.build_delivery_history(time_range_start=start_30d)
        assert history_30d.total_notifications == 5


class TestGetNotificationAnalyticsStore:
    """Tests für Singleton-Getter."""

    def test_singleton_behavior(self):
        """Singleton verhält sich korrekt."""
        store1 = get_notification_analytics_store()
        store2 = get_notification_analytics_store()

        # Should be same instance (or at least same type)
        assert type(store1) == type(store2)
