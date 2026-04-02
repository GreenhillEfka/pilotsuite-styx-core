"""Contract tests for Zone Presence Hold Notification Surface (Slice 43)."""
import pytest
from datetime import datetime, timezone, timedelta

from copilot_core.core.zone_presence_hold import ZoneHoldState
from copilot_core.core.zone_presence_hold_notifications import (
    ZonePresenceHoldNotificationStore,
    ZonePresenceHoldNotification,
    ZonePresenceHoldNotificationSummary,
    HoldNotificationType,
    get_zone_presence_hold_notification_store,
    reset_zone_presence_hold_notification_store,
    record_hold_set_notification,
    record_hold_released_notification,
    record_hold_expired_notification,
    record_hold_expiring_soon_notification,
)


@pytest.fixture(autouse=True)
def reset_store():
    """Reset notification store before each test."""
    reset_zone_presence_hold_notification_store()
    yield
    reset_zone_presence_hold_notification_store()


class TestZonePresenceHoldNotificationContract:
    """Test ZonePresenceHoldNotification V1 contract."""

    def test_notification_creation(self):
        """Test notification creation with required fields."""
        now = datetime.now(timezone.utc).isoformat()
        notification = ZonePresenceHoldNotification(
            notification_id="notif-001",
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Manual override for evening",
            hold_set_at=now,
            hold_expires_at=None,
        )

        result = notification.to_dict()
        assert result["contract"] == "ZonePresenceHoldNotificationV1"
        assert result["notification_id"] == "notif-001"
        assert result["zone_id"] == "zone-living-room"
        assert result["notification_type"] == "hold_set"
        assert result["hold_state"] == "force_on"
        assert result["reason"] == "Manual override for evening"
        assert "triggered_at" in result

    def test_notification_with_metadata(self):
        """Test notification with metadata."""
        notification = ZonePresenceHoldNotification(
            notification_id="notif-002",
            zone_id="zone-bedroom",
            notification_type=HoldNotificationType.HOLD_EXPIRED,
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Auto-expired",
            metadata={"auto_expired": True, "original_duration": 3600},
        )

        result = notification.to_dict()
        assert result["metadata"]["auto_expired"] is True
        assert result["metadata"]["original_duration"] == 3600


class TestZonePresenceHoldNotificationSummaryContract:
    """Test ZonePresenceHoldNotificationSummary V1 contract."""

    def test_summary_creation(self):
        """Test summary creation with required fields."""
        summary = ZonePresenceHoldNotificationSummary(
            notification_revision=5,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
            total_notifications=10,
            unread_notifications=3,
            by_type={"hold_set": 5, "hold_released": 3, "hold_expired": 2},
            by_zone={"zone-living-room": 6, "zone-bedroom": 4},
        )

        result = summary.to_dict()
        assert result["contract"] == "ZonePresenceHoldNotificationSummaryV1"
        assert result["notification_revision"] == 5
        assert result["total_notifications"] == 10
        assert result["unread_notifications"] == 3
        assert result["by_type"]["hold_set"] == 5
        assert result["by_zone"]["zone-living-room"] == 6
        assert result["has_changes"] is True

    def test_summary_delta_detection(self):
        """Test summary delta detection with since_revision."""
        summary = ZonePresenceHoldNotificationSummary(
            notification_revision=10,
            since_revision=8,
        )
        assert summary.has_changes is True

        summary_no_change = ZonePresenceHoldNotificationSummary(
            notification_revision=10,
            since_revision=10,
        )
        assert summary_no_change.has_changes is False


