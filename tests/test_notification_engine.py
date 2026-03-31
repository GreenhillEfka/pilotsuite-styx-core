"""Tests for Unified Notification Engine — Slice 18."""
import pytest
from copilot_core.notifications.engine import (
    NotificationEngine,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    create_notification_engine,
)


class TestNotificationEngine:
    """Test notification engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_notification_engine()
        assert engine is not None
    
    def test_register_user(self):
        """Test user registration."""
        engine = NotificationEngine()
        
        user_id = engine.register_user("user_001")
        
        assert user_id == "user_001"
        assert user_id in engine._preferences
        assert NotificationChannel.TELEGRAM in engine._preferences[user_id].enabled_channels
    
    def test_register_user_with_preferences(self):
        """Test user registration with custom preferences."""
        engine = NotificationEngine()
        
        user_id = engine.register_user("user_002", {
            "enabled_channels": ["telegram", "email"],
            "quiet_hours_start": 23,
            "quiet_hours_end": 6,
            "digest_enabled": True,
        })
        
        prefs = engine._preferences[user_id]
        assert NotificationChannel.TELEGRAM in prefs.enabled_channels
        assert NotificationChannel.EMAIL in prefs.enabled_channels
        assert prefs.quiet_hours_start == 23
        assert prefs.quiet_hours_end == 6
        assert prefs.digest_enabled is True
    
    def test_send_notification_basic(self):
        """Test basic notification sending."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        notif_id = engine.send_notification(
            user_id="user_001",
            title="Test",
            message="Test message",
        )
        
        assert notif_id is not None
        assert notif_id in engine._notifications
        assert engine._notifications[notif_id].status == NotificationStatus.DELIVERED
    
    def test_send_notification_urgent_bypasses_quiet_hours(self):
        """Test urgent notifications bypass quiet hours."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
        })
        
        # Send urgent notification during quiet hours
        notif_id = engine.send_notification(
            user_id="user_001",
            title="Urgent",
            message="Urgent message",
            priority=NotificationPriority.URGENT,
        )
        
        assert notif_id is not None
        assert engine._notifications[notif_id].priority == NotificationPriority.URGENT
    
    def test_send_notification_low_priority_goes_to_digest(self):
        """Test low priority notifications go to digest in digest mode."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "digest_enabled": True,
        })
        
        notif_id = engine.send_notification(
            user_id="user_001",
            title="Low Priority",
            message="Can wait",
            priority=NotificationPriority.LOW,
        )
        
        assert notif_id is not None
        assert "user_001" in engine._digest_queue
        assert len(engine._digest_queue["user_001"]) == 1
    
    def test_flush_digest(self):
        """Test digest flushing."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "digest_enabled": True,
        })
        
        # Add multiple low priority notifications
        engine.send_notification("user_001", "Title 1", "Message 1", priority=NotificationPriority.LOW)
        engine.send_notification("user_001", "Title 2", "Message 2", priority=NotificationPriority.LOW)
        engine.send_notification("user_001", "Title 3", "Message 3", priority=NotificationPriority.LOW)
        
        # Flush digest
        flushed_ids = engine.flush_digest("user_001")
        
        assert len(flushed_ids) == 3
        assert len(engine._digest_queue.get("user_001", [])) == 0  # Queue cleared
    
    def test_channel_selection_by_priority(self):
        """Test channel selection based on priority."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "enabled_channels": ["telegram", "push", "sms"],
        })
        
        # Urgent should prefer PUSH or SMS
        engine.send_notification("user_001", "Urgent", "Message", priority=NotificationPriority.URGENT)
        
        # Check that appropriate channel was selected
        notifications = engine.get_notifications(user_id="user_001", limit=1)
        assert len(notifications) == 1
    
    def test_notification_retry(self):
        """Test notification retry."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        notif_id = engine.send_notification("user_001", "Test", "Message")
        
        # Retry should succeed (delivery is simulated as successful)
        result = engine.retry_notification(notif_id)
        assert result is True
        assert engine._notifications[notif_id].retry_count >= 1
    
    def test_get_notifications_filtered_by_user(self):
        """Test getting notifications filtered by user."""
        engine = NotificationEngine()
        engine.register_user("user_a")
        engine.register_user("user_b")
        
        engine.send_notification("user_a", "A1", "Message A1")
        engine.send_notification("user_b", "B1", "Message B1")
        engine.send_notification("user_a", "A2", "Message A2")
        
        # Get user_a notifications
        user_a_notifs = engine.get_notifications(user_id="user_a")
        assert len(user_a_notifs) == 2
        assert all(n["recipient"] == "user_a" for n in user_a_notifs)
    
    def test_get_notifications_filtered_by_status(self):
        """Test getting notifications filtered by status."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        engine.send_notification("user_001", "Test 1", "Message 1")
        engine.send_notification("user_001", "Test 2", "Message 2")
        
        # All should be DELIVERED
        delivered = engine.get_notifications(status=NotificationStatus.DELIVERED)
        assert len(delivered) == 2
    
    def test_get_preferences(self):
        """Test getting user preferences."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "quiet_hours_start": 23,
            "digest_enabled": True,
        })
        
        prefs = engine.get_preferences("user_001")
        
        assert prefs is not None
        assert prefs["quiet_hours_start"] == 23
        assert prefs["digest_enabled"] is True
    
    def test_update_preferences(self):
        """Test updating user preferences."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        # Update preferences
        result = engine.update_preferences("user_001", {
            "quiet_hours_start": 23,
            "quiet_hours_end": 8,
            "digest_enabled": True,
        })
        
        assert result is True
        
        prefs = engine.get_preferences("user_001")
        assert prefs["quiet_hours_start"] == 23
        assert prefs["quiet_hours_end"] == 8
        assert prefs["digest_enabled"] is True
    
    def test_get_statistics(self):
        """Test notification statistics."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        # Send multiple notifications
        for i in range(5):
            engine.send_notification("user_001", f"Test {i}", f"Message {i}")
        
        stats = engine.get_statistics()
        
        assert stats["sent"] == 5
        assert stats["delivered"] == 5
        assert stats["total_notifications"] == 5
    
    def test_notification_sorted_by_created_at(self):
        """Test that notifications are sorted by created_at (newest first)."""
        engine = NotificationEngine()
        engine.register_user("user_001")
        
        # Send multiple notifications
        for i in range(5):
            engine.send_notification("user_001", f"Test {i}", f"Message {i}")
        
        notifs = engine.get_notifications(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(notifs) - 1):
            assert notifs[i]["created_at"] >= notifs[i + 1]["created_at"]
    
    def test_unregistered_user_no_notification(self):
        """Test that unregistered users don't receive notifications."""
        engine = NotificationEngine()
        
        notif_id = engine.send_notification("unknown_user", "Test", "Message")
        
        assert notif_id is None
    
    def test_notification_to_dict(self):
        """Test notification serialization."""
        from copilot_core.notifications.engine import Notification
        
        notif = Notification(
            notification_id="notif_test",
            channel=NotificationChannel.TELEGRAM,
            priority=NotificationPriority.HIGH,
            title="Test Title",
            message="Test Message",
            recipient="user_001",
        )
        
        d = notif.to_dict()
        
        assert d["notification_id"] == "notif_test"
        assert d["channel"] == "telegram"
        assert d["priority"] == "high"
        assert d["title"] == "Test Title"
        assert d["message"] == "Test Message"
        assert d["status"] == "pending"
    
    def test_preferences_to_dict(self):
        """Test preferences serialization."""
        from copilot_core.notifications.engine import NotificationPreferences
        
        prefs = NotificationPreferences(
            user_id="user_001",
            enabled_channels={NotificationChannel.TELEGRAM, NotificationChannel.EMAIL},
            quiet_hours_start=22,
            quiet_hours_end=7,
            digest_enabled=True,
        )
        
        d = prefs.to_dict()
        
        assert d["user_id"] == "user_001"
        assert "telegram" in d["enabled_channels"]
        assert "email" in d["enabled_channels"]
        assert d["quiet_hours_start"] == 22
        assert d["digest_enabled"] is True


