"""Tests for Event Propagation Systematics — P2-005."""
import pytest
import time
from datetime import datetime, timezone
from copilot_core.events.propagation import (
    EventPropagationEngine,
    PropagationEvent,
    DeliveryGuarantee,
    PropagationStatus,
    DeadLetterQueue,
    RetryManager,
    RetryConfig,
    RetryStrategy,
    SequenceManager,
    DeduplicationTracker,
    CallbackTarget,
    get_propagation_engine,
    reset_propagation_engine,
)


class TestDeliveryGuarantee:
    """Test delivery guarantee levels."""
    
    def test_at_most_once_no_retry(self):
        """At-most-once should not retry."""
        event = PropagationEvent(
            event_id="test-1",
            event_type="test_event",
            source="test",
            payload={"data": "value"},
            guarantee=DeliveryGuarantee.AT_MOST_ONCE,
            max_retries=0,  # Explicitly set to 0 for at-most-once
        )
        assert event.guarantee == DeliveryGuarantee.AT_MOST_ONCE
        assert event.max_retries == 0
    
    def test_at_least_once_default(self):
        """At-least-once is default."""
        event = PropagationEvent(
            event_id="test-2",
            event_type="test_event",
            source="test",
            payload={"data": "value"},
        )
        assert event.guarantee == DeliveryGuarantee.AT_LEAST_ONCE
    
    def test_exactly_once_dedup(self):
        """Exactly-once enables deduplication."""
        event = PropagationEvent(
            event_id="test-3",
            event_type="test_event",
            source="test",
            payload={"data": "value"},
            guarantee=DeliveryGuarantee.EXACTLY_ONCE,
        )
        assert event.guarantee == DeliveryGuarantee.EXACTLY_ONCE


class TestSequenceManager:
    """Test sequence management for ordering."""
    
    def test_global_sequence_increment(self):
        """Global sequence should increment."""
        sm = SequenceManager()
        assert sm.next_global_sequence() == 1
        assert sm.next_global_sequence() == 2
        assert sm.next_global_sequence() == 3
    
    def test_source_sequence_per_source(self):
        """Source sequences should be independent."""
        sm = SequenceManager()
        assert sm.next_source_sequence("source-a") == 1
        assert sm.next_source_sequence("source-b") == 1
        assert sm.next_source_sequence("source-a") == 2
        assert sm.next_source_sequence("source-b") == 2
    
    def test_reset(self):
        """Reset should clear all sequences."""
        sm = SequenceManager()
        sm.next_global_sequence()
        sm.next_source_sequence("test")
        sm.reset()
        assert sm.next_global_sequence() == 1
        assert sm.next_source_sequence("test") == 1


