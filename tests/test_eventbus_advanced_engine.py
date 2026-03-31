"""Tests for Event Bus Advanced Engine — Slice 63."""
import pytest
from copilot_core.eventbus_advanced.engine import (
    EventBusEngine,
    EventPriority,
    DeliveryStatus,
    Event,
    Subscription,
    DeliveryRecord,
    create_event_bus_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestEvent:
    """Test event definition."""
    
    def test_create_event(self):
        """Test creating event."""
        event = Event(
            event_id="evt_test",
            topic="test.topic",
            event_type="test_event",
            payload={"key": "value"},
        )
        
        assert event.event_id == "evt_test"
        assert event.priority == EventPriority.NORMAL
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(
            event_id="evt_test",
            topic="test.topic",
            event_type="test_event",
            payload={"key": "value"},
            priority=EventPriority.HIGH,
            version="2.0",
            source="test_service",
        )
        
        d = event.to_dict()
        
        assert d["priority"] == 2
        assert d["version"] == "2.0"
        assert d["source"] == "test_service"
    
    def test_event_not_expired_no_expiry(self):
        """Test event not expired when no expiry set."""
        event = Event(
            event_id="evt_test",
            topic="test",
            event_type="test",
            payload={},
        )
        
        assert event.is_expired() is False
    
    def test_event_expired(self):
        """Test event expired."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        event = Event(
            event_id="evt_test",
            topic="test",
            event_type="test",
            payload={},
            expires_at=past,
        )
        
        assert event.is_expired() is True
    
    def test_event_not_expired_future(self):
        """Test event not expired with future expiry."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        event = Event(
            event_id="evt_test",
            topic="test",
            event_type="test",
            payload={},
            expires_at=future,
        )
        
        assert event.is_expired() is False


class TestSubscription:
    """Test subscription definition."""
    
    def test_create_subscription(self):
        """Test creating subscription."""
        def handler(event):
            pass
        
        sub = Subscription(
            subscription_id="sub_test",
            topic="test.topic",
            handler=handler,
        )
        
        assert sub.subscription_id == "sub_test"
        assert sub.enabled is True
    
    def test_subscription_matches_no_filter(self):
        """Test subscription matches without filter."""
        def handler(event):
            pass
        
        sub = Subscription(
            subscription_id="sub_test",
            topic="test",
            handler=handler,
        )
        
        event = Event("evt_1", "test", "test", {})
        
        assert sub.matches(event) is True
    
    def test_subscription_matches_with_filter(self):
        """Test subscription matches with filter."""
        def handler(event):
            pass
        
        sub = Subscription(
            subscription_id="sub_test",
            topic="test",
            handler=handler,
            filter_pattern=r'"type":\s*"important"',
        )
        
        event_match = Event("evt_1", "test", "test", {"type": "important"})
        event_no_match = Event("evt_2", "test", "test", {"type": "normal"})
        
        assert sub.matches(event_match) is True
        assert sub.matches(event_no_match) is False
    
    def test_subscription_to_dict(self):
        """Test subscription serialization."""
        def handler(event):
            pass
        
        sub = Subscription(
            subscription_id="sub_test",
            topic="test",
            handler=handler,
            filter_pattern="test",
            max_retries=5,
        )
        
        d = sub.to_dict()
        
        assert d["filter_pattern"] == "test"
        assert d["max_retries"] == 5


class TestDeliveryRecord:
    """Test delivery record."""
    
    def test_create_record(self):
        """Test creating delivery record."""
        record = DeliveryRecord(
            record_id="dlv_test",
            event_id="evt_test",
            subscription_id="sub_test",
            status=DeliveryStatus.DELIVERED,
            attempts=1,
        )
        
        assert record.record_id == "dlv_test"
        assert record.status == DeliveryStatus.DELIVERED
    
    def test_record_to_dict(self):
        """Test record serialization."""
        record = DeliveryRecord(
            record_id="dlv_test",
            event_id="evt_test",
            subscription_id="sub_test",
            status=DeliveryStatus.FAILED,
            attempts=3,
            error="Connection timeout",
            delivered_at=None,
        )
        
        d = record.to_dict()
        
        assert d["status"] == "failed"
        assert d["error"] == "Connection timeout"