class TestZonePresenceHoldNotificationStore:
    """Test ZonePresenceHoldNotificationStore operations."""

    def test_record_notification(self):
        """Test recording a notification."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        notification = store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test hold",
            hold_set_at=now,
        )

        assert notification.notification_id is not None
        assert notification.zone_id == "zone-living-room"
        assert notification.notification_type == "hold_set"
        assert notification.hold_state == ZoneHoldState.FORCE_ON

    def test_notification_revision_increments(self):
        """Test that revision increments on each notification."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        store.record_notification(
            zone_id="zone-1",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        summary1 = store.get_summary()
        assert summary1.notification_revision == 1

        store.record_notification(
            zone_id="zone-2",
            notification_type=HoldNotificationType.HOLD_RELEASED,
            hold_state=ZoneHoldState.AUTO,
            reason="Test 2",
            hold_set_at=now,
        )
        summary2 = store.get_summary()
        assert summary2.notification_revision == 2

    def test_get_summary_with_filters(self):
        """Test summary with zone and type filters."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        store.record_notification(
            zone_id="zone-bedroom",
            notification_type=HoldNotificationType.HOLD_EXPIRED,
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        # Filter by zone
        summary_living = store.get_summary(zone_id="zone-living-room")
        assert summary_living.total_notifications == 1
        assert summary_living.by_zone.get("zone-living-room") == 1

        # Filter by type
        summary_expired = store.get_summary(notification_type="hold_expired")
        assert summary_expired.total_notifications == 1
        assert summary_expired.by_type.get("hold_expired") == 1

    def test_get_notification_by_id(self):
        """Test retrieving a notification by ID."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        notification = store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        retrieved = store.get_notification(notification.notification_id)
        assert retrieved is not None
        assert retrieved.zone_id == "zone-living-room"

        # Non-existent ID
        assert store.get_notification("non-existent") is None

    def test_mark_read(self):
        """Test marking notifications as read."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        notification = store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        summary_before = store.get_summary()
        assert summary_before.unread_notifications == 1

        store.mark_read(notification.notification_id)

        summary_after = store.get_summary()
        assert summary_after.unread_notifications == 0

    def test_mark_all_read(self):
        """Test marking all notifications as read."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        store.record_notification(
            zone_id="zone-bedroom",
            notification_type=HoldNotificationType.HOLD_RELEASED,
            hold_state=ZoneHoldState.AUTO,
            reason="Test 2",
            hold_set_at=now,
        )

        summary_before = store.get_summary()
        assert summary_before.unread_notifications == 2

        count = store.mark_all_read()
        assert count == 2

        summary_after = store.get_summary()
        assert summary_after.unread_notifications == 0

    def test_mark_all_read_with_zone_filter(self):
        """Test marking all notifications as read with zone filter."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        store.record_notification(
            zone_id="zone-bedroom",
            notification_type=HoldNotificationType.HOLD_RELEASED,
            hold_state=ZoneHoldState.AUTO,
            reason="Test 2",
            hold_set_at=now,
        )

        count = store.mark_all_read(zone_id="zone-living-room")
        assert count == 1

        summary = store.get_summary()
        assert summary.unread_notifications == 1  # bedroom still unread

    def test_recent_notifications_limit(self):
        """Test recent notifications limit."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        for i in range(50):
            store.record_notification(
                zone_id=f"zone-{i}",
                notification_type=HoldNotificationType.HOLD_SET,
                hold_state=ZoneHoldState.FORCE_ON,
                reason=f"Test {i}",
                hold_set_at=now,
            )

        summary_default = store.get_summary()
        assert len(summary_default.recent_notifications) == 20  # default limit

        summary_limited = store.get_summary(recent_limit=5)
        assert len(summary_limited.recent_notifications) == 5

        summary_none = store.get_summary(recent_limit=0)
        assert len(summary_none.recent_notifications) == 0

    def test_delta_detection_with_since_revision(self):
        """Test delta detection with since_revision."""
        store = ZonePresenceHoldNotificationStore()
        now = datetime.now(timezone.utc).isoformat()

        store.record_notification(
            zone_id="zone-living-room",
            notification_type=HoldNotificationType.HOLD_SET,
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        summary_at_rev1 = store.get_summary(since_revision=1)
        assert summary_at_rev1.has_changes is False

        store.record_notification(
            zone_id="zone-bedroom",
            notification_type=HoldNotificationType.HOLD_RELEASED,
            hold_state=ZoneHoldState.AUTO,
            reason="Test 2",
            hold_set_at=now,
        )

        summary_after_new = store.get_summary(since_revision=1)
        assert summary_after_new.has_changes is True


class TestHelperFunctions:
    """Test helper functions for recording notifications."""

    def test_record_hold_set_notification(self):
        """Test record_hold_set_notification helper."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Evening mode",
            hold_set_at=now,
            hold_expires_at=None,
        )

        assert notification.notification_type == HoldNotificationType.HOLD_SET
        assert notification.zone_id == "zone-living-room"
        assert notification.hold_state == ZoneHoldState.FORCE_ON

    def test_record_hold_released_notification(self):
        """Test record_hold_released_notification helper."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_released_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.AUTO,
            reason="Manual release",
            hold_set_at=now,
            hold_released_at=now,
        )

        assert notification.notification_type == HoldNotificationType.HOLD_RELEASED
        assert notification.hold_state == ZoneHoldState.AUTO

    def test_record_hold_expired_notification(self):
        """Test record_hold_expired_notification helper."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_expired_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Auto-expired",
            hold_set_at=now,
            hold_expires_at=now,
        )

        assert notification.notification_type == HoldNotificationType.HOLD_EXPIRED
        assert notification.hold_state == ZoneHoldState.FORCE_OFF

    def test_record_hold_expiring_soon_notification(self):
        """Test record_hold_expiring_soon_notification helper."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_expiring_soon_notification(
            zone_id="zone-kitchen",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Expiring soon",
            hold_set_at=now,
            hold_expires_at=now,
            minutes_until_expiry=5,
        )

        assert notification.notification_type == HoldNotificationType.HOLD_EXPIRING_SOON
        assert notification.metadata["minutes_until_expiry"] == 5


class TestNotificationTypes:
    """Test all notification types are properly defined."""

    def test_hold_set_type(self):
        """Test HOLD_SET notification type."""
        assert HoldNotificationType.HOLD_SET == "hold_set"

    def test_hold_released_type(self):
        """Test HOLD_RELEASED notification type."""
        assert HoldNotificationType.HOLD_RELEASED == "hold_released"

    def test_hold_expired_type(self):
        """Test HOLD_EXPIRED notification type."""
        assert HoldNotificationType.HOLD_EXPIRED == "hold_expired"

    def test_hold_expiring_soon_type(self):
        """Test HOLD_EXPIRING_SOON notification type."""
        assert HoldNotificationType.HOLD_EXPIRING_SOON == "hold_expiring_soon"


class TestGlobalStore:
    """Test global store instance management."""

    def test_get_store_returns_singleton(self):
        """Test that get_store returns the same instance."""
        store1 = get_zone_presence_hold_notification_store()
        store2 = get_zone_presence_hold_notification_store()
        assert store1 is store2

    def test_reset_store_creates_new_instance(self):
        """Test that reset_store creates a new instance."""
        store1 = get_zone_presence_hold_notification_store()
        store1.record_notification(
            zone_id="zone-1",
            notification_type="hold_set",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=datetime.now(timezone.utc).isoformat(),
        )

        reset_zone_presence_hold_notification_store()

        store2 = get_zone_presence_hold_notification_store()
        assert store1 is not store2
        assert store2.get_summary().total_notifications == 0
