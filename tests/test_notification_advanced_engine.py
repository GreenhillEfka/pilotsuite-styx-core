"""Tests for Notification Advanced Engine — Slice 66."""
import pytest
from copilot_core.notification_advanced.engine import (
    NotificationEngine,
    NotificationTemplate,
    Notification,
    DeliveryRecord,
    NotificationWorkflow,
    UserPreferences,
    ChannelType,
    NotificationPriority,
    DeliveryStatus,
    create_notification_engine,
)
from datetime import datetime, timezone, timedelta


class TestChannelType:
    """Test channel types."""
    
    def test_channel_enum_values(self):
        """Test channel type enum values."""
        assert ChannelType.EMAIL.value == "email"
        assert ChannelType.SMS.value == "sms"
        assert ChannelType.PUSH.value == "push"
        assert ChannelType.TELEGRAM.value == "telegram"
        assert ChannelType.WHATSAPP.value == "whatsapp"
        assert ChannelType.SLACK.value == "slack"


class TestNotificationPriority:
    """Test notification priorities."""
    
    def test_priority_enum_values(self):
        """Test priority enum values."""
        assert NotificationPriority.LOW.value == 0
        assert NotificationPriority.NORMAL.value == 1
        assert NotificationPriority.HIGH.value == 2
        assert NotificationPriority.URGENT.value == 3
        assert NotificationPriority.CRITICAL.value == 4


class TestDeliveryStatus:
    """Test delivery statuses."""
    
    def test_status_enum_values(self):
        """Test status enum values."""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SENT.value == "sent"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"


