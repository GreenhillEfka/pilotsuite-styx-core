"""Event Propagation Systematics — P2-005.

Implements reliable event propagation with delivery guarantees, ordering,
deduplication, dead letter queue, and retry mechanisms.

Features:
- At-least-once delivery guarantee
- Exactly-once delivery guarantee (with deduplication)
- Event ordering (per-source and global sequence)
- Deduplication using event IDs and content hashes
- Dead letter queue for failed events
- Retry mechanisms with exponential backoff
- Propagation tracking and acknowledgments
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from abc import ABC, abstractmethod
import threading

logger = logging.getLogger(__name__)


# =============================================================================
# DELIVERY GUARANTEES
# =============================================================================

class DeliveryGuarantee(Enum):
    """Event delivery guarantee levels."""
    AT_MOST_ONCE = "at_most_once"  # Fire and forget
    AT_LEAST_ONCE = "at_least_once"  # Retry until ack
    EXACTLY_ONCE = "exactly_once"  # Deduplicated at-least-once


class PropagationStatus(Enum):
    """Event propagation status."""
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    DEDUPLICATED = "deduplicated"


# =============================================================================
# EVENT MODEL
# =============================================================================

@dataclass
class PropagationEvent:
    """Event with propagation metadata."""
    event_id: str
    event_type: str
    source: str
    payload: Dict[str, Any]
    guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    status: PropagationStatus = PropagationStatus.PENDING
    sequence: int = 0
    source_sequence: int = 0
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    failed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 5
    last_error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    recipients: Set[str] = field(default_factory=set)
    acknowledged_by: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
            "guarantee": self.guarantee.value,
            "status": self.status.value,
            "sequence": self.sequence,
            "source_sequence": self.source_sequence,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "acknowledged_at": self.acknowledged_at,
            "failed_at": self.failed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_error": self.last_error,
            "headers": self.headers,
            "recipients": list(self.recipients),
            "acknowledged_by": list(self.acknowledged_by),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PropagationEvent':
        data["guarantee"] = DeliveryGuarantee(data["guarantee"])
        data["status"] = PropagationStatus(data["status"])
        data["recipients"] = set(data.get("recipients", []))
        data["acknowledged_by"] = set(data.get("acknowledged_by", []))
        return cls(**data)
    
    def content_hash(self) -> str:
        """Generate content hash for deduplication."""
        content = json.dumps({
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# DEDUPLICATION TRACKER
# =============================================================================

class DeduplicationTracker:
    """Tracks seen events for deduplication."""
    
    def __init__(self, max_size: int = 100000, ttl_seconds: int = 3600):
        self._seen_ids: Dict[str, float] = {}  # event_id -> timestamp
        self._seen_hashes: Dict[str, str] = {}  # content_hash -> event_id
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
    
    def is_duplicate(self, event: PropagationEvent) -> Tuple[bool, Optional[str]]:
        """Check if event is duplicate. Returns (is_duplicate, original_event_id)."""
        now = time.time()
        
        with self._lock:
            # Check event ID
            if event.event_id in self._seen_ids:
                return True, self._seen_ids.get(event.event_id)
            
            # Check content hash (for exactly-once)
            if event.guarantee == DeliveryGuarantee.EXACTLY_ONCE:
                content_hash = event.content_hash()
                if content_hash in self._seen_hashes:
                    return True, self._seen_hashes[content_hash]
            
            return False, None
    
    def mark_seen(self, event: PropagationEvent) -> None:
        """Mark event as seen."""
        now = time.time()
        
        with self._lock:
            self._seen_ids[event.event_id] = now
            if event.guarantee == DeliveryGuarantee.EXACTLY_ONCE:
                content_hash = event.content_hash()
                self._seen_hashes[content_hash] = event.event_id
            
            # Cleanup old entries
            self._cleanup(now)
    
    def _cleanup(self, now: float) -> None:
        """Remove expired entries."""
        cutoff = now - self._ttl_seconds
        
        expired_ids = [
            eid for eid, ts in self._seen_ids.items()
            if ts < cutoff
        ]
        
        for eid in expired_ids:
            del self._seen_ids[eid]
        
        # Cleanup hash map
        expired_hashes = [
            h for h, eid in self._seen_hashes.items()
            if eid not in self._seen_ids
        ]
        
        for h in expired_hashes:
            del self._seen_hashes[h]
        
        # Enforce max size
        if len(self._seen_ids) > self._max_size:
            sorted_ids = sorted(self._seen_ids.items(), key=lambda x: x[1])
            for eid, _ in sorted_ids[:len(sorted_ids) - self._max_size]:
                del self._seen_ids[eid]
    
    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "seen_ids": len(self._seen_ids),
                "seen_hashes": len(self._seen_hashes),
            }


# =============================================================================
# SEQUENCE MANAGER
# =============================================================================

class SequenceManager:
    """Manages event sequencing for ordering guarantees."""
    
    def __init__(self):
        self._global_sequence = 0
        self._source_sequences: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def next_global_sequence(self) -> int:
        """Get next global sequence number."""
        with self._lock:
            self._global_sequence += 1
            return self._global_sequence
    
    def next_source_sequence(self, source: str) -> int:
        """Get next sequence number for a source."""
        with self._lock:
            self._source_sequences[source] += 1
            return self._source_sequences[source]
    
    def get_source_sequence(self, source: str) -> int:
        """Get current sequence number for a source."""
        with self._lock:
            return self._source_sequences.get(source, 0)
    
    def reset(self) -> None:
        """Reset all sequences."""
        with self._lock:
            self._global_sequence = 0
            self._source_sequences.clear()
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "global_sequence": self._global_sequence,
                "source_count": len(self._source_sequences),
            }


# =============================================================================
# DEAD LETTER QUEUE
# =============================================================================

@dataclass
class DeadLetterEntry:
    """Entry in dead letter queue."""
    event: PropagationEvent
    failure_reason: str
    failed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retry_scheduled: bool = False
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event.to_dict(),
            "failure_reason": self.failure_reason,
            "failed_at": self.failed_at,
            "retry_scheduled": self.retry_scheduled,
            "retry_count": self.retry_count,
        }


class DeadLetterQueue:
    """Dead letter queue for failed events."""
    
    def __init__(self, max_size: int = 10000, retention_hours: int = 72):
        self._queue: List[DeadLetterEntry] = []
        self._max_size = max_size
        self._retention_hours = retention_hours
        self._lock = threading.Lock()
    
    def add(self, event: PropagationEvent, failure_reason: str) -> None:
        """Add failed event to DLQ."""
        with self._lock:
            entry = DeadLetterEntry(
                event=event,
                failure_reason=failure_reason,
            )
            
            self._queue.append(entry)
            
            # Enforce max size
            if len(self._queue) > self._max_size:
                removed = self._queue.pop(0)
                logger.warning(f"DLQ full, removed oldest: {removed.event.event_id}")
    
    def get_all(self, limit: int = 100) -> List[DeadLetterEntry]:
        """Get all DLQ entries."""
        with self._lock:
            return self._queue[-limit:]
    
    def get_by_event_id(self, event_id: str) -> Optional[DeadLetterEntry]:
        """Get DLQ entry by event ID."""
        with self._lock:
            for entry in self._queue:
                if entry.event.event_id == event_id:
                    return entry
            return None
    
    def remove(self, event_id: str) -> bool:
        """Remove entry from DLQ."""
        with self._lock:
            for i, entry in enumerate(self._queue):
                if entry.event.event_id == event_id:
                    self._queue.pop(i)
                    return True
            return False
    
    def mark_retry_scheduled(self, event_id: str) -> bool:
        """Mark entry as retry scheduled."""
        with self._lock:
            for entry in self._queue:
                if entry.event.event_id == event_id:
                    entry.retry_scheduled = True
                    entry.retry_count += 1
                    return True
            return False
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self._retention_hours)
            original_count = len(self._queue)
            
            self._queue = [
                e for e in self._queue
                if datetime.fromisoformat(e.failed_at) > cutoff
            ]
            
            removed = original_count - len(self._queue)
            if removed > 0:
                logger.info(f"Cleaned up {removed} expired DLQ entries")
            
            return removed
    
    def clear(self) -> int:
        """Clear all entries."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count
    
    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._queue),
                "max_size": self._max_size,
                "retention_hours": self._retention_hours,
                "retry_pending": sum(1 for e in self._queue if e.retry_scheduled),
            }


