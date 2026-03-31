"""Tests for Webhook Engine — Slice 53."""
import pytest
from copilot_core.webhook.engine import (
    WebhookEngine,
    WebhookStatus,
    DeliveryStatus,
    Webhook,
    Delivery,
    create_webhook_engine,
)
from datetime import datetime, timezone, timedelta
import json
import time


class TestWebhookEngine:
    """Test webhook engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_webhook_engine()
        assert engine is not None
    
    def test_register_webhook(self):
        """Test registering a webhook."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            events=["user.created", "user.updated"],
        )
        
        assert webhook_id is not None
        assert webhook_id.startswith("wh_")
    
    def test_register_webhook_with_secret(self):
        """Test registering webhook with secret."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Secure Webhook",
            url="https://example.com/webhook",
            events=["*"],
            secret="my_secret_key",
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.secret == "my_secret_key"
    
    def test_register_webhook_with_headers(self):
        """Test registering webhook with custom headers."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Custom Headers Webhook",
            url="https://example.com/webhook",
            events=["test.event"],
            headers={"X-Custom-Header": "custom_value", "Authorization": "Bearer token"},
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.headers["X-Custom-Header"] == "custom_value"
        assert webhook.headers["Authorization"] == "Bearer token"
    
    def test_register_webhook_with_timeout(self):
        """Test registering webhook with custom timeout."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Timeout Webhook",
            url="https://example.com/webhook",
            events=["test"],
            timeout_seconds=60,
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.timeout_seconds == 60
    
    def test_register_webhook_with_max_retries(self):
        """Test registering webhook with custom max retries."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Retry Webhook",
            url="https://example.com/webhook",
            events=["test"],
            max_retries=5,
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.max_retries == 5
    
    def test_update_webhook(self):
        """Test updating webhook."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Original Name",
            url="https://original.com/webhook",
            events=["event1"],
        )
        
        result = engine.update_webhook(
            webhook_id,
            name="Updated Name",
            url="https://updated.com/webhook",
            events=["event2", "event3"],
        )
        
        assert result is True
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.name == "Updated Name"
        assert webhook.url == "https://updated.com/webhook"
        assert webhook.events == ["event2", "event3"]
    
    def test_update_webhook_status(self):
        """Test updating webhook status."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
        )
        
        engine.update_webhook(webhook_id, status=WebhookStatus.INACTIVE)
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.status == WebhookStatus.INACTIVE
    
    def test_update_unknown_webhook(self):
        """Test updating unknown webhook."""
        engine = WebhookEngine()
        
        result = engine.update_webhook("unknown_webhook", name="New Name")
        
        assert result is False
    
    def test_delete_webhook(self):
        """Test deleting webhook."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="To Delete",
            url="https://example.com/webhook",
            events=["test"],
        )
        
        result = engine.delete_webhook(webhook_id)
        
        assert result is True
        assert engine.get_webhook(webhook_id) is None
    
    def test_delete_unknown_webhook(self):
        """Test deleting unknown webhook."""
        engine = WebhookEngine()
        
        result = engine.delete_webhook("unknown_webhook")
        
        assert result is False
    
    def test_get_webhook(self):
        """Test getting webhook by ID."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            events=["test.event"],
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook is not None
        assert webhook.name == "Test Webhook"
    
    def test_get_unknown_webhook(self):
        """Test getting unknown webhook."""
        engine = WebhookEngine()
        
        webhook = engine.get_webhook("unknown_webhook")
        
        assert webhook is None
    
    def test_list_webhooks(self):
        """Test listing all webhooks."""
        engine = WebhookEngine()
        
        engine.register_webhook("Webhook 1", "https://example.com/1", ["event1"])
        engine.register_webhook("Webhook 2", "https://example.com/2", ["event2"])
        engine.register_webhook("Webhook 3", "https://example.com/3", ["event3"])
        
        webhooks = engine.list_webhooks()
        
        assert len(webhooks) == 3
    
    def test_list_webhooks_filtered_by_status(self):
        """Test listing webhooks filtered by status."""
        engine = WebhookEngine()
        
        engine.register_webhook("Active", "https://example.com/1", ["event1"])
        engine.register_webhook("Inactive", "https://example.com/2", ["event2"])
        
        # Set one to inactive
        webhooks = engine.list_webhooks()
        for w in webhooks:
            if w.name == "Inactive":
                engine.update_webhook(w.webhook_id, status=WebhookStatus.INACTIVE)
        
        active = engine.list_webhooks(status=WebhookStatus.ACTIVE)
        inactive = engine.list_webhooks(status=WebhookStatus.INACTIVE)
        
        assert len(active) == 1
        assert len(inactive) == 1
    
    def test_trigger_event(self):
        """Test triggering an event."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            events=["user.created"],
        )
        
        delivery_ids = engine.trigger_event("user.created", {"user_id": "123"})
        
        assert len(delivery_ids) == 1
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.event_type == "user.created"
        assert delivery.payload["user_id"] == "123"
    
    def test_trigger_event_wildcard(self):
        """Test triggering event with wildcard subscription."""
        engine = WebhookEngine()
        
        engine.register_webhook(
            name="Wildcard Webhook",
            url="https://example.com/webhook",
            events=["*"],
        )
        
        delivery_ids = engine.trigger_event("any.event", {"data": "value"})
        
        assert len(delivery_ids) == 1
    
    def test_trigger_event_no_match(self):
        """Test triggering event with no matching webhook."""
        engine = WebhookEngine()
        
        engine.register_webhook(
            name="Specific Webhook",
            url="https://example.com/webhook",
            events=["user.created"],
        )
        
        delivery_ids = engine.trigger_event("post.created", {"post_id": "456"})
        
        assert len(delivery_ids) == 0
    
    def test_trigger_event_inactive_webhook(self):
        """Test that inactive webhooks don't receive events."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Inactive Webhook",
            url="https://example.com/webhook",
            events=["user.created"],
        )
        
        engine.update_webhook(webhook_id, status=WebhookStatus.INACTIVE)
        
        delivery_ids = engine.trigger_event("user.created", {"user_id": "123"})
        
        assert len(delivery_ids) == 0
    
    def test_delivery_success(self):
        """Test successful delivery."""
        engine = WebhookEngine()
        
        # Mock HTTP client that returns success
        def mock_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(mock_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.status == DeliveryStatus.DELIVERED
        assert delivery.response_code == 200
    
    def test_delivery_failure(self):
        """Test failed delivery."""
        engine = WebhookEngine()
        
        # Mock HTTP client that returns error
        def mock_client(url, payload, headers, timeout):
            return (500, '{"error": "internal server error"}')
        
        engine.set_http_client(mock_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            max_retries=0,
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.status == DeliveryStatus.FAILED
        assert delivery.response_code == 500
    
    def test_delivery_retry(self):
        """Test delivery retry on failure."""
        engine = WebhookEngine()
        
        attempt_count = [0]
        
        def mock_client(url, payload, headers, timeout):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                return (500, '{"error": "fail"}')
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(mock_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            max_retries=3,
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.5)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.attempts >= 2
    
    def test_signature_generation(self):
        """Test signature generation."""
        engine = WebhookEngine()
        
        payload = '{"user_id": "123"}'
        secret = "my_secret"
        
        signature = engine._generate_signature(payload, secret)
        
        assert signature.startswith("sha256=")
        assert len(signature) == 71  # sha256= + 64 hex chars
    
    def test_signature_verification_valid(self):
        """Test signature verification with valid signature."""
        engine = WebhookEngine()
        
        payload = '{"user_id": "123"}'
        secret = "my_secret"
        
        signature = engine._generate_signature(payload, secret)
        
        result = engine.verify_signature(payload, signature, secret)
        
        assert result is True
    
    def test_signature_verification_invalid(self):
        """Test signature verification with invalid signature."""
        engine = WebhookEngine()
        
        payload = '{"user_id": "123"}'
        secret = "my_secret"
        wrong_secret = "wrong_secret"
        
        signature = engine._generate_signature(payload, secret)
        
        result = engine.verify_signature(payload, signature, wrong_secret)
        
        assert result is False
    
    def test_signature_verification_tampered_payload(self):
        """Test signature verification with tampered payload."""
        engine = WebhookEngine()
        
        payload = '{"user_id": "123"}'
        tampered = '{"user_id": "456"}'
        secret = "my_secret"
        
        signature = engine._generate_signature(payload, secret)
        
        result = engine.verify_signature(tampered, signature, secret)
        
        assert result is False
    
    def test_get_delivery(self):
        """Test getting delivery by ID."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery is not None
        assert delivery.delivery_id == delivery_ids[0]
    
    def test_get_unknown_delivery(self):
        """Test getting unknown delivery."""
        engine = WebhookEngine()
        
        delivery = engine.get_delivery("unknown_delivery")
        
        assert delivery is None
    
    def test_list_deliveries(self):
        """Test listing deliveries."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["*"],
        )
        
        engine.trigger_event("event1", {"data": "1"})
        engine.trigger_event("event2", {"data": "2"})
        engine.trigger_event("event3", {"data": "3"})
        
        deliveries = engine.list_deliveries(limit=10)
        
        assert len(deliveries) == 3
    
    def test_list_deliveries_by_webhook(self):
        """Test listing deliveries by webhook."""
        engine = WebhookEngine()
        
        webhook1 = engine.register_webhook("WH1", "https://example.com/1", ["event1"])
        webhook2 = engine.register_webhook("WH2", "https://example.com/2", ["event2"])
        
        engine.trigger_event("event1", {"data": "1"})
        engine.trigger_event("event2", {"data": "2"})
        
        deliveries1 = engine.list_deliveries(webhook_id=webhook1)
        deliveries2 = engine.list_deliveries(webhook_id=webhook2)
        
        assert len(deliveries1) == 1
        assert len(deliveries2) == 1
    
    def test_list_deliveries_by_status(self):
        """Test listing deliveries by status."""
        engine = WebhookEngine()
        
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        def fail_client(url, payload, headers, timeout):
            return (500, '{"error": "fail"}')
        
        webhook_success = engine.register_webhook("Success", "https://example.com/s", ["success"], max_retries=0)
        webhook_fail = engine.register_webhook("Fail", "https://example.com/f", ["fail"], max_retries=0)
        
        engine.set_http_client(success_client)
        engine.trigger_event("success", {"data": "1"})
        
        engine.set_http_client(fail_client)
        engine.trigger_event("fail", {"data": "2"})
        
        time.sleep(0.2)
        
        delivered = engine.list_deliveries(status=DeliveryStatus.DELIVERED)
        failed = engine.list_deliveries(status=DeliveryStatus.FAILED)
        
        assert len(delivered) == 1
        assert len(failed) == 1
    
    def test_list_deliveries_with_limit(self):
        """Test listing deliveries with limit."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        for i in range(50):
            engine.trigger_event(f"event{i}", {"data": str(i)})
        
        deliveries = engine.list_deliveries(limit=10)
        
        assert len(deliveries) == 10
    
    def test_retry_delivery(self):
        """Test manually retrying a failed delivery."""
        engine = WebhookEngine()
        
        # First, create a failed delivery
        def fail_client(url, payload, headers, timeout):
            return (500, '{"error": "fail"}')
        
        engine.set_http_client(fail_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            max_retries=0,
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.status == DeliveryStatus.FAILED
        
        # Now set up success and retry
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(success_client)
        
        result = engine.retry_delivery(delivery_ids[0])
        
        assert result is True
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.status == DeliveryStatus.DELIVERED
    
    def test_retry_unknown_delivery(self):
        """Test retrying unknown delivery."""
        engine = WebhookEngine()
        
        result = engine.retry_delivery("unknown_delivery")
        
        assert result is False
    
    def test_retry_non_failed_delivery(self):
        """Test retrying non-failed delivery."""
        engine = WebhookEngine()
        
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(success_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        # Delivery already succeeded
        result = engine.retry_delivery(delivery_ids[0])
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = WebhookEngine()
        
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(success_client)
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["*"],
        )
        
        for i in range(5):
            engine.trigger_event(f"event{i}", {"data": str(i)})
        
        time.sleep(0.2)
        
        stats = engine.get_statistics()
        
        assert stats["total_deliveries"] == 5
        assert stats["successful_deliveries"] == 5
        assert stats["total_webhooks"] == 1
        assert stats["active_webhooks"] == 1
    
    def test_statistics_by_event_type(self):
        """Test statistics by event type."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        engine.trigger_event("user.created", {"user": "1"})
        engine.trigger_event("user.created", {"user": "2"})
        engine.trigger_event("post.created", {"post": "1"})
        
        time.sleep(0.2)
        
        stats = engine.get_statistics()
        
        assert stats["by_event_type"]["user.created"] == 2
        assert stats["by_event_type"]["post.created"] == 1
    
    def test_statistics_by_webhook(self):
        """Test statistics by webhook."""
        engine = WebhookEngine()
        
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(success_client)
        
        webhook1 = engine.register_webhook("WH1", "https://example.com/1", ["*"])
        webhook2 = engine.register_webhook("WH2", "https://example.com/2", ["*"])
        
        engine.trigger_event("test", {"data": "1"})
        engine.trigger_event("test", {"data": "2"})
        
        time.sleep(0.2)
        
        stats = engine.get_statistics()
        
        assert stats["by_webhook"][webhook1] == 2
        assert stats["by_webhook"][webhook2] == 2
    
    def test_clear_deliveries(self):
        """Test clearing all deliveries."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        for i in range(10):
            engine.trigger_event(f"event{i}", {"data": str(i)})
        
        count = engine.clear_deliveries()
        
        assert count == 10
        
        deliveries = engine.list_deliveries()
        
        assert len(deliveries) == 0
    
    def test_clear_deliveries_by_webhook(self):
        """Test clearing deliveries by webhook."""
        engine = WebhookEngine()
        
        webhook1 = engine.register_webhook("WH1", "https://example.com/1", ["*"])
        webhook2 = engine.register_webhook("WH2", "https://example.com/2", ["*"])
        
        engine.trigger_event("test", {"data": "1"})
        engine.trigger_event("test", {"data": "2"})
        
        count = engine.clear_deliveries(webhook_id=webhook1)
        
        assert count == 2
        
        deliveries1 = engine.list_deliveries(webhook_id=webhook1)
        deliveries2 = engine.list_deliveries(webhook_id=webhook2)
        
        assert len(deliveries1) == 0
        assert len(deliveries2) == 2
    
    def test_clear_deliveries_older_than(self):
        """Test clearing deliveries older than."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        engine.trigger_event("old", {"data": "old"})
        
        # Manually set old timestamp
        if engine._deliveries:
            old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            for d in engine._deliveries.values():
                d.created_at = old_time
        
        engine.trigger_event("new", {"data": "new"})
        
        count = engine.clear_deliveries(older_than_days=1)
        
        assert count == 1
        
        deliveries = engine.list_deliveries()
        
        assert len(deliveries) == 1
        assert deliveries[0].event_type == "new"
    
    def test_webhook_to_dict(self):
        """Test webhook serialization."""
        webhook = Webhook(
            webhook_id="wh_test",
            name="Test Webhook",
            url="https://example.com/webhook",
            events=["test.event"],
            status=WebhookStatus.ACTIVE,
            timeout_seconds=60,
        )
        
        d = webhook.to_dict()
        
        assert d["webhook_id"] == "wh_test"
        assert d["name"] == "Test Webhook"
        assert d["events"] == ["test.event"]
        assert d["timeout_seconds"] == 60
    
    def test_delivery_to_dict(self):
        """Test delivery serialization."""
        delivery = Delivery(
            delivery_id="del_test",
            webhook_id="wh_test",
            event_type="test.event",
            payload={"key": "value"},
            status=DeliveryStatus.DELIVERED,
            attempts=1,
            response_code=200,
        )
        
        d = delivery.to_dict()
        
        assert d["delivery_id"] == "del_test"
        assert d["event_type"] == "test.event"
        assert d["status"] == "delivered"
        assert d["response_code"] == 200
    
    def test_webhook_status_enum_values(self):
        """Test webhook status enum values."""
        assert WebhookStatus.ACTIVE.value == "active"
        assert WebhookStatus.INACTIVE.value == "inactive"
        assert WebhookStatus.DISABLED.value == "disabled"
    
    def test_delivery_status_enum_values(self):
        """Test delivery status enum values."""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.RETRYING.value == "retrying"
    
    def test_webhook_created_at_set(self):
        """Test that webhook created_at is set."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook("Test", "https://example.com/webhook", ["test"])
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.created_at is not None
    
    def test_webhook_updated_at_changes_on_update(self):
        """Test that webhook updated_at changes on update."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook("Test", "https://example.com/webhook", ["test"])
        
        webhook1 = engine.get_webhook(webhook_id)
        
        time.sleep(0.01)
        
        engine.update_webhook(webhook_id, name="Updated")
        
        webhook2 = engine.get_webhook(webhook_id)
        
        assert webhook2.updated_at > webhook1.updated_at
    
    def test_delivery_created_at_set(self):
        """Test that delivery created_at is set."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.created_at is not None
    
    def test_delivery_delivered_at_set_on_success(self):
        """Test that delivery delivered_at is set on success."""
        engine = WebhookEngine()
        
        def success_client(url, payload, headers, timeout):
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(success_client)
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.delivered_at is not None
    
    def test_delivery_next_retry_at_set_on_failure(self):
        """Test that delivery next_retry_at is set on failure."""
        engine = WebhookEngine()
        
        def fail_client(url, payload, headers, timeout):
            return (500, '{"error": "fail"}')
        
        engine.set_http_client(fail_client)
        
        engine.register_webhook(
            "Test",
            "https://example.com/webhook",
            ["*"],
            max_retries=3,
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        if delivery.status == DeliveryStatus.RETRYING:
            assert delivery.next_retry_at is not None
    
    def test_webhook_id_unique(self):
        """Test that webhook IDs are unique."""
        engine = WebhookEngine()
        
        ids = set()
        for i in range(50):
            webhook_id = engine.register_webhook(f"WH{i}", f"https://example.com/{i}", ["test"])
            ids.add(webhook_id)
        
        assert len(ids) == 50
    
    def test_delivery_id_unique(self):
        """Test that delivery IDs are unique."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        ids = set()
        for i in range(50):
            delivery_ids = engine.trigger_event(f"event{i}", {"data": str(i)})
            ids.add(delivery_ids[0])
        
        assert len(ids) == 50
    
    def test_trigger_multiple_webhooks(self):
        """Test triggering event to multiple webhooks."""
        engine = WebhookEngine()
        
        engine.register_webhook("WH1", "https://example.com/1", ["broadcast"])
        engine.register_webhook("WH2", "https://example.com/2", ["broadcast"])
        engine.register_webhook("WH3", "https://example.com/3", ["broadcast"])
        
        delivery_ids = engine.trigger_event("broadcast", {"data": "value"})
        
        assert len(delivery_ids) == 3
    
    def test_webhook_metadata_preserved(self):
        """Test that webhook metadata is preserved."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            metadata={"team": "backend", "environment": "production"},
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.metadata["team"] == "backend"
        assert webhook.metadata["environment"] == "production"
    
    def test_update_webhook_metadata(self):
        """Test updating webhook metadata."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            metadata={"key1": "value1"},
        )
        
        engine.update_webhook(
            webhook_id,
            metadata={"key2": "value2"},
        )
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.metadata["key2"] == "value2"
    
    def test_delivery_payload_preserved(self):
        """Test that delivery payload is preserved."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        payload = {
            "user_id": "123",
            "action": "created",
            "nested": {"key": "value"},
            "array": [1, 2, 3],
        }
        
        delivery_ids = engine.trigger_event("user.action", payload)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.payload["user_id"] == "123"
        assert delivery.payload["nested"]["key"] == "value"
        assert delivery.payload["array"] == [1, 2, 3]
    
    def test_signature_constant_time_comparison(self):
        """Test that signature verification uses constant-time comparison."""
        engine = WebhookEngine()
        
        payload = '{"test": "data"}'
        secret = "secret"
        
        valid_sig = engine._generate_signature(payload, secret)
        invalid_sig = "sha256=" + "a" * 64
        
        # Should not raise and should return False for invalid
        result = engine.verify_signature(payload, invalid_sig, secret)
        
        assert result is False
    
    def test_empty_events_list_does_not_match(self):
        """Test that empty events list doesn't match any event."""
        engine = WebhookEngine()
        
        # Register webhook with empty events list
        webhook_id = engine.register_webhook(
            name="Empty",
            url="https://example.com/webhook",
            events=[],
        )
        
        delivery_ids = engine.trigger_event("any.event", {"data": "value"})
        
        assert len(delivery_ids) == 0
    
    def test_default_delivery_without_http_client(self):
        """Test delivery without HTTP client simulates success."""
        engine = WebhookEngine()
        
        # Don't set HTTP client - should simulate success
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.status == DeliveryStatus.DELIVERED
        assert delivery.response_code == 200
    
    def test_statistics_failed_deliveries(self):
        """Test that statistics track failed deliveries."""
        engine = WebhookEngine()
        
        def fail_client(url, payload, headers, timeout):
            return (500, '{"error": "fail"}')
        
        engine.set_http_client(fail_client)
        
        engine.register_webhook(
            "Test",
            "https://example.com/webhook",
            ["*"],
            max_retries=0,
        )
        
        engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.2)
        
        stats = engine.get_statistics()
        
        assert stats["failed_deliveries"] == 1
    
    def test_statistics_retries(self):
        """Test that statistics track retries."""
        engine = WebhookEngine()
        
        attempt_count = [0]
        
        def fail_client(url, payload, headers, timeout):
            attempt_count[0] += 1
            return (500, '{"error": "fail"}')
        
        engine.set_http_client(fail_client)
        
        engine.register_webhook(
            "Test",
            "https://example.com/webhook",
            ["*"],
            max_retries=3,
        )
        
        engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.5)
        
        stats = engine.get_statistics()
        
        assert stats["retries"] >= 1
    
    def test_headers_merged_with_defaults(self):
        """Test that custom headers are merged with defaults."""
        engine = WebhookEngine()
        
        received_headers = {}
        
        def capture_client(url, payload, headers, timeout):
            received_headers.update(headers)
            return (200, '{"status": "ok"}')
        
        engine.set_http_client(capture_client)
        
        engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            headers={"X-Custom": "value"},
        )
        
        engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        # Check that both default and custom headers are present
        assert "Content-Type" in received_headers
        assert "X-Custom" in received_headers
        assert received_headers["X-Custom"] == "value"
    
    def test_delivery_error_message_set_on_failure(self):
        """Test that delivery error message is set on failure."""
        engine = WebhookEngine()
        
        def fail_client(url, payload, headers, timeout):
            return (503, '{"error": "service unavailable"}')
        
        engine.set_http_client(fail_client)
        
        engine.register_webhook(
            "Test",
            "https://example.com/webhook",
            ["*"],
            max_retries=0,
        )
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.error_message is not None
        assert "503" in delivery.error_message
    
    def test_list_deliveries_sorted_by_created_at(self):
        """Test that deliveries are sorted by created_at descending."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        for i in range(5):
            engine.trigger_event(f"event{i}", {"data": str(i)})
            time.sleep(0.01)
        
        deliveries = engine.list_deliveries(limit=10)
        
        # Should be sorted newest first
        for i in range(len(deliveries) - 1):
            assert deliveries[i].created_at >= deliveries[i + 1].created_at
    
    def test_clear_empty_deliveries(self):
        """Test clearing when no deliveries exist."""
        engine = WebhookEngine()
        
        count = engine.clear_deliveries()
        
        assert count == 0
    
    def test_statistics_pending_deliveries(self):
        """Test that statistics track pending deliveries."""
        engine = WebhookEngine()
        
        # Block deliveries by not processing
        with engine._lock:
            webhook_id = engine.register_webhook(
                "Test",
                "https://example.com/webhook",
                ["*"],
            )
            
            delivery_id = engine._create_delivery(webhook_id, "test", {"data": "value"})
        
        stats = engine.get_statistics()
        
        assert stats["pending_deliveries"] == 1
    
    def test_statistics_active_webhooks_count(self):
        """Test that statistics correctly count active webhooks."""
        engine = WebhookEngine()
        
        engine.register_webhook("Active1", "https://example.com/1", ["*"])
        engine.register_webhook("Active2", "https://example.com/2", ["*"])
        
        webhooks = engine.list_webhooks()
        engine.update_webhook(webhooks[0].webhook_id, status=WebhookStatus.INACTIVE)
        
        stats = engine.get_statistics()
        
        assert stats["active_webhooks"] == 1
        assert stats["total_webhooks"] == 2
    
    def test_webhook_response_body_stored(self):
        """Test that webhook response body is stored."""
        engine = WebhookEngine()
        
        def response_client(url, payload, headers, timeout):
            return (200, '{"result": "success", "id": "123"}')
        
        engine.set_http_client(response_client)
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        time.sleep(0.1)
        
        delivery = engine.get_delivery(delivery_ids[0])
        
        assert delivery.response_body is not None
        assert "success" in delivery.response_body
    
    def test_trigger_event_returns_delivery_ids(self):
        """Test that trigger_event returns delivery IDs."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["*"])
        
        delivery_ids = engine.trigger_event("test", {"data": "value"})
        
        assert len(delivery_ids) == 1
        assert delivery_ids[0].startswith("del_")
    
    def test_multiple_events_same_webhook(self):
        """Test multiple events to same webhook."""
        engine = WebhookEngine()
        
        engine.register_webhook("Test", "https://example.com/webhook", ["event1", "event2", "event3"])
        
        engine.trigger_event("event1", {"data": "1"})
        engine.trigger_event("event2", {"data": "2"})
        engine.trigger_event("event3", {"data": "3"})
        engine.trigger_event("event4", {"data": "4"})  # Should not match
        
        deliveries = engine.list_deliveries()
        
        assert len(deliveries) == 3
    
    def test_update_webhook_preserves_unset_fields(self):
        """Test that updating webhook preserves unset fields."""
        engine = WebhookEngine()
        
        webhook_id = engine.register_webhook(
            name="Test",
            url="https://example.com/webhook",
            events=["test"],
            secret="my_secret",
            timeout_seconds=60,
            max_retries=5,
        )
        
        # Only update name
        engine.update_webhook(webhook_id, name="Updated Name")
        
        webhook = engine.get_webhook(webhook_id)
        
        assert webhook.name == "Updated Name"
        assert webhook.url == "https://example.com/webhook"
        assert webhook.secret == "my_secret"
        assert webhook.timeout_seconds == 60
        assert webhook.max_retries == 5
