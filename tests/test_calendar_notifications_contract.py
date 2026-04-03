"""Calendar Notifications Contract Tests — Slice 69."""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from copilot_core.notifications.calendar_notifications import (
    CalendarNotificationStore,
    CalendarNotificationV1,
    CalendarNotificationType,
    NotificationPriority,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def store(temp_db):
    """Create notification store with temp database."""
    return CalendarNotificationStore(db_path=temp_db)


class TestCalendarNotificationV1:
    """Test CalendarNotificationV1 dataclass."""

    def test_create_notification(self):
        notification = CalendarNotificationV1(
            notification_id="notif-1",
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Zeit für eine Pause",
            message="Du arbeitest seit 90 Minuten ohne Pause.",
            zone_id="zone-office",
            event_id=None,
            created_at=datetime.now().isoformat(),
            expires_at=None,
            status="pending",
            revision=1,
        )
        assert notification.notification_id == "notif-1"
        assert notification.notification_type == "break_reminder"
        assert notification.priority == "medium"
        assert notification.status == "pending"


class TestCalendarNotificationStore:
    """Test CalendarNotificationStore operations."""

    def test_init_creates_tables(self, store):
        """Test database initialization creates required tables."""
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert "notifications" in tables
            assert "dispatch_claims" in tables
            assert "delivery_receipts" in tables
            assert "notification_revision" in tables

    def test_create_notification(self, store):
        """Test creating a new notification."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Zeit für eine Pause",
            message="Du arbeitest seit 90 Minuten ohne Pause.",
            zone_id="zone-office",
        )
        
        assert notification.notification_id is not None
        assert notification.suggestion_id == "suggestion-1"
        assert notification.notification_type == "break_reminder"
        assert notification.priority == "medium"
        assert notification.status == "pending"
        assert notification.revision > 0

        # Verify in database
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT notification_id, suggestion_id, notification_type, priority, status FROM notifications"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == notification.notification_id
            assert row[1] == "suggestion-1"
            assert row[2] == "break_reminder"
            assert row[3] == "medium"
            assert row[4] == "pending"

    def test_create_notification_increments_revision(self, store):
        """Test that creating notifications increments revision."""
        initial_revision = store._get_revision()
        store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        new_revision = store._get_revision()
        assert new_revision > initial_revision

    def test_update_notification_status(self, store):
        """Test updating notification status."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="meeting_prep",
            priority="high",
            title="Meeting in 15 Minuten",
            message="Vorbereitung für das nächste Meeting.",
        )
        
        store.update_notification_status(notification.notification_id, "sent")
        
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM notifications WHERE notification_id = ?",
                (notification.notification_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "sent"

    def test_get_digest(self, store):
        """Test getting notification digest."""
        # Create some notifications
        for i in range(5):
            store.create_notification(
                suggestion_id=f"suggestion-{i}",
                notification_type="break_reminder",
                priority="medium",
                title=f"Notification {i}",
                message=f"Message {i}",
            )
        
        digest = store.get_digest()
        assert digest.total_count == 5
        assert digest.pending_count == 5
        assert digest.revision > 0
        assert len(digest.notifications) == 5

    def test_get_digest_with_status_filter(self, store):
        """Test digest with status filtering."""
        # Create notifications and update some statuses
        notif1 = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test 1",
            message="Message 1",
        )
        notif2 = store.create_notification(
            suggestion_id="suggestion-2",
            notification_type="meeting_prep",
            priority="high",
            title="Test 2",
            message="Message 2",
        )
        
        store.update_notification_status(notif1.notification_id, "sent")
        
        digest_pending = store.get_digest(status_filter="pending")
        assert digest_pending.total_count == 1
        assert digest_pending.pending_count == 1
        
        digest_sent = store.get_digest(status_filter="sent")
        assert digest_sent.total_count == 1

    def test_get_digest_with_since_revision(self, store):
        """Test digest with revision-based delta filtering."""
        # Create initial notifications
        store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test 1",
            message="Message 1",
        )
        initial_revision = store._get_revision()
        
        # Create more notifications
        store.create_notification(
            suggestion_id="suggestion-2",
            notification_type="meeting_prep",
            priority="high",
            title="Test 2",
            message="Message 2",
        )
        
        digest = store.get_digest(since_revision=initial_revision)
        assert digest.has_changes is True
        assert digest.total_count >= 1

    def test_create_dispatch_candidate(self, store):
        """Test creating dispatch candidates."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="focus_block",
            priority="medium",
            title="Focus Block verfügbar",
            message="Optimale Zeit für konzentrierte Arbeit.",
            zone_id="zone-office",
            metadata={"duration_minutes": 90},
        )
        
        candidate = store.create_dispatch_candidate(notification, delivery_mode="scheduled")
        
        assert candidate.dispatch_id is not None
        assert candidate.notification_id == notification.notification_id
        assert candidate.suggestion_id == notification.suggestion_id
        assert candidate.notification_type == "focus_block"
        assert candidate.delivery_mode == "scheduled"
        assert candidate.zone_id == "zone-office"
        assert candidate.metadata == {"duration_minutes": 90}

    def test_claim_dispatch(self, store):
        """Test claiming a dispatch for processing."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        
        claim = store.claim_dispatch(candidate.dispatch_id, candidate.notification_id, "worker-1", lease_seconds=300)
        
        assert claim.claim_id is not None
        assert claim.dispatch_id == candidate.dispatch_id
        assert claim.notification_id == candidate.notification_id
        assert claim.claimed_by == "worker-1"
        assert claim.lease_seconds == 300
        assert claim.status == "active"
        assert claim.expires_at is not None

        # Verify in database
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT claimed_by, lease_seconds, status FROM dispatch_claims WHERE claim_id = ?",
                (claim.claim_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "worker-1"
            assert row[1] == 300
            assert row[2] == "active"

    def test_release_claim(self, store):
        """Test releasing a claim without settlement."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        claim = store.claim_dispatch(candidate.dispatch_id, candidate.notification_id, "worker-1")
        
        store.release_claim(claim.claim_id)
        
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM dispatch_claims WHERE claim_id = ?",
                (claim.claim_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "released"

    def test_settle_claim(self, store):
        """Test settling a claim with result."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        claim = store.claim_dispatch(candidate.dispatch_id, candidate.notification_id, "worker-1")
        
        settlement = {
            "result": "completed",
            "delivered_at": datetime.now().isoformat(),
            "metadata": {"channel": "telegram"},
        }
        store.settle_claim(claim.claim_id, settlement)
        
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, settlement FROM dispatch_claims WHERE claim_id = ?",
                (claim.claim_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "settled"
            assert row[1] is not None

    def test_get_claim_summary(self, store):
        """Test getting claim summary."""
        # Create some claims
        for i in range(3):
            notification = store.create_notification(
                suggestion_id=f"suggestion-{i}",
                notification_type="break_reminder",
                priority="medium",
                title=f"Test {i}",
                message=f"Message {i}",
            )
            candidate = store.create_dispatch_candidate(notification)
            store.claim_dispatch(candidate.dispatch_id, candidate.notification_id, f"worker-{i % 2}")
        
        summary = store.get_claim_summary()
        assert summary.total_count == 3
        assert summary.active_count == 3
        assert summary.expired_count == 0
        assert summary.revision > 0

    def test_record_receipt(self, store):
        """Test recording a delivery receipt."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        
        receipt = store.record_receipt(
            candidate.dispatch_id,
            notification.notification_id,
            delivery_status="delivered",
            metadata={"channel": "telegram", "message_id": "12345"},
        )
        
        assert receipt.receipt_id is not None
        assert receipt.delivery_status == "delivered"
        assert receipt.delivered_at is not None
        assert receipt.retry_count == 0
        assert receipt.next_retry_at is None

        # Verify in database
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT delivery_status, delivered_at FROM delivery_receipts WHERE receipt_id = ?",
                (receipt.receipt_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "delivered"
            assert row[1] is not None

    def test_record_receipt_failed(self, store):
        """Test recording a failed delivery receipt."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        
        receipt = store.record_receipt(
            candidate.dispatch_id,
            notification.notification_id,
            delivery_status="failed",
            metadata={"error": "channel_unavailable"},
        )
        
        assert receipt.delivery_status == "failed"
        assert receipt.delivered_at is None
        assert receipt.next_retry_at is not None

    def test_get_receipt_summary(self, store):
        """Test getting receipt summary."""
        # Create some receipts
        for i in range(5):
            notification = store.create_notification(
                suggestion_id=f"suggestion-{i}",
                notification_type="break_reminder",
                priority="medium",
                title=f"Test {i}",
                message=f"Message {i}",
            )
            candidate = store.create_dispatch_candidate(notification)
            status = "delivered" if i < 3 else "failed" if i < 4 else "sent"
            store.record_receipt(candidate.dispatch_id, notification.notification_id, status)
        
        summary = store.get_receipt_summary()
        assert summary.total_count == 5
        assert summary.delivered_count == 3
        assert summary.failed_count == 1
        assert summary.pending_count == 1
        assert summary.revision > 0


class TestCalendarNotificationTypes:
    """Test notification type coverage."""

    def test_all_notification_types_defined(self):
        """Test that all expected notification types are defined."""
        expected_types = [
            "break_reminder",
            "meeting_prep",
            "focus_block",
            "alarm_adjustment",
            "lighting_scene",
            "stress_relief",
            "lunch_reminder",
            "end_of_day_wrap",
        ]
        
        for expected in expected_types:
            assert hasattr(CalendarNotificationType, expected.upper())
            assert getattr(CalendarNotificationType, expected.upper()).value == expected

    def test_all_priority_levels_defined(self):
        """Test that all priority levels are defined."""
        expected_priorities = ["low", "medium", "high", "critical"]
        
        for expected in expected_priorities:
            assert hasattr(NotificationPriority, expected.upper())
            assert getattr(NotificationPriority, expected.upper()).value == expected


class TestCalendarNotificationsAPIContract:
    """Test API contract structure (without Flask app)."""

    def test_notification_structure(self, store):
        """Test notification structure matches API contract."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
            zone_id="zone-office",
        )
        
        # Verify all fields required by API are present
        assert hasattr(notification, "notification_id")
        assert hasattr(notification, "suggestion_id")
        assert hasattr(notification, "notification_type")
        assert hasattr(notification, "priority")
        assert hasattr(notification, "title")
        assert hasattr(notification, "message")
        assert hasattr(notification, "zone_id")
        assert hasattr(notification, "event_id")
        assert hasattr(notification, "created_at")
        assert hasattr(notification, "expires_at")
        assert hasattr(notification, "status")
        assert hasattr(notification, "revision")
        assert hasattr(notification, "metadata")

    def test_digest_structure(self, store):
        """Test digest structure matches API contract."""
        digest = store.get_digest()
        
        assert hasattr(digest, "notifications")
        assert hasattr(digest, "total_count")
        assert hasattr(digest, "pending_count")
        assert hasattr(digest, "revision")
        assert hasattr(digest, "latest_change_at")
        assert hasattr(digest, "has_changes")
        
        assert isinstance(digest.notifications, list)
        assert isinstance(digest.total_count, int)
        assert isinstance(digest.has_changes, bool)

    def test_claim_structure(self, store):
        """Test claim structure matches API contract."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        claim = store.claim_dispatch(candidate.dispatch_id, candidate.notification_id, "worker-1")
        
        assert hasattr(claim, "claim_id")
        assert hasattr(claim, "dispatch_id")
        assert hasattr(claim, "notification_id")
        assert hasattr(claim, "claimed_by")
        assert hasattr(claim, "claimed_at")
        assert hasattr(claim, "lease_seconds")
        assert hasattr(claim, "expires_at")
        assert hasattr(claim, "status")
        assert hasattr(claim, "settlement")

    def test_receipt_structure(self, store):
        """Test receipt structure matches API contract."""
        notification = store.create_notification(
            suggestion_id="suggestion-1",
            notification_type="break_reminder",
            priority="medium",
            title="Test",
            message="Test message",
        )
        candidate = store.create_dispatch_candidate(notification)
        receipt = store.record_receipt(
            candidate.dispatch_id, notification.notification_id, "delivered"
        )
        
        assert hasattr(receipt, "receipt_id")
        assert hasattr(receipt, "dispatch_id")
        assert hasattr(receipt, "notification_id")
        assert hasattr(receipt, "delivery_status")
        assert hasattr(receipt, "delivered_at")
        assert hasattr(receipt, "read_at")
        assert hasattr(receipt, "acknowledged_at")
        assert hasattr(receipt, "failure_reason")
        assert hasattr(receipt, "retry_count")
        assert hasattr(receipt, "next_retry_at")
        assert hasattr(receipt, "metadata")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