# =============================================================================
# RETRY MANAGER WITH BACKOFF
# =============================================================================

class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"


@dataclass
class RetryConfig:
    """Retry configuration."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_WITH_JITTER
    base_delay_ms: int = 100
    max_delay_ms: int = 60000  # 1 minute
    max_retries: int = 5
    jitter_factor: float = 0.1  # 10% jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for attempt (returns seconds)."""
        import random
        
        if self.strategy == RetryStrategy.FIXED:
            delay_ms = self.base_delay_ms
        elif self.strategy == RetryStrategy.LINEAR:
            delay_ms = self.base_delay_ms * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay_ms = self.base_delay_ms * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.EXPONENTIAL_WITH_JITTER:
            base = self.base_delay_ms * (2 ** (attempt - 1))
            jitter = base * self.jitter_factor * random.random()
            delay_ms = base + jitter
        else:
            delay_ms = self.base_delay_ms
        
        # Cap at max delay
        delay_ms = min(delay_ms, self.max_delay_ms)
        
        return delay_ms / 1000.0  # Convert to seconds


class RetryManager:
    """Manages retry scheduling with backoff."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self._config = config or RetryConfig()
        self._pending_retries: Dict[str, Tuple[PropagationEvent, float]] = {}  # event_id -> (event, retry_at)
        self._lock = threading.Lock()
    
    def schedule_retry(self, event: PropagationEvent) -> float:
        """Schedule retry for event. Returns delay in seconds."""
        attempt = event.retry_count + 1
        delay = self._config.get_delay(attempt)
        retry_at = time.time() + delay
        
        with self._lock:
            self._pending_retries[event.event_id] = (event, retry_at)
        
        logger.debug(f"Scheduled retry for {event.event_id} in {delay:.2f}s (attempt {attempt})")
        
        return delay
    
    def get_due_retries(self) -> List[PropagationEvent]:
        """Get events due for retry."""
        now = time.time()
        due = []
        
        with self._lock:
            event_ids_to_remove = []
            
            for event_id, (event, retry_at) in self._pending_retries.items():
                if now >= retry_at:
                    due.append(event)
                    event_ids_to_remove.append(event_id)
            
            for event_id in event_ids_to_remove:
                del self._pending_retries[event_id]
        
        return due
    
    def cancel_retry(self, event_id: str) -> bool:
        """Cancel scheduled retry."""
        with self._lock:
            if event_id in self._pending_retries:
                del self._pending_retries[event_id]
                return True
            return False
    
    def is_pending(self, event_id: str) -> bool:
        """Check if retry is pending."""
        with self._lock:
            return event_id in self._pending_retries
    
    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_retries)
    
    @property
    def config(self) -> RetryConfig:
        return self._config


# =============================================================================
# PROPAGATION TARGET
# =============================================================================

class PropagationTarget(ABC):
    """Abstract propagation target."""
    
    @abstractmethod
    def deliver(self, event: PropagationEvent) -> bool:
        """Deliver event to target. Returns True if successful."""
        pass
    
    @abstractmethod
    def acknowledge(self, event_id: str) -> bool:
        """Acknowledge event delivery."""
        pass
    
    @property
    @abstractmethod
    def target_id(self) -> str:
        """Target identifier."""
        pass


class CallbackTarget(PropagationTarget):
    """Callback-based propagation target."""
    
    def __init__(self, target_id: str, callback: Callable[[PropagationEvent], bool]):
        self._target_id = target_id
        self._callback = callback
        self._acknowledged: Set[str] = set()
        self._lock = threading.Lock()
    
    def deliver(self, event: PropagationEvent) -> bool:
        try:
            success = self._callback(event)
            if success:
                with self._lock:
                    self._acknowledged.add(event.event_id)
            return success
        except Exception as e:
            logger.exception(f"Callback delivery failed for {self._target_id}: {e}")
            return False
    
    def acknowledge(self, event_id: str) -> bool:
        with self._lock:
            self._acknowledged.add(event_id)
            return True
    
    @property
    def target_id(self) -> str:
        return self._target_id


# =============================================================================
# EVENT PROPAGATION ENGINE
# =============================================================================

class EventPropagationEngine:
    """Main event propagation engine with guarantees."""
    
    def __init__(
        self,
        guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        retry_config: Optional[RetryConfig] = None,
        dlq_max_size: int = 10000,
        dlq_retention_hours: int = 72,
        dedup_max_size: int = 100000,
        dedup_ttl_seconds: int = 3600,
    ):
        self._guarantee = guarantee
        self._sequence_manager = SequenceManager()
        self._dedup_tracker = DeduplicationTracker(
            max_size=dedup_max_size,
            ttl_seconds=dedup_ttl_seconds,
        )
        self._dead_letter_queue = DeadLetterQueue(
            max_size=dlq_max_size,
            retention_hours=dlq_retention_hours,
        )
        self._retry_manager = RetryManager(retry_config)
        
        self._targets: Dict[str, PropagationTarget] = {}
        self._pending_events: Dict[str, PropagationEvent] = {}
        self._event_history: List[PropagationEvent] = []
        self._max_history_size = 10000
        
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._stats = {
            "published": 0,
            "delivered": 0,
            "acknowledged": 0,
            "failed": 0,
            "deduplicated": 0,
            "dead_lettered": 0,
        }
    
    def register_target(self, target: PropagationTarget) -> None:
        """Register a propagation target."""
        with self._lock:
            self._targets[target.target_id] = target
        logger.info(f"Registered propagation target: {target.target_id}")
    
    def unregister_target(self, target_id: str) -> bool:
        """Unregister a propagation target."""
        with self._lock:
            if target_id in self._targets:
                del self._targets[target_id]
                logger.info(f"Unregistered propagation target: {target_id}")
                return True
            return False
    
    def publish(self, event: PropagationEvent) -> str:
        """Publish event for propagation."""
        with self._lock:
            # Assign sequences
            event.sequence = self._sequence_manager.next_global_sequence()
            event.source_sequence = self._sequence_manager.next_source_sequence(event.source)
            
            # Check for duplicates
            is_dup, original_id = self._dedup_tracker.is_duplicate(event)
            if is_dup:
                event.status = PropagationStatus.DEDUPLICATED
                event.headers["X-Duplicate-Of"] = original_id
                self._stats["deduplicated"] += 1
                logger.debug(f"Event deduplicated: {event.event_id} (duplicate of {original_id})")
                return event.event_id
            
            # Mark as seen
            self._dedup_tracker.mark_seen(event)
            
            # Set guarantee
            if event.guarantee == DeliveryGuarantee.AT_MOST_ONCE:
                event.max_retries = 0
            
            # Add to pending
            self._pending_events[event.event_id] = event
            
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history = self._event_history[-self._max_history_size:]
            
            self._stats["published"] += 1
        
        logger.debug(f"Event published: {event.event_type} ({event.event_id})")
        
        return event.event_id
    
    def publish_sync(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "unknown",
        guarantee: Optional[DeliveryGuarantee] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Synchronous publish helper."""
        event = PropagationEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            payload=payload,
            guarantee=guarantee or self._guarantee,
            correlation_id=correlation_id,
        )
        return self.publish(event)
    
    def acknowledge(self, event_id: str, target_id: str) -> bool:
        """Acknowledge event delivery from a target."""
        with self._lock:
            event = self._pending_events.get(event_id)
            if not event:
                logger.warning(f"Ack for unknown event: {event_id}")
                return False
            
            event.acknowledged_by.add(target_id)
            
            # Check if all targets acknowledged
            if event.recipients and event.acknowledged_by >= event.recipients:
                event.status = PropagationStatus.ACKNOWLEDGED
                event.acknowledged_at = datetime.now(timezone.utc).isoformat()
                self._stats["acknowledged"] += 1
                
                # Remove from pending
                del self._pending_events[event_id]
                
                # Cancel any pending retries
                self._retry_manager.cancel_retry(event_id)
                
                logger.debug(f"Event fully acknowledged: {event_id}")
            
            return True
    
    def process_pending(self) -> int:
        """Process pending events. Returns count processed."""
        processed = 0
        
        with self._lock:
            events_to_process = list(self._pending_events.values())
        
        for event in events_to_process:
            if event.status in (PropagationStatus.DELIVERED, PropagationStatus.ACKNOWLEDGED):
                continue
            
            if event.status == PropagationStatus.DEDUPLICATED:
                continue
            
            # Check if due for retry
            if event.retry_count > 0 and self._retry_manager.is_pending(event.event_id):
                continue
            
            # Deliver to targets
            self._deliver_event(event)
            processed += 1
        
        # Process due retries
        due_retries = self._retry_manager.get_due_retries()
        for event in due_retries:
            if event.event_id in self._pending_events:
                event.status = PropagationStatus.PENDING
                self._deliver_event(event)
                processed += 1
        
        return processed
    
    def _deliver_event(self, event: PropagationEvent) -> None:
        """Deliver event to all targets."""
        if not self._targets:
            logger.debug(f"No targets registered, event {event.event_id} marked delivered")
            event.status = PropagationStatus.DELIVERED
            event.delivered_at = datetime.now(timezone.utc).isoformat()
            return
        
        event.status = PropagationStatus.IN_FLIGHT
        failed_targets = []
        
        for target_id, target in self._targets.items():
            if target_id in event.acknowledged_by:
                continue
            
            event.recipients.add(target_id)
            
            try:
                success = target.deliver(event)
                if success:
                    event.acknowledged_by.add(target_id)
                else:
                    failed_targets.append((target_id, "Delivery failed"))
            except Exception as e:
                failed_targets.append((target_id, str(e)))
        
        # Check result
        if not failed_targets:
            event.status = PropagationStatus.DELIVERED
            event.delivered_at = datetime.now(timezone.utc).isoformat()
            self._stats["delivered"] += 1
            logger.debug(f"Event delivered: {event.event_id}")
        else:
            self._handle_delivery_failure(event, failed_targets)
    
    def _handle_delivery_failure(
        self,
        event: PropagationEvent,
        failed_targets: List[Tuple[str, str]],
    ) -> None:
        """Handle delivery failure."""
        event.retry_count += 1
        failure_reasons = [f"{tid}: {reason}" for tid, reason in failed_targets]
        event.last_error = "; ".join(failure_reasons)
        
        if event.retry_count >= event.max_retries:
            # Move to dead letter queue
            event.status = PropagationStatus.DEAD_LETTERED
            event.failed_at = datetime.now(timezone.utc).isoformat()
            
            self._dead_letter_queue.add(event, event.last_error)
            self._stats["dead_lettered"] += 1
            self._stats["failed"] += 1
            
            # Remove from pending
            with self._lock:
                if event.event_id in self._pending_events:
                    del self._pending_events[event.event_id]
            
            logger.error(f"Event failed after {event.retry_count} retries: {event.event_id}")
        else:
            # Schedule retry
            event.status = PropagationStatus.PENDING
            delay = self._retry_manager.schedule_retry(event)
            self._stats["failed"] += 1
            logger.warning(f"Event delivery failed, retry {event.retry_count}/{event.max_retries} in {delay:.2f}s: {event.event_id}")
    
    def start(self) -> None:
        """Start background processing."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._worker_thread.start()
        
        logger.info("EventPropagationEngine started")
    
    def stop(self) -> None:
        """Stop background processing."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        
        logger.info("EventPropagationEngine stopped")
    
    def _process_loop(self) -> None:
        """Background processing loop."""
        while self._running:
            try:
                self.process_pending()
                time.sleep(0.01)  # 10ms poll interval
            except Exception as e:
                logger.error(f"Process loop error: {e}", exc_info=True)
                time.sleep(0.1)
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID."""
        with self._lock:
            # Check pending
            if event_id in self._pending_events:
                return self._pending_events[event_id].to_dict()
            
            # Check history
            for event in self._event_history:
                if event.event_id == event_id:
                    return event.to_dict()
        
        # Check DLQ
        entry = self._dead_letter_queue.get_by_event_id(event_id)
        if entry:
            return entry.to_dict()
        
        return None
    
    def get_dead_letter_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get dead letter queue events."""
        entries = self._dead_letter_queue.get_all(limit)
        return [e.to_dict() for e in entries]
    
    def retry_dead_letter(self, event_id: str) -> bool:
        """Retry a dead letter event."""
        entry = self._dead_letter_queue.get_by_event_id(event_id)
        if not entry:
            return False
        
        event = entry.event
        event.retry_count = 0
        event.status = PropagationStatus.PENDING
        event.last_error = None
        event.failed_at = None
        
        self._dead_letter_queue.remove(event_id)
        
        with self._lock:
            self._pending_events[event.event_id] = event
        
        logger.info(f"Dead letter event retried: {event_id}")
        return True
    
    def purge_dead_letter_queue(self) -> int:
        """Purge dead letter queue."""
        return self._dead_letter_queue.clear()
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "guarantee": self._guarantee.value,
                "pending_count": len(self._pending_events),
                "target_count": len(self._targets),
                "history_size": len(self._event_history),
                **self._stats,
                "sequence_manager": self._sequence_manager.stats,
                "dedup_tracker": self._dedup_tracker.stats,
                "dead_letter_queue": self._dead_letter_queue.stats,
                "retry_manager": {
                    "pending_count": self._retry_manager.pending_count,
                    "config": {
                        "strategy": self._retry_manager.config.strategy.value,
                        "base_delay_ms": self._retry_manager.config.base_delay_ms,
                        "max_delay_ms": self._retry_manager.config.max_delay_ms,
                        "max_retries": self._retry_manager.config.max_retries,
                    },
                },
            }


# =============================================================================
# SINGLETON
# =============================================================================

_propagation_engine_instance: Optional[EventPropagationEngine] = None


def get_propagation_engine(
    guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
) -> EventPropagationEngine:
    """Get singleton propagation engine instance."""
    global _propagation_engine_instance
    
    if _propagation_engine_instance is None:
        _propagation_engine_instance = EventPropagationEngine(guarantee=guarantee)
    
    return _propagation_engine_instance


def reset_propagation_engine() -> None:
    """Reset singleton instance (for testing)."""
    global _propagation_engine_instance
    if _propagation_engine_instance:
        _propagation_engine_instance.stop()
    _propagation_engine_instance = None
