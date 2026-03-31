"""Tests for Event Bus & Message Queue — Slice 28."""
import pytest
from copilot_core.events.bus import (
    EventBusEngine,
    EventPriority,
    EventStatus,
    create_event_bus_engine,
)
from datetime import datetime, timezone, timedelta


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
            event_type="test.event",
            payload={"key": "value"},
            source="test_source",
        )
        
        assert event_id is not None
        assert engine._stats["published"] == 1
    
    def test_publish_event_with_priority(self):
        """Test publishing event with priority."""
        engine = EventBusEngine()
        
        engine.publish("event.low", {}, priority=EventPriority.LOW)
        engine.publish("event.urgent", {}, priority=EventPriority.URGENT)
        engine.publish("event.normal", {}, priority=EventPriority.NORMAL)
        
        # Urgent should be first in queue
        events = list(engine._queue)
        assert events[0].priority == EventPriority.URGENT
    
    def test_subscribe_to_all_events(self):
        """Test subscribing to all events."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        sub_id = engine.subscribe(
            subscriber_id="test_subscriber",
            callback=callback,
        )
        
        assert sub_id is not None
        assert len(engine._subscriptions) == 1
        
        # Publish and process
        engine.publish("test.event", {"data": "test"})
        engine.process_events()
        
        assert len(events_received) == 1
    
    def test_subscribe_to_specific_events(self):
        """Test subscribing to specific event types."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        engine.subscribe(
            subscriber_id="test_subscriber",
            event_types=["light.changed", "switch.changed"],
            callback=callback,
        )
        
        # Publish matching and non-matching events
        engine.publish("light.changed", {})
        engine.publish("temperature.changed", {})
        engine.publish("switch.changed", {})
        
        engine.process_events()
        
        # Should only receive matching events
        assert len(events_received) == 2
    
    def test_unsubscribe(self):
        """Test unsubscribing."""
        engine = EventBusEngine()
        
        sub_id = engine.subscribe("test_sub", event_types=["test.event"])
        
        result = engine.unsubscribe(sub_id)
        
        assert result is True
        assert sub_id not in engine._subscriptions
    
    def test_unsubscribe_unknown(self):
        """Test unsubscribing unknown subscription."""
        engine = EventBusEngine()
        
        result = engine.unsubscribe("unknown_sub")
        
        assert result is False
    
    def test_process_events(self):
        """Test processing events."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        engine.subscribe("sub1", callback=callback)
        
        # Publish events
        for i in range(5):
            engine.publish("test.event", {"index": i})
        
        processed = engine.process_events()
        
        assert processed == 5
        assert len(events_received) == 5
    
    def test_event_delivery_failure_retry(self):
        """Test event retry on delivery failure."""
        engine = EventBusEngine(max_queue_size=100)
        
        call_count = [0]
        
        def failing_callback(event):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Simulated failure")
        
        engine.subscribe("failing_sub", callback=failing_callback)
        
        engine.publish("test.event", {})
        
        # First processing - fails
        engine.process_events()
        assert call_count[0] == 1
        
        # Second processing - fails
        engine.process_events()
        assert call_count[0] == 2
        
        # Third processing - succeeds
        engine.process_events()
        assert call_count[0] == 3
    
    def test_dead_letter_queue(self):
        """Test dead letter queue."""
        engine = EventBusEngine()
        engine._max_retries = 2  # For faster testing
        
        def always_fails(event):
            raise Exception("Always fails")
        
        engine.subscribe("failing_sub", callback=always_fails)
        
        engine.publish("test.event", {})
        
        # Process until event goes to dead letter
        for i in range(5):
            engine.process_events()
        
        # Event should be in dead letter queue
        assert len(engine._dead_letter_queue) >= 1
    
    def test_get_event(self):
        """Test getting event by ID."""
        engine = EventBusEngine()
        
        event_id = engine.publish("test.event", {"data": "test"})
        
        event = engine.get_event(event_id)
        
        assert event is not None
        assert event["event_id"] == event_id
        assert event["event_type"] == "test.event"
    
    def test_get_unknown_event(self):
        """Test getting unknown event."""
        engine = EventBusEngine()
        
        event = engine.get_event("unknown_event_id")
        
        assert event is None
    
    def test_get_events_by_type(self):
        """Test getting events by type."""
        engine = EventBusEngine()
        
        engine.publish("light.event", {"device": "light1"})
        engine.publish("switch.event", {"device": "switch1"})
        engine.publish("light.event", {"device": "light2"})
        
        light_events = engine.get_events_by_type("light.event")
        
        assert len(light_events) == 2
    
    def test_get_dead_letter_events(self):
        """Test getting dead letter events."""
        engine = EventBusEngine()
        engine._max_retries = 1
        
        def always_fails(event):
            raise Exception("Fail")
        
        engine.subscribe("failing", callback=always_fails)
        
        engine.publish("test.event", {})
        
        # Process until dead lettered
        for i in range(3):
            engine.process_events()
        
        dl_events = engine.get_dead_letter_events()
        
        assert len(dl_events) >= 1
    
    def test_retry_dead_letter(self):
        """Test retrying dead letter event."""
        engine = EventBusEngine()
        engine._max_retries = 1
        
        call_count = [0]
        
        def sometimes_fails(event):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First try fails")
        
        engine.subscribe("sub", callback=sometimes_fails)
        
        event_id = engine.publish("test.event", {})
        
        # Process until dead lettered
        for i in range(3):
            engine.process_events()
        
        # Retry
        result = engine.retry_dead_letter(event_id)
        
        assert result is True
        assert len(engine._dead_letter_queue) == 0
    
    def test_retry_unknown_dead_letter(self):
        """Test retrying unknown dead letter event."""
        engine = EventBusEngine()
        
        result = engine.retry_dead_letter("unknown_event")
        
        assert result is False
    
    def test_purge_dead_letter_queue(self):
        """Test purging dead letter queue."""
        engine = EventBusEngine()
        
        # Add events to dead letter queue
        from copilot_core.events.bus import Event
        for i in range(5):
            event = Event(
                event_id=f"dl_{i}",
                event_type="test",
                source="test",
                payload={},
                status=EventStatus.DEAD_LETTERED,
            )
            engine._dead_letter_queue.append(event)
        
        count = engine.purge_dead_letter_queue()
        
        assert count == 5
        assert len(engine._dead_letter_queue) == 0
    
    def test_cleanup_old_dead_letters(self):
        """Test cleaning up old dead letter events."""
        engine = EventBusEngine(dead_letter_retention_hours=1)
        
        # Add old event
        from copilot_core.events.bus import Event
        old_event = Event(
            event_id="old_dl",
            event_type="test",
            source="test",
            payload={},
            status=EventStatus.DEAD_LETTERED,
            created_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        engine._dead_letter_queue.append(old_event)
        
        # Add new event
        new_event = Event(
            event_id="new_dl",
            event_type="test",
            source="test",
            payload={},
            status=EventStatus.DEAD_LETTERED,
        )
        engine._dead_letter_queue.append(new_event)
        
        removed = engine.cleanup_old_dead_letters()
        
        assert removed == 1
        assert len(engine._dead_letter_queue) == 1
    
    def test_get_subscriptions(self):
        """Test getting subscriptions."""
        engine = EventBusEngine()
        
        engine.subscribe("sub_a", event_types=["event.a"])
        engine.subscribe("sub_b", event_types=["event.b"])
        
        all_subs = engine.get_subscriptions()
        sub_a = engine.get_subscriptions(subscriber_id="sub_a")
        
        assert len(all_subs) == 2
        assert len(sub_a) == 1
    
    def test_enable_disable_subscription(self):
        """Test enabling/disabling subscription."""
        engine = EventBusEngine()
        
        sub_id = engine.subscribe("test_sub", event_types=["test.event"])
        
        # Disable
        result = engine.disable_subscription(sub_id)
        assert result is True
        assert engine._subscriptions[sub_id].enabled is False
        
        # Enable
        result = engine.enable_subscription(sub_id)
        assert result is True
        assert engine._subscriptions[sub_id].enabled is True
    
    def test_get_queue_status(self):
        """Test queue status."""
        engine = EventBusEngine()
        
        engine.publish("event1", {})
        engine.publish("event2", {})
        engine.subscribe("sub1")
        
        status = engine.get_queue_status()
        
        assert status["queue_size"] == 2
        assert status["total_subscriptions"] == 1
    
    def test_get_statistics(self):
        """Test statistics."""
        engine = EventBusEngine()
        
        engine.publish("event1", {})
        engine.publish("event2", {})
        engine.process_events()
        
        stats = engine.get_statistics()
        
        assert stats["published"] == 2
        assert stats["delivered"] == 2
    
    def test_replay_events(self):
        """Test replaying events."""
        engine = EventBusEngine()
        
        # Publish original events
        engine.publish("test.event", {"original": True})
        engine.publish("test.event", {"original": True})
        
        # Replay
        replayed = engine.replay_events(event_type="test.event")
        
        assert len(replayed) == 2
        assert "original_id" in replayed[0]
        assert "replayed_id" in replayed[0]
    
    def test_replay_events_with_since_filter(self):
        """Test replaying events with time filter."""
        engine = EventBusEngine()
        
        now = datetime.now(timezone.utc)
        
        # Publish events
        engine.publish("test.event", {})
        
        # Replay since now
        replayed = engine.replay_events(since=now)
        
        assert len(replayed) >= 1
    
    def test_event_priority_ordering(self):
        """Test that events are ordered by priority."""
        engine = EventBusEngine()
        
        engine.publish("low", {}, priority=EventPriority.LOW)
        engine.publish("high", {}, priority=EventPriority.HIGH)
        engine.publish("urgent", {}, priority=EventPriority.URGENT)
        engine.publish("normal", {}, priority=EventPriority.NORMAL)
        
        queue = list(engine._queue)
        
        # Order should be: urgent, high, normal, low
        assert queue[0].priority == EventPriority.URGENT
        assert queue[1].priority == EventPriority.HIGH
        assert queue[2].priority == EventPriority.NORMAL
        assert queue[3].priority == EventPriority.LOW
    
    def test_filter_expression_evaluation(self):
        """Test filter expression evaluation."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        # Subscribe with filter
        engine.subscribe(
            "filtered_sub",
            event_types=["device.event"],
            callback=callback,
            filter_expression="payload.device_type == 'light'",
        )
        
        # Publish matching and non-matching
        engine.publish("device.event", {"device_type": "light"})
        engine.publish("device.event", {"device_type": "switch"})
        
        engine.process_events()
        
        # Should only receive matching event
        assert len(events_received) == 1
    
    def test_event_headers(self):
        """Test event headers."""
        engine = EventBusEngine()
        
        event_id = engine.publish(
            "test.event",
            {},
            headers={"X-Custom-Header": "custom_value"},
        )
        
        event = engine.get_event(event_id)
        
        assert event["headers"]["X-Custom-Header"] == "custom_value"
    
    def test_event_to_dict(self):
        """Test event serialization."""
        from copilot_core.events.bus import Event
        
        event = Event(
            event_id="event_test",
            event_type="test.event",
            source="test_source",
            payload={"key": "value"},
            priority=EventPriority.HIGH,
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "event_test"
        assert d["event_type"] == "test.event"
        assert d["priority"] == "high"
        assert d["payload"] == {"key": "value"}
    
    def test_subscription_to_dict(self):
        """Test subscription serialization."""
        from copilot_core.events.bus import Subscription
        
        sub = Subscription(
            subscription_id="sub_test",
            subscriber_id="test_subscriber",
            event_types={"event.a", "event.b"},
            filter_expression="payload.test == 'value'",
            priority=5,
        )
        
        d = sub.to_dict()
        
        assert d["subscription_id"] == "sub_test"
        assert d["subscriber_id"] == "test_subscriber"
        assert "event.a" in d["event_types"]
        assert d["filter_expression"] == "payload.test == 'value'"
    
    def test_queue_max_size(self):
        """Test queue max size enforcement."""
        engine = EventBusEngine(max_queue_size=5)
        
        # Publish more than max
        for i in range(10):
            engine.publish(f"event.{i}", {})
        
        assert len(engine._queue) <= 5
    
    def test_event_history_max_size(self):
        """Test event history max size enforcement."""
        engine = EventBusEngine()
        engine._max_history_size = 10
        
        # Publish more than max
        for i in range(20):
            engine.publish(f"event.{i}", {})
        
        assert len(engine._event_history) <= 10
    
    def test_subscription_priority_ordering(self):
        """Test that subscribers are called in priority order."""
        engine = EventBusEngine()
        
        call_order = []
        
        def callback1(event):
            call_order.append(1)
        
        def callback2(event):
            call_order.append(2)
        
        def callback3(event):
            call_order.append(3)
        
        engine.subscribe("sub1", callback=callback1, priority=1)
        engine.subscribe("sub2", callback=callback2, priority=10)
        engine.subscribe("sub3", callback=callback3, priority=5)
        
        engine.publish("test.event", {})
        engine.process_events()
        
        # Higher priority should be called first
        assert call_order == [2, 3, 1]
    
    def test_disabled_subscription_not_called(self):
        """Test that disabled subscriptions are not called."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        sub_id = engine.subscribe("test_sub", callback=callback)
        engine.disable_subscription(sub_id)
        
        engine.publish("test.event", {})
        engine.process_events()
        
        assert len(events_received) == 0
    
    def test_event_status_transitions(self):
        """Test event status transitions."""
        engine = EventBusEngine()
        
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        engine.subscribe("sub", callback=callback)
        
        event_id = engine.publish("test.event", {})
        
        # Initially pending
        event = engine.get_event(event_id)
        assert event["status"] == "pending"
        
        # After processing - delivered
        engine.process_events()
        event = engine.get_event(event_id)
        assert event["status"] == "delivered"
        assert event["delivered_at"] is not None
    
    def test_event_priority_enum_values(self):
        """Test event priority enum values."""
        assert EventPriority.LOW.value == "low"
        assert EventPriority.NORMAL.value == "normal"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.URGENT.value == "urgent"
    
    def test_event_status_enum_values(self):
        """Test event status enum values."""
        assert EventStatus.PENDING.value == "pending"
        assert EventStatus.PROCESSING.value == "processing"
        assert EventStatus.DELIVERED.value == "delivered"
        assert EventStatus.FAILED.value == "failed"
        assert EventStatus.DEAD_LETTERED.value == "dead_lettered"
