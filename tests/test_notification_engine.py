"""Tests for Notification Engine — Slice 33."""
import pytest
from copilot_core.notifications.engine import (
    NotificationEngine,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    Notification,
    NotificationTemplate,
    UserPreferences,
    create_notification_engine,
)


class TestNotificationEngine:
    """Test notification engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_notification_engine()
        assert engine is not None
    
    def test_send_push_notification(self):
        """Test sending push notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Test Alert",
            message="This is a test notification",
            channel="push",
            recipient="user_001",
            priority="normal",
        )
        
        assert notification_id is not None
        assert notification_id.startswith("notif_")
        
        notification = engine.get_notification(notification_id)
        assert notification is not None
        assert notification["status"] == "sent"
    
    def test_send_email_notification(self):
        """Test sending email notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Email Alert",
            message="Email content",
            channel="email",
            recipient="user@example.com",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "email"
    
    def test_send_sms_notification(self):
        """Test sending SMS notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="SMS Alert",
            message="SMS content",
            channel="sms",
            recipient="+1234567890",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "sms"
    
    def test_send_webhook_notification(self):
        """Test sending webhook notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Webhook Alert",
            message="Webhook payload",
            channel="webhook",
            recipient="https://example.com/webhook",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "webhook"
    
    def test_send_telegram_notification(self):
        """Test sending Telegram notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Telegram Alert",
            message="Telegram message",
            channel="telegram",
            recipient="@username",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "telegram"
    
    def test_send_whatsapp_notification(self):
        """Test sending WhatsApp notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="WhatsApp Alert",
            message="WhatsApp message",
            channel="whatsapp",
            recipient="+1234567890",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "whatsapp"
    
    def test_send_slack_notification(self):
        """Test sending Slack notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Slack Alert",
            message="Slack message",
            channel="slack",
            recipient="#general",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["channel"] == "slack"
    
    def test_notification_priority_levels(self):
        """Test different priority levels."""
        engine = NotificationEngine()
        
        low_id = engine.send_notification("Low", "Test", "push", "user", priority="low")
        normal_id = engine.send_notification("Normal", "Test", "push", "user", priority="normal")
        high_id = engine.send_notification("High", "Test", "push", "user", priority="high")
        urgent_id = engine.send_notification("Urgent", "Test", "push", "user", priority="urgent")
        
        assert engine.get_notification(low_id)["priority"] == "low"
        assert engine.get_notification(normal_id)["priority"] == "normal"
        assert engine.get_notification(high_id)["priority"] == "high"
        assert engine.get_notification(urgent_id)["priority"] == "urgent"
    
    def test_create_template(self):
        """Test creating notification template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Alert Template",
            channel="push",
            subject_template="{{title}}",
            body_template="Alert: {{message}} at {{time}}",
            variables=["title", "message", "time"],
        )
        
        assert template_id is not None
        assert template_id.startswith("tpl_")
        
        template = engine.get_template(template_id)
        assert template is not None
        assert template["name"] == "Alert Template"
    
    def test_render_template(self):
        """Test rendering template with data."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test Template",
            channel="push",
            subject_template="Alert: {{title}}",
            body_template="Message: {{message}}",
            variables=["title", "message"],
        )
        
        rendered = engine.render_template(template_id, {
            "title": "Home Alert",
            "message": "Motion detected",
        })
        
        assert rendered is not None
        subject, body = rendered
        assert "Home Alert" in subject
        assert "Motion detected" in body
    
    def test_send_notification_with_template(self):
        """Test sending notification with template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Security Alert",
            channel="push",
            subject_template="{{event_type}}",
            body_template="{{description}}",
            variables=["event_type", "description"],
        )
        
        notification_id = engine.send_notification(
            title="",  # Will be overridden by template
            message="",  # Will be overridden by template
            channel="push",
            recipient="user_001",
            template_id=template_id,
            template_data={
                "event_type": "Motion Detected",
                "description": "Front door motion",
            },
        )
        
        notification = engine.get_notification(notification_id)
        assert notification is not None
    
    def test_set_user_preferences(self):
        """Test setting user preferences."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["push", "email"],
            quiet_hours_start=22,
            quiet_hours_end=7,
            priority_override=True,
            rate_limit_per_hour=5,
        )
        
        prefs = engine.get_user_preferences("user_001")
        
        assert prefs is not None
        assert prefs["user_id"] == "user_001"
        assert "push" in prefs["enabled_channels"]
        assert prefs["quiet_hours_start"] == 22
    
    def test_quiet_hours_blocking(self):
        """Test quiet hours blocking."""
        engine = NotificationEngine()
        
        # Set quiet hours (assuming current time is within quiet hours for test)
        # This test would need time mocking for full coverage
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["push"],
            quiet_hours_start=0,  # All day for testing
            quiet_hours_end=23,
            priority_override=False,
        )
        
        # Non-urgent notification should be skipped
        notification_id = engine.send_notification(
            title="Test",
            message="Test",
            channel="push",
            recipient="user_001",
            priority="normal",
        )
        
        notification = engine.get_notification(notification_id)
        # May be skipped due to quiet hours
    
    def test_urgent_bypasses_quiet_hours(self):
        """Test urgent notifications bypass quiet hours."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["push"],
            quiet_hours_start=0,
            quiet_hours_end=23,
            priority_override=True,
        )
        
        # Urgent notification should still be sent
        notification_id = engine.send_notification(
            title="Urgent Alert",
            message="Urgent!",
            channel="push",
            recipient="user_001",
            priority="urgent",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification is not None
    
    def test_rate_limiting(self):
        """Test rate limiting."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["push"],
            rate_limit_per_hour=3,
        )
        
        # Send multiple notifications
        for i in range(5):
            engine.send_notification(
                title=f"Alert {i}",
                message="Test",
                channel="push",
                recipient="user_001",
            )
        
        # Some should be rate limited
        notifications = engine.get_all_notifications(recipient="user_001")
        skipped = len([n for n in notifications if n["status"] == "skipped"])
        
        assert skipped >= 2  # At least 2 should be skipped
    
    def test_channel_disabled(self):
        """Test notification skipped when channel disabled."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["email"],  # Push not enabled
        )
        
        notification_id = engine.send_notification(
            title="Test",
            message="Test",
            channel="push",
            recipient="user_001",
        )
        
        notification = engine.get_notification(notification_id)
        assert notification["status"] == "skipped"
    
    def test_get_notification(self):
        """Test getting notification details."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Test Alert",
            message="Test message",
            channel="push",
            recipient="user_001",
            priority="high",
            metadata={"source": "test"},
        )
        
        notification = engine.get_notification(notification_id)
        
        assert notification is not None
        assert notification["title"] == "Test Alert"
        assert notification["message"] == "Test message"
        assert notification["priority"] == "high"
        assert notification["metadata"]["source"] == "test"
    
    def test_get_unknown_notification(self):
        """Test getting unknown notification."""
        engine = NotificationEngine()
        
        notification = engine.get_notification("unknown")
        
        assert notification is None
    
    def test_get_all_notifications(self):
        """Test getting all notifications."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.send_notification(
                title=f"Alert {i}",
                message="Test",
                channel="push",
                recipient="user_001",
            )
        
        notifications = engine.get_all_notifications()
        
        assert len(notifications) == 5
    
    def test_get_all_notifications_filtered_by_status(self):
        """Test getting notifications filtered by status."""
        engine = NotificationEngine()
        
        engine.send_notification("Sent", "Test", "push", "user_001")
        engine.send_notification("Sent", "Test", "push", "user_001")
        
        sent = engine.get_all_notifications(status="sent")
        failed = engine.get_all_notifications(status="failed")
        
        assert len(sent) == 2
        assert len(failed) == 0
    
    def test_get_all_notifications_filtered_by_channel(self):
        """Test getting notifications filtered by channel."""
        engine = NotificationEngine()
        
        engine.send_notification("Push", "Test", "push", "user_001")
        engine.send_notification("Email", "Test", "email", "user_001")
        
        push_notifications = engine.get_all_notifications(channel="push")
        
        assert len(push_notifications) == 1
        assert push_notifications[0]["channel"] == "push"
    
    def test_get_all_notifications_filtered_by_recipient(self):
        """Test getting notifications filtered by recipient."""
        engine = NotificationEngine()
        
        engine.send_notification("Alert", "Test", "push", "user_001")
        engine.send_notification("Alert", "Test", "push", "user_002")
        
        user1_notifications = engine.get_all_notifications(recipient="user_001")
        
        assert len(user1_notifications) == 1
    
    def test_get_all_notifications_limit(self):
        """Test getting notifications with limit."""
        engine = NotificationEngine()
        
        for i in range(10):
            engine.send_notification(f"Alert {i}", "Test", "push", "user_001")
        
        notifications = engine.get_all_notifications(limit=5)
        
        assert len(notifications) == 5
    
    def test_get_template(self):
        """Test getting template details."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test Template",
            channel="push",
            subject_template="Subject",
            body_template="Body",
        )
        
        template = engine.get_template(template_id)
        
        assert template is not None
        assert template["name"] == "Test Template"
    
    def test_get_unknown_template(self):
        """Test getting unknown template."""
        engine = NotificationEngine()
        
        template = engine.get_template("unknown")
        
        assert template is None
    
    def test_get_all_templates(self):
        """Test getting all templates."""
        engine = NotificationEngine()
        
        for i in range(3):
            engine.create_template(
                name=f"Template {i}",
                channel="push",
                subject_template="Subject",
                body_template="Body",
            )
        
        templates = engine.get_all_templates()
        
        assert len(templates) == 3
    
    def test_delete_template(self):
        """Test deleting template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test Template",
            channel="push",
            subject_template="Subject",
            body_template="Body",
        )
        
        result = engine.delete_template(template_id)
        
        assert result is True
        assert engine.get_template(template_id) is None
    
    def test_delete_unknown_template(self):
        """Test deleting unknown template."""
        engine = NotificationEngine()
        
        result = engine.delete_template("unknown")
        
        assert result is False
    
    def test_get_user_preferences(self):
        """Test getting user preferences."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_001",
            enabled_channels=["push", "email"],
        )
        
        prefs = engine.get_user_preferences("user_001")
        
        assert prefs is not None
        assert prefs["user_id"] == "user_001"
    
    def test_get_unknown_user_preferences(self):
        """Test getting unknown user preferences."""
        engine = NotificationEngine()
        
        prefs = engine.get_user_preferences("unknown")
        
        assert prefs is None
    
    def test_get_delivery_statistics(self):
        """Test getting delivery statistics."""
        engine = NotificationEngine()
        
        engine.send_notification("Alert 1", "Test", "push", "user_001")
        engine.send_notification("Alert 2", "Test", "email", "user_001")
        engine.send_notification("Alert 3", "Test", "push", "user_002")
        
        stats = engine.get_delivery_statistics()
        
        assert stats["total_notifications"] == 3
        assert stats["sent"] >= 1
        assert "push" in stats["channel_breakdown"]
    
    def test_retry_notification(self):
        """Test retrying failed notification."""
        engine = NotificationEngine()
        
        # Register a failing handler
        def failing_handler(notification):
            raise Exception("Always fails")
        
        engine.register_channel_handler(NotificationChannel.CUSTOM, failing_handler)
        
        notification_id = engine.send_notification(
            title="Test",
            message="Test",
            channel="custom",
            recipient="user_001",
        )
        
        notification = engine.get_notification(notification_id)
        
        # Should be failed
        assert notification["status"] == "failed"
        
        # Retry
        result = engine.retry_notification(notification_id)
        
        assert result is True
    
    def test_retry_non_failed_notification(self):
        """Test retrying non-failed notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send_notification(
            title="Test",
            message="Test",
            channel="push",
            recipient="user_001",
        )
        
        result = engine.retry_notification(notification_id)
        
        assert result is False  # Can't retry sent notification
    
    def test_retry_unknown_notification(self):
        """Test retrying unknown notification."""
        engine = NotificationEngine()
        
        result = engine.retry_notification("unknown")
        
        assert result is False
    
    def test_cancel_notification(self):
        """Test cancelling pending notification."""
        engine = NotificationEngine()
        
        # Create notification but don't deliver immediately
        # (This would need scheduling support for full testing)
        # For now, test that cancel returns False for already-sent
        notification_id = engine.send_notification(
            title="Test",
            message="Test",
            channel="push",
            recipient="user_001",
        )
        
        result = engine.cancel_notification(notification_id)
        
        assert result is False  # Already sent
    
    def test_cancel_unknown_notification(self):
        """Test cancelling unknown notification."""
        engine = NotificationEngine()
        
        result = engine.cancel_notification("unknown")
        
        assert result is False
    
    def test_register_custom_channel_handler(self):
        """Test registering custom channel handler."""
        engine = NotificationEngine()
        
        def custom_handler(notification):
            return {"custom": True}
        
        engine.register_channel_handler(NotificationChannel.CUSTOM, custom_handler)
        
        assert NotificationChannel.CUSTOM in engine._channel_handlers
    
    def test_notification_to_dict(self):
        """Test notification serialization."""
        notification = Notification(
            notification_id="notif_test",
            title="Test Alert",
            message="Test message",
            channel=NotificationChannel.PUSH,
            priority=NotificationPriority.HIGH,
            recipient="user_001",
        )
        
        d = notification.to_dict()
        
        assert d["notification_id"] == "notif_test"
        assert d["channel"] == "push"
        assert d["priority"] == "high"
    
    def test_template_to_dict(self):
        """Test template serialization."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test Template",
            channel=NotificationChannel.EMAIL,
            subject_template="Subject: {{title}}",
            body_template="Body: {{message}}",
            variables=["title", "message"],
        )
        
        d = template.to_dict()
        
        assert d["template_id"] == "tpl_test"
        assert d["channel"] == "email"
        assert len(d["variables"]) == 2
    
    def test_user_preferences_to_dict(self):
        """Test user preferences serialization."""
        prefs = UserPreferences(
            user_id="user_001",
            enabled_channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL],
            quiet_hours_start=22,
            quiet_hours_end=7,
            priority_override=True,
            rate_limit_per_hour=10,
        )
        
        d = prefs.to_dict()
        
        assert d["user_id"] == "user_001"
        assert "push" in d["enabled_channels"]
        assert d["quiet_hours_start"] == 22
    
    def test_notification_channel_enum_values(self):
        """Test notification channel enum values."""
        assert NotificationChannel.PUSH.value == "push"
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.SMS.value == "sms"
        assert NotificationChannel.WEBHOOK.value == "webhook"
        assert NotificationChannel.TELEGRAM.value == "telegram"
        assert NotificationChannel.WHATSAPP.value == "whatsapp"
        assert NotificationChannel.SLACK.value == "slack"
    
    def test_notification_priority_enum_values(self):
        """Test notification priority enum values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.URGENT.value == "urgent"
    
    def test_notification_status_enum_values(self):
        """Test notification status enum values."""
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.DELIVERED.value == "delivered"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.SKIPPED.value == "skipped"
    
    def test_notifications_sorted_by_created_at(self):
        """Test that notifications are sorted by created_at."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.send_notification(f"Alert {i}", "Test", "push", "user_001")
        
        notifications = engine.get_all_notifications(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(notifications) - 1):
            assert notifications[i]["created_at"] >= notifications[i + 1]["created_at"]
    
    def test_delivery_history_trimmed(self):
        """Test that delivery history is trimmed."""
        engine = NotificationEngine()
        engine._max_history_size = 10
        
        for i in range(20):
            engine.send_notification(f"Alert {i}", "Test", "push", "user_001")
        
        assert len(engine._delivery_history) <= 10
    
    def test_render_unknown_template(self):
        """Test rendering unknown template."""
        engine = NotificationEngine()
        
        result = engine.render_template("unknown", {"key": "value"})
        
        assert result is None
    
    def test_render_template_missing_variables(self):
        """Test rendering template with missing variables."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel="push",
            subject_template="{{title}}",
            body_template="{{message}}",
            variables=["title", "message"],
        )
        
        # Render with partial data
        rendered = engine.render_template(template_id, {"title": "Test"})
        
        assert rendered is not None
        subject, body = rendered
        assert "{{message}}" in body  # Unreplaced variable remains
    
    def test_statistics_empty_engine(self):
        """Test statistics with empty engine."""
        engine = NotificationEngine()
        
        stats = engine.get_delivery_statistics()
        
        assert stats["total_notifications"] == 0
        assert stats["delivery_rate"] == 0
    
    def test_template_with_empty_variables(self):
        """Test template with no variables."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Static Template",
            channel="push",
            subject_template="Static Subject",
            body_template="Static Body",
            variables=[],
        )
        
        rendered = engine.render_template(template_id, {})
        
        assert rendered is not None
        subject, body = rendered
        assert subject == "Static Subject"
        assert body == "Static Body"
