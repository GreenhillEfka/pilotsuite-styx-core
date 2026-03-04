"""
Integration Bus — Event-based pub/sub for cross-module communication.

Thread-safe, synchronous event bus that allows modules to communicate
without direct dependencies. Designed for the existing Flask/Waitress
synchronous architecture.

Usage::

    bus = IntegrationBus.get_instance()

    # Subscribe to events
    sub_id = bus.subscribe("mood.changed", my_handler)

    # Publish events
    bus.publish("mood.changed", {"mood": "focus", "confidence": 0.87})

    # Unsubscribe
    bus.unsubscribe(sub_id)
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Valid event types (extensible — unknown types are allowed but logged)
KNOWN_EVENT_TYPES = frozenset({
    "neuron.evaluated",
    "mood.changed",
    "pattern.discovered",
    "suggestion.created",
    "suggestion.accepted",
    "suggestion.rejected",
    "graph.updated",
    "module.state_changed",
})


@dataclass(frozen=True)
class BusEvent:
    """Immutable event payload on the integration bus."""

    event_type: str
    data: Dict[str, Any]
    source: str  # Module ID that published the event
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class IntegrationBus:
    """Thread-safe event bus for module-to-module communication.

    Singleton — use ``IntegrationBus.get_instance()`` for production,
    or instantiate directly in tests.
    """

    _instance: Optional[IntegrationBus] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # event_type → [(subscription_id, callback)]
        self._subscribers: Dict[str, List[tuple[str, Callable[[BusEvent], None]]]] = defaultdict(list)
        # subscription_id → event_type (for fast unsubscribe)
        self._sub_index: Dict[str, str] = {}
        # Metrics
        self._events_published = 0
        self._events_delivered = 0
        self._errors = 0
        _LOGGER.info("IntegrationBus initialized")

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> IntegrationBus:
        """Return the singleton IntegrationBus."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Reset singleton (testing only)."""
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[BusEvent], None],
    ) -> str:
        """Subscribe to events of a given type.

        Args:
            event_type: Event type to listen for (e.g. ``"mood.changed"``).
            callback: Function called with ``BusEvent`` when event fires.

        Returns:
            Subscription ID (use for unsubscribe).
        """
        sub_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._subscribers[event_type].append((sub_id, callback))
            self._sub_index[sub_id] = event_type
        _LOGGER.debug("Subscribed %s to %s", sub_id[:8], event_type)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription.

        Returns:
            ``True`` if the subscription was found and removed.
        """
        with self._lock:
            event_type = self._sub_index.pop(subscription_id, None)
            if event_type is None:
                return False
            self._subscribers[event_type] = [
                (sid, cb) for sid, cb in self._subscribers[event_type]
                if sid != subscription_id
            ]
        _LOGGER.debug("Unsubscribed %s from %s", subscription_id[:8], event_type)
        return True

    def publish(self, event_type: str, data: Dict[str, Any], source: str = "unknown") -> BusEvent:
        """Publish an event to all subscribers.

        Callbacks are invoked synchronously in subscription order.
        A failing callback does not prevent subsequent callbacks from running.

        Args:
            event_type: Type of event.
            data: Event payload.
            source: Module ID of the publisher.

        Returns:
            The published ``BusEvent``.
        """
        if event_type not in KNOWN_EVENT_TYPES:
            _LOGGER.debug("Publishing unknown event type: %s", event_type)

        event = BusEvent(event_type=event_type, data=data, source=source)
        self._events_published += 1

        with self._lock:
            subscribers = list(self._subscribers.get(event_type, []))

        for sub_id, callback in subscribers:
            try:
                callback(event)
                self._events_delivered += 1
            except Exception:
                self._errors += 1
                _LOGGER.exception(
                    "Subscriber %s failed on %s event from %s",
                    sub_id[:8], event_type, source,
                )

        return event

    def subscriber_count(self, event_type: str) -> int:
        """Return the number of subscribers for a given event type."""
        with self._lock:
            return len(self._subscribers.get(event_type, []))

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return bus throughput and health metrics."""
        with self._lock:
            total_subs = sum(len(subs) for subs in self._subscribers.values())
            event_types = list(self._subscribers.keys())
        return {
            "events_published": self._events_published,
            "events_delivered": self._events_delivered,
            "errors": self._errors,
            "total_subscribers": total_subs,
            "event_types_active": event_types,
        }

    def reset_stats(self) -> None:
        """Reset metrics counters (testing only)."""
        self._events_published = 0
        self._events_delivered = 0
        self._errors = 0