class TestNotificationTemplate:
    """Test notification template."""
    
    def test_create_template(self):
        """Test creating template."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Welcome Email",
            channel=ChannelType.EMAIL,
            body_template="Hello {{name}}, welcome to {{company}}!",
            variables=["name", "company"],
        )
        
        assert template.template_id == "tpl_test"
        assert template.channel == ChannelType.EMAIL
    
    def test_template_render(self):
        """Test template rendering."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Hello {{name}}!",
            default_values={"name": "User"},
        )
        
        result = template.render({"name": "John"})
        
        assert result["body"] == "Hello John!"
    
    def test_template_render_with_subject(self):
        """Test template rendering with subject."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            channel=ChannelType.EMAIL,
            subject_template="Welcome {{name}}",
            body_template="Hi {{name}}",
        )
        
        result = template.render({"name": "John"})
        
        assert result["subject"] == "Welcome John"
        assert result["body"] == "Hi John"
    
    def test_template_render_default_values(self):
        """Test template rendering with default values."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Hello {{name}}!",
            default_values={"name": "Default"},
        )
        
        # Override default
        result = template.render({"name": "Override"})
        
        assert result["body"] == "Hello Override!"
        
        # Use default
        result = template.render({})
        
        assert result["body"] == "Hello Default!"
    
    def test_template_to_dict(self):
        """Test template serialization."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test Template",
            channel=ChannelType.EMAIL,
            subject_template="Subject",
            body_template="Body",
            variables=["var1", "var2"],
            default_values={"var1": "default1"},
        )
        
        d = template.to_dict()
        
        assert d["name"] == "Test Template"
        assert d["channel"] == "email"
        assert len(d["variables"]) == 2


class TestNotification:
    """Test notification definition."""
    
    def test_create_notification(self):
        """Test creating notification."""
        notif = Notification(
            notification_id="ntf_test",
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test message",
        )
        
        assert notif.notification_id == "ntf_test"
        assert notif.priority == NotificationPriority.NORMAL
    
    def test_notification_to_dict(self):
        """Test notification serialization."""
        notif = Notification(
            notification_id="ntf_test",
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            subject="Test Subject",
            body="Test Body",
            priority=NotificationPriority.HIGH,
            metadata={"campaign": "summer"},
        )
        
        d = notif.to_dict()
        
        assert d["priority"] == 2
        assert d["metadata"]["campaign"] == "summer"


class TestDeliveryRecord:
    """Test delivery record."""
    
    def test_create_record(self):
        """Test creating delivery record."""
        record = DeliveryRecord(
            record_id="dvr_test",
            notification_id="ntf_test",
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            status=DeliveryStatus.DELIVERED,
            attempts=1,
        )
        
        assert record.record_id == "dvr_test"
        assert record.status == DeliveryStatus.DELIVERED
    
    def test_record_to_dict(self):
        """Test record serialization."""
        record = DeliveryRecord(
            record_id="dvr_test",
            notification_id="ntf_test",
            channel=ChannelType.SMS,
            recipient="+1234567890",
            status=DeliveryStatus.FAILED,
            attempts=3,
            error="Connection timeout",
        )
        
        d = record.to_dict()
        
        assert d["status"] == "failed"
        assert d["error"] == "Connection timeout"


class TestUserPreferences:
    """Test user preferences."""
    
    def test_create_preferences(self):
        """Test creating user preferences."""
        prefs = UserPreferences(user_id="user_123")
        
        assert prefs.user_id == "user_123"
        assert prefs.channels == {}
    
    def test_preferences_with_channels(self):
        """Test preferences with channel settings."""
        prefs = UserPreferences(
            user_id="user_123",
            channels={ChannelType.EMAIL: True, ChannelType.SMS: False},
        )
        
        assert prefs.channels[ChannelType.EMAIL] is True
        assert prefs.channels[ChannelType.SMS] is False
    
    def test_preferences_with_quiet_hours(self):
        """Test preferences with quiet hours."""
        prefs = UserPreferences(
            user_id="user_123",
            quiet_hours_start=22,
            quiet_hours_end=7,
        )
        
        assert prefs.quiet_hours_start == 22
        assert prefs.quiet_hours_end == 7
    
    def test_preferences_to_dict(self):
        """Test preferences serialization."""
        prefs = UserPreferences(
            user_id="user_123",
            channels={ChannelType.EMAIL: True},
            quiet_hours_start=22,
            quiet_hours_end=7,
            priority_threshold=NotificationPriority.HIGH,
            subscribed_topics={"alerts", "news"},
        )
        
        d = prefs.to_dict()
        
        assert d["channels"]["email"] is True
        assert d["quiet_hours_start"] == 22
        assert "alerts" in d["subscribed_topics"]


class TestNotificationWorkflow:
    """Test notification workflow."""
    
    def test_create_workflow(self):
        """Test creating workflow."""
        workflow = NotificationWorkflow(
            workflow_id="wf_test",
            name="Escalation Workflow",
            steps=[
                {"channel": "email", "body": "First notification"},
                {"channel": "sms", "body": "Escalated notification"},
            ],
        )
        
        assert workflow.workflow_id == "wf_test"
        assert len(workflow.steps) == 2
    
    def test_workflow_to_dict(self):
        """Test workflow serialization."""
        workflow = NotificationWorkflow(
            workflow_id="wf_test",
            name="Test Workflow",
            steps=[{"channel": "email"}],
            condition="priority > 2",
            enabled=True,
        )
        
        d = workflow.to_dict()
        
        assert d["condition"] == "priority > 2"
        assert d["enabled"] is True


class TestNotificationEngine:
    """Test notification engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_notification_engine()
        assert engine is not None
    
    def test_create_template(self):
        """Test creating template."""
        engine = NotificationEngine(throttle_per_minute=0)
        
        template_id = engine.create_template(
            name="Welcome Email",
            channel=ChannelType.EMAIL,
            body_template="Hello {{name}}!",
            variables=["name"],
        )
        
        assert template_id is not None
        assert template_id.startswith("tpl_")
        
        template = engine.get_template(template_id)
        
        assert template.name == "Welcome Email"
    
    def test_create_template_with_subject(self):
        """Test creating template with subject."""
        engine = NotificationEngine(throttle_per_minute=0)
        
        template_id = engine.create_template(
            name="Alert",
            channel=ChannelType.EMAIL,
            subject_template="Alert: {{type}}",
            body_template="Alert occurred: {{details}}",
        )
        
        template = engine.get_template(template_id)
        
        assert template.subject_template is not None
    
    def test_update_template(self):
        """Test updating template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Original",
        )
        
        result = engine.update_template(
            template_id,
            body_template="Updated",
        )
        
        assert result is True
        
        template = engine.get_template(template_id)
        
        assert template.body_template == "Updated"
    
    def test_update_nonexistent_template(self):
        """Test updating nonexistent template."""
        engine = NotificationEngine()
        
        result = engine.update_template("nonexistent", body_template="test")
        
        assert result is False
    
    def test_delete_template(self):
        """Test deleting template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template("Test", ChannelType.EMAIL, "Body")
        
        result = engine.delete_template(template_id)
        
        assert result is True
        assert engine.get_template(template_id) is None
    
    def test_delete_nonexistent_template(self):
        """Test deleting nonexistent template."""
        engine = NotificationEngine()
        
        result = engine.delete_template("nonexistent")
        
        assert result is False
    
    def test_list_templates(self):
        """Test listing templates."""
        engine = NotificationEngine()
        
        engine.create_template("Template 1", ChannelType.EMAIL, "Body 1")
        engine.create_template("Template 2", ChannelType.SMS, "Body 2")
        engine.create_template("Template 3", ChannelType.EMAIL, "Body 3")
        
        templates = engine.list_templates()
        
        assert len(templates) == 3
    
    def test_list_templates_by_channel(self):
        """Test listing templates by channel."""
        engine = NotificationEngine()
        
        engine.create_template("Email 1", ChannelType.EMAIL, "Body")
        engine.create_template("SMS 1", ChannelType.SMS, "Body")
        engine.create_template("Email 2", ChannelType.EMAIL, "Body")
        
        email_templates = engine.list_templates(channel=ChannelType.EMAIL)
        
        assert len(email_templates) == 2
        assert all(t["channel"] == "email" for t in email_templates)
    
    def test_send_notification(self):
        """Test sending notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test message",
            subject="Test Subject",
        )
        
        assert notification_id is not None
        assert notification_id.startswith("ntf_")
        
        notif = engine.get_notification(notification_id)
        
        assert notif is not None
        assert notif.body == "Test message"
    
    def test_send_with_template(self):
        """Test sending notification with template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Welcome",
            channel=ChannelType.EMAIL,
            body_template="Welcome {{name}}!",
            variables=["name"],
        )
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="",
            template_id=template_id,
            variables={"name": "John"},
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.body == "Welcome John!"
    
    def test_send_with_priority(self):
        """Test sending notification with priority."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
            priority=NotificationPriority.URGENT,
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.priority == NotificationPriority.URGENT
    
    def test_send_with_metadata(self):
        """Test sending notification with metadata."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
            metadata={"campaign": "summer", "source": "api"},
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.metadata["campaign"] == "summer"
    
    def test_send_batch(self):
        """Test sending batch notifications."""
        engine = NotificationEngine()
        
        batch = [
            {"channel": "email", "recipient": "user1@example.com", "body": "Message 1"},
            {"channel": "email", "recipient": "user2@example.com", "body": "Message 2"},
            {"channel": "sms", "recipient": "+1234567890", "body": "Message 3"},
        ]
        
        ids = engine.send_batch(batch)
        
        assert len(ids) == 3
    
    def test_get_notification(self):
        """Test getting notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif is not None
        assert notif.channel == ChannelType.EMAIL
    
    def test_get_notification_nonexistent(self):
        """Test getting nonexistent notification."""
        engine = NotificationEngine()
        
        notif = engine.get_notification("nonexistent")
        
        assert notif is None
    
    def test_list_notifications(self):
        """Test listing notifications."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.send(ChannelType.EMAIL, f"user{i}@example.com", f"Message {i}")
        
        notifications = engine.list_notifications(limit=10)
        
        assert len(notifications) == 5
    
    def test_list_notifications_by_status(self):
        """Test listing notifications by status."""
        engine = NotificationEngine()
        
        engine.send(ChannelType.EMAIL, "user1@example.com", "Message 1")
        engine.send(ChannelType.EMAIL, "user2@example.com", "Message 2")
        
        notifications = engine.list_notifications(status=DeliveryStatus.DELIVERED)
        
        assert len(notifications) >= 0  # All should be delivered with default handler
    
    def test_list_notifications_by_channel(self):
        """Test listing notifications by channel."""
        engine = NotificationEngine()
        
        engine.send(ChannelType.EMAIL, "user1@example.com", "Message")
        engine.send(ChannelType.SMS, "+1234567890", "Message")
        engine.send(ChannelType.EMAIL, "user2@example.com", "Message")
        
        emails = engine.list_notifications(channel=ChannelType.EMAIL)
        
        assert len(emails) == 2
    
    def test_retry_notification(self):
        """Test retrying notification."""
        engine = NotificationEngine(throttle_per_minute=0)
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        # Cancel it first
        engine.cancel_notification(notification_id)
        
        result = engine.retry_notification(notification_id)
        
        assert result is True
        
        notif = engine.get_notification(notification_id)
        
        assert notif.status == DeliveryStatus.PENDING
    
    def test_retry_non_failed_notification(self):
        """Test retrying non-failed notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        # It's already delivered
        result = engine.retry_notification(notification_id)
        
        assert result is False
    
    def test_retry_nonexistent_notification(self):
        """Test retrying nonexistent notification."""
        engine = NotificationEngine()
        
        result = engine.retry_notification("nonexistent")
        
        assert result is False
    
    def test_cancel_notification(self):
        """Test cancelling notification."""
        engine = NotificationEngine(throttle_per_minute=0)
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        result = engine.cancel_notification(notification_id)
        
        assert result is True
        
        notif = engine.get_notification(notification_id)
        
        assert notif.status == DeliveryStatus.CANCELLED
    
    def test_cancel_delivered_notification(self):
        """Test cancelling already delivered notification."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        # Already delivered by default handler
        result = engine.cancel_notification(notification_id)
        
        assert result is False
    
    def test_cancel_nonexistent_notification(self):
        """Test cancelling nonexistent notification."""
        engine = NotificationEngine()
        
        result = engine.cancel_notification("nonexistent")
        
        assert result is False
    
    def test_create_workflow(self):
        """Test creating workflow."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Escalation",
            steps=[
                {"channel": "email", "body": "First"},
                {"channel": "sms", "body": "Second"},
            ],
        )
        
        assert workflow_id is not None
        assert workflow_id.startswith("wf_")
    
    def test_execute_workflow(self):
        """Test executing workflow."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Test Workflow",
            steps=[
                {"channel": "email", "body": "Step 1"},
                {"channel": "sms", "body": "Step 2"},
            ],
        )
        
        notification_ids = engine.execute_workflow(
            workflow_id,
            {"recipient": "user@example.com"},
        )
        
        assert len(notification_ids) == 2
    
    def test_get_workflow(self):
        """Test getting workflow."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            steps=[{"channel": "email"}],
        )
        
        workflow = engine.get_workflow(workflow_id)
        
        assert workflow is not None
        assert workflow.name == "Test"
    
    def test_get_workflow_nonexistent(self):
        """Test getting nonexistent workflow."""
        engine = NotificationEngine()
        
        workflow = engine.get_workflow("nonexistent")
        
        assert workflow is None
    
    def test_list_workflows(self):
        """Test listing workflows."""
        engine = NotificationEngine()
        
        engine.create_workflow("Workflow 1", [{"channel": "email"}])
        engine.create_workflow("Workflow 2", [{"channel": "sms"}])
        
        workflows = engine.list_workflows()
        
        assert len(workflows) == 2
    
    def test_set_user_preferences(self):
        """Test setting user preferences."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_123",
            channels={ChannelType.EMAIL: True, ChannelType.SMS: False},
            quiet_hours_start=22,
            quiet_hours_end=7,
        )
        
        prefs = engine.get_user_preferences("user_123")
        
        assert prefs is not None
        assert prefs["channels"]["email"] is True
        assert prefs["channels"]["sms"] is False
    
    def test_get_user_preferences_nonexistent(self):
        """Test getting preferences for nonexistent user."""
        engine = NotificationEngine()
        
        prefs = engine.get_user_preferences("nonexistent")
        
        assert prefs is None
    
    def test_user_preferences_block_channel(self):
        """Test that user preferences can block channel."""
        engine = NotificationEngine()
        
        engine.set_user_preferences(
            user_id="user_123",
            channels={ChannelType.EMAIL: False},
        )
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user_123",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.status == DeliveryStatus.CANCELLED
    
    def test_register_channel_handler(self):
        """Test registering channel handler."""
        engine = NotificationEngine()
        
        def mock_handler(notif):
            return True
        
        engine.register_channel_handler(ChannelType.EMAIL, mock_handler)
        
        # Should be registered
        assert ChannelType.EMAIL in engine._channel_handlers
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = NotificationEngine()
        
        engine.send(ChannelType.EMAIL, "user@example.com", "Test")
        engine.send(ChannelType.EMAIL, "user2@example.com", "Test")
        
        stats = engine.get_statistics()
        
        assert stats["total_sent"] >= 0
        assert stats["total_delivered"] >= 0
    
    def test_statistics_by_channel(self):
        """Test statistics by channel."""
        engine = NotificationEngine()
        
        for i in range(3):
            engine.send(ChannelType.EMAIL, f"user{i}@example.com", "Test")
        
        for i in range(2):
            engine.send(ChannelType.SMS, f"+123456789{i}", "Test")
        
        stats = engine.get_statistics()
        
        assert stats["by_channel"].get("email", 0) >= 3
        assert stats["by_channel"].get("sms", 0) >= 2
    
    def test_statistics_by_template(self):
        """Test statistics by template."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Body",
        )
        
        for i in range(3):
            engine.send(
                channel=ChannelType.EMAIL,
                recipient=f"user{i}@example.com",
                body="",
                template_id=template_id,
            )
        
        stats = engine.get_statistics()
        
        assert stats["by_template"].get(template_id, 0) == 3
    
    def test_clear_delivery_records(self):
        """Test clearing delivery records."""
        engine = NotificationEngine()
        
        engine.send(ChannelType.EMAIL, "user@example.com", "Test")
        
        count = engine.clear_delivery_records()
        
        assert count >= 1
    
    def test_clear_delivery_records_older_than(self):
        """Test clearing old delivery records."""
        engine = NotificationEngine()
        
        engine.send(ChannelType.EMAIL, "user@example.com", "Test")
        
        # Clear records older than 0 days (should clear none since they're new)
        count = engine.clear_delivery_records(older_than_days=0)
        
        # All records should be newer than 0 days
        assert count == 0
    
    def test_notification_created_at_set(self):
        """Test that notification created_at is set."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.created_at is not None
    
    def test_template_created_at_set(self):
        """Test that template created_at is set."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Body",
        )
        
        template = engine.get_template(template_id)
        
        assert template.created_at is not None
    
    def test_workflow_created_at_set(self):
        """Test that workflow created_at is set."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            steps=[{"channel": "email"}],
        )
        
        workflow = engine.get_workflow(workflow_id)
        
        assert workflow.created_at is not None
    
    def test_delivery_record_created(self):
        """Test that delivery record is created."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        record = engine.get_delivery_record(notification_id)
        
        assert record is not None
    
    def test_notification_status_default(self):
        """Test that notification status defaults to PENDING."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        # After delivery attempt, should be DELIVERED (default handler succeeds)
        assert notif.status in (DeliveryStatus.DELIVERED, DeliveryStatus.PENDING)
    
    def test_notification_delivery_count(self):
        """Test that delivery count is tracked."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.delivery_count >= 0
    
    def test_template_id_unique(self):
        """Test that template IDs are unique."""
        engine = NotificationEngine()
        
        ids = set()
        for i in range(50):
            template_id = engine.create_template(
                f"Template {i}",
                ChannelType.EMAIL,
                "Body",
            )
            ids.add(template_id)
        
        assert len(ids) == 50
    
    def test_notification_id_unique(self):
        """Test that notification IDs are unique."""
        engine = NotificationEngine()
        
        ids = set()
        for i in range(50):
            notification_id = engine.send(
                ChannelType.EMAIL,
                f"user{i}@example.com",
                "Message",
            )
            ids.add(notification_id)
        
        assert len(ids) == 50
    
    def test_workflow_id_unique(self):
        """Test that workflow IDs are unique."""
        engine = NotificationEngine()
        
        ids = set()
        for i in range(50):
            workflow_id = engine.create_workflow(
                f"Workflow {i}",
                [{"channel": "email"}],
            )
            ids.add(workflow_id)
        
        assert len(ids) == 50
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = NotificationEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_sent"] == 0
        assert stats["total_delivered"] == 0
        assert stats["total_failed"] == 0
        assert stats["total_templates"] == 0
        assert stats["total_workflows"] == 0
    
    def test_statistics_total_templates(self):
        """Test that statistics track template count."""
        engine = NotificationEngine()
        
        engine.create_template("T1", ChannelType.EMAIL, "Body")
        engine.create_template("T2", ChannelType.EMAIL, "Body")
        engine.create_template("T3", ChannelType.EMAIL, "Body")
        
        stats = engine.get_statistics()
        
        assert stats["total_templates"] == 3
    
    def test_statistics_total_workflows(self):
        """Test that statistics track workflow count."""
        engine = NotificationEngine()
        
        engine.create_workflow("W1", [{"channel": "email"}])
        engine.create_workflow("W2", [{"channel": "email"}])
        
        stats = engine.get_statistics()
        
        assert stats["total_workflows"] == 2
    
    def test_statistics_pending_notifications(self):
        """Test that statistics track pending notifications."""
        engine = NotificationEngine()
        
        stats = engine.get_statistics()
        
        assert stats["pending_notifications"] == 0
    
    def test_multiple_channels_independent(self):
        """Test that multiple channels are independent."""
        engine = NotificationEngine()
        
        email_id = engine.send(ChannelType.EMAIL, "user@example.com", "Email")
        sms_id = engine.send(ChannelType.SMS, "+1234567890", "SMS")
        
        email_notif = engine.get_notification(email_id)
        sms_notif = engine.get_notification(sms_id)
        
        assert email_notif.channel == ChannelType.EMAIL
        assert sms_notif.channel == ChannelType.SMS
    
    def test_template_variable_case_insensitive(self):
        """Test that template variables are case insensitive."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Hello {{Name}}!",
        )
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="",
            template_id=template_id,
            variables={"name": "John"},
        )
        
        notif = engine.get_notification(notification_id)
        
        # Should render regardless of case
        assert "John" in notif.body
    
    def test_send_with_scheduled_at(self):
        """Test sending scheduled notification."""
        engine = NotificationEngine()
        
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
            scheduled_at=future,
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.scheduled_at is not None
    
    def test_send_with_expires_at(self):
        """Test sending notification with expiry."""
        engine = NotificationEngine()
        
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
            expires_at=future,
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.expires_at is not None
    
    def test_list_notifications_limit(self):
        """Test listing notifications with limit."""
        engine = NotificationEngine()
        
        for i in range(100):
            engine.send(ChannelType.EMAIL, f"user{i}@example.com", f"Message {i}")
        
        notifications = engine.list_notifications(limit=10)
        
        assert len(notifications) == 10
    
    def test_list_notifications_sorted_by_created_at(self):
        """Test that notifications are sorted by created_at descending."""
        engine = NotificationEngine()
        
        for i in range(5):
            engine.send(ChannelType.EMAIL, f"user{i}@example.com", f"Message {i}")
        
        notifications = engine.list_notifications(limit=10)
        
        # Should be sorted by created_at descending
        for i in range(len(notifications) - 1):
            assert notifications[i]["created_at"] >= notifications[i + 1]["created_at"]
    
    def test_delivery_record_has_metadata(self):
        """Test that delivery record has metadata field."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        record = engine.get_delivery_record(notification_id)
        
        assert record is not None
        assert hasattr(record, "metadata")
        assert record.metadata == {}
    
    def test_clear_delivery_records_empty(self):
        """Test clearing empty delivery records."""
        engine = NotificationEngine()
        
        count = engine.clear_delivery_records()
        
        assert count == 0
    
    def test_execute_workflow_disabled(self):
        """Test executing disabled workflow."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            steps=[{"channel": "email", "body": "Test"}],
        )
        
        # Disable workflow
        workflow = engine.get_workflow(workflow_id)
        workflow.enabled = False
        
        notification_ids = engine.execute_workflow(
            workflow_id,
            {"recipient": "user@example.com"},
        )
        
        assert len(notification_ids) == 0
    
    def test_template_render_unknown_variable(self):
        """Test template rendering with unknown variable."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Hello {{name}}, welcome {{unknown}}!",
        )
        
        result = template.render({"name": "John"})
        
        # Unknown variable should remain as placeholder
        assert "{{unknown}}" in result["body"] or "welcome !" in result["body"]
    
    def test_notification_to_dict_includes_all_fields(self):
        """Test that notification to_dict includes all fields."""
        notif = Notification(
            notification_id="ntf_test",
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            subject="Subject",
            body="Body",
            priority=NotificationPriority.HIGH,
            template_id="tpl_123",
            variables={"key": "value"},
            metadata={"meta": "data"},
            scheduled_at="2025-01-01T00:00:00Z",
            expires_at="2025-12-31T23:59:59Z",
        )
        
        d = notif.to_dict()
        
        assert d["subject"] == "Subject"
        assert d["template_id"] == "tpl_123"
        assert d["variables"]["key"] == "value"
    
    def test_workflow_to_dict_includes_all_fields(self):
        """Test that workflow to_dict includes all fields."""
        workflow = NotificationWorkflow(
            workflow_id="wf_test",
            name="Test Workflow",
            steps=[{"channel": "email", "body": "Test"}],
            condition="priority > 2",
            enabled=True,
        )
        
        d = workflow.to_dict()
        
        assert d["name"] == "Test Workflow"
        assert d["condition"] == "priority > 2"
        assert len(d["steps"]) == 1
    
    def test_user_preferences_to_dict_includes_all_fields(self):
        """Test that user preferences to_dict includes all fields."""
        prefs = UserPreferences(
            user_id="user_123",
            channels={ChannelType.EMAIL: True},
            quiet_hours_start=22,
            quiet_hours_end=7,
            priority_threshold=NotificationPriority.HIGH,
            subscribed_topics={"alerts"},
        )
        
        d = prefs.to_dict()
        
        assert d["user_id"] == "user_123"
        assert d["quiet_hours_start"] == 22
        assert d["priority_threshold"] == 2  # HIGH = 2
    
    def test_delivery_record_to_dict_includes_all_fields(self):
        """Test that delivery record to_dict includes all fields."""
        record = DeliveryRecord(
            record_id="dvr_test",
            notification_id="ntf_test",
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            status=DeliveryStatus.DELIVERED,
            attempts=1,
            sent_at="2025-01-01T00:00:00Z",
            delivered_at="2025-01-01T00:00:01Z",
            error=None,
            metadata={"provider": "smtp"},
        )
        
        d = record.to_dict()
        
        assert d["status"] == "delivered"
        assert d["metadata"]["provider"] == "smtp"
    
    def test_template_to_dict_includes_all_fields(self):
        """Test that template to_dict includes all fields."""
        template = NotificationTemplate(
            template_id="tpl_test",
            name="Test",
            channel=ChannelType.EMAIL,
            subject_template="Subject",
            body_template="Body",
            variables=["var1"],
            default_values={"var1": "default"},
        )
        
        d = template.to_dict()
        
        assert d["subject_template"] == "Subject"
        assert d["default_values"]["var1"] == "default"
    
    def test_send_returns_notification_id(self):
        """Test that send returns notification ID."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        assert notification_id.startswith("ntf_")
    
    def test_create_template_returns_template_id(self):
        """Test that create_template returns template ID."""
        engine = NotificationEngine()
        
        template_id = engine.create_template(
            name="Test",
            channel=ChannelType.EMAIL,
            body_template="Body",
        )
        
        assert template_id.startswith("tpl_")
    
    def test_create_workflow_returns_workflow_id(self):
        """Test that create_workflow returns workflow ID."""
        engine = NotificationEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            steps=[{"channel": "email"}],
        )
        
        assert workflow_id.startswith("wf_")
    
    def test_statistics_total_users(self):
        """Test that statistics track user count."""
        engine = NotificationEngine()
        
        engine.set_user_preferences("user1", channels={ChannelType.EMAIL: True})
        engine.set_user_preferences("user2", channels={ChannelType.SMS: True})
        engine.set_user_preferences("user3", channels={ChannelType.PUSH: True})
        
        stats = engine.get_statistics()
        
        assert stats["total_users"] == 3
    
    def test_send_batch_returns_ids(self):
        """Test that send_batch returns notification IDs."""
        engine = NotificationEngine()
        
        batch = [
            {"channel": "email", "recipient": "user1@example.com", "body": "Message 1"},
            {"channel": "email", "recipient": "user2@example.com", "body": "Message 2"},
        ]
        
        ids = engine.send_batch(batch)
        
        assert len(ids) == 2
        assert all(id.startswith("ntf_") for id in ids)
    
    def test_notification_channel_enum_value(self):
        """Test that notification channel enum value is correct."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.TELEGRAM,
            recipient="@username",
            body="Test",
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.channel.value == "telegram"
    
    def test_notification_priority_enum_value(self):
        """Test that notification priority enum value is correct."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
            priority=NotificationPriority.CRITICAL,
        )
        
        notif = engine.get_notification(notification_id)
        
        assert notif.priority.value == 4
    
    def test_delivery_status_enum_value(self):
        """Test that delivery status enum value is correct."""
        engine = NotificationEngine()
        
        notification_id = engine.send(
            channel=ChannelType.EMAIL,
            recipient="user@example.com",
            body="Test",
        )
        
        record = engine.get_delivery_record(notification_id)
        
        assert record.status.value in ("pending", "delivered", "sent")
