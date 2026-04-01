"""Queue Engine — Slice 50.

Message queue for PilotSuite Core.

Features:
- Multiple queue types (FIFO, priority, delayed)
- Message acknowledgment
- Dead letter queue
- Queue subscriptions
- Message filtering
- Queue statistics
"""
from __future__ import annotations

import logging
import heapq
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class QueueType(Enum):
    """Queue types."""
    FIFO = "fifo"
    PRIORITY = "priority"
    DELAYED = "delayed"


class MessageStatus(Enum):
    """Message status."""
    PENDING = "pending"
    PROCESSING = "processing"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class Message:
    """Queue message."""
    message_id: str
    queue_name: str
    body: Any
    created_at: str
    priority: int = 0
    delay_until: Optional[str] = None
    visible_at: Optional[str] = None
    expires_at: Optional[str] = None
    status: MessageStatus = MessageStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    ack_timeout_seconds: int = 30
    acknowledged_at: Optional[str] = None
    processed_at: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_visible(self) -> bool:
        """Check if message is visible."""
        if self.visible_at:
            visible = datetime.fromisoformat(self.visible_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) < visible:
                return False
        return True
    
    def is_delayed(self) -> bool:
        """Check if message is delayed."""
        if self.delay_until:
            delay = datetime.fromisoformat(self.delay_until.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) < delay:
                return True
        return False
    
    def is_expired(self) -> bool:
        """Check if message is expired."""
        if self.expires_at:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expiry
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "queue_name": self.queue_name,
            "body": self.body,
            "priority": self.priority,
            "created_at": self.created_at,
            "delay_until": self.delay_until,
            "visible_at": self.visible_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "ack_timeout_seconds": self.ack_timeout_seconds,
            "acknowledged_at": self.acknowledged_at,
            "processed_at": self.processed_at,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class Queue:
    """Message queue."""
    name: str
    queue_type: QueueType = QueueType.FIFO
    max_size: int = 10000
    default_ttl_seconds: int = 3600
    default_delay_seconds: int = 0
    dead_letter_queue: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "queue_type": self.queue_type.value,
            "max_size": self.max_size,
            "default_ttl_seconds": self.default_ttl_seconds,
            "default_delay_seconds": self.default_delay_seconds,
            "dead_letter_queue": self.dead_letter_queue,
            "created_at": self.created_at,
        }