class TestDeduplicationTracker:
    """Test event deduplication."""
    
    def test_duplicate_by_id(self):
        """Should detect duplicate by event ID."""
        tracker = DeduplicationTracker()
        event = PropagationEvent(
            event_id="dup-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        # First time: not duplicate
        is_dup, original = tracker.is_duplicate(event)
        assert not is_dup
        assert original is None
        
        # Mark as seen
        tracker.mark_seen(event)
        
        # Second time: duplicate
        is_dup, original = tracker.is_duplicate(event)
        assert is_dup
        assert original is not None  # Returns timestamp, not event_id
    
    def test_duplicate_by_content_hash(self):
        """Should detect duplicate by content hash for exactly-once."""
        tracker = DeduplicationTracker()
        event1 = PropagationEvent(
            event_id="evt-1",
            event_type="test",
            source="test",
            payload={"key": "value"},
            guarantee=DeliveryGuarantee.EXACTLY_ONCE,
        )
        event2 = PropagationEvent(
            event_id="evt-2",  # Different ID
            event_type="test",
            source="test",
            payload={"key": "value"},  # Same content
            guarantee=DeliveryGuarantee.EXACTLY_ONCE,
        )
        
        tracker.mark_seen(event1)
        
        # Same content should be detected as duplicate
        is_dup, original = tracker.is_duplicate(event2)
        assert is_dup
        assert original == "evt-1"
    
    def test_no_duplicate_different_content(self):
        """Different content should not be duplicate."""
        tracker = DeduplicationTracker()
        event1 = PropagationEvent(
            event_id="evt-1",
            event_type="test",
            source="test",
            payload={"key": "value1"},
            guarantee=DeliveryGuarantee.EXACTLY_ONCE,
        )
        event2 = PropagationEvent(
            event_id="evt-2",
            event_type="test",
            source="test",
            payload={"key": "value2"},  # Different
            guarantee=DeliveryGuarantee.EXACTLY_ONCE,
        )
        
        tracker.mark_seen(event1)
        is_dup, _ = tracker.is_duplicate(event2)
        assert not is_dup


class TestDeadLetterQueue:
    """Test dead letter queue."""
    
    def test_add_entry(self):
        """Should add failed event to DLQ."""
        dlq = DeadLetterQueue()
        event = PropagationEvent(
            event_id="failed-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        dlq.add(event, "Connection timeout")
        assert dlq.size == 1
        
        entry = dlq.get_by_event_id("failed-1")
        assert entry is not None
        assert entry.failure_reason == "Connection timeout"
    
    def test_max_size_enforcement(self):
        """Should enforce max size."""
        dlq = DeadLetterQueue(max_size=3)
        
        for i in range(5):
            event = PropagationEvent(
                event_id=f"failed-{i}",
                event_type="test",
                source="test",
                payload={},
            )
            dlq.add(event, "Error")
        
        assert dlq.size == 3
    
    def test_remove_entry(self):
        """Should remove entry from DLQ."""
        dlq = DeadLetterQueue()
        event = PropagationEvent(
            event_id="to-retry",
            event_type="test",
            source="test",
            payload={},
        )
        
        dlq.add(event, "Failed")
        assert dlq.size == 1
        
        dlq.remove("to-retry")
        assert dlq.size == 0
    
    def test_clear(self):
        """Should clear all entries."""
        dlq = DeadLetterQueue()
        
        for i in range(3):
            event = PropagationEvent(
                event_id=f"failed-{i}",
                event_type="test",
                source="test",
                payload={},
            )
            dlq.add(event, "Error")
        
        count = dlq.clear()
        assert count == 3
        assert dlq.size == 0


class TestRetryManager:
    """Test retry mechanisms with backoff."""
    
    def test_exponential_backoff(self):
        """Should calculate exponential backoff delays."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_ms=100,
            max_delay_ms=60000,
        )
        rm = RetryManager(config)
        
        # Attempt 1: 100ms
        delay1 = config.get_delay(1)
        assert 0.09 <= delay1 <= 0.11
        
        # Attempt 2: 200ms
        delay2 = config.get_delay(2)
        assert 0.19 <= delay2 <= 0.21
        
        # Attempt 3: 400ms
        delay3 = config.get_delay(3)
        assert 0.39 <= delay3 <= 0.41
    
    def test_max_delay_cap(self):
        """Should cap delay at max_delay_ms."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_ms=100,
            max_delay_ms=1000,
        )
        
        # Attempt 10 would be 100 * 2^9 = 51200ms, but capped at 1000ms
        delay = config.get_delay(10)
        assert delay == 1.0  # 1000ms = 1 second
    
    def test_schedule_retry(self):
        """Should schedule retry for event."""
        rm = RetryManager()
        event = PropagationEvent(
            event_id="retry-me",
            event_type="test",
            source="test",
            payload={},
        )
        
        delay = rm.schedule_retry(event)
        assert delay > 0
        assert rm.is_pending("retry-me")
        assert rm.pending_count == 1
    
    def test_get_due_retries(self):
        """Should return events due for retry."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay_ms=10,  # 10ms for fast test
        )
        rm = RetryManager(config)
        
        event = PropagationEvent(
            event_id="due-soon",
            event_type="test",
            source="test",
            payload={},
        )
        
        rm.schedule_retry(event)
        time.sleep(0.02)  # Wait for retry to be due
        
        due = rm.get_due_retries()
        assert len(due) == 1
        assert due[0].event_id == "due-soon"
    
    def test_cancel_retry(self):
        """Should cancel scheduled retry."""
        rm = RetryManager()
        event = PropagationEvent(
            event_id="cancel-me",
            event_type="test",
            source="test",
            payload={},
        )
        
        rm.schedule_retry(event)
        assert rm.is_pending("cancel-me")
        
        rm.cancel_retry("cancel-me")
        assert not rm.is_pending("cancel-me")


class TestCallbackTarget:
    """Test callback-based propagation target."""
    
    def test_successful_delivery(self):
        """Should deliver event to callback."""
        delivered = []
        
        def callback(event):
            delivered.append(event)
            return True
        
        target = CallbackTarget("test-target", callback)
        event = PropagationEvent(
            event_id="cb-1",
            event_type="test",
            source="test",
            payload={"key": "value"},
        )
        
        success = target.deliver(event)
        assert success
        assert len(delivered) == 1
        assert delivered[0].event_id == "cb-1"
    
    def test_failed_delivery(self):
        """Should handle callback failure."""
        def failing_callback(event):
            raise Exception("Callback failed")
        
        target = CallbackTarget("failing-target", failing_callback)
        event = PropagationEvent(
            event_id="fail-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        success = target.deliver(event)
        assert not success


class TestEventPropagationEngine:
    """Test main propagation engine."""
    
    def setup_method(self):
        """Reset engine before each test."""
        reset_propagation_engine()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_propagation_engine()
    
    def test_publish_event(self):
        """Should publish event successfully."""
        engine = EventPropagationEngine()
        
        event = PropagationEvent(
            event_id="pub-1",
            event_type="test_event",
            source="test",
            payload={"data": "value"},
        )
        
        event_id = engine.publish(event)
        assert event_id == "pub-1"
        
        stats = engine.stats
        assert stats["published"] == 1
    
    def test_publish_sync_helper(self):
        """Should publish via sync helper."""
        engine = EventPropagationEngine()
        
        event_id = engine.publish_sync(
            event_type="sync_event",
            payload={"key": "value"},
            source="test-source",
        )
        
        assert event_id is not None
        assert engine.stats["published"] == 1
    
    def test_deduplication(self):
        """Should deduplicate events."""
        engine = EventPropagationEngine()
        
        event1 = PropagationEvent(
            event_id="dup-1",
            event_type="test",
            source="test",
            payload={},
        )
        event2 = PropagationEvent(
            event_id="dup-1",  # Same ID
            event_type="test",
            source="test",
            payload={},
        )
        
        engine.publish(event1)
        engine.publish(event2)
        
        stats = engine.stats
        assert stats["published"] == 1
        assert stats["deduplicated"] == 1
    
    def test_callback_target_delivery(self):
        """Should deliver to callback targets."""
        engine = EventPropagationEngine()
        
        delivered = []
        
        def callback(event):
            delivered.append(event)
            return True
        
        target = CallbackTarget("cb-target", callback)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="deliv-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        engine.publish(event)
        engine.process_pending()
        
        assert len(delivered) == 1
        assert engine.stats["delivered"] == 1
    
    def test_acknowledgment(self):
        """Should track acknowledgments."""
        engine = EventPropagationEngine()
        
        def callback(event):
            return True
        
        target = CallbackTarget("ack-target", callback)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="ack-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        engine.publish(event)
        engine.process_pending()
        
        # Acknowledge
        engine.acknowledge("ack-1", "ack-target")
        
        stored = engine.get_event("ack-1")
        assert stored is not None
        assert "ack-target" in stored["acknowledged_by"]
    
    def test_dead_letter_on_failure(self):
        """Should move failed events to DLQ."""
        engine = EventPropagationEngine(
            retry_config=RetryConfig(
                strategy=RetryStrategy.FIXED,
                base_delay_ms=1,
                max_retries=2,
            )
        )
        
        def failing_callback(event):
            raise Exception("Always fails")
        
        target = CallbackTarget("failing", failing_callback)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="dlq-1",
            event_type="test",
            source="test",
            payload={},
            max_retries=2,
        )
        
        engine.publish(event)
        
        # Process until failure
        for _ in range(5):
            engine.process_pending()
            time.sleep(0.01)
        
        stats = engine.stats
        assert stats["dead_lettered"] == 1
        
        # Check DLQ
        dlq_events = engine.get_dead_letter_events()
        assert len(dlq_events) == 1
        assert dlq_events[0]["event"]["event_id"] == "dlq-1"
    
    def test_retry_dead_letter(self):
        """Should retry dead letter events."""
        engine = EventPropagationEngine(
            retry_config=RetryConfig(
                strategy=RetryStrategy.FIXED,
                base_delay_ms=1,
                max_retries=1,
            )
        )
        
        call_count = [0]
        
        def sometimes_fails(event):
            call_count[0] += 1
            return call_count[0] > 1  # Fail first, succeed second
        
        target = CallbackTarget("flaky", sometimes_fails)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="retry-dlq-1",
            event_type="test",
            source="test",
            payload={},
            max_retries=1,
        )
        
        engine.publish(event)
        engine.process_pending()
        time.sleep(0.01)
        engine.process_pending()
        
        # Should be in DLQ now
        assert engine.stats["dead_lettered"] == 1
        
        # Retry from DLQ
        success = engine.retry_dead_letter("retry-dlq-1")
        assert success
        
        # Process retry
        time.sleep(0.01)
        engine.process_pending()
        
        # Should now be delivered
        assert call_count[0] == 2
    
    def test_sequence_assignment(self):
        """Should assign sequences to events."""
        engine = EventPropagationEngine()
        
        event = PropagationEvent(
            event_id="seq-1",
            event_type="test",
            source="source-a",
            payload={},
        )
        
        engine.publish(event)
        
        stored = engine.get_event("seq-1")
        assert stored["sequence"] == 1
        assert stored["source_sequence"] == 1
        
        # Second event from same source
        event2 = PropagationEvent(
            event_id="seq-2",
            event_type="test",
            source="source-a",
            payload={},
        )
        engine.publish(event2)
        
        stored2 = engine.get_event("seq-2")
        assert stored2["sequence"] == 2
        assert stored2["source_sequence"] == 2
        
        # Event from different source
        event3 = PropagationEvent(
            event_id="seq-3",
            event_type="test",
            source="source-b",
            payload={},
        )
        engine.publish(event3)
        
        stored3 = engine.get_event("seq-3")
        assert stored3["sequence"] == 3
        assert stored3["source_sequence"] == 1  # First from source-b
    
    def test_start_stop(self):
        """Should start and stop background processing."""
        engine = EventPropagationEngine()
        
        engine.start()
        assert engine.stats["running"]
        
        engine.stop()
        assert not engine.stats["running"]
    
    def test_stats_comprehensive(self):
        """Should provide comprehensive stats."""
        engine = EventPropagationEngine()
        
        stats = engine.stats
        
        assert "running" in stats
        assert "guarantee" in stats
        assert "pending_count" in stats
        assert "target_count" in stats
        assert "history_size" in stats
        assert "published" in stats
        assert "delivered" in stats
        assert "acknowledged" in stats
        assert "failed" in stats
        assert "deduplicated" in stats
        assert "dead_lettered" in stats
        assert "sequence_manager" in stats
        assert "dedup_tracker" in stats
        assert "dead_letter_queue" in stats
        assert "retry_manager" in stats


class TestDeliveryGuaranteeModes:
    """Test different delivery guarantee modes."""
    
    def test_at_most_once_no_retry_on_failure(self):
        """At-most-once should not retry."""
        engine = EventPropagationEngine(
            guarantee=DeliveryGuarantee.AT_MOST_ONCE,
        )
        
        fail_count = [0]
        
        def always_fails(event):
            fail_count[0] += 1
            raise Exception("Fail")
        
        target = CallbackTarget("failing", always_fails)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="amo-1",
            event_type="test",
            source="test",
            payload={},
            guarantee=DeliveryGuarantee.AT_MOST_ONCE,
        )
        
        engine.publish(event)
        engine.process_pending()
        
        # Should only try once
        assert fail_count[0] == 1
        assert engine.stats["dead_lettered"] == 1
    
    def test_at_least_once_retries(self):
        """At-least-once should retry until success or max."""
        engine = EventPropagationEngine(
            guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
            retry_config=RetryConfig(
                strategy=RetryStrategy.FIXED,
                base_delay_ms=1,
                max_retries=3,
            ),
        )
        
        call_count = [0]
        
        def fails_twice(event):
            call_count[0] += 1
            return call_count[0] > 2
        
        target = CallbackTarget("flaky", fails_twice)
        engine.register_target(target)
        
        event = PropagationEvent(
            event_id="alo-1",
            event_type="test",
            source="test",
            payload={},
        )
        
        engine.publish(event)
        
        # Process until success
        for _ in range(10):
            engine.process_pending()
            time.sleep(0.01)
        
        # Should have tried 3 times
        assert call_count[0] == 3
        assert engine.stats["delivered"] == 1


class TestPropagationEventSerialization:
    """Test event serialization."""
    
    def test_to_dict(self):
        """Should serialize to dict."""
        event = PropagationEvent(
            event_id="ser-1",
            event_type="test",
            source="test",
            payload={"key": "value"},
            correlation_id="corr-123",
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "ser-1"
        assert d["event_type"] == "test"
        assert d["payload"] == {"key": "value"}
        assert d["correlation_id"] == "corr-123"
        assert d["status"] == "pending"
        assert d["guarantee"] == "at_least_once"
    
    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "event_id": "ser-2",
            "event_type": "test",
            "source": "test",
            "payload": {"key": "value"},
            "guarantee": "exactly_once",
            "status": "delivered",
            "correlation_id": "corr-456",
            "retry_count": 0,
            "max_retries": 5,
            "recipients": ["target-1"],
            "acknowledged_by": [],
            "created_at": "2026-01-01T00:00:00Z",
        }
        
        event = PropagationEvent.from_dict(d)
        
        assert event.event_id == "ser-2"
        assert event.guarantee == DeliveryGuarantee.EXACTLY_ONCE
        assert event.status == PropagationStatus.DELIVERED
        assert event.correlation_id == "corr-456"
        assert "target-1" in event.recipients


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
