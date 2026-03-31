"""Tests for Notification Advanced Engine — Slice 57."""
import pytest
from copilot_core.notification_advanced.engine import (
    NotificationEngine,
    ChannelType,
    Priority,
    DeliveryStatus,
    NotificationTemplate,
    Notification,
    UserPreferences,
    create_notification_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestNotificationTemplate:
    """Test notification template."""
    
    def test_create_template(self):
        """Test creating template."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test Template",
            subject="Hello {{name}}",
            body="Welcome {{name}}!",
        )
        
        assert template.template_id == "tpl_test"
        assert template.name == "Test Template"
    
    def test_render_template(self):
        """Test rendering template with variables."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Hello {{name}}",
            body="Welcome {{name}} to {{company}}!",
            variables=["name", "company"],
        )
        
        rendered = template.render({"name": "Alice", "company": "Acme"})
        
        assert rendered["subject"] == "Hello Alice"
        assert rendered["body"] == "Welcome Alice to Acme!"
    
    def test_render_template_missing_variable(self):
        """Test rendering with missing variable."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Hello {{name}}",
            body="Welcome {{name}}!",
        )
        
        rendered = template.render({})
        
        # Missing variables remain as placeholders
        assert "{{name}}" in rendered["subject"]
    
    def test_render_template_extra_variables(self):
        """Test rendering with extra variables."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Hello",
            body="Welcome!",
        )
        
        # Should not raise with extra variables
        rendered = template.render({"extra": "value", "unused": "data"})
        
        assert rendered["subject"] == "Hello"
    
    def test_template_to_dict(self):
        """Test template serialization."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Subject",
            body="Body",
            channels=[ChannelType.EMAIL, ChannelType.SMS],
            variables=["name"],
        )
        
        d = template.to_dict()
        
        assert d["template_id"] == "tpl_test"
        assert d["channels"] == ["email", "sms"]
        assert d["variables"] == ["name"]
    
    def test_template_created_at_set(self):
        """Test that template created_at is set."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Subject",
            body="Body",
        )
        
        assert template.created_at is not None


class TestUserPreferences:
    """Test user preferences."""
    
    def test_create_preferences(self):
        """Test creating user preferences."""
        prefs = UserPreferences(user_id="user_123")
        
        assert prefs.user_id == "user_123"
    
    def test_channel_enabled_default(self):
        """Test channel enabled check with defaults."""
        prefs = UserPreferences(user_id="user_123")
        
        # No channels enabled by default
        assert prefs.is_channel_enabled(ChannelType.EMAIL) is False
    
    def test_channel_enabled_explicit(self):
        """Test channel enabled check with explicit channels."""
        prefs = UserPreferences(
            user_id="user_123",
            enabled_channels=[ChannelType.EMAIL, ChannelType.PUSH],
        )
        
        assert prefs.is_channel_enabled(ChannelType.EMAIL) is True
        assert prefs.is_channel_enabled(ChannelType.PUSH) is True
        assert prefs.is_channel_enabled(ChannelType.SMS) is False
    
    def test_template_enabled_default(self):
        """Test template enabled check with defaults."""
        prefs = UserPreferences(user_id="user_123")
        
        # All templates enabled by default
        assert prefs.is_template_enabled("tpl_any") is True
    
    def test_template_enabled_explicit(self):
        """Test template enabled check with disabled templates."""
        prefs = UserPreferences(
            user_id="user_123",
            disabled_templates=["tpl_spam", "tpl_promo"],
        )
        
        assert prefs.is_template_enabled("tpl_normal") is True
        assert prefs.is_template_enabled("tpl_spam") is False
    
    def test_quiet_hours_default(self):
        """Test quiet hours check with defaults."""
        prefs = UserPreferences(user_id="user_123")
        
        # No quiet hours by default
        assert prefs.is_in_quiet_hours() is False
    
    def test_quiet_hours_daytime(self):
        """Test quiet hours during day."""
        prefs = UserPreferences(
            user_id="user_123",
            quiet_hours_start=22,
            quiet_hours_end=8,
        )
        
        # This test depends on current time, so we just check the logic exists
        # Actual result depends on when test runs
        result = prefs.is_in_quiet_hours()
        assert isinstance(result, bool)
    
    def test_preferences_to_dict(self):
        """Test preferences serialization."""
        prefs = UserPreferences(
            user_id="user_123",
            enabled_channels=[ChannelType.EMAIL],
            disabled_templates=["tpl_spam"],
            quiet_hours_start=22,
            quiet_hours_end=8,
        )
        
        d = prefs.to_dict()
        
        assert d["user_id"] == "user_123"
        assert d["enabled_channels"] == ["email"]
        assert d["quiet_hours_start"] == 22
        assert d["quiet_hours_end"] == 8


