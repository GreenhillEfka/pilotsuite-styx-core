"""EventBus - Zentrale Kommunikationsschicht zwischen allen Core-Modulen.

Architektur-Pattern: Publish/Subscribe mit optionalem Filtering.

Module kommunizieren NICHT direkt miteinander, sondern ueber den EventBus.
Das entkoppelt Module und ermoeglicht:
  - Lose Kopplung (Module kennen sich nicht)
  - Einfaches Testen (EventBus mocken)
  - Nachvollziehbarkeit (alle Events zentralisiert)
  - Resillienz (ein fehlerhafter Subscriber crasht nicht andere)

Events:
  - zone.updated        Zone erstellt/geaendert
  - zone.deleted        Zone geloescht
  - zone.synced         Zonen von HA synchronisiert
  - neuron.evaluated    Neuronale Pipeline durchgelaufen
  - mood.changed        Stimmung hat sich geaendert
  - candidate.created   Neuer Automatisierungsvorschlag
  - candidate.accepted  Vorschlag vom Benutzer akzeptiert
  - candidate.dismissed Vorschlag vom Benutzer verworfen
  - graph.updated       Brain Graph aktualisiert
  - event.ingested      HA Events verarbeitet
  - habitus.pattern     Neues Muster entdeckt
  - chat.message        Chat-Nachricht empfangen
  - rag.indexed         RAG-Dokument indiziert

Usage:
    bus = EventBus()
    bus.subscribe("mood.changed", my_handler)
    bus.publish("mood.changed", {"mood": "relax", "confidence": 0.85})
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

EventHandler = Callable[[str, Dict[str, Any]], None]


@dataclass(frozen=True)
class Event:
    """Immutable event object."""
    topic: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""


class EventBus:
    """Thread-safe publish/subscribe event bus for inter-module communication.

    Features:
      - Topic-based routing (exact match + wildcard prefix)
      - Subscriber isolation (errors in one subscriber don't affect others)
      - Event history (bounded, configurable)
      - Thread-safe via Lock
      - Metrics: event counts, subscriber counts, error counts
    """

    def __init__(self, history_size: int = 500):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()
        self._history: List[Event] = []
        self._history_size = history_size
        self._metrics: Dict[str, int] = defaultdict(int)
        _LOGGER.info("EventBus initialized (history_size=%d)", history_size)

    def subscribe(self, topic: str, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to a topic. Returns unsubscribe function.

        Args:
            topic: Event topic. Use 'zone.*' for wildcard matching.
            handler: Callback(topic, data) called on matching events.

        Returns:
            Callable that unsubscribes when called.
        """
        with self._lock:
            if topic.endswith(".*"):
                prefix = topic[:-2]
                self._wildcard_subscribers[prefix].append(handler)
                _LOGGER.debug("Subscribed wildcard: %s.* -> %s", prefix, handler.__name__)
            else:
                self._subscribers[topic].append(handler)
                _LOGGER.debug("Subscribed: %s -> %s", topic, handler.__name__)

        def unsubscribe():
            with self._lock:
                if topic.endswith(".*"):
                    prefix = topic[:-2]
                    handlers = self._wildcard_subscribers.get(prefix, [])
                    if handler in handlers:
                        handlers.remove(handler)
                else:
                    handlers = self._subscribers.get(topic, [])
                    if handler in handlers:
                        handlers.remove(handler)
            _LOGGER.debug("Unsubscribed: %s -> %s", topic, handler.__name__)

        return unsubscribe

    def publish(self, topic: str, data: Optional[Dict[str, Any]] = None, source: str = "") -> None:
        """Publish an event to all subscribers.

        Args:
            topic: Event topic (e.g., 'mood.changed')
            data: Event payload dict
            source: Optional source identifier
        """
        data = data or {}
        event = Event(topic=topic, data=data, source=source)

        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
            self._metrics[f"published.{topic}"] += 1

            # Collect matching handlers (copy to release lock)
            handlers = list(self._subscribers.get(topic, []))
            # Wildcard matching: 'zone.updated' matches 'zone.*'
            topic_prefix = topic.rsplit(".", 1)[0] if "." in topic else topic
            handlers.extend(self._wildcard_subscribers.get(topic_prefix, []))

        # Call handlers outside lock to prevent deadlocks
        for handler in handlers:
            try:
                handler(topic, data)
            except Exception:
                self._metrics[f"errors.{topic}"] += 1
                _LOGGER.exception(
                    "EventBus subscriber error: %s on topic %s",
                    getattr(handler, "__name__", repr(handler)),
                    topic,
                )

    def get_history(self, topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent event history.

        Args:
            topic: Filter by topic (None = all)
            limit: Max entries to return

        Returns:
            List of event dicts, newest first.
        """
        with self._lock:
            events = list(reversed(self._history))
        if topic:
            events = [e for e in events if e.topic == topic or e.topic.startswith(f"{topic}.")]
        return [
            {"topic": e.topic, "data": e.data, "timestamp": e.timestamp, "source": e.source}
            for e in events[:limit]
        ]

    def get_metrics(self) -> Dict[str, Any]:
        """Get event bus metrics."""
        with self._lock:
            return {
                "total_events": len(self._history),
                "subscriber_count": sum(len(h) for h in self._subscribers.values()),
                "wildcard_count": sum(len(h) for h in self._wildcard_subscribers.values()),
                "topic_counts": dict(self._metrics),
            }

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()
            self._metrics.clear()


# Singleton instance
_bus_instance: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Get the singleton EventBus instance."""
    global _bus_instance
    if _bus_instance is None:
        with _bus_lock:
            if _bus_instance is None:
                _bus_instance = EventBus()
    return _bus_instance


def reset_event_bus() -> None:
    """Reset the singleton EventBus (for testing)."""
    global _bus_instance
    with _bus_lock:
        _bus_instance = None


__all__ = ["EventBus", "Event", "EventHandler", "get_event_bus", "reset_event_bus"]
