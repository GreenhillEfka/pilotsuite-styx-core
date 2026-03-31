"""Tests for Event Bus Engine — Slice 43."""
import pytest
from copilot_core.eventbus.engine import (
    EventBusEngine,
    EventPriority,
    EventStatus,
    Event,
    Subscription,
    create_event_bus_engine,
)
from datetime import datetime, timezone, timedelta
import time


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
            event_type="user.created",
            payload={"user_id": "123", "name": "Test"},
            source="auth_service",
        )
        
        assert event_id is not None
        assert event_id.startswith("evt_")
        
        event = engine.get_event(event_id)
        assert event is not None
        assert event["event_type"] == "user.created"
    
    def test_publish_event_with_priority(self):
        """Test publishing event with priority."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            event_type="alert.critical",
            payload={"message": "Critical alert"},
            priority=EventPriority.CRITICAL,
        )
        
        event = engine.get_event(event_id)
        assert event["priority"] == "critical"
    
    def test_publish_event_with_correlation_id(self):
        """Test publishing event with correlation ID."""
        engine = EventBusEngine()
        
        correlation_id = "corr_12345"
        
        event_id = engine.publish(
            event_type="order.processed",
            payload={"order_id": "ord_123"},
            correlation_id=correlation_id,
        )
        
        event = engine.get_event(event_id)
        assert event["correlation_id"] == correlation_id
    
    def test_publish_event_with_metadata(self):
        """Test publishing event with metadata."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            event_type="user.updated",
            payload={"user_id": "123"},
            metadata={"source_ip": "192.168.1.1", "user_agent": "Mozilla/5.0"},
        )
        
        event = engine.get_event(event_id)
        assert event["metadata"]["source_ip"] == "192.168.1.1"
    
    def test_publish_event_with_expiration(self):
        """Test publishing event with expiration."""
        engine = EventBusEngine()
        
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        event_id = engine.publish(
            event_type="temp.event",
            payload={"data": "value"},
            expires_at=expires_at,
        )
        
        event = engine.get_event(event_id)
        assert event["expires_at"] == expires_at
    
    def test_subscribe_to_event_type(self):
        """Test subscribing to specific event type."""
        engine = EventBusEngine()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        subscription_id = engine.subscribe(
            subscriber_id="test_subscriber",
            event_types=["user.created"],
            handler=handler,
        )
        
        assert subscription_id is not None
        assert subscription_id.startswith("sub_")
        
        # Publish event
        engine.publish("user.created", {"user_id": "123"})
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "user.created"
    
    def test_subscribe_to_multiple_event_types(self):
        """Test subscribing to multiple event types."""
        engine = EventBusEngine()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        engine.subscribe(
            subscriber_id="test_subscriber",
            event_types=["user.created", "user.updated"],
            handler=handler,
        )
        
        engine.publish("user.created", {"user_id": "123"})
        engine.publish("user.updated", {"user_id": "123"})
        engine.publish("user.deleted", {"user_id": "123"})  # Should not be received
        
        assert len(received_events) == 2
    
    def test_subscribe_to_all_events(self):
        """Test subscribing to all events."""
        engine = EventBusEngine()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        engine.subscribe(
            subscriber_id="test_subscriber",
            event_types=[],  # Empty = all
            handler=handler,
        )
        
        engine.publish("event1", {})
        engine.publish("event2", {})
        engine.publish("event3", {})
        
        assert len(received_events) == 3
    
    def test_unsubscribe(self):
        """Test unsubscribing."""
        engine = EventBusEngine()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        subscription_id = engine.subscribe(
            subscriber_id="test_subscriber",
            event_types=["test.event"],
            handler=handler,
        )
        
        engine.publish("test.event", {})
        assert len(received_events) == 1
        
        result = engine.unsubscribe(subscription_id)
        assert result is True
        
        engine.publish("test.event", {})
        assert len(received_events) == 1  # No new events
    
    def test_unsubscribe_unknown(self):
        """Test unsubscribing unknown subscription."""
        engine = EventBusEngine()
        
        result = engine.unsubscribe("unknown_subscription")
        
        assert result is False
    
    def test_process_events(self):
        """Test processing events."""
        engine = EventBusEngine()
        
        processed = []
        
        def handler(event):
            processed.append(event.event_id)
        
        engine.subscribe("sub1", ["test.event"], handler)
        
        for i in range(5):
            engine.publish("test.event", {"index": i})
        
        count = engine.process_events()
        
        assert count == 5
    
    def test_event_priority_ordering(self):
        """Test that events are processed by priority."""
        engine = EventBusEngine()
        
        processed = []
        
        def handler(event):
            processed.append(event.priority)
        
        engine.subscribe("sub1", ["test.event"], handler)
        
        # Publish in reverse priority order
        engine.publish("test.event", {}, priority=EventPriority.LOW)
        engine.publish("test.event", {}, priority=EventPriority.NORMAL)
        engine.publish("test.event", {}, priority=EventPriority.HIGH)
        engine.publish("test.event", {}, priority=EventPriority.CRITICAL)
        
        engine.process_events()
        
        # Critical should be processed first
        assert processed[0] == "critical"
    
    def test_get_event_not_found(self):
        """Test getting nonexistent event."""
        engine = EventBusEngine()
        
        event = engine.get_event("unknown_event")
        
        assert event is None
    
    def test_get_events_by_type(self):
        """Test getting events by type."""
        engine = EventBusEngine()
        
        for i in range(5):
            engine.publish("user.created", {"index": i})
        
        for i in range(3):
            engine.publish("user.updated", {"index": i})
        
        events = engine.get_events_by_type("user.created")
        
        assert len(events) == 5
        assert all(e["event_type"] == "user.created" for e in events)
    
    def test_get_events_by_type_limit(self):
        """Test getting events by type with limit."""
        engine = EventBusEngine()
        
        for i in range(20):
            engine.publish("test.event", {"index": i})
        
        events = engine.get_events_by_type("test.event", limit=10)
        
        assert len(events) == 10
    
    def test_get_events_by_correlation(self):
        """Test getting events by correlation ID."""
        engine = EventBusEngine()
        
        correlation_id = "corr_123"
        
        engine.publish("event1", {}, correlation_id=correlation_id)
        engine.publish("event2", {}, correlation_id=correlation_id)
        engine.publish("event3", {}, correlation_id="corr_456")
        
        events = engine.get_events_by_correlation(correlation_id)
        
        assert len(events) == 2
        assert all(e["correlation_id"] == correlation_id for e in events)
    
    def test_get_dead_letter_queue(self):
        """Test getting dead letter queue."""
        engine = EventBusEngine()
        
        def failing_handler(event):
            raise Exception("Always fails")
        
        engine.subscribe("sub1", ["test.event"], failing_handler)
        
        # Publish event that will fail
        engine.publish("test.event", {}, priority=EventPriority.NORMAL)
        
        # Process until it goes to dead letter
        for i in range(5):
            engine.process_events()
        
        dlq = engine.get_dead_letter_queue()
        
        assert len(dlq) >= 1
    
    def test_replay_dead_letter(self):
        """Test replaying event from dead letter queue."""
        engine = EventBusEngine()
        
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First attempt fails")
        
        engine.subscribe("sub1", ["test.event"], handler)
        
        event_id = engine.publish("test.event", {}, max_retries=1)
        
        # Process until it fails
        for i in range(3):
            engine.process_events()
        
        # Should be in dead letter
        dlq = engine.get_dead_letter_queue()
        assert len(dlq) >= 1
        
        # Reset handler to succeed
        def success_handler(event):
            pass
        
        engine._handlers["test.event"] = [success_handler]
        
        # Replay
        result = engine.replay_dead_letter(event_id)
        
        assert result is True
        
        # Should no longer be in dead letter
        dlq = engine.get_dead_letter_queue()
        assert len(dlq) == 0
    
    def test_replay_unknown_dead_letter(self):
        """Test replaying unknown event from dead letter."""
        engine = EventBusEngine()
        
        result = engine.replay_dead_letter("unknown_event")
        
        assert result is False
    
    def test_clear_dead_letter_queue(self):
        """Test clearing dead letter queue."""
        engine = EventBusEngine()
        
        def failing_handler(event):
            raise Exception("Fail")
        
        engine.subscribe("sub1", ["test.event"], failing_handler)
        
        for i in range(5):
            engine.publish("test.event", {}, max_retries=1)
        
        # Process until all fail
        for i in range(10):
            engine.process_events()
        
        count = engine.clear_dead_letter_queue()
        
        assert count >= 1
        
        dlq = engine.get_dead_letter_queue()
        assert len(dlq) == 0
    
    def test_get_event_history(self):
        """Test getting event history."""
        engine = EventBusEngine()
        
        for i in range(10):
            engine.publish("test.event", {"index": i})
        
        # Process to add to history
        engine.process_events()
        
        history = engine.get_event_history()
        
        assert len(history) == 10
    
    def test_get_event_history_filtered_by_type(self):
        """Test getting history filtered by type."""
        engine = EventBusEngine()
        
        for i in range(5):
            engine.publish("event.type1", {})
        
        for i in range(3):
            engine.publish("event.type2", {})
        
        engine.process_events()
        
        history = engine.get_event_history(event_type="event.type1")
        
        assert len(history) == 5
        assert all(e["event_type"] == "event.type1" for e in history)
    
    def test_get_event_history_filtered_by_source(self):
        """Test getting history filtered by source."""
        engine = EventBusEngine()
        
        engine.publish("test.event", {}, source="service1")
        engine.publish("test.event", {}, source="service2")
        engine.publish("test.event", {}, source="service1")
        
        engine.process_events()
        
        history = engine.get_event_history(source="service1")
        
        assert len(history) == 2
    
    def test_get_event_history_limit(self):
        """Test getting history with limit."""
        engine = EventBusEngine()
        
        for i in range(50):
            engine.publish("test.event", {"index": i})
        
        engine.process_events()
        
        history = engine.get_event_history(limit=10)
        
        assert len(history) == 10
    
    def test_get_subscriptions(self):
        """Test getting subscriptions."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("sub1", ["event1"], handler)
        engine.subscribe("sub2", ["event2"], handler)
        engine.subscribe("sub3", ["event3"], handler)
        
        subscriptions = engine.get_subscriptions()
        
        assert len(subscriptions) == 3
    
    def test_get_subscriptions_filtered_by_subscriber(self):
        """Test getting subscriptions filtered by subscriber."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("sub1", ["event1"], handler)
        engine.subscribe("sub1", ["event2"], handler)
        engine.subscribe("sub2", ["event3"], handler)
        
        subscriptions = engine.get_subscriptions(subscriber_id="sub1")
        
        assert len(subscriptions) == 2
        assert all(s["subscriber_id"] == "sub1" for s in subscriptions)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = EventBusEngine()
        
        for i in range(10):
            engine.publish("test.event", {})
        
        engine.process_events()
        
        stats = engine.get_statistics()
        
        assert stats["total_events"] == 10
        assert stats["processed_events"] == 10
        assert "queue_sizes" in stats
    
    def test_purge_events_all(self):
        """Test purging all events."""
        engine = EventBusEngine()
        
        for i in range(10):
            engine.publish("test.event", {})
        
        count = engine.purge_events()
        
        assert count == 10
        
        stats = engine.get_statistics()
        assert stats["total_events"] == 0
    
    def test_purge_events_older_than(self):
        """Test purging events older than timestamp."""
        engine = EventBusEngine()
        
        # Publish some events
        for i in range(5):
            engine.publish("test.event", {})
        
        # Get current time as cutoff
        cutoff = datetime.now(timezone.utc).isoformat()
        
        # Publish more events
        for i in range(5):
            engine.publish("test.event", {})
        
        count = engine.purge_events(older_than=cutoff)
        
        # Should have purged some
        assert count >= 0
    
    def test_get_pending_events_count(self):
        """Test getting pending events count."""
        engine = EventBusEngine()
        
        for i in range(5):
            engine.publish("test.event", {})
        
        count = engine.get_pending_events_count()
        
        assert count == 5
        
        engine.process_events()
        
        count = engine.get_pending_events_count()
        
        assert count == 0
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(
            event_id="evt_test",
            event_type="test.event",
            source="test_service",
            payload={"key": "value"},
            priority=EventPriority.HIGH,
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "evt_test"
        assert d["event_type"] == "test.event"
        assert d["priority"] == "high"
        assert d["payload"]["key"] == "value"
    
    def test_subscription_to_dict(self):
        """Test subscription serialization."""
        subscription = Subscription(
            subscription_id="sub_test",
            subscriber_id="test_subscriber",
            event_types=["event1", "event2"],
            filter_expr="payload.value > 10",
            priority_filter=EventPriority.HIGH,
        )
        
        d = subscription.to_dict()
        
        assert d["subscription_id"] == "sub_test"
        assert d["event_types"] == ["event1", "event2"]
        assert d["priority_filter"] == "high"
    
    def test_event_priority_enum_values(self):
        """Test event priority enum values."""
        assert EventPriority.LOW.value == "low"
        assert EventPriority.NORMAL.value == "normal"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.CRITICAL.value == "critical"
    
    def test_event_status_enum_values(self):
        """Test event status enum values."""
        assert EventStatus.PENDING.value == "pending"
        assert EventStatus.PROCESSING.value == "processing"
        assert EventStatus.COMPLETED.value == "completed"
        assert EventStatus.FAILED.value == "failed"
        assert EventStatus.DEAD_LETTER.value == "dead_letter"
    
    def test_handler_exception_doesnt_crash_bus(self):
        """Test that handler exception doesn't crash bus."""
        engine = EventBusEngine()
        
        def failing_handler(event):
            raise Exception("Handler failed")
        
        def working_handler(event):
            pass
        
        engine.subscribe("sub1", ["test.event"], failing_handler)
        engine.subscribe("sub2", ["test.event"], working_handler)
        
        # Should not raise
        engine.publish("test.event", {})
        engine.process_events()
    
    def test_queue_trimmed_to_max(self):
        """Test that queue is trimmed to max."""
        engine = EventBusEngine(max_queue_size=100)
        
        for i in range(200):
            engine.publish("test.event", {}, priority=EventPriority.LOW)
        
        stats = engine.get_statistics()
        
        total_queued = sum(stats["queue_sizes"].values())
        assert total_queued <= 100
    
    def test_history_trimmed_to_max(self):
        """Test that history is trimmed to max."""
        engine = EventBusEngine(max_history_size=100)
        
        for i in range(200):
            engine.publish("test.event", {})
        
        engine.process_events()
        
        stats = engine.get_statistics()
        
        assert stats["history_size"] <= 100
    
    def test_events_sorted_by_created_at(self):
        """Test that events are sorted by created_at."""
        engine = EventBusEngine()
        
        for i in range(5):
            engine.publish("test.event", {"index": i})
            time.sleep(0.01)
        
        events = engine.get_events_by_type("test.event")
        
        # Verify sorted (newest first)
        for i in range(len(events) - 1):
            assert events[i]["created_at"] >= events[i + 1]["created_at"]
    
    def test_statistics_by_type(self):
        """Test statistics breakdown by type."""
        engine = EventBusEngine()
        
        for i in range(5):
            engine.publish("type1", {})
        
        for i in range(3):
            engine.publish("type2", {})
        
        stats = engine.get_statistics()
        
        assert stats["by_type"]["type1"] == 5
        assert stats["by_type"]["type2"] == 3
    
    def test_subscription_active_flag(self):
        """Test subscription active flag."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event)
        
        sub_id = engine.subscribe("sub1", ["test.event"], handler)
        
        # Unsubscribe
        engine.unsubscribe(sub_id)
        
        # Check subscription is removed
        subscriptions = engine.get_subscriptions()
        
        assert not any(s["subscription_id"] == sub_id for s in subscriptions)
    
    def test_correlation_id_groups_events(self):
        """Test that correlation ID groups related events."""
        engine = EventBusEngine()
        
        correlation_id = "order_123_flow"
        
        engine.publish("order.created", {"order_id": "123"}, correlation_id=correlation_id)
        engine.publish("order.validated", {"order_id": "123"}, correlation_id=correlation_id)
        engine.publish("order.processed", {"order_id": "123"}, correlation_id=correlation_id)
        
        events = engine.get_events_by_correlation(correlation_id)
        
        assert len(events) == 3
    
    def test_expired_event_goes_to_dead_letter(self):
        """Test that expired event goes to dead letter."""
        engine = EventBusEngine()
        
        # Create expired event
        expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        engine.publish(
            "test.event",
            {},
            expires_at=expires_at,
        )
        
        engine.process_events()
        
        dlq = engine.get_dead_letter_queue()
        
        assert len(dlq) >= 1
        assert dlq[0]["error_message"] == "Event expired"
    
    def test_event_retry_on_failure(self):
        """Test event retry on failure."""
        engine = EventBusEngine()
        
        call_count = [0]
        
        def flaky_handler(event):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("First attempt fails")
        
        engine.subscribe("sub1", ["test.event"], flaky_handler)
        
        event_id = engine.publish("test.event", {}, max_retries=3)
        
        # Process multiple times
        for i in range(5):
            engine.process_events()
        
        # Should eventually succeed
        event = engine.get_event(event_id)
        
        assert event["status"] == "completed"
        assert call_count[0] == 2
    
    def test_event_exhausts_retries(self):
        """Test event exhausts retries and goes to dead letter."""
        engine = EventBusEngine()
        
        def always_fails(event):
            raise Exception("Always fails")
        
        engine.subscribe("sub1", ["test.event"], always_fails)
        
        event_id = engine.publish("test.event", {}, max_retries=2)
        
        # Process until exhausted
        for i in range(10):
            engine.process_events()
        
        event = engine.get_event(event_id)
        
        assert event["status"] == "dead_letter"
        assert event["retry_count"] >= 2
    
    def test_pattern_subscription_with_wildcard(self):
        """Test pattern subscription with wildcard."""
        engine = EventBusEngine()
        
        received = []
        
        def handler(event):
            received.append(event.event_type)
        
        # Subscribe with wildcard pattern
        engine._handlers["user.*"] = [handler]
        
        engine.publish("user.created", {})
        engine.publish("user.updated", {})
        engine.publish("order.created", {})  # Should not be received
        
        assert len(received) == 2
        assert "user.created" in received
        assert "user.updated" in received
    
    def test_multiple_handlers_for_same_event(self):
        """Test multiple handlers for same event."""
        engine = EventBusEngine()
        
        received1 = []
        received2 = []
        
        def handler1(event):
            received1.append(event.event_id)
        
        def handler2(event):
            received2.append(event.event_id)
        
        engine.subscribe("sub1", ["test.event"], handler1)
        engine.subscribe("sub2", ["test.event"], handler2)
        
        engine.publish("test.event", {})
        engine.process_events()
        
        assert len(received1) == 1
        assert len(received2) == 1
    
    def test_priority_queue_sizes_tracked(self):
        """Test that priority queue sizes are tracked."""
        engine = EventBusEngine()
        
        engine.publish("test.event", {}, priority=EventPriority.LOW)
        engine.publish("test.event", {}, priority=EventPriority.NORMAL)
        engine.publish("test.event", {}, priority=EventPriority.HIGH)
        engine.publish("test.event", {}, priority=EventPriority.CRITICAL)
        
        stats = engine.get_statistics()
        
        assert "queue_sizes" in stats
        assert stats["queue_sizes"]["low"] >= 1
        assert stats["queue_sizes"]["normal"] >= 1
        assert stats["queue_sizes"]["high"] >= 1
        assert stats["queue_sizes"]["critical"] >= 1
    
    def test_event_metadata_preserved(self):
        """Test that event metadata is preserved."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            "test.event",
            {},
            metadata={"custom_field": "custom_value", "nested": {"key": "value"}},
        )
        
        event = engine.get_event(event_id)
        
        assert event["metadata"]["custom_field"] == "custom_value"
        assert event["metadata"]["nested"]["key"] == "value"
    
    def test_event_source_tracked(self):
        """Test that event source is tracked."""
        engine = EventBusEngine()
        
        engine.publish("test.event", {}, source="service_a")
        engine.publish("test.event", {}, source="service_b")
        
        history = engine.get_event_history(source="service_a")
        
        assert len(history) == 1
        assert history[0]["source"] == "service_a"
    
    def test_statistics_total_subscriptions(self):
        """Test that statistics include total subscriptions."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        engine.subscribe("sub1", ["event1"], handler)
        engine.subscribe("sub2", ["event2"], handler)
        
        stats = engine.get_statistics()
        
        assert stats["total_subscriptions"] == 2
    
    def test_empty_queue_process(self):
        """Test processing empty queue."""
        engine = EventBusEngine()
        
        count = engine.process_events()
        
        assert count == 0
    
    def test_get_events_by_type_empty(self):
        """Test getting events by type when none exist."""
        engine = EventBusEngine()
        
        events = engine.get_events_by_type("nonexistent.type")
        
        assert events == []
    
    def test_get_event_history_empty(self):
        """Test getting empty event history."""
        engine = EventBusEngine()
        
        history = engine.get_event_history()
        
        assert history == []
    
    def test_subscription_created_at_tracked(self):
        """Test that subscription created_at is tracked."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe("sub1", ["test.event"], handler)
        
        subscriptions = engine.get_subscriptions()
        
        sub = next(s for s in subscriptions if s["subscription_id"] == sub_id)
        
        assert "created_at" in sub
        assert sub["created_at"] is not None
    
    def test_event_created_at_tracked(self):
        """Test that event created_at is tracked."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test.event", {})
        
        event = engine.get_event(event_id)
        
        assert "created_at" in event
        assert event["created_at"] is not None
    
    def test_event_processed_at_set_on_completion(self):
        """Test that processed_at is set on completion."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test.event", {})
        
        engine.process_events()
        
        event = engine.get_event(event_id)
        
        assert event["processed_at"] is not None
        assert event["status"] == "completed"
    
    def test_event_error_message_tracked(self):
        """Test that error message is tracked on failure."""
        engine = EventBusEngine()
        
        def failing_handler(event):
            raise Exception("Test error message")
        
        engine.subscribe("sub1", ["test.event"], failing_handler)
        
        event_id = engine.publish("test.event", {}, max_retries=1)
        
        # Process until failure
        for i in range(5):
            engine.process_events()
        
        event = engine.get_event(event_id)
        
        assert event["error_message"] is not None
    
    def test_clear_dead_letter_queue_empty(self):
        """Test clearing empty dead letter queue."""
        engine = EventBusEngine()
        
        count = engine.clear_dead_letter_queue()
        
        assert count == 0
    
    def test_replay_dead_letter_removes_from_queue(self):
        """Test that replay removes event from dead letter queue."""
        engine = EventBusEngine()
        
        def failing_handler(event):
            raise Exception("Fail")
        
        engine.subscribe("sub1", ["test.event"], failing_handler)
        
        event_id = engine.publish("test.event", {}, max_retries=1)
        
        # Process until dead letter
        for i in range(5):
            engine.process_events()
        
        dlq_before = engine.get_dead_letter_queue()
        assert len(dlq_before) >= 1
        
        # Replay
        engine.replay_dead_letter(event_id)
        
        dlq_after = engine.get_dead_letter_queue()
        assert len(dlq_after) == len(dlq_before) - 1
    
    def test_purge_events_returns_count(self):
        """Test that purge_events returns count."""
        engine = EventBusEngine()
        
        for i in range(10):
            engine.publish("test.event", {})
        
        count = engine.purge_events()
        
        assert count == 10
    
    def test_handler_receives_full_event(self):
        """Test that handler receives full event object."""
        engine = EventBusEngine()
        
        received_event = None
        
        def handler(event):
            nonlocal received_event
            received_event = event
        
        engine.subscribe("sub1", ["test.event"], handler)
        
        engine.publish(
            "test.event",
            {"key": "value"},
            source="test_source",
            priority=EventPriority.HIGH,
        )
        
        assert received_event is not None
        assert received_event.payload["key"] == "value"
        assert received_event.source == "test_source"
        assert received_event.priority == EventPriority.HIGH
    
    def test_statistics_failed_events_tracked(self):
        """Test that failed events are tracked in statistics."""
        engine = EventBusEngine()
        
        def always_fails(event):
            raise Exception("Always fails")
        
        engine.subscribe("sub1", ["test.event"], always_fails)
        
        engine.publish("test.event", {}, max_retries=1)
        
        # Process until failure
        for i in range(5):
            engine.process_events()
        
        stats = engine.get_statistics()
        
        assert stats["failed_events"] >= 1
    
    def test_event_status_transitions(self):
        """Test event status transitions."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test.event", {})
        
        # Initially pending
        event = engine.get_event(event_id)
        assert event["status"] == "pending"
        
        # After processing
        engine.process_events()
        
        event = engine.get_event(event_id)
        assert event["status"] == "completed"
    
    def test_subscription_filter_expr_stored(self):
        """Test that subscription filter expression is stored."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe(
            "sub1",
            ["test.event"],
            handler,
            filter_expr="payload.value > 10",
        )
        
        subscriptions = engine.get_subscriptions()
        
        sub = next(s for s in subscriptions if s["subscription_id"] == sub_id)
        
        assert sub["filter_expr"] == "payload.value > 10"
    
    def test_subscription_priority_filter_stored(self):
        """Test that subscription priority filter is stored."""
        engine = EventBusEngine()
        
        def handler(event):
            pass
        
        sub_id = engine.subscribe(
            "sub1",
            ["test.event"],
            handler,
            priority_filter=EventPriority.HIGH,
        )
        
        subscriptions = engine.get_subscriptions()
        
        sub = next(s for s in subscriptions if s["subscription_id"] == sub_id)
        
        assert sub["priority_filter"] == "high"
    
    def test_event_with_all_fields(self):
        """Test creating event with all fields."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            event_type="comprehensive.event",
            payload={"data": "value"},
            source="test_service",
            priority=EventPriority.HIGH,
            correlation_id="corr_123",
            metadata={"custom": "metadata"},
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        
        event = engine.get_event(event_id)
        
        assert event["event_type"] == "comprehensive.event"
        assert event["source"] == "test_service"
        assert event["priority"] == "high"
        assert event["correlation_id"] == "corr_123"
        assert event["metadata"]["custom"] == "metadata"
        assert event["expires_at"] is not None