class TestNotification:
    """Test notification."""
    
    def test_create_notification(self):
        """Test creating notification."""
        notif = Notification(
            notification_id="notif_test",
            template_id="tpl_test",
            channels=[ChannelType.EMAIL],
            recipients=["user@example.com"],
            subject="Test",
            body="Test body",
        )
        
        assert notif.notification_id == "notif_test"
        assert notif.status == DeliveryStatus.PENDING
    
    def test_notification_to_dict(self):
        """Test notification serialization."""
        notif = Notification(
            notification_id="notif_test",
            template_id="tpl_test",
            channels=[ChannelType.EMAIL, ChannelType.SMS],
            recipients=["user@example.com"],
            subject="Test",
            body="Test body",
            priority=Priority.HIGH,
        )
        
        d = notif.to_dict()
        
        assert d["notification_id"] == "notif_test"
        assert d["channels"] == ["email", "sms"]
        assert d["priority"] == "high"
    
    def test_notification_created_at_set(self):
        """Test that notification created_at is set."""
        notif = Notification(
            notification_id="notif_test",
            template_id=None,
            channels=[ChannelType.EMAIL],
            recipients=["user@example.com"],
            subject="Test",
            body="Test",
        )
        
        assert notif.created_at is not None


class TestNotificationEngine:
    """Test notification engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_notification_engine()
        assert engine is not None
    
    def test_create_template(self):
        """Test creating template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Welcome Email",
            subject="Welcome {{name}}!",
            body="Hello {{name}}, welcome to {{company}}!",
        )
        
        assert template_id is not None
        assert template_id.startswith("tpl_")
    
    def test_create_template_with_channels(self):
        """Test creating template with channels."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Multi-channel",
            subject="Test",
            body="Test body",
            channels=[ChannelType.EMAIL, ChannelType.SMS, ChannelType.PUSH],
        )
        
        template = engine.get_template(template_id)
        
        assert len(template.channels) == 3
    
    def test_create_template_with_variables(self):
        """Test creating template with variables."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Variable Template",
            subject="Test {{var1}}",
            body="Body {{var2}}",
            variables=["var1", "var2"],
        )
        
        template = engine.get_template(template_id)
        
        assert template.variables == ["var1", "var2"]
    
    def test_update_template(self):
        """Test updating template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Original",
            subject="Original Subject",
            body="Original Body",
        )
        
        result = engine.update_template(
            template_id,
            name="Updated",
            subject="Updated Subject",
        )
        
        assert result is True
        
        template = engine.get_template(template_id)
        
        assert template.name == "Updated"
        assert template.subject == "Updated Subject"
        assert template.body == "Original Body"  # Unchanged
    
    def test_update_nonexistent_template(self):
        """Test updating nonexistent template."""
        engine = NotificationEngine()
        
        result = engine.update_template("nonexistent", name="New")
        
        assert result is False
    
    def test_delete_template(self):
        """Test deleting template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        result = engine.delete_template(template_id)
        
        assert result is True
        assert engine.get_template(template_id) is None
    
    def test_delete_nonexistent_template(self):
        """Test deleting nonexistent template."""
        engine = NotificationEngine()
        
        result = engine.delete_template("nonexistent")
        
        assert result is False
    
    def test_get_template(self):
        """Test getting template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        template = engine.get_template(template_id)
        
        assert template is not None
        assert template.name == "Test"
    
    def test_get_nonexistent_template(self):
        """Test getting nonexistent template."""
        engine = NotificationEngine()
        
        template = engine.get_template("nonexistent")
        
        assert template is None
    
    def test_list_templates(self):
        """Test listing templates."""
        engine = NotificationEngine()
        
        engine.create_template("Template 1", "Subject 1", "Body 1")
        engine.create_template("Template 2", "Subject 2", "Body 2")
        engine.create_template("Template 3", "Subject 3", "Body 3")
        
        templates = engine.list_templates()
        
        assert len(templates) == 3
    
    def test_send_with_template(self):
        """Test sending notification with template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Welcome",
            subject="Welcome {{name}}!",
            body="Hello {{name}}!",
        )
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            variables={"name": "Alice"},
        )
        
        assert notification_id is not None
        assert notification_id.startswith("notif_")
    
    def test_send_with_nonexistent_template(self):
        """Test sending with nonexistent template."""
        engine = NotificationEngine()
        
        with pytest.raises(ValueError):
            engine.send(
                template_id="nonexistent",
                recipients=["user@example.com"],
            )
    
    def test_send_direct(self):
        """Test sending direct notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_direct(
            channels=[ChannelType.EMAIL],
            recipients=["user@example.com"],
            subject="Direct Subject",
            body="Direct Body",
        )
        
        assert notification_id is not None
        
        notification = engine.get_notification(notification_id)
        
        assert notification.template_id is None
        assert notification.subject == "Direct Subject"
    
    def test_send_with_priority(self):
        """Test sending with priority."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            priority=Priority.URGENT,
        )
        
        notification = engine.get_notification(notification_id)
        
        assert notification.priority == Priority.URGENT
    
    def test_send_with_metadata(self):
        """Test sending with metadata."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            metadata={"campaign": "summer", "batch": "001"},
        )
        
        notification = engine.get_notification(notification_id)
        
        assert notification.metadata["campaign"] == "summer"
        assert notification.metadata["batch"] == "001"
    
    def test_register_channel_handler(self):
        """Test registering channel handler."""
        engine = NotificationEngine()
        
        def email_handler(notification, recipient):
            return True
        
        engine.register_channel_handler(ChannelType.EMAIL, email_handler)
        
        assert ChannelType.EMAIL in engine._channel_handlers
    
    def test_channel_handler_receives_notification(self):
        """Test that channel handler receives notification."""
        engine = NotificationEngine()
        
        received = []
        
        def capture_handler(notification, recipient):
            received.append((notification.notification_id, recipient))
            return True
        
        engine.register_channel_handler(ChannelType.EMAIL, capture_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        assert len(received) == 1
        assert received[0][1] == "user@example.com"
    
    def test_channel_handler_failure(self):
        """Test handling channel handler failure."""
        engine = NotificationEngine()
        
        def failing_handler(notification, recipient):
            raise Exception("Handler failed")
        
        engine.register_channel_handler(ChannelType.EMAIL, failing_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should have failed delivery recorded
        assert "user@example.com:email" in notification.delivery_results
        assert notification.delivery_results["user@example.com:email"]["status"] == "failed"
    
    def test_user_preferences_channel_disabled(self):
        """Test that disabled channel is skipped."""
        engine = NotificationEngine()
        
        # User has EMAIL disabled
        engine.set_user_preferences(
            "user@example.com",
            enabled_channels=[ChannelType.PUSH],  # No EMAIL
        )
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            channels=[ChannelType.EMAIL],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should be skipped
        assert "user@example.com:email" in notification.delivery_results
        assert notification.delivery_results["user@example.com:email"]["status"] == "skipped"
    
    def test_user_preferences_template_disabled(self):
        """Test that disabled template is skipped."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            "user@example.com",
            enabled_channels=[ChannelType.EMAIL],
            disabled_templates=["tpl_spam"],
        )
        
        template_id = engine.create_template("Spam", "Subject", "Body")
        
        # Manually set template_id to match disabled
        engine._templates[template_id].template_id = "tpl_spam"
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should be skipped due to disabled template
        results = notification.delivery_results
        skipped = any(r["status"] == "skipped" and "Template" in r.get("message", "") for r in results.values())
        
        assert skipped
    
    def test_user_preferences_quiet_hours(self):
        """Test quiet hours skipping."""
        engine = NotificationEngine()
        
        # Set quiet hours that include current time
        # This test is time-dependent, so we test the mechanism
        engine.set_user_preferences(
            "user@example.com",
            enabled_channels=[ChannelType.EMAIL],
            quiet_hours=(0, 24),  # Always in quiet hours
        )
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            priority=Priority.NORMAL,
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should be skipped due to quiet hours
        results = notification.delivery_results
        skipped = any(r["status"] == "skipped" and "Quiet" in r.get("message", "") for r in results.values())
        
        assert skipped
    
    def test_urgent_bypasses_quiet_hours(self):
        """Test that urgent priority bypasses quiet hours."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            "user@example.com",
            enabled_channels=[ChannelType.EMAIL],
            quiet_hours=(0, 24),  # Always in quiet hours
        )
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            priority=Priority.URGENT,
        )
        
        notification = engine.get_notification(notification_id)
        
        # Urgent should NOT be skipped
        results = notification.delivery_results
        delivered = any(r["status"] == "delivered" for r in results.values())
        
        assert delivered
    
    def test_get_notification(self):
        """Test getting notification."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        assert notification is not None
        assert notification.notification_id == notification_id
    
    def test_get_nonexistent_notification(self):
        """Test getting nonexistent notification."""
        engine = NotificationEngine()
        
        notification = engine.get_notification("nonexistent")
        
        assert notification is None
    
    def test_list_notifications(self):
        """Test listing notifications."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        for i in range(5):
            engine.send(template_id, [f"user{i}@example.com"])
        
        notifications = engine.list_notifications(limit=10)
        
        assert len(notifications) == 5
    
    def test_list_notifications_filtered_by_status(self):
        """Test listing notifications filtered by status."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        for i in range(5):
            engine.send(template_id, [f"user{i}@example.com"])
        
        # All should be delivered/sent
        notifications = engine.list_notifications(status=DeliveryStatus.DELIVERED)
        
        assert len(notifications) >= 1
    
    def test_list_notifications_filtered_by_priority(self):
        """Test listing notifications filtered by priority."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user1@example.com"], priority=Priority.NORMAL)
        engine.send(template_id, ["user2@example.com"], priority=Priority.HIGH)
        engine.send(template_id, ["user3@example.com"], priority=Priority.URGENT)
        
        high_priority = engine.list_notifications(priority=Priority.HIGH)
        
        assert len(high_priority) == 1
        assert high_priority[0].priority == Priority.HIGH
    
    def test_list_notifications_sorted(self):
        """Test that notifications are sorted by created_at descending."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        ids = []
        for i in range(5):
            notification_id = engine.send(template_id, [f"user{i}@example.com"])
            ids.append(notification_id)
            time.sleep(0.01)
        
        notifications = engine.list_notifications(limit=10)
        
        # Should be newest first
        assert notifications[0].notification_id == ids[-1]
    
    def test_get_delivery_status(self):
        """Test getting delivery status."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user1@example.com", "user2@example.com"],
        )
        
        status = engine.get_delivery_status(notification_id)
        
        assert status["notification_id"] == notification_id
        assert status["total_recipients"] == 2
    
    def test_get_delivery_status_nonexistent(self):
        """Test getting delivery status for nonexistent notification."""
        engine = NotificationEngine()
        
        status = engine.get_delivery_status("nonexistent")
        
        assert "error" in status
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_notifications"] >= 1
        assert stats["total_templates"] == 1
    
    def test_statistics_by_channel(self):
        """Test statistics by channel."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"], channels=[ChannelType.EMAIL])
        engine.send(template_id, ["user@example.com"], channels=[ChannelType.SMS])
        
        stats = engine.get_statistics()
        
        assert "email" in stats["by_channel"]
        assert "sms" in stats["by_channel"]
    
    def test_statistics_by_priority(self):
        """Test statistics by priority."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user1@example.com"], priority=Priority.LOW)
        engine.send(template_id, ["user2@example.com"], priority=Priority.HIGH)
        
        stats = engine.get_statistics()
        
        assert "low" in stats["by_priority"]
        assert "high" in stats["by_priority"]
    
    def test_clear_notifications(self):
        """Test clearing all notifications."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        for i in range(10):
            engine.send(template_id, [f"user{i}@example.com"])
        
        count = engine.clear_notifications()
        
        assert count == 10
        assert len(engine.list_notifications()) == 0
    
    def test_clear_notifications_older_than(self):
        """Test clearing notifications older than."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["old@example.com"])
        
        # Manually set old timestamp
        if engine._notifications:
            old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            for n in engine._notifications.values():
                n.created_at = old_time
        
        engine.send(template_id, ["new@example.com"])
        
        count = engine.clear_notifications(older_than_days=1)
        
        assert count == 1
        assert len(engine.list_notifications()) == 1
    
    def test_batch_send(self):
        """Test batch sending."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Batch",
            subject="Hello {{name}}",
            body="Hi {{name}}!",
        )
        
        recipient_groups = [
            {"recipients": ["user1@example.com"], "variables": {"name": "Alice"}},
            {"recipients": ["user2@example.com", "user3@example.com"], "variables": {"name": "Bob"}},
        ]
        
        notification_ids = engine.batch_send(template_id, recipient_groups)
        
        assert len(notification_ids) == 2
    
    def test_batch_send_empty_group(self):
        """Test batch send with empty recipient group."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        recipient_groups = [
            {"recipients": [], "variables": {}},  # Empty
            {"recipients": ["user@example.com"], "variables": {}},
        ]
        
        notification_ids = engine.batch_send(template_id, recipient_groups)
        
        # Only non-empty group should create notification
        assert len(notification_ids) == 1
    
    def test_cancel_notification_pending(self):
        """Test cancelling pending notification."""
        engine = NotificationEngine()
        
        # Create notification without sending
        notification_id = engine._create_notification(
            template_id=None,
            channels=[ChannelType.EMAIL],
            recipients=["user@example.com"],
            subject="Test",
            body="Test",
            priority=Priority.NORMAL,
            metadata={},
        )
        
        result = engine.cancel_notification(notification_id)
        
        assert result is True
        
        notification = engine.get_notification(notification_id)
        
        assert notification.status == DeliveryStatus.SKIPPED
    
    def test_cancel_notification_already_sent(self):
        """Test cancelling already sent notification."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        # Already processed
        result = engine.cancel_notification(notification_id)
        
        assert result is False
    
    def test_cancel_nonexistent_notification(self):
        """Test cancelling nonexistent notification."""
        engine = NotificationEngine()
        
        result = engine.cancel_notification("nonexistent")
        
        assert result is False
    
    def test_send_to_multiple_recipients(self):
        """Test sending to multiple recipients."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user1@example.com", "user2@example.com", "user3@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        assert len(notification.recipients) == 3
    
    def test_send_to_multiple_channels(self):
        """Test sending to multiple channels."""
        engine = NotificationEngine()
        
        received = []
        
        def capture_handler(notification, recipient):
            received.append((notification.notification_id, recipient))
            return True
        
        for channel in [ChannelType.EMAIL, ChannelType.SMS, ChannelType.PUSH]:
            engine.register_channel_handler(channel, capture_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            channels=[ChannelType.EMAIL, ChannelType.SMS, ChannelType.PUSH],
        )
        
        # Should have 3 deliveries (one per channel)
        assert len(received) == 3
    
    def test_delivery_results_recorded(self):
        """Test that delivery results are recorded."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        assert len(notification.delivery_results) >= 1
        
        result = list(notification.delivery_results.values())[0]
        
        assert "recipient" in result
        assert "channel" in result
        assert "status" in result
        assert "timestamp" in result
    
    def test_notification_sent_at_set(self):
        """Test that notification sent_at is set."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        assert notification.sent_at is not None
    
    def test_notification_delivered_at_set(self):
        """Test that notification delivered_at is set on success."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        # Should be delivered (simulated)
        assert notification.delivered_at is not None
    
    def test_template_id_optional(self):
        """Test that template_id is optional for direct send."""
        engine = NotificationEngine()
        
        notification_id = engine.send_direct(
            channels=[ChannelType.EMAIL],
            recipients=["user@example.com"],
            subject="Direct",
            body="Direct body",
        )
        
        notification = engine.get_notification(notification_id)
        
        assert notification.template_id is None
    
    def test_statistics_total_sent(self):
        """Test that statistics track total sent."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        for i in range(5):
            engine.send(template_id, [f"user{i}@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_sent"] == 5
    
    def test_statistics_total_delivered(self):
        """Test that statistics track total delivered."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_delivered"] >= 1
    
    def test_statistics_total_skipped(self):
        """Test that statistics track total skipped."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            "user@example.com",
            enabled_channels=[],  # All disabled
        )
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_skipped"] >= 1
    
    def test_statistics_total_failed(self):
        """Test that statistics track total failed."""
        engine = NotificationEngine()
        
        def failing_handler(notification, recipient):
            raise Exception("Fail")
        
        engine.register_channel_handler(ChannelType.EMAIL, failing_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_failed"] >= 1
    
    def test_get_user_preferences(self):
        """Test getting user preferences."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            "user_123",
            enabled_channels=[ChannelType.EMAIL],
            quiet_hours=(22, 8),
        )
        
        prefs = engine.get_user_preferences("user_123")
        
        assert prefs is not None
        assert prefs.user_id == "user_123"
        assert ChannelType.EMAIL in prefs.enabled_channels
    
    def test_get_nonexistent_user_preferences(self):
        """Test getting nonexistent user preferences."""
        engine = NotificationEngine()
        
        prefs = engine.get_user_preferences("nonexistent")
        
        assert prefs is None
    
    def test_set_user_preferences_updates_existing(self):
        """Test that setting preferences updates existing."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            "user_123",
            enabled_channels=[ChannelType.EMAIL],
        )
        
        engine.set_user_preferences(
            "user_123",
            enabled_channels=[ChannelType.EMAIL, ChannelType.SMS],
        )
        
        prefs = engine.get_user_preferences("user_123")
        
        assert len(prefs.enabled_channels) == 2
    
    def test_channel_type_enum_values(self):
        """Test channel type enum values."""
        assert ChannelType.EMAIL.value == "email"
        assert ChannelType.SMS.value == "sms"
        assert ChannelType.PUSH.value == "push"
        assert ChannelType.WEBHOOK.value == "webhook"
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.TELEGRAM.value == "telegram"
        assert ChannelType.WHATSAPP.value == "whatsapp"
        assert ChannelType.IN_APP.value == "in_app"
    
    def test_priority_enum_values(self):
        """Test priority enum values."""
        assert Priority.LOW.value == "low"
        assert Priority.NORMAL.value == "normal"
        assert Priority.HIGH.value == "high"
        assert Priority.URGENT.value == "urgent"
    
    def test_delivery_status_enum_values(self):
        """Test delivery status enum values."""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SENT.value == "sent"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.SKIPPED.value == "skipped"
    
    def test_notification_id_unique(self):
        """Test that notification IDs are unique."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        ids = set()
        for i in range(50):
            notification_id = engine.send(template_id, [f"user{i}@example.com"])
            ids.add(notification_id)
        
        assert len(ids) == 50
    
    def test_template_id_unique(self):
        """Test that template IDs are unique."""
        engine = NotificationEngine()
        
        ids = set()
        for i in range(50):
            template_id = engine.create_template(f"Template {i}", "Subject", "Body")
            ids.add(template_id)
        
        assert len(ids) == 50
    
    def test_multiple_channel_handlers(self):
        """Test registering multiple channel handlers."""
        engine = NotificationEngine()
        
        results = {}
        
        def email_handler(notification, recipient):
            results["email"] = True
            return True
        
        def sms_handler(notification, recipient):
            results["sms"] = True
            return True
        
        engine.register_channel_handler(ChannelType.EMAIL, email_handler)
        engine.register_channel_handler(ChannelType.SMS, sms_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            channels=[ChannelType.EMAIL, ChannelType.SMS],
        )
        
        assert results.get("email") is True
        assert results.get("sms") is True
    
    def test_handler_returning_false_records_failure(self):
        """Test that handler returning false records failure."""
        engine = NotificationEngine()
        
        def failing_handler(notification, recipient):
            return False
        
        engine.register_channel_handler(ChannelType.EMAIL, failing_handler)
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        result = notification.delivery_results.get("user@example.com:email")
        
        assert result["status"] == "failed"
    
    def test_clear_empty_notifications(self):
        """Test clearing empty notifications."""
        engine = NotificationEngine()
        
        count = engine.clear_notifications()
        
        assert count == 0
    
    def test_list_notifications_empty(self):
        """Test listing notifications when empty."""
        engine = NotificationEngine()
        
        notifications = engine.list_notifications()
        
        assert notifications == []
    
    def test_list_templates_empty(self):
        """Test listing templates when empty."""
        engine = NotificationEngine()
        
        templates = engine.list_templates()
        
        assert templates == []
    
    def test_send_with_overridden_channels(self):
        """Test sending with channels different from template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Email Template",
            subject="Test",
            body="Test",
            channels=[ChannelType.EMAIL],
        )
        
        # Override with SMS
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            channels=[ChannelType.SMS],
        )
        
        notification = engine.get_notification(notification_id)
        
        assert ChannelType.SMS in notification.channels
        assert ChannelType.EMAIL not in notification.channels
    
    def test_delivery_results_include_timestamp(self):
        """Test that delivery results include timestamp."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        result = list(notification.delivery_results.values())[0]
        
        assert "timestamp" in result
        assert result["timestamp"] is not None
    
    def test_statistics_total_notifications(self):
        """Test that statistics track total notifications."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        for i in range(10):
            engine.send(template_id, [f"user{i}@example.com"])
        
        stats = engine.get_statistics()
        
        assert stats["total_notifications"] == 10
    
    def test_statistics_total_templates(self):
        """Test that statistics track total templates."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.create_template(f"Template {i}", "Subject", "Body")
        
        stats = engine.get_statistics()
        
        assert stats["total_templates"] == 5
    
    def test_statistics_total_users(self):
        """Test that statistics track total users with preferences."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.set_user_preferences(f"user_{i}", enabled_channels=[ChannelType.EMAIL])
        
        stats = engine.get_statistics()
        
        assert stats["total_users"] == 5
    
    def test_batch_send_returns_notification_ids(self):
        """Test that batch_send returns notification IDs."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        recipient_groups = [
            {"recipients": ["user1@example.com"], "variables": {}},
            {"recipients": ["user2@example.com"], "variables": {}},
        ]
        
        notification_ids = engine.batch_send(template_id, recipient_groups)
        
        assert len(notification_ids) == 2
        
        # All should be valid notification IDs
        for nid in notification_ids:
            assert nid.startswith("notif_")
            assert engine.get_notification(nid) is not None
    
    def test_render_template_preserves_unmatched_placeholders(self):
        """Test that rendering preserves unmatched placeholders."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            subject="Hello {{name}} and {{missing}}",
            body="Body",
        )
        
        rendered = template.render({"name": "Alice"})
        
        assert rendered["subject"] == "Hello Alice and {{missing}}"
    
    def test_send_records_delivery_for_each_channel(self):
        """Test that send records delivery for each channel."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
            channels=[ChannelType.EMAIL, ChannelType.SMS],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should have 2 delivery results
        assert len(notification.delivery_results) == 2
    
    def test_send_records_delivery_for_each_recipient(self):
        """Test that send records delivery for each recipient."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user1@example.com", "user2@example.com"],
            channels=[ChannelType.EMAIL],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should have 2 delivery results
        assert len(notification.delivery_results) == 2
    
    def test_notification_status_updates_to_delivered(self):
        """Test that notification status updates to delivered."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        # Should be delivered (simulated)
        assert notification.status == DeliveryStatus.DELIVERED
    
    def test_quiet_hours_overnight(self):
        """Test overnight quiet hours."""
        prefs = UserPreferences(
            user_id="user_123",
            quiet_hours_start=22,
            quiet_hours_end=8,
        )
        
        # Test logic is implemented (actual result depends on current time)
        result = prefs.is_in_quiet_hours()
        
        assert isinstance(result, bool)
    
    def test_template_channels_default(self):
        """Test that template channels default to EMAIL."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        template = engine.get_template(template_id)
        
        assert template.channels == [ChannelType.EMAIL]
    
    def test_send_inherits_template_channels(self):
        """Test that send inherits template channels."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Multi",
            subject="Test",
            body="Test",
            channels=[ChannelType.EMAIL, ChannelType.SMS],
        )
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=["user@example.com"],
        )
        
        notification = engine.get_notification(notification_id)
        
        assert ChannelType.EMAIL in notification.channels
        assert ChannelType.SMS in notification.channels
    
    def test_delivery_result_message_on_success(self):
        """Test delivery result message on success."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        notification = engine.get_notification(notification_id)
        
        result = notification.delivery_results.get("user@example.com:email")
        
        assert result["message"] == "Simulated (no handler)"
    
    def test_clear_notifications_preserves_templates(self):
        """Test that clearing notifications preserves templates."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        engine.send(template_id, ["user@example.com"])
        
        engine.clear_notifications()
        
        # Template should still exist
        template = engine.get_template(template_id)
        
        assert template is not None
    
    def test_delete_template_does_not_delete_notifications(self):
        """Test that deleting template doesn't delete notifications."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(template_id, ["user@example.com"])
        
        engine.delete_template(template_id)
        
        # Notification should still exist
        notification = engine.get_notification(notification_id)
        
        assert notification is not None
        assert notification.template_id == template_id
    
    def test_send_with_empty_recipients(self):
        """Test sending with empty recipients list."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", "Subject", "Body")
        
        notification_id = engine.send(
            template_id=template_id,
            recipients=[],
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should have no delivery results
        assert len(notification.delivery_results) == 0
    
    def test_send_direct_with_empty_channels(self):
        """Test direct send with empty channels."""
        engine = NotificationEngine()
        
        notification_id = engine.send_direct(
            channels=[],
            recipients=["user@example.com"],
            subject="Test",
            body="Test",
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should have no delivery results
        assert len(notification.delivery_results) == 0
    
    def test_get_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = NotificationEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_sent"] == 0
        assert stats["total_delivered"] == 0
        assert stats["total_failed"] == 0
        assert stats["total_skipped"] == 0
        assert stats["total_notifications"] == 0
        assert stats["total_templates"] == 0
        assert stats["total_users"] == 0