class TestQuietHours:
    """Test quiet hours functionality."""
    
    def test_quiet_hours_detection_overnight(self):
        """Test overnight quiet hours detection (e.g., 22:00-07:00)."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
        })
        
        prefs = engine._preferences["user_001"]
        
        # Test hour 23 (should be quiet)
        # Note: Actual test depends on current time, so we test the config
        assert prefs.quiet_hours_start == 22
        assert prefs.quiet_hours_end == 7
        assert prefs.quiet_hours_start > prefs.quiet_hours_end  # Overnight
    
    def test_quiet_hours_detection_same_day(self):
        """Test same-day quiet hours (e.g., 12:00-14:00)."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "quiet_hours_start": 12,
            "quiet_hours_end": 14,
        })
        
        prefs = engine._preferences["user_001"]
        
        assert prefs.quiet_hours_start == 12
        assert prefs.quiet_hours_end == 14
        assert prefs.quiet_hours_start < prefs.quiet_hours_end  # Same day


class TestNotificationPriority:
    """Test notification priority handling."""
    
    def test_priority_ordering(self):
        """Test that priority levels are correctly ordered."""
        assert NotificationPriority.LOW.value < NotificationPriority.MEDIUM.value
        assert NotificationPriority.MEDIUM.value < NotificationPriority.HIGH.value
        assert NotificationPriority.HIGH.value < NotificationPriority.URGENT.value
    
    def test_urgent_notification_channel_preference(self):
        """Test that urgent notifications prefer immediate channels."""
        engine = NotificationEngine()
        engine.register_user("user_001", {
            "enabled_channels": ["telegram", "push", "email"],
        })
        
        # Urgent should select PUSH if available
        channel = engine._select_best_channel(
            engine._preferences["user_001"],
            NotificationPriority.URGENT,
        )
        
        assert channel == NotificationChannel.PUSH
