"""API tests for Zone Presence Hold Notifications (Slice 43)."""
import pytest
from datetime import datetime, timezone

from copilot_core.core.zone_presence_hold import ZoneHoldState
from copilot_core.core.zone_presence_hold_notifications import (
    get_zone_presence_hold_notification_store,
    reset_zone_presence_hold_notification_store,
    HoldNotificationType,
    record_hold_set_notification,
)


@pytest.fixture(autouse=True)
def reset_store():
    """Reset notification store before each test."""
    reset_zone_presence_hold_notification_store()
    yield
    reset_zone_presence_hold_notification_store()


@pytest.fixture
def app_client():
    """Create test client with registered routes."""
    from copilot_core.app import create_app
    app = create_app()
    
    # Ensure notification routes are registered
    from copilot_core.api.v1.zone_presence_hold_notifications import setup_routes
    setup_routes(app)
    
    with app.test_client() as client:
        yield client


class TestListHoldNotifications:
    """Test GET /api/v1/presence/holds/notifications endpoint."""

    def test_list_notifications_empty(self, app_client):
        """Test listing notifications when store is empty."""
        response = app_client.get("/api/v1/presence/holds/notifications")
        assert response.status_code == 200

        data = response.get_json()
        assert data["contract"] == "ZonePresenceHoldNotificationsListV1"
        assert data["summary"]["total_notifications"] == 0
        assert len(data["notifications"]) == 0

    def test_list_notifications_with_items(self, app_client):
        """Test listing notifications with items in store."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test hold",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test hold 2",
            hold_set_at=now,
        )

        response = app_client.get("/api/v1/presence/holds/notifications")
        assert response.status_code == 200

        data = response.get_json()
        assert data["summary"]["total_notifications"] == 2
        assert len(data["notifications"]) == 2  # default limit is 20

    def test_list_notifications_zone_filter(self, app_client):
        """Test listing notifications with zone filter."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        response = app_client.get(
            "/api/v1/presence/holds/notifications",
            query_string={"zone_id": "zone-living-room"},
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["summary"]["total_notifications"] == 1
        assert data["summary"]["by_zone"]["zone-living-room"] == 1

    def test_list_notifications_type_filter(self, app_client):
        """Test listing notifications with type filter."""
        store = get_zone_presence_hold_notification_store()
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

        response = app_client.get(
            "/api/v1/presence/holds/notifications",
            query_string={"notification_type": "hold_expired"},
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["summary"]["total_notifications"] == 1
        assert data["summary"]["by_type"]["hold_expired"] == 1

    def test_list_notifications_since_revision(self, app_client):
        """Test listing notifications with since_revision for delta."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        # First request at revision 1
        response1 = app_client.get(
            "/api/v1/presence/holds/notifications",
            query_string={"since_revision": 1},
        )
        data1 = response1.get_json()
        assert data1["summary"]["has_changes"] is False

        # Add another notification
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        # Second request should detect changes
        response2 = app_client.get(
            "/api/v1/presence/holds/notifications",
            query_string={"since_revision": 1},
        )
        data2 = response2.get_json()
        assert data2["summary"]["has_changes"] is True
        assert data2["summary"]["total_notifications"] == 2

    def test_list_notifications_recent_limit(self, app_client):
        """Test listing notifications with recent_limit."""
        store = get_zone_presence_hold_notification_store()
        now = datetime.now(timezone.utc).isoformat()

        for i in range(50):
            store.record_notification(
                zone_id=f"zone-{i}",
                notification_type=HoldNotificationType.HOLD_SET,
                hold_state=ZoneHoldState.FORCE_ON,
                reason=f"Test {i}",
                hold_set_at=now,
            )

        response = app_client.get(
            "/api/v1/presence/holds/notifications",
            query_string={"recent_limit": 10},
        )
        assert response.status_code == 200

        data = response.get_json()
        assert len(data["notifications"]) == 10


class TestGetHoldNotificationsSummary:
    """Test GET /api/v1/presence/holds/notifications/summary endpoint."""

    def test_summary_empty(self, app_client):
        """Test summary when store is empty."""
        response = app_client.get("/api/v1/presence/holds/notifications/summary")
        assert response.status_code == 200

        data = response.get_json()
        assert data["contract"] == "ZonePresenceHoldNotificationSummaryV1"
        assert data["total_notifications"] == 0
        assert data["notification_revision"] == 0

    def test_summary_with_items(self, app_client):
        """Test summary with items in store."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        response = app_client.get("/api/v1/presence/holds/notifications/summary")
        assert response.status_code == 200

        data = response.get_json()
        assert data["total_notifications"] == 2
        assert data["notification_revision"] == 2
        assert len(data["recent_notifications"]) == 0  # summary endpoint returns 0 recent

    def test_summary_with_zone_filter(self, app_client):
        """Test summary with zone filter."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        response = app_client.get(
            "/api/v1/presence/holds/notifications/summary",
            query_string={"zone_id": "zone-living-room"},
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["total_notifications"] == 1
        assert data["by_zone"]["zone-living-room"] == 1


class TestGetHoldNotification:
    """Test GET /api/v1/presence/holds/notifications/<id> endpoint."""

    def test_get_notification_success(self, app_client):
        """Test getting a single notification by ID."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test hold",
            hold_set_at=now,
        )

        response = app_client.get(f"/api/v1/presence/holds/notifications/{notification.notification_id}")
        assert response.status_code == 200

        data = response.get_json()
        assert data["contract"] == "ZonePresenceHoldNotificationV1"
        assert data["notification"]["notification_id"] == notification.notification_id
        assert data["notification"]["zone_id"] == "zone-living-room"

    def test_get_notification_not_found(self, app_client):
        """Test getting a non-existent notification."""
        response = app_client.get("/api/v1/presence/holds/notifications/non-existent-id")
        assert response.status_code == 404

        data = response.get_json()
        assert "detail" in data


