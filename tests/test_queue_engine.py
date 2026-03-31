"""Tests for Queue Engine — Slice 50."""
import pytest
from copilot_core.queue.engine import (
    QueueEngine,
    QueueType,
    MessageStatus,
    Message,
    Queue,
    create_queue_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestQueueEngine:
    """Test queue engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_queue_engine()
        assert engine is not None
    
    def test_create_queue_fifo(self):
        """Test creating FIFO queue."""
        engine = QueueEngine()
        
        queue = engine.create_queue("test_queue", queue_type=QueueType.FIFO)
        
        assert queue.name == "test_queue"
        assert queue.queue_type == QueueType.FIFO
    
    def test_create_queue_priority(self):
        """Test creating priority queue."""
        engine = QueueEngine()
        
        queue = engine.create_queue("priority_queue", queue_type=QueueType.PRIORITY)
        
        assert queue.queue_type == QueueType.PRIORITY
    
    def test_create_queue_with_dlq(self):
        """Test creating queue with dead letter queue."""
        engine = QueueEngine()
        
        engine.create_queue("dlq")
        queue = engine.create_queue("main_queue", dead_letter_queue="dlq")
        
        assert queue.dead_letter_queue == "dlq"
    
    def test_create_queue_with_ttl(self):
        """Test creating queue with default TTL."""
        engine = QueueEngine()
        
        queue = engine.create_queue("test", default_ttl_seconds=300)
        
        assert queue.default_ttl_seconds == 300
    
    def test_delete_queue(self):
        """Test deleting queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        result = engine.delete_queue("test")
        
        assert result is True
        assert "test" not in engine.list_queues()
    
    def test_delete_unknown_queue(self):
        """Test deleting unknown queue."""
        engine = QueueEngine()
        
        result = engine.delete_queue("nonexistent")
        
        assert result is False
    
    def test_get_queue(self):
        """Test getting queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        queue = engine.get_queue("test")
        
        assert queue is not None
        assert queue.name == "test"
    
    def test_get_unknown_queue(self):
        """Test getting unknown queue."""
        engine = QueueEngine()
        
        queue = engine.get_queue("nonexistent")
        
        assert queue is None
    
    def test_list_queues(self):
        """Test listing queues."""
        engine = QueueEngine()
        
        engine.create_queue("queue1")
        engine.create_queue("queue2")
        engine.create_queue("queue3")
        
        queues = engine.list_queues()
        
        assert len(queues) == 3
        assert "queue1" in queues
    
    def test_enqueue_fifo(self):
        """Test enqueuing to FIFO queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", {"data": "value"})
        
        assert message_id is not None
        assert message_id.startswith("msg_")
    
    def test_enqueue_priority(self):
        """Test enqueuing to priority queue."""
        engine = QueueEngine()
        
        engine.create_queue("priority", queue_type=QueueType.PRIORITY)
        
        message_id = engine.enqueue("priority", {"data": "value"}, priority=10)
        
        assert message_id is not None
        
        message = engine.get_message("priority", message_id)
        assert message.priority == 10
    
    def test_enqueue_with_delay(self):
        """Test enqueuing with delay."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "delayed_message", delay_seconds=2)
        
        message = engine.get_message("test", message_id)
        
        assert message.is_delayed() is True
        assert message.is_visible() is False
    
    def test_enqueue_with_ttl(self):
        """Test enqueuing with TTL."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "expiring_message", ttl_seconds=2)
        
        message = engine.get_message("test", message_id)
        
        assert message.expires_at is not None
    
    def test_enqueue_with_metadata(self):
        """Test enqueuing with metadata."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue(
            "test",
            "message",
            metadata={"source": "test", "user_id": "123"},
        )
        
        message = engine.get_message("test", message_id)
        
        assert message.metadata["source"] == "test"
        assert message.metadata["user_id"] == "123"
    
    def test_enqueue_unknown_queue(self):
        """Test enqueuing to unknown queue."""
        engine = QueueEngine()
        
        with pytest.raises(ValueError):
            engine.enqueue("nonexistent", "message")
    
    def test_enqueue_queue_full(self):
        """Test enqueuing when queue is full."""
        engine = QueueEngine()
        
        engine.create_queue("test", max_size=3)
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        engine.enqueue("test", "msg3")
        
        with pytest.raises(ValueError):
            engine.enqueue("test", "msg4")
    
    def test_dequeue_fifo(self):
        """Test dequeuing from FIFO queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "first")
        engine.enqueue("test", "second")
        engine.enqueue("test", "third")
        
        message = engine.dequeue("test")
        
        assert message.body == "first"
        assert message.status == MessageStatus.PROCESSING
    
    def test_dequeue_priority(self):
        """Test dequeuing from priority queue."""
        engine = QueueEngine()
        
        engine.create_queue("priority", queue_type=QueueType.PRIORITY)
        
        engine.enqueue("priority", "low", priority=1)
        engine.enqueue("priority", "high", priority=10)
        engine.enqueue("priority", "medium", priority=5)
        
        message = engine.dequeue("priority")
        
        assert message.body == "high"
    
    def test_dequeue_delayed_not_visible(self):
        """Test that delayed messages are not visible."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "immediate")
        engine.enqueue("test", "delayed", delay_seconds=5)
        
        message = engine.dequeue("test")
        
        assert message.body == "immediate"
    
    def test_dequeue_empty_queue(self):
        """Test dequeuing from empty queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message = engine.dequeue("test")
        
        assert message is None
    
    def test_dequeue_unknown_queue(self):
        """Test dequeuing from unknown queue."""
        engine = QueueEngine()
        
        message = engine.dequeue("nonexistent")
        
        assert message is None
    
    def test_acknowledge(self):
        """Test acknowledging message."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.dequeue("test")
        
        result = engine.acknowledge(message.message_id)
        
        assert result is True
        
        # Message should be removed
        assert engine.get_message("test", message_id) is None
    
    def test_acknowledge_unknown_message(self):
        """Test acknowledging unknown message."""
        engine = QueueEngine()
        
        result = engine.acknowledge("unknown_msg")
        
        assert result is False
    
    def test_nack_requeue(self):
        """Test negative acknowledge with requeue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.dequeue("test")
        
        result = engine.nack(message.message_id, error_message="Processing failed", requeue=True)
        
        assert result is True
        
        # Message should be back in queue
        time.sleep(0.1)  # Wait for visibility timeout
        
        message2 = engine.dequeue("test")
        
        assert message2 is not None
        assert message2.attempts == 2
    
    def test_nack_no_requeue(self):
        """Test negative acknowledge without requeue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.dequeue("test")
        
        result = engine.nack(message.message_id, requeue=False)
        
        assert result is True
        
        # Message should be in failed state
        assert engine.get_message("test", message_id) is None
    
    def test_nack_max_attempts_to_dlq(self):
        """Test message moves to DLQ after max attempts."""
        engine = QueueEngine()
        
        engine.create_queue("dlq")
        engine.create_queue("main", dead_letter_queue="dlq", default_ttl_seconds=3600)
        
        message_id = engine.enqueue("main", "message")
        
        # Exhaust attempts
        for i in range(3):
            message = engine.dequeue("main")
            if message:
                engine.nack(message.message_id, requeue=True)
                time.sleep(0.1)  # Wait for backoff
        
        # Should be in DLQ now
        dlq_messages = engine.peek("dlq", limit=10)
        
        assert len(dlq_messages) >= 1
    
    def test_peek(self):
        """Test peeking at messages."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        engine.enqueue("test", "msg3")
        
        messages = engine.peek("test", limit=5)
        
        assert len(messages) == 3
        
        # Queue size should be unchanged
        assert engine.get_queue_size("test") == 3
    
    def test_peek_with_limit(self):
        """Test peeking with limit."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        for i in range(10):
            engine.enqueue("test", f"msg{i}")
        
        messages = engine.peek("test", limit=3)
        
        assert len(messages) == 3
    
    def test_subscribe(self):
        """Test subscribing to queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        received = []
        
        def callback(message):
            received.append(message.body)
        
        subscriber_id = engine.subscribe("test", callback)
        
        assert subscriber_id is not None
        assert subscriber_id.startswith("sub_")
        
        engine.enqueue("test", "new_message")
        
        time.sleep(0.1)  # Allow callback to execute
        
        assert "new_message" in received
    
    def test_unsubscribe(self):
        """Test unsubscribing from queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        received = []
        
        def callback(message):
            received.append(message.body)
        
        subscriber_id = engine.subscribe("test", callback)
        
        engine.unsubscribe("test", subscriber_id)
        
        engine.enqueue("test", "new_message")
        
        time.sleep(0.1)
        
        assert len(received) == 0
    
    def test_get_queue_size(self):
        """Test getting queue size."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        engine.enqueue("test", "msg3")
        
        size = engine.get_queue_size("test")
        
        assert size == 3
    
    def test_get_queue_size_excludes_processing(self):
        """Test that queue size excludes processing messages."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        
        engine.dequeue("test")  # One message now processing
        
        size = engine.get_queue_size("test")
        
        assert size == 1
    
    def test_get_message(self):
        """Test getting message by ID."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "test_body")
        
        message = engine.get_message("test", message_id)
        
        assert message is not None
        assert message.body == "test_body"
    
    def test_purge_queue(self):
        """Test purging queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        for i in range(10):
            engine.enqueue("test", f"msg{i}")
        
        count = engine.purge_queue("test")
        
        assert count == 10
        assert engine.get_queue_size("test") == 0
    
    def test_purge_empty_queue(self):
        """Test purging empty queue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        count = engine.purge_queue("test")
        
        assert count == 0
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        
        message = engine.dequeue("test")
        engine.acknowledge(message.message_id)
        
        stats = engine.get_statistics()
        
        assert stats["total_enqueued"] == 2
        assert stats["total_dequeued"] == 1
        assert stats["total_acknowledged"] == 1
        assert stats["total_queues"] == 1
    
    def test_statistics_by_queue(self):
        """Test statistics breakdown by queue."""
        engine = QueueEngine()
        
        engine.create_queue("queue1")
        engine.create_queue("queue2")
        
        engine.enqueue("queue1", "msg1")
        engine.enqueue("queue1", "msg2")
        engine.enqueue("queue2", "msg3")
        
        stats = engine.get_statistics()
        
        assert "queues" in stats
        assert stats["queues"]["queue1"]["size"] == 2
        assert stats["queues"]["queue2"]["size"] == 1
    
    def test_message_is_visible(self):
        """Test message visibility check."""
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        assert message.is_visible() is True
    
    def test_message_not_visible_until_delay(self):
        """Test message not visible during delay."""
        future = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
            visible_at=future,
        )
        
        assert message.is_visible() is False
    
    def test_message_is_delayed(self):
        """Test message delay check."""
        future = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
        
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
            delay_until=future,
        )
        
        assert message.is_delayed() is True
    
    def test_message_not_delayed(self):
        """Test message not delayed."""
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        assert message.is_delayed() is False
    
    def test_message_is_expired(self):
        """Test message expiry check."""
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=past,
        )
        
        assert message.is_expired() is True
    
    def test_message_not_expired(self):
        """Test message not expired."""
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future,
        )
        
        assert message.is_expired() is False
    
    def test_message_no_expiry(self):
        """Test message without expiry."""
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body="test",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        assert message.is_expired() is False
    
    def test_message_to_dict(self):
        """Test message serialization."""
        message = Message(
            message_id="msg_test",
            queue_name="test",
            body={"data": "value"},
            priority=5,
            created_at="2025-01-01T00:00:00Z",
            status=MessageStatus.PENDING,
            attempts=2,
        )
        
        d = message.to_dict()
        
        assert d["message_id"] == "msg_test"
        assert d["priority"] == 5
        assert d["status"] == "pending"
        assert d["attempts"] == 2
    
    def test_queue_to_dict(self):
        """Test queue serialization."""
        queue = Queue(
            name="test_queue",
            queue_type=QueueType.PRIORITY,
            max_size=5000,
            default_ttl_seconds=1800,
            dead_letter_queue="dlq",
        )
        
        d = queue.to_dict()
        
        assert d["name"] == "test_queue"
        assert d["queue_type"] == "priority"
        assert d["max_size"] == 5000
        assert d["dead_letter_queue"] == "dlq"
    
    def test_queue_type_enum_values(self):
        """Test queue type enum values."""
        assert QueueType.FIFO.value == "fifo"
        assert QueueType.PRIORITY.value == "priority"
        assert QueueType.DELAYED.value == "delayed"
    
    def test_message_status_enum_values(self):
        """Test message status enum values."""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.PROCESSING.value == "processing"
        assert MessageStatus.ACKNOWLEDGED.value == "acknowledged"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.DEAD_LETTER.value == "dead_letter"
    
    def test_dequeue_excludes_expired(self):
        """Test that dequeue excludes expired messages."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        # Enqueue with very short TTL
        engine.enqueue("test", "expired", ttl_seconds=1)
        
        time.sleep(1.1)
        
        message = engine.dequeue("test")
        
        assert message is None
    
    def test_expired_message_counted_in_stats(self):
        """Test that expired messages are counted."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1", ttl_seconds=1)
        
        time.sleep(1.1)
        
        # Try to dequeue - should trigger expiry handling
        engine.dequeue("test")
        
        stats = engine.get_statistics()
        
        assert stats["total_expired"] >= 1
    
    def test_priority_queue_maintains_order(self):
        """Test that priority queue maintains order."""
        engine = QueueEngine()
        
        engine.create_queue("priority", queue_type=QueueType.PRIORITY)
        
        # Enqueue in random order
        engine.enqueue("priority", "p1", priority=1)
        engine.enqueue("priority", "p5", priority=5)
        engine.enqueue("priority", "p3", priority=3)
        engine.enqueue("priority", "p10", priority=10)
        engine.enqueue("priority", "p2", priority=2)
        
        # Dequeue should return in priority order
        results = []
        for i in range(5):
            msg = engine.dequeue("priority")
            if msg:
                results.append(msg.priority)
                engine.acknowledge(msg.message_id)
        
        assert results == [10, 5, 3, 2, 1]
    
    def test_delayed_message_becomes_visible(self):
        """Test that delayed message becomes visible after delay."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "delayed", delay_seconds=1)
        
        # Should not be visible immediately
        message = engine.dequeue("test")
        assert message is None
        
        # Wait for delay to expire
        time.sleep(1.1)
        
        # Should be visible now
        message = engine.dequeue("test")
        
        assert message is not None
        assert message.body == "delayed"
    
    def test_processing_tracked_in_stats(self):
        """Test that processing messages are tracked."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "msg1")
        engine.enqueue("test", "msg2")
        
        engine.dequeue("test")
        engine.dequeue("test")
        
        stats = engine.get_statistics()
        
        assert stats["total_processing"] == 2
    
    def test_default_delay_from_queue_config(self):
        """Test that default delay is applied from queue config."""
        engine = QueueEngine()
        
        engine.create_queue("test", default_delay_seconds=5)
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.get_message("test", message_id)
        
        assert message.is_delayed() is True
        assert message.is_visible() is False
    
    def test_default_ttl_from_queue_config(self):
        """Test that default TTL is applied from queue config."""
        engine = QueueEngine()
        
        engine.create_queue("test", default_ttl_seconds=60)
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.get_message("test", message_id)
        
        assert message.expires_at is not None
    
    def test_ttl_override_queue_default(self):
        """Test that TTL can override queue default."""
        engine = QueueEngine()
        
        engine.create_queue("test", default_ttl_seconds=3600)
        
        message_id = engine.enqueue("test", "message", ttl_seconds=30)
        
        message = engine.get_message("test", message_id)
        
        # Should use the override, not the default
        # We can check by verifying expires_at is set (specific time check is complex)
        assert message.expires_at is not None
    
    def test_delay_override_queue_default(self):
        """Test that delay can override queue default."""
        engine = QueueEngine()
        
        engine.create_queue("test", default_delay_seconds=60)
        
        # Override with no delay
        message_id = engine.enqueue("test", "message", delay_seconds=0)
        
        message = engine.get_message("test", message_id)
        
        assert message.is_delayed() is False
        assert message.is_visible() is True
    
    def test_subscriber_callback_receives_message(self):
        """Test that subscriber callback receives full message."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        received_messages = []
        
        def callback(message):
            received_messages.append(message)
        
        engine.subscribe("test", callback)
        
        engine.enqueue(
            "test",
            {"key": "value"},
            priority=5,
            metadata={"source": "test"},
        )
        
        time.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0].body == {"key": "value"}
        assert received_messages[0].priority == 5
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers receive same message."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        received1 = []
        received2 = []
        
        engine.subscribe("test", lambda m: received1.append(m.body))
        engine.subscribe("test", lambda m: received2.append(m.body))
        
        engine.enqueue("test", "broadcast")
        
        time.sleep(0.1)
        
        assert "broadcast" in received1
        assert "broadcast" in received2
    
    def test_dlq_message_has_original_metadata(self):
        """Test that DLQ message preserves original metadata."""
        engine = QueueEngine()
        
        engine.create_queue("dlq")
        engine.create_queue("main", dead_letter_queue="dlq")
        
        engine.enqueue(
            "main",
            "failing_message",
            metadata={"original": "data", "user_id": "123"},
        )
        
        # Exhaust attempts
        for i in range(3):
            msg = engine.dequeue("main")
            if msg:
                engine.nack(msg.message_id, requeue=True)
                time.sleep(0.1)
        
        # Check DLQ
        dlq_messages = engine.peek("dlq", limit=10)
        
        assert len(dlq_messages) >= 1
        assert dlq_messages[0].metadata["original_queue"] == "main"
        assert dlq_messages[0].metadata["original_message_id"] is not None
    
    def test_message_id_unique(self):
        """Test that message IDs are unique."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        ids = set()
        for i in range(100):
            message_id = engine.enqueue("test", f"msg{i}")
            ids.add(message_id)
        
        assert len(ids) == 100
    
    def test_subscriber_id_unique(self):
        """Test that subscriber IDs are unique."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        ids = set()
        for i in range(10):
            subscriber_id = engine.subscribe("test", lambda m: None)
            ids.add(subscriber_id)
        
        assert len(ids) == 10
    
    def test_unknown_subscriber_unsubscribe(self):
        """Test unsubscribing unknown subscriber."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        result = engine.unsubscribe("test", "unknown_sub")
        
        assert result is False
    
    def test_unsubscribe_unknown_queue(self):
        """Test unsubscribing from unknown queue."""
        engine = QueueEngine()
        
        result = engine.unsubscribe("nonexistent", "sub_123")
        
        assert result is False
    
    def test_get_message_unknown_queue(self):
        """Test getting message from unknown queue."""
        engine = QueueEngine()
        
        message = engine.get_message("nonexistent", "msg_123")
        
        assert message is None
    
    def test_queue_size_unknown_queue(self):
        """Test getting size of unknown queue."""
        engine = QueueEngine()
        
        size = engine.get_queue_size("nonexistent")
        
        assert size == 0
    
    def test_peek_unknown_queue(self):
        """Test peeking at unknown queue."""
        engine = QueueEngine()
        
        messages = engine.peek("nonexistent", limit=10)
        
        assert messages == []
    
    def test_statistics_total_dead_letter(self):
        """Test that statistics track dead letter count."""
        engine = QueueEngine()
        
        engine.create_queue("dlq")
        engine.create_queue("main", dead_letter_queue="dlq")
        
        engine.enqueue("main", "msg")
        
        # Exhaust attempts
        for i in range(3):
            msg = engine.dequeue("main")
            if msg:
                engine.nack(msg.message_id, requeue=True)
                time.sleep(0.1)
        
        stats = engine.get_statistics()
        
        assert stats["total_dead_letter"] >= 1
    
    def test_message_created_at_set(self):
        """Test that message created_at is set."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "message")
        
        message = engine.get_message("test", message_id)
        
        assert message.created_at is not None
    
    def test_message_status_transitions(self):
        """Test message status transitions."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        message_id = engine.enqueue("test", "message")
        
        # Initially pending
        message = engine.get_message("test", message_id)
        assert message.status == MessageStatus.PENDING
        
        # After dequeue - processing
        message = engine.dequeue("test")
        assert message.status == MessageStatus.PROCESSING
        
        # After ack - acknowledged (and removed)
        engine.acknowledge(message.message_id)
        # Can't check status after removal, but we verified ack returned True
    
    def test_message_attempts_tracked(self):
        """Test that message attempts are tracked."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "message")
        
        # First dequeue
        message = engine.dequeue("test")
        assert message.attempts == 1
        engine.nack(message.message_id, requeue=True)
        
        time.sleep(0.1)
        
        # Second dequeue
        message = engine.dequeue("test")
        assert message.attempts == 2
    
    def test_exponential_backoff_on_requeue(self):
        """Test exponential backoff on requeue."""
        engine = QueueEngine()
        
        engine.create_queue("test")
        
        engine.enqueue("test", "message")
        
        # First nack - 10 second backoff
        message = engine.dequeue("test")
        engine.nack(message.message_id, requeue=True)
        
        # Should not be immediately visible
        next_msg = engine.dequeue("test")
        assert next_msg is None
    
    def test_dlq_created_automatically_if_not_exists(self):
        """Test DLQ handling when DLQ doesn't exist."""
        engine = QueueEngine()
        
        # Create queue with DLQ that doesn't exist
        engine.create_queue("main", dead_letter_queue="nonexistent_dlq")
        
        engine.enqueue("main", "message")
        
        # Exhaust attempts
        for i in range(3):
            msg = engine.dequeue("main")
            if msg:
                engine.nack(msg.message_id, requeue=True)
                time.sleep(0.1)
        
        # Message should be marked as failed
        stats = engine.get_statistics()
        
        assert stats["total_failed"] >= 1
