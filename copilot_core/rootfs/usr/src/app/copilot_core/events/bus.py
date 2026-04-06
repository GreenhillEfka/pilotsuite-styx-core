"""Event Bus & Message Queue — Slice 28.

Internal event bus for PilotSuite Core communication.

Features:
- Publish/subscribe messaging
- Event routing and filtering
- Message persistence
- Dead letter queue
- Event replay capability
- Priority queues
"""
from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
from collections import deque
import uuid

logger = logging.getLogger(__name__)


def _append_wal_entry(event):
    """Mirror semantic events into WAL in best-effort mode."""
    try:
        from copilot_core.events.wal import log_semantic_event
        log_semantic_event(
            event_type=event.event_type,
            event_id=event.event_id,
            source=event.source,
            data={
                "payload": event.payload,
                "priority": event.priority.value,
                "headers": event.headers,
            },
        )
    except Exception:
        logger.debug("Failed to write semantic event to WAL", exc_info=True)


class EventPriority(Enum):
    """Event priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class Event:
    """Event message."""
    event_id: str
    event_type: str
    source: str
    payload: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivered_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    headers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "failed_at": self.failed_at,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "headers": self.headers,
        }


@dataclass
class Subscription:
    """Event subscription."""
    subscription_id: str
    subscriber_id: str
    event_types: Set[str]  # Event types to subscribe to (empty = all)
    callback: Optional[Callable] = None
    filter_expression: Optional[str] = None
    priority: int = 0
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "subscriber_id": self.subscriber_id,
            "event_types": list(self.event_types),
            "filter_expression": self.filter_expression,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class EventBusEngine:
    """Event bus and message queue engine."""
    
    def __init__(self, max_queue_size: int = 10000,
                 dead_letter_retention_hours: int = 24):
        self._queue: deque = deque(maxlen=max_queue_size)
        self._subscriptions: Dict[str, Subscription] = {}
        self._dead_letter_queue: List[Event] = []
        self._event_history: List[Event] = []
        self._max_history_size = 10000
        self._dead_letter_retention_hours = dead_letter_retention_hours
        self._max_retries = 3
        
        # Statistics
        self._stats = {
            "published": 0,
            "delivered": 0,
            "failed": 0,
            "dead_lettered": 0,
        }
    
    def publish(self, event_type: str, payload: Dict[str, Any],
               source: str = "unknown",
               priority: EventPriority = EventPriority.NORMAL,
               headers: Optional[Dict[str, str]] = None) -> str:
        """Publish an event to the bus."""
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            payload=payload,
            priority=priority,
            max_retries=self._max_retries,
            headers=headers or {},
        )
        
        # Add to queue (priority ordering)
        self._enqueue_event(event)
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
        
        self._stats["published"] += 1
        
        _append_wal_entry(event)
        
        logger.debug("Event published: %s (%s)", event_type, event.event_id)
        
        return event.event_id
    
    def _enqueue_event(self, event: Event) -> None:
        """Add event to queue with priority ordering."""
        # Priority order: urgent > high > normal > low
        priority_order = {
            EventPriority.URGENT: 0,
            EventPriority.HIGH: 1,
            EventPriority.NORMAL: 2,
            EventPriority.LOW: 3,
        }
        
        event.status = EventStatus.PENDING
        
        # Find insertion point based on priority
        inserted = False
        for i, existing_event in enumerate(self._queue):
            if priority_order[event.priority] < priority_order[existing_event.priority]:
                self._queue.insert(i, event)
                inserted = True
                break
        
        if not inserted:
            self._queue.append(event)
    
    def subscribe(self, subscriber_id: str, event_types: Optional[List[str]] = None,
                 callback: Optional[Callable] = None,
                 filter_expression: Optional[str] = None,
                 priority: int = 0) -> str:
        """Subscribe to events."""
        subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
        
        subscription = Subscription(
            subscription_id=subscription_id,
            subscriber_id=subscriber_id,
            event_types=set(event_types) if event_types else set(),
            callback=callback,
            filter_expression=filter_expression,
            priority=priority,
        )
        
        self._subscriptions[subscription_id] = subscription
        
        logger.info("Subscription created: %s for %s", subscription_id, subscriber_id)
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id not in self._subscriptions:
            return False
        
        del self._subscriptions[subscription_id]
        logger.info("Subscription removed: %s", subscription_id)
        
        return True
    
    def process_events(self, batch_size: int = 100) -> int:
        """Process pending events.

        Only events that are already queued at the beginning of this call are
        processed. Retries re-queued during processing are left for the next
        invocation, which keeps retry cadence deterministic and prevents a
        single failing event from being retried multiple times in one pass.
        """
        processed = 0
        pending_this_run = min(batch_size, len(self._queue))
        
        while processed < pending_this_run and self._queue:
            event = self._queue.popleft()
            
            if event.status != EventStatus.PENDING:
                continue
            
            event.status = EventStatus.PROCESSING
            
            # Find matching subscriptions
            subscribers = self._find_subscribers(event)
            
            if not subscribers:
                event.status = EventStatus.DELIVERED
                event.delivered_at = datetime.now(timezone.utc).isoformat()
                self._stats["delivered"] += 1
                processed += 1
                continue
            
            # Deliver to subscribers
            delivery_success = True
            for subscription in subscribers:
                if not self._deliver_to_subscriber(event, subscription):
                    delivery_success = False
            
            if delivery_success:
                event.status = EventStatus.DELIVERED
                event.delivered_at = datetime.now(timezone.utc).isoformat()
                self._stats["delivered"] += 1
            else:
                event.retry_count += 1
                if event.retry_count >= event.max_retries:
                    event.status = EventStatus.DEAD_LETTERED
                    event.failed_at = datetime.now(timezone.utc).isoformat()
                    self._dead_letter_queue.append(event)
                    self._stats["dead_lettered"] += 1
                else:
                    event.status = EventStatus.PENDING
                    self._queue.append(event)  # Re-queue for retry
            
            processed += 1
        
        return processed
    
    def _find_subscribers(self, event: Event) -> List[Subscription]:
        """Find subscriptions matching an event."""
        matching = []
        
        for subscription in self._subscriptions.values():
            if not subscription.enabled:
                continue
            
            # Check event type filter
            if subscription.event_types and event.event_type not in subscription.event_types:
                continue
            
            # Check filter expression (simplified)
            if subscription.filter_expression:
                if not self._evaluate_filter(event, subscription.filter_expression):
                    continue
            
            matching.append(subscription)
        
        # Sort by priority (higher first)
        matching.sort(key=lambda s: s.priority, reverse=True)
        
        return matching
    
    def _evaluate_filter(self, event: Event, filter_expression: str) -> bool:
        """Evaluate filter expression against event."""
        # Simplified filter evaluation
        # In production, use proper expression parser
        try:
            # Support basic filters like "payload.device_type == 'light'"
            if "==" in filter_expression:
                parts = filter_expression.split("==")
                if len(parts) == 2:
                    field_path = parts[0].strip()
                    expected_value = parts[1].strip().strip("'\"")
                    
                    if field_path.startswith("payload."):
                        field_name = field_path[8:]
                        actual_value = event.payload.get(field_name, "")
                        return str(actual_value) == expected_value
            
            return True  # Default to match if filter can't be evaluated
        except Exception:
            return True
    
    def _deliver_to_subscriber(self, event: Event, subscription: Subscription) -> bool:
        """Deliver event to a subscriber."""
        if not subscription.callback:
            return True  # No callback, consider delivered
        
        try:
            subscription.callback(event)
            return True
        except Exception as exc:
            logger.exception("Failed to deliver event to %s: %s",
                           subscription.subscriber_id, exc)
            return False
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID."""
        # Search in history
        for event in self._event_history:
            if event.event_id == event_id:
                return event.to_dict()
        
        # Search in dead letter queue
        for event in self._dead_letter_queue:
            if event.event_id == event_id:
                return event.to_dict()
        
        return None
    
    def get_events_by_type(self, event_type: str,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get events by type."""
        events = [
            e for e in self._event_history
            if e.event_type == event_type
        ]
        
        # Sort by created_at (newest first)
        events.sort(key=lambda e: e.created_at, reverse=True)
        
        return [e.to_dict() for e in events[:limit]]
    
    def get_dead_letter_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get dead letter queue events."""
        events = self._dead_letter_queue[-limit:]
        return [e.to_dict() for e in events]
    
    def retry_dead_letter(self, event_id: str) -> bool:
        """Retry a dead letter event."""
        for i, event in enumerate(self._dead_letter_queue):
            if event.event_id == event_id:
                event.retry_count = 0
                event.status = EventStatus.PENDING
                event.error_message = None
                self._queue.append(event)
                del self._dead_letter_queue[i]
                logger.info("Dead letter event retried: %s", event_id)
                return True
        
        return False
    
    def purge_dead_letter_queue(self) -> int:
        """Purge dead letter queue."""
        count = len(self._dead_letter_queue)
        self._dead_letter_queue.clear()
        logger.info("Dead letter queue purged: %d events", count)
        return count
    
    def cleanup_old_dead_letters(self) -> int:
        """Clean up old dead letter events."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._dead_letter_retention_hours)
        
        original_count = len(self._dead_letter_queue)
        self._dead_letter_queue = [
            e for e in self._dead_letter_queue
            if datetime.fromisoformat(e.created_at) > cutoff
        ]
        
        removed = original_count - len(self._dead_letter_queue)
        
        if removed > 0:
            logger.info("Cleaned up %d old dead letter events", removed)
        
        return removed
    
    def get_subscriptions(self, subscriber_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get subscriptions."""
        subscriptions = list(self._subscriptions.values())
        
        if subscriber_id:
            subscriptions = [s for s in subscriptions if s.subscriber_id == subscriber_id]
        
        return [s.to_dict() for s in subscriptions]
    
    def enable_subscription(self, subscription_id: str) -> bool:
        """Enable a subscription."""
        if subscription_id not in self._subscriptions:
            return False
        
        self._subscriptions[subscription_id].enabled = True
        return True
    
    def disable_subscription(self, subscription_id: str) -> bool:
        """Disable a subscription."""
        if subscription_id not in self._subscriptions:
            return False
        
        self._subscriptions[subscription_id].enabled = False
        return True
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status."""
        pending = len([e for e in self._queue if e.status == EventStatus.PENDING])
        processing = len([e for e in self._queue if e.status == EventStatus.PROCESSING])
        
        return {
            "queue_size": len(self._queue),
            "pending_events": pending,
            "processing_events": processing,
            "dead_letter_count": len(self._dead_letter_queue),
            "total_subscriptions": len(self._subscriptions),
            "active_subscriptions": len([s for s in self._subscriptions.values() if s.enabled]),
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            **self._stats,
            "event_history_size": len(self._event_history),
            "queue_size": len(self._queue),
            "dead_letter_count": len(self._dead_letter_queue),
        }
    
    def replay_events(self, event_type: Optional[str] = None,
                     since: Optional[datetime] = None,
                     limit: int = 1000) -> List[Dict[str, Any]]:
        """Replay events from history."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if since:
            events = [e for e in events if datetime.fromisoformat(e.created_at) >= since]
        
        # Sort by created_at (oldest first for replay)
        events.sort(key=lambda e: e.created_at)
        
        replayed = []
        for event in events[:limit]:
            # Re-publish the event
            new_event_id = self.publish(
                event_type=event.event_type,
                payload=event.payload,
                source=f"replay:{event.source}",
                priority=event.priority,
                headers={**event.headers, "X-Replayed-From": event.event_id},
            )
            replayed.append({"original_id": event.event_id, "replayed_id": new_event_id})
        
        logger.info("Replayed %d events", len(replayed))
        
        return replayed


def create_event_bus_engine(max_queue_size: int = 10000) -> EventBusEngine:
    """Factory function to create event bus engine."""
    return EventBusEngine(max_queue_size=max_queue_size)
