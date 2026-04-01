"""Event Bus Advanced Engine — Slice 63.

Advanced event bus for PilotSuite Core.

Features:
- Pub/sub with topics
- Event filtering
- Priority queues
- Dead letter queue
- Event replay
- Subscription management
- Event versioning
"""
from __future__ import annotations

import logging
import threading
import queue
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set, Pattern
from enum import Enum
import uuid
import re

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class DeliveryStatus(Enum):
    """Event delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class Event:
    """Event definition."""
    event_id: str
    topic: str
    event_type: str
    payload: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    version: str = "1.0"
    source: str = "unknown"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    delivery_count: int = 0
    last_delivery_attempt: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "event_type": self.event_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "version": self.version,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "headers": self.headers,
            "delivery_count": self.delivery_count,
        }
    
    def is_expired(self) -> bool:
        """Check if event is expired."""
        if not self.expires_at:
            return False
        
        expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry


@dataclass
class Subscription:
    """Event subscription."""
    subscription_id: str
    topic: str
    handler: Callable[[Event], None]
    filter_pattern: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    max_retries: int = 3
    retry_delay_seconds: int = 5
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def matches(self, event: Event) -> bool:
        """Check if event matches subscription filter."""
        if not self.filter_pattern:
            return True
        
        try:
            pattern = re.compile(self.filter_pattern)
            event_json = json.dumps(event.payload)
            return bool(pattern.search(event_json))
        except re.error:
            return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "topic": self.topic,
            "filter_pattern": self.filter_pattern,
            "priority": self.priority.value,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass
class DeliveryRecord:
    """Event delivery record."""
    record_id: str
    event_id: str
    subscription_id: str
    status: DeliveryStatus
    attempts: int
    last_attempt: Optional[str] = None
    error: Optional[str] = None
    delivered_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "event_id": self.event_id,
            "subscription_id": self.subscription_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_attempt": self.last_attempt,
            "error": self.error,
            "delivered_at": self.delivered_at,
        }


class EventBusEngine:
    """Advanced event bus engine."""
    
    def __init__(self, max_queue_size: int = 10000,
                 dead_letter_max_size: int = 1000,
                 max_delivery_attempts: int = 3):
        self._topics: Dict[str, List[Subscription]] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._event_queues: Dict[str, queue.PriorityQueue] = {}
        self._dead_letter_queue: List[Event] = []
        self._event_store: Dict[str, Event] = {}
        self._delivery_records: Dict[str, DeliveryRecord] = {}
        self._lock = threading.RLock()
        self._running = False
        self._workers: List[threading.Thread] = []
        
        self._max_queue_size = max_queue_size
        self._dead_letter_max_size = dead_letter_max_size
        self._max_delivery_attempts = max_delivery_attempts
        
        # Statistics
        self._stats = {
            "total_published": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_dead_lettered": 0,
            "by_topic": {},
            "by_subscription": {},
        }
    
    def start(self, num_workers: int = 4) -> None:
        """Start event bus workers."""
        self._running = True
        
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            worker.start()
            self._workers.append(worker)
        
        logger.info("Event bus started with %d workers", num_workers)
    
    def stop(self) -> None:
        """Stop event bus workers."""
        self._running = False
        
        for worker in self._workers:
            worker.join(timeout=5)
        
        self._workers.clear()
        
        logger.info("Event bus stopped")
    
    def publish(self, topic: str, event_type: str,
               payload: Dict[str, Any],
               priority: EventPriority = EventPriority.NORMAL,
               expires_at: Optional[str] = None,
               version: str = "1.0",
               source: str = "unknown",
               correlation_id: Optional[str] = None,
               headers: Optional[Dict[str, str]] = None) -> str:
        """Publish an event."""
        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        
        event = Event(
            event_id=event_id,
            topic=topic,
            event_type=event_type,
            payload=payload,
            priority=priority,
            expires_at=expires_at,
            version=version,
            source=source,
            correlation_id=correlation_id,
            headers=headers or {},
        )
        
        with self._lock:
            # Store event
            self._event_store[event_id] = event
            
            # Create queue for topic if needed
            if topic not in self._event_queues:
                self._event_queues[topic] = queue.PriorityQueue(maxsize=self._max_queue_size)
            
            # Add to queue (priority, timestamp, event)
            # Lower priority number = higher priority, so we negate
            queue_item = (-event.priority.value, event.created_at, event)
            
            try:
                self._event_queues[topic].put_nowait(queue_item)
            except queue.Full:
                logger.warning("Queue full for topic: %s", topic)
            
            # Update statistics
            self._stats["total_published"] += 1
            self._stats["by_topic"][topic] = self._stats["by_topic"].get(topic, 0) + 1
        
        logger.debug("Event published: %s to %s", event_id, topic)
        
        return event_id
    
    def subscribe(self, topic: str, handler: Callable[[Event], None],
                 filter_pattern: Optional[str] = None,
                 priority: EventPriority = EventPriority.NORMAL,
                 max_retries: int = 3,
                 retry_delay_seconds: int = 5) -> str:
        """Subscribe to a topic."""
        subscription_id = f"sub_{uuid.uuid4().hex[:16]}"
        
        subscription = Subscription(
            subscription_id=subscription_id,
            topic=topic,
            handler=handler,
            filter_pattern=filter_pattern,
            priority=priority,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        
        with self._lock:
            self._subscriptions[subscription_id] = subscription
            
            if topic not in self._topics:
                self._topics[topic] = []
            
            self._topics[topic].append(subscription)
        
        logger.info("Subscription created: %s for topic %s", subscription_id, topic)
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            subscription = self._subscriptions[subscription_id]
            
            # Remove from topic list
            if subscription.topic in self._topics:
                self._topics[subscription.topic] = [
                    s for s in self._topics[subscription.topic]
                    if s.subscription_id != subscription_id
                ]
            
            del self._subscriptions[subscription_id]
        
        logger.info("Subscription removed: %s", subscription_id)
        
        return True
    
    def enable_subscription(self, subscription_id: str) -> bool:
        """Enable a subscription."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            self._subscriptions[subscription_id].enabled = True
        
        return True
    
    def disable_subscription(self, subscription_id: str) -> bool:
        """Disable a subscription."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            self._subscriptions[subscription_id].enabled = False
        
        return True
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID from store."""
        return self._event_store.get(event_id)
    
    def replay_event(self, event_id: str) -> bool:
        """Replay an event from store."""
        with self._lock:
            event = self._event_store.get(event_id)
            
            if not event:
                return False
            
            # Republish
            self.publish(
                topic=event.topic,
                event_type=event.event_type,
                payload=event.payload,
                priority=event.priority,
                version=event.version,
                source="replay",
                correlation_id=event.correlation_id,
            )
        
        logger.info("Event replayed: %s", event_id)
        
        return True
    
    def replay_events(self, topic: str,
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> int:
        """Replay multiple events from store."""
        count = 0
        
        with self._lock:
            events = list(self._event_store.values())

        for event in events:
            if event.topic != topic:
                continue
            
            if start_time and event.created_at < start_time:
                continue
            
            if end_time and event.created_at > end_time:
                continue
            
            self.publish(
                topic=event.topic,
                event_type=event.event_type,
                payload=event.payload,
                priority=event.priority,
                source="replay",
            )
            
            count += 1
        
        logger.info("Replayed %d events for topic %s", count, topic)
        
        return count
    
    def _worker_loop(self, worker_id: int) -> None:
        """Worker loop for processing events."""
        while self._running:
            try:
                self._process_events()
            except Exception as e:
                logger.exception("Worker %d error: %s", worker_id, e)
            
            # Small sleep to prevent busy waiting
            threading.Event().wait(0.01)
    
    def _process_events(self) -> None:
        """Process events from all queues."""
        with self._lock:
            topics = list(self._topics.keys())
        
        for topic in topics:
            self._process_topic(topic)
    
    def _process_topic(self, topic: str) -> None:
        """Process events for a specific topic."""
        if topic not in self._event_queues:
            return
        
        q = self._event_queues[topic]
        
        try:
            # Non-blocking get
            queue_item = q.get_nowait()
            event = queue_item[2]
            
            # Check expiration
            if event.is_expired():
                logger.debug("Event expired: %s", event.event_id)
                return
            
            # Get subscriptions for topic
            with self._lock:
                subscriptions = self._topics.get(topic, []).copy()
            
            # Deliver to each subscription
            for subscription in subscriptions:
                if not subscription.enabled:
                    continue
                
                if not subscription.matches(event):
                    continue
                
                self._deliver_event(event, subscription)
                
        except queue.Empty:
            pass
    
    def _deliver_event(self, event: Event, subscription: Subscription) -> None:
        """Deliver event to subscription."""
        record_id = f"dlv_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()
        
        record = DeliveryRecord(
            record_id=record_id,
            event_id=event.event_id,
            subscription_id=subscription.subscription_id,
            status=DeliveryStatus.PENDING,
            attempts=0,
        )
        
        success = False
        error = None
        
        try:
            subscription.handler(event)
            success = True
        except Exception as e:
            error = str(e)
            logger.exception("Delivery failed for %s to %s", event.event_id, subscription.subscription_id)
        
        # Update record
        event.delivery_count += 1
        event.last_delivery_attempt = now
        
        record.attempts = event.delivery_count
        record.last_attempt = now
        
        if success:
            record.status = DeliveryStatus.DELIVERED
            record.delivered_at = now
            
            with self._lock:
                self._delivery_records[record_id] = record
                self._stats["total_delivered"] += 1
                self._stats["by_subscription"][subscription.subscription_id] = \
                    self._stats["by_subscription"].get(subscription.subscription_id, 0) + 1
        else:
            # Check if should retry
            if event.delivery_count < subscription.max_retries:
                record.status = DeliveryStatus.RETRYING
                record.error = error
                
                with self._lock:
                    self._delivery_records[record_id] = record
            else:
                # Max retries exceeded - dead letter
                record.status = DeliveryStatus.DEAD_LETTERED
                record.error = error
                
                with self._lock:
                    self._delivery_records[record_id] = record
                    self._dead_letter_queue.append(event)
                    self._stats["total_dead_lettered"] += 1
                    
                    # Trim dead letter queue
                    if len(self._dead_letter_queue) > self._dead_letter_max_size:
                        self._dead_letter_queue = self._dead_letter_queue[-self._dead_letter_max_size:]
                
                self._stats["total_failed"] += 1
    
    def get_delivery_record(self, record_id: str) -> Optional[DeliveryRecord]:
        """Get delivery record by ID."""
        return self._delivery_records.get(record_id)
    
    def get_delivery_records(self, event_id: Optional[str] = None,
                            subscription_id: Optional[str] = None,
                            status: Optional[DeliveryStatus] = None,
                            limit: int = 100) -> List[DeliveryRecord]:
        """Get delivery records with filters."""
        with self._lock:
            records = list(self._delivery_records.values())
            
            if event_id:
                records = [r for r in records if r.event_id == event_id]
            
            if subscription_id:
                records = [r for r in records if r.subscription_id == subscription_id]
            
            if status:
                records = [r for r in records if r.status == status]
            
            # Sort by last_attempt descending
            records = sorted(
                [r for r in records if r.last_attempt],
                key=lambda r: r.last_attempt,
                reverse=True,
            )
            
            return records[:limit]
    
    def get_dead_letter_queue(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get dead letter queue contents."""
        with self._lock:
            events = self._dead_letter_queue[-limit:]
            return [e.to_dict() for e in events]
    
    def retry_dead_letter(self, event_id: str) -> bool:
        """Retry an event from dead letter queue."""
        with self._lock:
            event = None
            for i, e in enumerate(self._dead_letter_queue):
                if e.event_id == event_id:
                    event = e
                    del self._dead_letter_queue[i]
                    break
            
            if not event:
                return False
            
            # Reset delivery count
            event.delivery_count = 0
            
            # Republish
            self.publish(
                topic=event.topic,
                event_type=event.event_type,
                payload=event.payload,
                priority=event.priority,
                source="retry",
            )
        
        logger.info("Dead letter retry: %s", event_id)
        
        return True
    
    def clear_dead_letter_queue(self) -> int:
        """Clear dead letter queue."""
        with self._lock:
            count = len(self._dead_letter_queue)
            self._dead_letter_queue.clear()
            return count
    
    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription by ID."""
        with self._lock:
            subscription = self._subscriptions.get(subscription_id)
            
            if not subscription:
                return None
            
            return subscription.to_dict()
    
    def list_subscriptions(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """List subscriptions with optional topic filter."""
        with self._lock:
            subscriptions = list(self._subscriptions.values())
            
            if topic:
                subscriptions = [s for s in subscriptions if s.topic == topic]
            
            return [s.to_dict() for s in subscriptions]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_subscriptions": len(self._subscriptions),
                "total_topics": len(self._topics),
                "dead_letter_size": len(self._dead_letter_queue),
                "event_store_size": len(self._event_store),
            }
    
    def clear_event_store(self, older_than_days: Optional[int] = None) -> int:
        """Clear event store."""
        with self._lock:
            if older_than_days is not None:
                if older_than_days <= 0:
                    return 0
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                to_delete = [
                    eid for eid, event in self._event_store.items()
                    if datetime.fromisoformat(event.created_at.replace('Z', '+00:00')) < cutoff
                ]
                
                for eid in to_delete:
                    del self._event_store[eid]
                
                return len(to_delete)
            else:
                count = len(self._event_store)
                self._event_store.clear()
                return count
    
    def clear_delivery_records(self, older_than_days: Optional[int] = None) -> int:
        """Clear delivery records."""
        with self._lock:
            if older_than_days is not None:
                if older_than_days <= 0:
                    return 0
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                to_delete = [
                    rid for rid, record in self._delivery_records.items()
                    if record.last_attempt and
                    datetime.fromisoformat(record.last_attempt.replace('Z', '+00:00')) < cutoff
                ]
                
                for rid in to_delete:
                    del self._delivery_records[rid]
                
                return len(to_delete)
            else:
                count = len(self._delivery_records)
                self._delivery_records.clear()
                return count


def create_event_bus_engine(**kwargs) -> EventBusEngine:
    """Factory function to create event bus engine."""
    return EventBusEngine(**kwargs)