class QueueEngine:
    """Message queue engine."""
    
    def __init__(self):
        self._queues: Dict[str, Queue] = {}
        self._messages: Dict[str, Dict[str, Message]] = {}  # queue_name -> {message_id -> Message}
        self._priority_queues: Dict[str, List[tuple]] = {}  # queue_name -> [(priority, timestamp, message_id)]
        self._subscribers: Dict[str, List[tuple[str, Callable[[Message], None]]]] = {}
        self._processing: Dict[str, Message] = {}  # message_id -> Message
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_acknowledged": 0,
            "total_failed": 0,
            "total_dead_letter": 0,
            "total_expired": 0,
            "by_queue": {},
        }
    
    def create_queue(self, name: str,
                    queue_type: QueueType = QueueType.FIFO,
                    max_size: int = 10000,
                    default_ttl_seconds: int = 3600,
                    default_delay_seconds: int = 0,
                    dead_letter_queue: Optional[str] = None) -> Queue:
        """Create a new queue."""
        queue = Queue(
            name=name,
            queue_type=queue_type,
            max_size=max_size,
            default_ttl_seconds=default_ttl_seconds,
            default_delay_seconds=default_delay_seconds,
            dead_letter_queue=dead_letter_queue,
        )
        
        with self._lock:
            self._queues[name] = queue
            self._messages[name] = {}
            self._priority_queues[name] = []
            self._subscribers[name] = []
        
        logger.info("Queue created: %s (%s)", name, queue_type.value)
        
        return queue
    
    def delete_queue(self, name: str) -> bool:
        """Delete a queue."""
        with self._lock:
            if name not in self._queues:
                return False
            
            del self._queues[name]
            del self._messages[name]
            del self._priority_queues[name]
            del self._subscribers[name]
        
        logger.info("Queue deleted: %s", name)
        
        return True
    
    def get_queue(self, name: str) -> Optional[Queue]:
        """Get queue by name."""
        return self._queues.get(name)
    
    def list_queues(self) -> List[str]:
        """List all queue names."""
        return list(self._queues.keys())
    
    def enqueue(self, queue_name: str, body: Any,
               priority: int = 0,
               delay_seconds: Optional[int] = None,
               ttl_seconds: Optional[int] = None,
               metadata: Optional[Dict[str, Any]] = None) -> str:
        """Enqueue a message."""
        if queue_name not in self._queues:
            raise ValueError(f"Queue not found: {queue_name}")
        
        queue = self._queues[queue_name]
        
        # Check max size
        if len(self._messages[queue_name]) >= queue.max_size:
            raise ValueError(f"Queue {queue_name} is full")
        
        now = datetime.now(timezone.utc)
        
        # Calculate timestamps
        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        
        delay_until = None
        delay_secs = queue.default_delay_seconds if delay_seconds is None else delay_seconds
        if delay_secs > 0:
            delay_until = (now + timedelta(seconds=delay_secs)).isoformat()

        expires_at = None
        ttl = queue.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl > 0:
            expires_at = (now + timedelta(seconds=ttl)).isoformat()
        
        message = Message(
            message_id=message_id,
            queue_name=queue_name,
            body=body,
            priority=priority,
            created_at=now.isoformat(),
            delay_until=delay_until,
            visible_at=delay_until,  # Not visible until delay expires
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._messages[queue_name][message_id] = message
            
            if queue.queue_type == QueueType.PRIORITY:
                heapq.heappush(
                    self._priority_queues[queue_name],
                    (-priority, now.timestamp(), message_id)  # Negative for max-heap
                )
            
            self._stats["total_enqueued"] += 1
            self._stats["by_queue"][queue_name] = self._stats["by_queue"].get(queue_name, 0) + 1
        
        # Notify subscribers
        self._notify_subscribers(queue_name, message)
        
        logger.debug("Message enqueued: %s to %s", message_id, queue_name)
        
        return message_id
    
    def dequeue(self, queue_name: str, timeout_seconds: int = 0) -> Optional[Message]:
        """Dequeue a message."""
        if queue_name not in self._queues:
            return None
        
        queue = self._queues[queue_name]
        
        with self._lock:
            messages = self._messages[queue_name]
            
            # Find visible, non-expired message
            candidate = None
            
            if queue.queue_type == QueueType.PRIORITY:
                # Priority queue - get highest priority visible message
                while self._priority_queues[queue_name]:
                    _, _, message_id = heapq.heappop(self._priority_queues[queue_name])
                    
                    if message_id not in messages:
                        continue
                    
                    msg = messages[message_id]
                    
                    if msg.status != MessageStatus.PENDING:
                        continue
                    
                    if not msg.is_visible():
                        # Re-add to priority queue
                        heapq.heappush(
                            self._priority_queues[queue_name],
                            (-msg.priority, datetime.fromisoformat(msg.visible_at).timestamp() if msg.visible_at else 0, message_id)
                        )
                        continue
                    
                    if msg.is_expired():
                        self._handle_expired(message_id, msg)
                        continue
                    
                    candidate = msg
                    break
            else:
                # FIFO - get oldest visible message
                for message_id, msg in list(messages.items()):
                    if msg.status != MessageStatus.PENDING:
                        continue
                    
                    if not msg.is_visible():
                        continue
                    
                    if msg.is_expired():
                        self._handle_expired(message_id, msg)
                        continue
                    
                    candidate = msg
                    break
            
            if not candidate:
                return None
            
            # Mark as processing
            candidate.status = MessageStatus.PROCESSING
            candidate.attempts += 1
            candidate.visible_at = (datetime.now(timezone.utc) + timedelta(seconds=candidate.ack_timeout_seconds)).isoformat()
            
            self._processing[candidate.message_id] = candidate
            
            self._stats["total_dequeued"] += 1
        
        logger.debug("Message dequeued: %s from %s", candidate.message_id, queue_name)
        
        return candidate
    
    def acknowledge(self, message_id: str) -> bool:
        """Acknowledge a message."""
        with self._lock:
            if message_id not in self._processing:
                return False
            
            message = self._processing[message_id]
            queue_name = message.queue_name
            
            # Remove from processing
            del self._processing[message_id]
            
            # Remove from queue
            if queue_name in self._messages and message_id in self._messages[queue_name]:
                del self._messages[queue_name][message_id]
            
            message.status = MessageStatus.ACKNOWLEDGED
            message.acknowledged_at = datetime.now(timezone.utc).isoformat()
            message.processed_at = message.acknowledged_at
            
            self._stats["total_acknowledged"] += 1
        
        logger.debug("Message acknowledged: %s", message_id)
        
        return True
    
    def nack(self, message_id: str, error_message: Optional[str] = None,
            requeue: bool = True) -> bool:
        """Negative acknowledge a message."""
        with self._lock:
            if message_id not in self._processing:
                return False
            
            message = self._processing[message_id]
            queue_name = message.queue_name
            
            # Remove from processing
            del self._processing[message_id]
            
            message.error_message = error_message
            
            if requeue and message.attempts < message.max_attempts:
                # Requeue for retry
                message.status = MessageStatus.PENDING
                backoff_seconds = 0.05 * (2 ** max(message.attempts - 1, 0))
                message.visible_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                ).isoformat()

                if queue_name in self._messages:
                    self._messages[queue_name][message_id] = message

                if self._queues[queue_name].queue_type == QueueType.PRIORITY:
                    heapq.heappush(
                        self._priority_queues[queue_name],
                        (-message.priority, datetime.now(timezone.utc).timestamp(), message_id),
                    )
                
                logger.debug("Message requeued: %s (attempt %d)", message_id, message.attempts)
            else:
                # Move to dead letter queue
                message.status = MessageStatus.DEAD_LETTER
                
                dlq = self._queues.get(queue_name)
                if dlq and dlq.dead_letter_queue:
                    self._move_to_dead_letter(message, dlq.dead_letter_queue)
                else:
                    message.status = MessageStatus.FAILED
                    self._stats["total_failed"] += 1
                
                if queue_name in self._messages and message_id in self._messages[queue_name]:
                    del self._messages[queue_name][message_id]
                
                self._stats["total_dead_letter"] += 1
        
        return True
    
    def peek(self, queue_name: str, limit: int = 1) -> List[Message]:
        """Peek at messages without removing them."""
        if queue_name not in self._queues:
            return []
        
        results = []
        
        with self._lock:
            messages = self._messages[queue_name]
            
            for msg in messages.values():
                if msg.status == MessageStatus.PENDING and msg.is_visible() and not msg.is_expired():
                    results.append(msg)
                    
                    if len(results) >= limit:
                        break
        
        return results
    
    def subscribe(self, queue_name: str, callback: Callable[[Message], None]) -> str:
        """Subscribe to queue messages."""
        if queue_name not in self._queues:
            raise ValueError(f"Queue not found: {queue_name}")
        
        subscriber_id = f"sub_{uuid.uuid4().hex[:8]}"
        
        with self._lock:
            self._subscribers[queue_name].append((subscriber_id, callback))
        
        logger.info("Subscriber added to %s: %s", queue_name, subscriber_id)
        
        return subscriber_id
    
    def unsubscribe(self, queue_name: str, subscriber_id: str) -> bool:
        """Unsubscribe from queue."""
        if queue_name not in self._subscribers:
            return False

        with self._lock:
            original_len = len(self._subscribers[queue_name])
            self._subscribers[queue_name] = [
                (sid, cb) for sid, cb in self._subscribers[queue_name]
                if sid != subscriber_id
            ]

        return len(self._subscribers[queue_name]) != original_len
    
    def get_queue_size(self, queue_name: str) -> int:
        """Get queue size (pending messages only)."""
        if queue_name not in self._messages:
            return 0
        
        with self._lock:
            count = 0
            for msg in self._messages[queue_name].values():
                if msg.status == MessageStatus.PENDING and msg.is_visible() and not msg.is_expired():
                    count += 1
            return count
    
    def get_message(self, queue_name: str, message_id: str) -> Optional[Message]:
        """Get message by ID."""
        if queue_name not in self._messages:
            return None
        
        return self._messages[queue_name].get(message_id)
    
    def purge_queue(self, queue_name: str) -> int:
        """Purge all messages from queue."""
        if queue_name not in self._messages:
            return 0
        
        with self._lock:
            count = len(self._messages[queue_name])
            self._messages[queue_name].clear()
            self._priority_queues[queue_name].clear()
        
        logger.info("Queue purged: %s (%d messages)", queue_name, count)
        
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        queue_stats = {}
        
        for queue_name in self._queues:
            queue_stats[queue_name] = {
                "size": self.get_queue_size(queue_name),
                "total_messages": len(self._messages.get(queue_name, {})),
                "processing": len([m for m in self._processing.values() if m.queue_name == queue_name]),
            }
        
        return {
            **self._stats,
            "total_queues": len(self._queues),
            "total_processing": len(self._processing),
            "queues": queue_stats,
        }
    
    def _notify_subscribers(self, queue_name: str, message: Message) -> None:
        """Notify subscribers of new message."""
        if queue_name not in self._subscribers:
            return
        
        for subscriber_id, callback in self._subscribers[queue_name]:
            try:
                callback(message)
            except Exception as e:
                logger.exception("Subscriber callback failed: %s", e)
    
    def _handle_expired(self, message_id: str, message: Message) -> None:
        """Handle expired message."""
        self._stats["total_expired"] += 1
        
        if message.queue_name in self._messages:
            del self._messages[message.queue_name][message_id]
        
        logger.debug("Message expired: %s", message_id)
    
    def _move_to_dead_letter(self, message: Message, dlq_name: str) -> None:
        """Move message to dead letter queue."""
        if dlq_name not in self._queues:
            logger.warning("Dead letter queue not found: %s", dlq_name)
            message.status = MessageStatus.FAILED
            self._stats["total_failed"] += 1
            return
        
        # Create copy for DLQ
        dlq_message = Message(
            message_id=f"dlq_{message.message_id}",
            queue_name=dlq_name,
            body=message.body,
            priority=message.priority,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                **message.metadata,
                "original_queue": message.queue_name,
                "original_message_id": message.message_id,
                "error_message": message.error_message,
                "attempts": message.attempts,
            },
        )
        
        self._messages[dlq_name][dlq_message.message_id] = dlq_message
        
        logger.info("Message moved to DLQ: %s -> %s", message.message_id, dlq_name)


def create_queue_engine() -> QueueEngine:
    """Factory function to create queue engine."""
    return QueueEngine()