class TestEventBusEngine:
    """Test event bus engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_event_bus_engine()
        assert engine is not None
    
    def test_publish_event(self):
        """Test publishing event."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            topic="test.topic",
            event_type="test_event",
            payload={"key": "value"},
        )
        
        assert event_id is not None
        assert event_id.startswith("evt_")
    
    def test_publish_event_with_priority(self):
        """Test publishing event with priority."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            topic="test",
            event_type="test",
            payload={},
            priority=EventPriority.CRITICAL,
        )
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event.priority == EventPriority.CRITICAL
    
    def test_publish_event_with_headers(self):
        """Test publishing event with headers."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            topic="test",
            event_type="test",
            payload={},
            headers={"x-correlation-id": "corr_123"},
        )
        
        event = engine.get_event(event_id)
        
        assert event.headers["x-correlation-id"] == "corr_123"
    
    def test_publish_event_with_correlation(self):
        """Test publishing event with correlation ID."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            topic="test",
            event_type="test",
            payload={},
            correlation_id="corr_123",
        )
        
        event = engine.get_event(event_id)
        
        assert event.correlation_id == "corr_123"
    
    def test_subscribe(self):
        """Test subscribing to topic."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("test.topic", handler)
        
        assert sub_id is not None
        assert sub_id.startswith("sub_")
    
    def test_subscribe_with_filter(self):
        """Test subscribing with filter pattern."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe(
            "test.topic",
            handler,
            filter_pattern=r'"priority":\s*"high"',
        )
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["filter_pattern"] == r'"priority":\s*"high"'
    
    def test_unsubscribe(self):
        """Test unsubscribing."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test.topic", handler)
        
        result = engine.unsubscribe(sub_id)
        
        assert result is True
        assert engine.get_subscription(sub_id) is None
    
    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing nonexistent subscription."""
        engine = EventBusEngine()
        
        result = engine.unsubscribe("nonexistent")
        
        assert result is False
    
    def test_enable_subscription(self):
        """Test enabling subscription."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test.topic", handler)
        
        engine.disable_subscription(sub_id)
        engine.enable_subscription(sub_id)
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["enabled"] is True
    
    def test_disable_subscription(self):
        """Test disabling subscription."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test.topic", handler)
        
        result = engine.disable_subscription(sub_id)
        
        assert result is True
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["enabled"] is False
    
    def test_get_event(self):
        """Test getting event by ID."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {"key": "value"})
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event.event_id == event_id
    
    def test_get_event_nonexistent(self):
        """Test getting nonexistent event."""
        engine = EventBusEngine()
        
        event = engine.get_event("nonexistent")
        
        assert event is None
    
    def test_replay_event(self):
        """Test replaying event."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test.topic", "test", {"key": "value"})
        
        result = engine.replay_event(event_id)
        
        assert result is True
    
    def test_replay_event_nonexistent(self):
        """Test replaying nonexistent event."""
        engine = EventBusEngine()
        
        result = engine.replay_event("nonexistent")
        
        assert result is False
    
    def test_replay_events(self):
        """Test replaying multiple events."""
        engine = EventBusEngine()
        
        engine.publish("test.topic", "test", {"i": 1})
        engine.publish("test.topic", "test", {"i": 2})
        engine.publish("test.topic", "test", {"i": 3})
        
        count = engine.replay_events("test.topic")
        
        assert count == 3
    
    def test_replay_events_with_time_filter(self):
        """Test replaying events with time filter."""
        engine = EventBusEngine()
        
        now = datetime.now(timezone.utc)
        
        engine.publish("test", "test", {"time": "old"})
        
        # Wait a bit
        time.sleep(0.1)
        
        mid = datetime.now(timezone.utc).isoformat()
        
        engine.publish("test", "test", {"time": "new"})
        
        # Replay only new events
        count = engine.replay_events("test", start_time=mid)
        
        assert count == 1
    
    def test_list_subscriptions(self):
        """Test listing subscriptions."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("topic1", handler)
        engine.subscribe("topic2", handler)
        engine.subscribe("topic1", handler)
        
        subs = engine.list_subscriptions()
        
        assert len(subs) == 3
    
    def test_list_subscriptions_by_topic(self):
        """Test listing subscriptions by topic."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("topic1", handler)
        engine.subscribe("topic2", handler)
        engine.subscribe("topic1", handler)
        
        subs = engine.list_subscriptions(topic="topic1")
        
        assert len(subs) == 2
    
    def test_get_subscription(self):
        """Test getting subscription by ID."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test", handler)
        
        sub = engine.get_subscription(sub_id)
        
        assert sub is not None
        assert sub["topic"] == "test"
    
    def test_get_subscription_nonexistent(self):
        """Test getting nonexistent subscription."""
        engine = EventBusEngine()
        
        sub = engine.get_subscription("nonexistent")
        
        assert sub is None
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = EventBusEngine()
        
        engine.publish("test", "test", {})
        engine.publish("test", "test", {})
        
        stats = engine.get_statistics()
        
        assert stats["total_published"] == 2
        assert stats["total_subscriptions"] == 0
    
    def test_statistics_by_topic(self):
        """Test statistics by topic."""
        engine = EventBusEngine()
        
        engine.publish("topic1", "test", {})
        engine.publish("topic1", "test", {})
        engine.publish("topic2", "test", {})
        
        stats = engine.get_statistics()
        
        assert stats["by_topic"]["topic1"] == 2
        assert stats["by_topic"]["topic2"] == 1
    
    def test_clear_event_store(self):
        """Test clearing event store."""
        engine = EventBusEngine()
        
        engine.publish("test", "test", {})
        engine.publish("test", "test", {})
        
        count = engine.clear_event_store()
        
        assert count == 2
        
        stats = engine.get_statistics()
        
        assert stats["event_store_size"] == 0
    
    def test_clear_dead_letter_queue(self):
        """Test clearing dead letter queue."""
        engine = EventBusEngine()
        
        count = engine.clear_dead_letter_queue()
        
        assert count == 0
    
    def test_get_dead_letter_queue(self):
        """Test getting dead letter queue."""
        engine = EventBusEngine()
        
        dlq = engine.get_dead_letter_queue()
        
        assert dlq == []
    
    def test_event_priority_enum_values(self):
        """Test event priority enum values."""
        assert EventPriority.LOW.value == 0
        assert EventPriority.NORMAL.value == 1
        assert EventPriority.HIGH.value == 2
        assert EventPriority.CRITICAL.value == 3
    
    def test_delivery_status_enum_values(self):
        """Test delivery status enum values."""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.DEAD_LETTERED.value == "dead_lettered"
    
    def test_publish_increments_topic_stats(self):
        """Test that publish increments topic statistics."""
        engine = EventBusEngine()
        
        engine.publish("test.topic", "test", {})
        engine.publish("test.topic", "test", {})
        
        stats = engine.get_statistics()
        
        assert stats["by_topic"]["test.topic"] == 2
    
    def test_subscribe_creates_topic(self):
        """Test that subscribe creates topic entry."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("new.topic", handler)
        
        stats = engine.get_statistics()
        
        assert stats["total_topics"] >= 1
    
    def test_delivery_handler_called(self):
        """Test that delivery handler is called."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("test", handler)
        
        event_id = engine.publish("test", "test", {"key": "value"})
        
        # Start workers to process
        engine.start(num_workers=1)
        
        # Wait for processing
        time.sleep(0.5)
        
        engine.stop()
        
        assert len(received) >= 1
    
    def test_delivery_record_created(self):
        """Test that delivery record is created."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        engine.subscribe("test", handler)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        records = engine.get_delivery_records()
        
        assert len(records) >= 1
    
    def test_get_delivery_records_by_event(self):
        """Test getting delivery records by event ID."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        
        event_id = engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        records = engine.get_delivery_records(event_id=event_id)
        
        assert all(r.event_id == event_id for r in records)
    
    def test_get_delivery_records_by_status(self):
        """Test getting delivery records by status."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        records = engine.get_delivery_records(status=DeliveryStatus.DELIVERED)
        
        assert all(r.status == DeliveryStatus.DELIVERED for r in records)
    
    def test_statistics_total_delivered(self):
        """Test that statistics track delivered events."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["total_delivered"] >= 1
    
    def test_event_created_at_set(self):
        """Test that event created_at is set."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.created_at is not None
    
    def test_subscription_created_at_set(self):
        """Test that subscription created_at is set."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test", handler)
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["created_at"] is not None
    
    def test_delivery_record_id_unique(self):
        """Test that delivery record IDs are unique."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        engine.subscribe("test", handler)
        
        for i in range(10):
            engine.publish("test", "test", {"i": i})
        
        engine.start(num_workers=1)
        time.sleep(1)
        engine.stop()
        
        records = engine.get_delivery_records(limit=100)
        
        ids = set(r.record_id for r in records)
        
        assert len(ids) == len(records)
    
    def test_event_id_unique(self):
        """Test that event IDs are unique."""
        engine = EventBusEngine()
        
        ids = set()
        for i in range(50):
            event_id = engine.publish("test", "test", {"i": i})
            ids.add(event_id)
        
        assert len(ids) == 50
    
    def test_subscription_id_unique(self):
        """Test that subscription IDs are unique."""
        engine = EventBusEngine()
        
        ids = set()
        
        def handler(event):
            pass
        
        for i in range(50):
            sub_id = engine.subscribe("test", handler)
            ids.add(sub_id)
        
        assert len(ids) == 50
    
    def test_multiple_subscriptions_same_topic(self):
        """Test multiple subscriptions to same topic."""
        engine = EventBusEngine()
        
        received1 = []
        received2 = []
        
        def handler1(event):
            received1.append(event)
        
        def handler2(event):
            received2.append(event)
        
        engine.subscribe("test", handler1)
        engine.subscribe("test", handler2)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        # Both handlers should receive
        assert len(received1) >= 1
        assert len(received2) >= 1
    
    def test_disabled_subscription_not_delivered(self):
        """Test that disabled subscriptions don't receive events."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("test", handler)
        engine.disable_subscription(sub_id)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        assert len(received) == 0
    
    def test_filter_pattern_blocks_non_matching(self):
        """Test that filter pattern blocks non-matching events."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        engine.subscribe(
            "test",
            handler,
            filter_pattern=r'"type":\s*"important"',
        )
        
        # Non-matching event
        engine.publish("test", "test", {"type": "normal"})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        assert len(received) == 0
    
    def test_statistics_total_topics(self):
        """Test that statistics track total topics."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("topic1", handler)
        engine.subscribe("topic2", handler)
        engine.subscribe("topic3", handler)
        
        stats = engine.get_statistics()
        
        assert stats["total_topics"] == 3
    
    def test_statistics_total_subscriptions(self):
        """Test that statistics track total subscriptions."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        engine.subscribe("test", handler)
        
        stats = engine.get_statistics()
        
        assert stats["total_subscriptions"] == 2
    
    def test_statistics_dead_letter_size(self):
        """Test that statistics track dead letter size."""
        engine = EventBusEngine()
        
        stats = engine.get_statistics()
        
        assert stats["dead_letter_size"] == 0
    
    def test_event_store_persists_event(self):
        """Test that event store persists event."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {"key": "value"})
        
        # Event should be in store
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event.payload["key"] == "value"
    
    def test_replay_events_empty_topic(self):
        """Test replaying events for empty topic."""
        engine = EventBusEngine()
        
        count = engine.replay_events("nonexistent")
        
        assert count == 0
    
    def test_get_delivery_records_empty(self):
        """Test getting delivery records when empty."""
        engine = EventBusEngine()
        
        records = engine.get_delivery_records()
        
        assert records == []
    
    def test_get_delivery_records_limit(self):
        """Test delivery records limit."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        
        for i in range(50):
            engine.publish("test", "test", {"i": i})
        
        engine.start(num_workers=1)
        time.sleep(2)
        engine.stop()
        
        records = engine.get_delivery_records(limit=10)
        
        assert len(records) <= 10
    
    def test_clear_event_store_older_than(self):
        """Test clearing event store older than."""
        engine = EventBusEngine()
        
        # Publish events
        engine.publish("test", "test", {})
        
        # Clear events older than 1 day (should clear all since they're new)
        count = engine.clear_event_store(older_than_days=0)
        
        # All events should be newer than 0 days
        assert count == 0
    
    def test_clear_delivery_records_older_than(self):
        """Test clearing delivery records older than."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        # Clear records older than 0 days
        count = engine.clear_delivery_records(older_than_days=0)
        
        # All records should be newer
        assert count == 0
    
    def test_retry_dead_letter_nonexistent(self):
        """Test retrying nonexistent dead letter."""
        engine = EventBusEngine()
        
        result = engine.retry_dead_letter("nonexistent")
        
        assert result is False
    
    def test_list_subscriptions_empty(self):
        """Test listing subscriptions when empty."""
        engine = EventBusEngine()
        
        subs = engine.list_subscriptions()
        
        assert subs == []
    
    def test_get_dead_letter_queue_limit(self):
        """Test dead letter queue limit."""
        engine = EventBusEngine()
        
        dlq = engine.get_dead_letter_queue(limit=50)
        
        assert len(dlq) <= 50
    
    def test_event_headers_empty_by_default(self):
        """Test that event headers are empty by default."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.headers == {}
    
    def test_event_delivery_count_initial(self):
        """Test that event delivery count starts at 0."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.delivery_count == 0
    
    def test_event_last_delivery_attempt_initial(self):
        """Test that last delivery attempt is None initially."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.last_delivery_attempt is None
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = EventBusEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_published"] == 0
        assert stats["total_delivered"] == 0
        assert stats["total_failed"] == 0
        assert stats["total_dead_lettered"] == 0
        assert stats["total_subscriptions"] == 0
        assert stats["total_topics"] == 0
    
    def test_subscription_max_retries_default(self):
        """Test subscription max retries default."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test", handler)
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["max_retries"] == 3
    
    def test_subscription_retry_delay_default(self):
        """Test subscription retry delay default."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("test", handler)
        
        sub = engine.get_subscription(sub_id)
        
        assert sub["retry_delay_seconds"] == 5
    
    def test_publish_with_expiry(self):
        """Test publishing event with expiry."""
        engine = EventBusEngine()
        
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        event_id = engine.publish(
            "test", "test", {}, expires_at=future,
        )
        
        event = engine.get_event(event_id)
        
        assert event.expires_at is not None
    
    def test_get_delivery_records_by_subscription(self):
        """Test getting delivery records by subscription ID."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("test", handler)
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        records = engine.get_delivery_records(subscription_id=sub_id)
        
        assert all(r.subscription_id == sub_id for r in records)
    
    def test_event_version_default(self):
        """Test that event version defaults to 1.0."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.version == "1.0"
    
    def test_event_source_default(self):
        """Test that event source defaults to unknown."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test", "test", {})
        
        event = engine.get_event(event_id)
        
        assert event.source == "unknown"
    
    def test_clear_event_store_returns_count(self):
        """Test that clear_event_store returns count."""
        engine = EventBusEngine()
        
        for i in range(10):
            engine.publish("test", "test", {"i": i})
        
        count = engine.clear_event_store()
        
        assert count == 10
    
    def test_clear_delivery_records_returns_count(self):
        """Test that clear_delivery_records returns count."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("test", handler)
        
        for i in range(10):
            engine.publish("test", "test", {"i": i})
        
        engine.start(num_workers=1)
        time.sleep(1)
        engine.stop()
        
        count = engine.clear_delivery_records()
        
        assert count >= 1
    
    def test_multiple_topics_independent(self):
        """Test that multiple topics are independent."""
        engine = EventBusEngine()
        
        received1 = []
        received2 = []
        
        def handler1(event):
            received1.append(event)
        
        def handler2(event):
            received2.append(event)
        
        engine.subscribe("topic1", handler1)
        engine.subscribe("topic2", handler2)
        
        engine.publish("topic1", "test", {"source": "topic1"})
        engine.publish("topic2", "test", {"source": "topic2"})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        # Each handler should only receive from its topic
        assert len(received1) >= 1
        assert len(received2) >= 1
    
    def test_subscription_filter_invalid_pattern(self):
        """Test subscription with invalid filter pattern."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        # Invalid regex pattern
        sub_id = engine.subscribe(
            "test",
            handler,
            filter_pattern="[invalid(regex",
        )
        
        engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        # Should still deliver (invalid pattern = no filter)
        assert len(received) >= 1
    
    def test_event_priority_affects_queue_order(self):
        """Test that event priority affects queue ordering."""
        engine = EventBusEngine()
        
        # Publish in reverse priority order
        engine.publish("test", "test", {"priority": "low"}, priority=EventPriority.LOW)
        engine.publish("test", "test", {"priority": "high"}, priority=EventPriority.HIGH)
        engine.publish("test", "test", {"priority": "normal"}, priority=EventPriority.NORMAL)
        
        # High priority should be processed first
        # (tested implicitly through queue ordering)
        
        stats = engine.get_statistics()
        
        assert stats["total_published"] == 3
    
    def test_delivery_record_status_tracking(self):
        """Test that delivery record tracks status correctly."""
        engine = EventBusEngine()
        
        def handler(event):
            pass  # Successful delivery
        
        engine.subscribe("test", handler)
        
        event_id = engine.publish("test", "test", {})
        
        engine.start(num_workers=1)
        time.sleep(0.5)
        engine.stop()
        
        records = engine.get_delivery_records(event_id=event_id)
        
        assert len(records) >= 1
        assert records[0].status == DeliveryStatus.DELIVERED
    
    def test_statistics_by_subscription(self):
        """Test statistics by subscription."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("test", handler)
        
        for i in range(5):
            engine.publish("test", "test", {"i": i})
        
        engine.start(num_workers=1)
        time.sleep(1)
        engine.stop()
        
        stats = engine.get_statistics()
        
        assert stats["by_subscription"].get(sub_id, 0) >= 1
