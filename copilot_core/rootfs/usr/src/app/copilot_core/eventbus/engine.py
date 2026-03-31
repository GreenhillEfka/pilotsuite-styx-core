"""Event Bus Engine — Slice 43.

Event bus for PilotSuite Core inter-module communication.

Features:
- Publish/subscribe messaging
- Event routing and filtering
- Event persistence
- Dead letter queue
- Event replay
- Priority queues
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid
import threading

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class Event:
    """Event definition."""
    event_id: str
    event_type: str
    source: str
    payload: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    status: EventStatus = EventStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: Optional[str] = None
    expires_at: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "processed_at": self.processed_at,
            "expires_at": self.expires_at,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
        }


@dataclass
class Subscription:
    """Event subscription."""
    subscription_id: str
    subscriber_id: str
    event_types: List[str]  # Empty = all events
    filter_expr: Optional[str] = None  # Filter expression
    priority_filter: Optional[EventPriority] = None
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "subscriber_id": self.subscriber_id,
            "event_types": self.event_types,
            "filter_expr": self.filter_expr,
            "priority_filter": self.priority_filter.value if self.priority_filter else None,
            "active": self.active,
            "created_at": self.created_at,
        }


class EventBusEngine:
    """Event bus messaging engine."""
    
    def __init__(self, max_queue_size: int = 10000,
                 max_history_size: int = 100000):
        self._events: Dict[str, Event] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._handlers: Dict[str, List[Callable]] = {}  # event_type -> [handlers]
        self._dead_letter_queue: List[Event] = []
        self._event_history: List[Event] = []
        
        self._max_queue_size = max_queue_size
        self._max_history_size = max_history_size
        
        # Priority queues
        self._priority_queues: Dict[EventPriority, List[str]] = {
            EventPriority.CRITICAL: [],
            EventPriority.HIGH: [],
            EventPriority.NORMAL: [],
            EventPriority.LOW: [],
        }
        
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "total_events": 0,
            "processed_events": 0,
            "failed_events": 0,
            "dead_letter_count": 0,
            "by_type": {},
        }
    
    def publish(self, event_type: str, payload: Dict[str, Any],
               source: str = "system",
               priority: EventPriority = EventPriority.NORMAL,
               correlation_id: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None,
               expires_at: Optional[str] = None) -> str:
        """Publish an event to the bus."""
        with self._lock:
            event_id = f"evt_{uuid.uuid4().hex[:12]}"
            
            event = Event(
                event_id=event_id,
                event_type=event_type,
                source=source,
                payload=payload,
                priority=priority,
                correlation_id=correlation_id,
                metadata=metadata or {},
                expires_at=expires_at,
            )
            
            self._events[event_id] = event
            
            # Add to priority queue
            self._priority_queues[priority].append(event_id)
            
            # Update stats
            self._stats["total_events"] += 1
            by_type = self._stats["by_type"].get(event_type, 0)
            self._stats["by_type"][event_type] = by_type + 1
            
            # Trim queue if needed
            self._trim_queue()
            
            # Process immediately
            self._dispatch_event(event)
            
            logger.debug("Event published: %s (%s)", event_type, event_id)
            
            return event_id
    
    def subscribe(self, subscriber_id: str, event_types: List[str],
                 handler: Callable[[Event], None],
                 filter_expr: Optional[str] = None,
                 priority_filter: Optional[EventPriority] = None) -> str:
        """Subscribe to events."""
        with self._lock:
            subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
            
            subscription = Subscription(
                subscription_id=subscription_id,
                subscriber_id=subscriber_id,
                event_types=event_types,
                filter_expr=filter_expr,
                priority_filter=priority_filter,
            )
            
            self._subscriptions[subscription_id] = subscription
            
            # Register handler for each event type
            for event_type in event_types:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                self._handlers[event_type].append(handler)
            
            # Also register for "all" if empty
            if not event_types:
                if "*" not in self._handlers:
                    self._handlers["*"] = []
                self._handlers["*"].append(handler)
            
            logger.info("Subscription created: %s for %s", subscription_id, subscriber_id)
            
            return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            subscription = self._subscriptions[subscription_id]
            subscription.active = False
            
            # Remove handlers
            for event_type in subscription.event_types:
                if event_type in self._handlers:
                    # Remove handler (simplified - in production use weak refs)
                    pass
            
            del self._subscriptions[subscription_id]
            
            logger.info("Subscription removed: %s", subscription_id)
            
            return True
    
    def process_events(self, batch_size: int = 100) -> int:
        """Process pending events."""
        processed = 0
        
        # Process by priority (critical first)
        for priority in [EventPriority.CRITICAL, EventPriority.HIGH, 
                        EventPriority.NORMAL, EventPriority.LOW]:
            queue = self._priority_queues[priority]
            
            while queue and processed < batch_size:
                event_id = queue.pop(0)
                
                if event_id in self._events:
                    event = self._events[event_id]
                    if event.status == EventStatus.PENDING:
                        self._process_event(event)
                        processed += 1
        
        return processed
    
    def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to handlers."""
        event_type = event.event_type
        
        # Get handlers for specific type
        handlers = self._handlers.get(event_type, [])
        
        # Get handlers for all events
        handlers.extend(self._handlers.get("*", []))
        
        # Get handlers for pattern matches
        for pattern_type, pattern_handlers in self._handlers.items():
            if pattern_type.endswith("*") and event_type.startswith(pattern_type[:-1]):
                handlers.extend(pattern_handlers)
        
        # Call handlers
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception("Handler failed for event %s: %s", event.event_id, exc)
    
    def _process_event(self, event: Event) -> None:
        """Process a single event."""
        with self._lock:
            # Check expiration
            if event.expires_at:
                expires = datetime.fromisoformat(event.expires_at)
                if datetime.now(timezone.utc) > expires:
                    event.status = EventStatus.FAILED
                    event.error_message = "Event expired"
                    self._move_to_dead_letter(event)
                    return
            
            event.status = EventStatus.PROCESSING
            
            try:
                # Dispatch to handlers
                self._dispatch_event(event)
                
                event.status = EventStatus.COMPLETED
                event.processed_at = datetime.now(timezone.utc).isoformat()
                
                self._stats["processed_events"] += 1
                
                # Add to history
                self._add_to_history(event)
                
            except Exception as exc:
                event.retry_count += 1
                event.error_message = str(exc)
                
                if event.retry_count >= event.max_retries:
                    event.status = EventStatus.FAILED
                    self._move_to_dead_letter(event)
                    self._stats["failed_events"] += 1
                else:
                    event.status = EventStatus.PENDING
                    # Re-queue
                    self._priority_queues[event.priority].insert(0, event.event_id)
    
    def _move_to_dead_letter(self, event: Event) -> None:
        """Move event to dead letter queue."""
        event.status = EventStatus.DEAD_LETTER
        self._dead_letter_queue.append(event)
        self._stats["dead_letter_count"] += 1
        
        # Trim dead letter queue
        if len(self._dead_letter_queue) > 1000:
            self._dead_letter_queue = self._dead_letter_queue[-1000:]
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._event_history.append(event)
        
        # Trim history
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
    
    def _trim_queue(self) -> None:
        """Trim queues if over capacity."""
        total_queued = sum(len(q) for q in self._priority_queues.values())
        
        if total_queued > self._max_queue_size:
            # Remove oldest low priority events
            while (len(self._priority_queues[EventPriority.LOW]) > 0 and 
                   sum(len(q) for q in self._priority_queues.values()) > self._max_queue_size):
                event_id = self._priority_queues[EventPriority.LOW].pop(0)
                if event_id in self._events:
                    del self._events[event_id]
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID."""
        if event_id not in self._events:
            return None
        
        return self._events[event_id].to_dict()
    
    def get_events_by_type(self, event_type: str,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get events by type."""
        events = [
            e for e in self._events.values()
            if e.event_type == event_type
        ]
        
        events.sort(key=lambda e: e.created_at, reverse=True)
        
        return [e.to_dict() for e in events[:limit]]
    
    def get_events_by_correlation(self, correlation_id: str,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get events by correlation ID."""
        events = [
            e for e in self._events.values()
            if e.correlation_id == correlation_id
        ]
        
        events.sort(key=lambda e: e.created_at, reverse=True)
        
        return [e.to_dict() for e in events[:limit]]
    
    def get_dead_letter_queue(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get dead letter queue."""
        return [e.to_dict() for e in self._dead_letter_queue[-limit:]]
    
    def replay_dead_letter(self, event_id: str) -> bool:
        """Replay event from dead letter queue."""
        with self._lock:
            event = None
            for e in self._dead_letter_queue:
                if e.event_id == event_id:
                    event = e
                    break
            
            if not event:
                return False
            
            # Reset event
            event.status = EventStatus.PENDING
            event.retry_count = 0
            event.error_message = None
            event.processed_at = None
            
            # Re-queue
            self._priority_queues[event.priority].append(event_id)
            
            # Remove from dead letter
            self._dead_letter_queue.remove(event)
            self._stats["dead_letter_count"] -= 1
            
            logger.info("Event replayed from dead letter: %s", event_id)
            
            return True
    
    def clear_dead_letter_queue(self) -> int:
        """Clear dead letter queue."""
        with self._lock:
            count = len(self._dead_letter_queue)
            self._dead_letter_queue.clear()
            self._stats["dead_letter_count"] = 0
            return count
    
    def get_event_history(self, event_type: Optional[str] = None,
                         source: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """Get event history."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        events.sort(key=lambda e: e.created_at, reverse=True)
        
        return [e.to_dict() for e in events[:limit]]
    
    def get_subscriptions(self, subscriber_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get subscriptions."""
        subscriptions = list(self._subscriptions.values())
        
        if subscriber_id:
            subscriptions = [s for s in subscriptions if s.subscriber_id == subscriber_id]
        
        return [s.to_dict() for s in subscriptions]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        queue_sizes = {
            p.value: len(q) for p, q in self._priority_queues.items()
        }
        
        return {
            **self._stats,
            "queue_sizes": queue_sizes,
            "total_subscriptions": len(self._subscriptions),
            "history_size": len(self._event_history),
        }
    
    def purge_events(self, older_than: Optional[str] = None) -> int:
        """Purge events from queues."""
        with self._lock:
            count = 0
            
            if older_than:
                cutoff = datetime.fromisoformat(older_than)
                keys_to_remove = []
                
                for event_id, event in self._events.items():
                    created = datetime.fromisoformat(event.created_at)
                    if created < cutoff:
                        keys_to_remove.append(event_id)
                
                for event_id in keys_to_remove:
                    del self._events[event_id]
                    count += 1
            else:
                count = len(self._events)
                self._events.clear()
                for q in self._priority_queues.values():
                    q.clear()
            
            return count
    
    def get_pending_events_count(self) -> int:
        """Get count of pending events."""
        return sum(
            1 for e in self._events.values()
            if e.status == EventStatus.PENDING
        )


def create_event_bus_engine(max_queue_size: int = 10000) -> EventBusEngine:
    """Factory function to create event bus engine."""
    return EventBusEngine(max_queue_size=max_queue_size)