class TestMarkHoldNotificationRead:
    """Test POST /api/v1/presence/holds/notifications/<id>/read endpoint."""

    def test_mark_read_success(self, app_client):
        """Test marking a notification as read."""
        now = datetime.now(timezone.utc).isoformat()
        notification = record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        # Verify it's unread
        summary_before = get_zone_presence_hold_notification_store().get_summary()
        assert summary_before.unread_notifications == 1

        response = app_client.post(f"/api/v1/presence/holds/notifications/{notification.notification_id}/read")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["notification_id"] == notification.notification_id
        assert data["status"] == "read"

        # Verify it's now read
        summary_after = get_zone_presence_hold_notification_store().get_summary()
        assert summary_after.unread_notifications == 0

    def test_mark_read_not_found(self, app_client):
        """Test marking a non-existent notification as read."""
        response = app_client.post("/api/v1/presence/holds/notifications/non-existent/read")
        assert response.status_code == 404


class TestMarkAllHoldNotificationsRead:
    """Test POST /api/v1/presence/holds/notifications/read-all endpoint."""

    def test_mark_all_read_success(self, app_client):
        """Test marking all notifications as read."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        response = app_client.post("/api/v1/presence/holds/notifications/read-all")
        assert response.status_code == 200

        data = response.get_json()
        assert data["success"] is True
        assert data["marked_count"] == 2

        summary = get_zone_presence_hold_notification_store().get_summary()
        assert summary.unread_notifications == 0

    def test_mark_all_read_with_zone_filter(self, app_client):
        """Test marking all notifications as read with zone filter."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test 1",
            hold_set_at=now,
        )
        record_hold_set_notification(
            zone_id="zone-bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="Test 2",
            hold_set_at=now,
        )

        response = app_client.post(
            "/api/v1/presence/holds/notifications/read-all",
            query_string={"zone_id": "zone-living-room"},
        )
        assert response.status_code == 200

        data = response.get_json()
        assert data["marked_count"] == 1
        assert data["zone_id"] == "zone-living-room"

        summary = get_zone_presence_hold_notification_store().get_summary()
        assert summary.unread_notifications == 1  # bedroom still unread


class TestNotificationContractStructure:
    """Test that notification contracts have correct structure."""

    def test_notification_list_contract_structure(self, app_client):
        """Test that notification list has correct contract structure."""
        now = datetime.now(timezone.utc).isoformat()
        record_hold_set_notification(
            zone_id="zone-living-room",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="Test",
            hold_set_at=now,
        )

        response = app_client.get("/api/v1/presence/holds/notifications")
        data = response.get_json()

        # Check top-level contract
        assert data["contract"] == "ZonePresenceHoldNotificationsListV1"
        assert "summary" in data
        assert "notifications" in data

        # Check summary contract
        summary = data["summary"]
        assert summary["contract"] == "ZonePresenceHoldNotificationSummaryV1"
        assert "notification_revision" in summary
        assert "latest_change_at" in summary
        assert "total_notifications" in summary
        assert "unread_notifications" in summary
        assert "by_type" in summary
        assert "by_zone" in summary
        assert "recent_notifications" in summary
        assert "has_changes" in summary

        # Check notification contract
        if data["notifications"]:
            notif = data["notifications"][0]
            assert notif["contract"] == "ZonePresenceHoldNotificationV1"
            assert "notification_id" in notif
            assert "zone_id" in notif
            assert "notification_type" in notif
            assert "hold_state" in notif
            assert "reason" in notif
            assert "triggered_at" in notif
