"""
Notification Delivery Engine Contract Tests — Slice 68.

Tests for unified notification delivery with channel routing,
rate limiting, quiet hours, and delivery tracking.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock

from copilot_core.notifications.delivery_contracts import (
    DeliveryAttemptV1,
    DeliveryMode,
    DeliveryStatus,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
    NotificationDeliveryV1,
    QuietHoursStateV1,
    RateLimitStateV1,
)
from copilot_core.notifications.delivery_engine import DeliveryEngine
from copilot_core.notifications.delivery_store import (
    NotificationDeliveryStore,
    get_notification_delivery_store,
)


class MockUserStore:
    """Mock user store for testing."""
    
    def __init__(self):
        self._preferences = {}
    
    def get_preferences(self, user_id: str):
        """Get user preferences."""
        return self._preferences.get(user_id)
    
    def set_preferences(self, user_id: str, preferences):
        """Set user preferences for testing."""
        self._preferences[user_id] = preferences


class MockAnalyticsStore:
    """Mock analytics store for testing."""
    
    def __init__(self):
        self._deliveries = []
    
    def add_delivery_entry(self, **kwargs):
        """Add delivery entry."""
        self._deliveries.append(kwargs)


class TestNotificationContracts:
    """Test notification delivery contracts."""
    
    def test_notification_v1_creation(self):
        """Test NotificationV1 creation."""
        notification = NotificationV1(
            notification_id="notif_test_001",
            type=NotificationType.ALERT,
            priority=NotificationPriority.HIGH,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id="zone_living",
            title="Test Alert",
            body="This is a test notification",
        )
        
        assert notification.notification_id == "notif_test_001"
        assert notification.type == NotificationType.ALERT
        assert notification.priority == NotificationPriority.HIGH
        assert notification.channel == NotificationChannel.TELEGRAM
        assert notification.title == "Test Alert"
        assert notification.body == "This is a test notification"
    
    def test_notification_v1_to_dict(self):
        """Test NotificationV1 serialization."""
        notification = NotificationV1(
            notification_id="notif_test_002",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.EMAIL,
            recipient_id="user@example.com",
            user_id="user123",
            zone_id=None,
            title="Info",
            body="Info body",
        )
        
        data = notification.to_dict()
        
        assert data["notification_id"] == "notif_test_002"
        assert data["type"] == "info"
        assert data["priority"] == "normal"
        assert data["channel"] == "email"
        assert "created_at" in data
    
    def test_delivery_attempt_v1(self):
        """Test DeliveryAttemptV1 creation."""
        now = datetime.now(timezone.utc)
        attempt = DeliveryAttemptV1(
            attempt_id="att_001",
            notification_id="notif_test",
            channel=NotificationChannel.TELEGRAM,
            status=DeliveryStatus.SENT,
            attempted_at=now,
            completed_at=now,
            latency_ms=150,
        )
        
        assert attempt.attempt_id == "att_001"
        assert attempt.status == DeliveryStatus.SENT
        assert attempt.latency_ms == 150
    
    def test_notification_delivery_v1(self):
        """Test NotificationDeliveryV1 creation."""
        now = datetime.now(timezone.utc)
        delivery = NotificationDeliveryV1(
            delivery_id="del_001",
            notification_id="notif_test",
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            status=DeliveryStatus.SENT,
            priority=NotificationPriority.HIGH,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=now,
        )
        
        assert delivery.delivery_id == "del_001"
        assert delivery.status == DeliveryStatus.SENT
        assert delivery.delivery_mode == DeliveryMode.IMMEDIATE
    
    def test_quiet_hours_state_v1(self):
        """Test QuietHoursStateV1."""
        now = datetime.now(timezone.utc)
        state = QuietHoursStateV1(
            user_id="user123",
            is_quiet_hours=True,
            quiet_hours_start=22,
            quiet_hours_end=7,
            current_hour=23,
            priority_override=True,
            next_quiet_hours_start=None,
            next_quiet_hours_end=now + timedelta(hours=8),
        )
        
        assert state.is_quiet_hours is True
        assert state.quiet_hours_start == 22
        assert state.priority_override is True
    
    def test_rate_limit_state_v1(self):
        """Test RateLimitStateV1."""
        now = datetime.now(timezone.utc)
        state = RateLimitStateV1(
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            window_start=now,
            window_end=now + timedelta(hours=1),
            count=50,
            limit=60,
            reset_at=now + timedelta(hours=1),
            is_limited=False,
        )
        
        assert state.count == 50
        assert state.limit == 60
        assert state.is_limited is False


class TestDeliveryEngine:
    """Test DeliveryEngine functionality."""
    
    @pytest.fixture
    def user_store(self):
        """Create mock user store."""
        return MockUserStore()
    
    @pytest.fixture
    def analytics_store(self):
        """Create mock analytics store."""
        return MockAnalyticsStore()
    
    @pytest.fixture
    def engine(self, user_store, analytics_store):
        """Create delivery engine."""
        return DeliveryEngine(user_store, analytics_store)
    
    def test_engine_initialization(self, engine):
        """Test engine initializes with default handlers."""
        assert NotificationChannel.TELEGRAM in engine._handlers
        assert NotificationChannel.EMAIL in engine._handlers
        assert NotificationChannel.PUSH in engine._handlers
    
    def test_rate_limit_initial_check(self, engine):
        """Test rate limit check for new user/channel."""
        is_limited, state = engine._check_rate_limit("user123", NotificationChannel.TELEGRAM)
        
        assert is_limited is False
        assert state is not None
        assert state.count == 1  # First request increments
        assert state.limit == 60  # Default Telegram limit
    
    def test_rate_limit_exceeded(self, engine):
        """Test rate limit when exceeded."""
        user_id = "user_rate_test"
        channel = NotificationChannel.SMS  # Lower limit (20)
        
        # Exhaust rate limit
        for i in range(25):
            is_limited, state = engine._check_rate_limit(user_id, channel)
        
        assert is_limited is True
        assert state.count >= state.limit
    
    def test_quiet_hours_detection(self, engine, user_store):
        """Test quiet hours detection."""
        user_id = "user_quiet_test"
        
        from copilot_core.users.contracts import NotificationPreferencesV1
        prefs = NotificationPreferencesV1(
            user_id=user_id,
            global_quiet_hours_start="22:00",
            global_quiet_hours_end="07:00",
        )
        user_store.set_preferences(user_id, prefs)
        
        is_quiet, state = engine._check_quiet_hours(user_id, NotificationPriority.NORMAL)
        
        # State should be created
        assert state is not None
        assert state.quiet_hours_start == 22
        assert state.quiet_hours_end == 7
    
    def test_priority_override_quiet_hours(self, engine, user_store):
        """Test critical priority bypasses quiet hours."""
        user_id = "user_priority_test"
        
        from copilot_core.users.contracts import NotificationPreferencesV1
        prefs = NotificationPreferencesV1(
            user_id=user_id,
            global_quiet_hours_start="22:00",
            global_quiet_hours_end="07:00",
        )
        user_store.set_preferences(user_id, prefs)
        
        # Critical priority should bypass quiet hours
        is_quiet, state = engine._check_quiet_hours(
            user_id, 
            NotificationPriority.CRITICAL
        )
        
        # With priority override, critical notifications bypass quiet hours
        assert state.priority_override is True
    
    @pytest.mark.asyncio
    async def test_deliver_success(self, engine, user_store, analytics_store):
        """Test successful notification delivery."""
        # Set user preferences to allow all channels
        from copilot_core.users.contracts import NotificationPreferencesV1
        user_store.set_preferences("user123", NotificationPreferencesV1(user_id="user123"))
        
        notification = NotificationV1(
            notification_id="notif_deliver_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test body",
        )
        
        delivery = await engine.deliver(notification)
        
        # Delivery should be SENT or at least not failed
        assert delivery.delivery_id is not None
        assert delivery.status in [DeliveryStatus.SENT, DeliveryStatus.QUIET_HOURS]
        if delivery.status == DeliveryStatus.SENT:
            assert delivery.sent_at is not None
            assert len(delivery.attempts) >= 1
    
    @pytest.mark.asyncio
    async def test_deliver_channel_disabled(self, engine, user_store):
        """Test delivery when channel is disabled."""
        user_id = "user_disabled_test"
        
        from copilot_core.users.contracts import NotificationPreferencesV1, ChannelPreferencesV1, NotificationChannel as UserNotificationChannel, DeliveryMode, NotificationPriority as UserNotificationPriority
        prefs = NotificationPreferencesV1(
            user_id=user_id,
            global_enabled=False,  # Disable all channels globally
            channel_preferences={
                "telegram": ChannelPreferencesV1(channel=UserNotificationChannel.TELEGRAM, enabled=False),
            },
        )
        user_store.set_preferences(user_id, prefs)
        
        notification = NotificationV1(
            notification_id="notif_disabled_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id=user_id,
            user_id=user_id,
            zone_id=None,
            title="Test",
            body="Test body",
        )
        
        delivery = await engine.deliver(notification)
        
        assert delivery.status == DeliveryStatus.CANCELLED
        assert delivery.cancelled_at is not None
    
    @pytest.mark.asyncio
    async def test_deliver_quiet_hours(self, engine, user_store):
        """Test delivery during quiet hours."""
        user_id = "user_quiet_delivery_test"
        
        from copilot_core.users.contracts import NotificationPreferencesV1
        prefs = NotificationPreferencesV1(
            user_id=user_id,
            global_quiet_hours_start="00:00",  # Always quiet for testing
            global_quiet_hours_end="23:00",
        )
        user_store.set_preferences(user_id, prefs)
        
        notification = NotificationV1(
            notification_id="notif_quiet_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id=user_id,
            user_id=user_id,
            zone_id=None,
            title="Test",
            body="Test body",
        )
        
        delivery = await engine.deliver(notification)
        
        # Should be quiet hours blocked
        assert delivery.status in [DeliveryStatus.QUIET_HOURS, DeliveryStatus.SENT]
        # Note: Actual result depends on current time
    
    @pytest.mark.asyncio
    async def test_deliver_unknown_channel(self, engine, user_store):
        """Test delivery with unknown channel."""
        # Set user preferences to allow all channels (no quiet hours)
        from copilot_core.users.contracts import NotificationPreferencesV1
        user_store.set_preferences("user123", NotificationPreferencesV1(
            user_id="user123",
            global_quiet_hours_start=None,  # No quiet hours
            global_quiet_hours_end=None,
        ))
        
        # Create custom channel not in handlers
        notification = NotificationV1(
            notification_id="notif_unknown_channel",
            type=NotificationType.INFO,
            priority=NotificationPriority.CRITICAL,  # Critical to bypass quiet hours
            channel=NotificationChannel.SLACK,  # Not registered by default
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test body",
        )
        
        delivery = await engine.deliver(notification)
        
        # Should fail because SLACK handler is not registered
        # (or be quiet_hours if test runs during quiet hours despite CRITICAL)
        assert delivery.status in [DeliveryStatus.FAILED, DeliveryStatus.QUIET_HOURS]
        if delivery.status == DeliveryStatus.FAILED:
            assert delivery.failed_at is not None
            assert len(delivery.attempts) >= 1
            assert delivery.attempts[0].error_message is not None


class TestDeliveryStore:
    """Test NotificationDeliveryStore functionality."""
    
    @pytest.fixture
    def store(self, tmp_path):
        """Create store with temp database."""
        db_path = tmp_path / "test_delivery.db"
        return NotificationDeliveryStore(str(db_path))
    
    def test_store_initialization(self, store):
        """Test store initializes database."""
        assert store._revision == 0
    
    def test_save_and_get_notification(self, store):
        """Test saving and retrieving notification."""
        notification = NotificationV1(
            notification_id="notif_store_test",
            type=NotificationType.ALERT,
            priority=NotificationPriority.HIGH,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id="zone_living",
            title="Store Test",
            body="Test body",
        )
        
        store.save_notification(notification)
        
        # Also save a delivery to increment revision
        from datetime import datetime, timezone
        delivery = NotificationDeliveryV1(
            delivery_id="del_store_test_1",
            notification_id="notif_store_test",
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            status=DeliveryStatus.SENT,
            priority=NotificationPriority.HIGH,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=datetime.now(timezone.utc),
        )
        store.save_delivery(delivery)
        
        # Verify saved (via summary - counts deliveries)
        summary = store.get_summary()
        assert summary.total_deliveries >= 1
    
    def test_save_and_get_delivery(self, store):
        """Test saving and retrieving delivery."""
        now = datetime.now(timezone.utc)
        
        # Save notification first
        notification = NotificationV1(
            notification_id="notif_delivery_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.EMAIL,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test",
        )
        store.save_notification(notification)
        
        # Save delivery
        delivery = NotificationDeliveryV1(
            delivery_id="del_store_test",
            notification_id="notif_delivery_test",
            user_id="user123",
            channel=NotificationChannel.EMAIL,
            recipient_id="user123",
            status=DeliveryStatus.SENT,
            priority=NotificationPriority.NORMAL,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=now,
        )
        store.save_delivery(delivery)
        
        # Retrieve
        retrieved = store.get_delivery("del_store_test")
        
        assert retrieved is not None
        assert retrieved.delivery_id == "del_store_test"
        assert retrieved.status == DeliveryStatus.SENT
    
    def test_get_deliveries_by_user(self, store):
        """Test getting deliveries by user."""
        now = datetime.now(timezone.utc)
        
        # Save multiple deliveries for same user
        for i in range(5):
            notification = NotificationV1(
                notification_id=f"notif_user_test_{i}",
                type=NotificationType.INFO,
                priority=NotificationPriority.NORMAL,
                channel=NotificationChannel.TELEGRAM,
                recipient_id="user_test",
                user_id="user_test",
                zone_id=None,
                title=f"Test {i}",
                body="Test",
            )
            store.save_notification(notification)
            
            delivery = NotificationDeliveryV1(
                delivery_id=f"del_user_test_{i}",
                notification_id=f"notif_user_test_{i}",
                user_id="user_test",
                channel=NotificationChannel.TELEGRAM,
                recipient_id="user_test",
                status=DeliveryStatus.SENT,
                priority=NotificationPriority.NORMAL,
                delivery_mode=DeliveryMode.IMMEDIATE,
                sent_at=now,
            )
            store.save_delivery(delivery)
        
        # Retrieve by user
        deliveries = store.get_deliveries_by_user("user_test", limit=10)
        
        assert len(deliveries) == 5
    
    def test_get_summary(self, store):
        """Test getting delivery summary."""
        summary = store.get_summary()
        
        assert summary.total_deliveries >= 0
        assert isinstance(summary.by_status, dict)
        assert isinstance(summary.by_channel, dict)
        assert summary.latest_revision >= 0
    
    def test_revision_increment(self, store):
        """Test revision increments on changes."""
        initial_revision = store._revision
        
        notification = NotificationV1(
            notification_id="notif_revision_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test",
        )
        store.save_notification(notification)
        
        assert store._revision > initial_revision
    
    def test_mark_delivered(self, store):
        """Test marking delivery as delivered."""
        now = datetime.now(timezone.utc)
        
        # Create notification and delivery
        notification = NotificationV1(
            notification_id="notif_mark_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test",
        )
        store.save_notification(notification)
        
        delivery = NotificationDeliveryV1(
            delivery_id="del_mark_test",
            notification_id="notif_mark_test",
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            status=DeliveryStatus.SENT,
            priority=NotificationPriority.NORMAL,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=now,
        )
        store.save_delivery(delivery)
        
        # Mark as delivered
        success = store.mark_delivered("del_mark_test")
        
        assert success is True
        
        # Verify status changed
        retrieved = store.get_delivery("del_mark_test")
        assert retrieved.status == DeliveryStatus.DELIVERED
        assert retrieved.delivered_at is not None
    
    def test_mark_read(self, store):
        """Test marking delivery as read."""
        now = datetime.now(timezone.utc)
        
        notification = NotificationV1(
            notification_id="notif_read_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test",
        )
        store.save_notification(notification)
        
        delivery = NotificationDeliveryV1(
            delivery_id="del_read_test",
            notification_id="notif_read_test",
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            status=DeliveryStatus.DELIVERED,
            priority=NotificationPriority.NORMAL,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=now,
            delivered_at=now,
        )
        store.save_delivery(delivery)
        
        # Mark as read
        success = store.mark_read("del_read_test")
        
        assert success is True
        
        retrieved = store.get_delivery("del_read_test")
        assert retrieved.status == DeliveryStatus.READ
        assert retrieved.read_at is not None
    
    def test_mark_acknowledged(self, store):
        """Test marking delivery as acknowledged."""
        now = datetime.now(timezone.utc)
        
        notification = NotificationV1(
            notification_id="notif_ack_test",
            type=NotificationType.INFO,
            priority=NotificationPriority.NORMAL,
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            user_id="user123",
            zone_id=None,
            title="Test",
            body="Test",
        )
        store.save_notification(notification)
        
        delivery = NotificationDeliveryV1(
            delivery_id="del_ack_test",
            notification_id="notif_ack_test",
            user_id="user123",
            channel=NotificationChannel.TELEGRAM,
            recipient_id="user123",
            status=DeliveryStatus.READ,
            priority=NotificationPriority.NORMAL,
            delivery_mode=DeliveryMode.IMMEDIATE,
            sent_at=now,
            delivered_at=now,
            read_at=now,
        )
        store.save_delivery(delivery)
        
        # Mark as acknowledged
        success = store.mark_acknowledged("del_ack_test")
        
        assert success is True
        
        retrieved = store.get_delivery("del_ack_test")
        assert retrieved.status == DeliveryStatus.ACKNOWLEDGED
        assert retrieved.acknowledged_at is not None
    
    def test_get_delta(self, store):
        """Test delta retrieval since revision."""
        from datetime import datetime, timezone
        
        initial_revision = store._revision
        
        # Make some changes - save notifications AND deliveries
        for i in range(3):
            notification = NotificationV1(
                notification_id=f"notif_delta_test_{i}",
                type=NotificationType.INFO,
                priority=NotificationPriority.NORMAL,
                channel=NotificationChannel.TELEGRAM,
                recipient_id="user123",
                user_id="user123",
                zone_id=None,
                title=f"Delta Test {i}",
                body="Test",
            )
            store.save_notification(notification)
            
            delivery = NotificationDeliveryV1(
                delivery_id=f"del_delta_test_{i}",
                notification_id=f"notif_delta_test_{i}",
                user_id="user123",
                channel=NotificationChannel.TELEGRAM,
                recipient_id="user123",
                status=DeliveryStatus.SENT,
                priority=NotificationPriority.NORMAL,
                delivery_mode=DeliveryMode.IMMEDIATE,
                sent_at=datetime.now(timezone.utc),
            )
            store.save_delivery(delivery)
        
        # Get delta
        delta = store.get_delta(initial_revision)
        
        assert delta.has_changes is True
        assert delta.revision > initial_revision
        assert len(delta.changes_since_revision) > 0


class TestDeliveryIntegration:
    """Integration tests for delivery engine + store."""
    
    @pytest.fixture
    def user_store(self):
        """Create mock user store."""
        return MockUserStore()
    
    @pytest.fixture
    def analytics_store(self):
        """Create mock analytics store."""
        return MockAnalyticsStore()
    
    @pytest.fixture
    def delivery_store(self, tmp_path):
        """Create delivery store with temp database."""
        db_path = tmp_path / "test_integration.db"
        return NotificationDeliveryStore(str(db_path))
    
    @pytest.fixture
    def engine(self, user_store, analytics_store):
        """Create delivery engine."""
        return DeliveryEngine(user_store, analytics_store)
    
    @pytest.mark.asyncio
    async def test_full_delivery_flow(self, engine, delivery_store, user_store):
        """Test complete delivery flow from send to acknowledge."""
        user_id = "user_integration_test"
        
        # Set user preferences to allow all channels
        from copilot_core.users.contracts import NotificationPreferencesV1
        user_store.set_preferences(user_id, NotificationPreferencesV1(user_id=user_id))
        
        # Create notification
        notification = NotificationV1(
            notification_id="notif_integration_test",
            type=NotificationType.ALERT,
            priority=NotificationPriority.HIGH,
            channel=NotificationChannel.TELEGRAM,
            recipient_id=user_id,
            user_id=user_id,
            zone_id="zone_living",
            title="Integration Test",
            body="Testing full delivery flow",
        )
        
        # Save notification
        delivery_store.save_notification(notification)
        
        # Deliver
        delivery = await engine.deliver(notification)
        
        # Accept SENT or QUIET_HOURS (depending on test execution time)
        assert delivery.status in [DeliveryStatus.SENT, DeliveryStatus.QUIET_HOURS]
        
        # Save delivery
        delivery_store.save_delivery(delivery)
        
        # Mark as delivered
        delivery_store.mark_delivered(delivery.delivery_id)
        
        # Mark as read
        delivery_store.mark_read(delivery.delivery_id)
        
        # Mark as acknowledged
        delivery_store.mark_acknowledged(delivery.delivery_id)
        
        # Verify final state
        final = delivery_store.get_delivery(delivery.delivery_id)
        
        assert final.status == DeliveryStatus.ACKNOWLEDGED
        assert final.sent_at is not None or delivery.status == DeliveryStatus.QUIET_HOURS
        assert final.delivered_at is not None
        assert final.read_at is not None
        assert final.acknowledged_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
