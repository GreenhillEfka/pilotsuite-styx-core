"""CQRS Pattern — Command Query Responsibility Segregation for Events."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, TypeVar
from enum import Enum
import time
import json
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


class EventType(Enum):
    """Event types for CQRS."""
    COMMAND = "command"
    QUERY = "query"
    EVENT = "event"


@dataclass
class Command:
    """Write operation command."""
    id: str
    type: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Query:
    """Read operation query."""
    id: str
    type: str
    filters: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class Event:
    """Domain event (fact that happened)."""
    id: str
    type: str
    aggregate_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())
    version: int = 1


@dataclass
class EventEnvelope:
    """Wrapped event for storage/transmission."""
    event: Event
    sequence_number: int
    checksum: str


class CommandHandler:
    """Handles write commands."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, command_type: str, handler: Callable):
        """Register command handler."""
        self._handlers[command_type] = handler
        logger.info(f"Command handler registered: {command_type}")

    async def handle(self, command: Command) -> Any:
        """Execute command."""
        if command.type not in self._handlers:
            raise ValueError(f"No handler for command: {command.type}")
        
        handler = self._handlers[command.type]
        result = await handler(command.payload)
        
        logger.info(f"Command executed: {command.type} ({command.id})")
        return result


class QueryHandler:
    """Handles read queries."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: int = 300  # 5 minutes

    def register(self, query_type: str, handler: Callable):
        """Register query handler."""
        self._handlers[query_type] = handler

    async def handle(self, query: Query) -> Any:
        """Execute query."""
        if query.type not in self._handlers:
            raise ValueError(f"No handler for query: {query.type}")
        
        # Check cache
        cache_key = f"{query.type}:{json.dumps(query.filters, sort_keys=True)}"
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Query cache hit: {query.type}")
                return cached_result
        
        # Execute query
        handler = self._handlers[query.type]
        result = await handler(query.filters)
        
        # Cache result
        self._cache[cache_key] = (time.time(), result)
        
        logger.info(f"Query executed: {query.type} ({query.id})")
        return result


class EventStore:
    """Append-only event store for event sourcing."""

    def __init__(self, storage_path: str = "/config/events"):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._sequence = 0
        self._events: List[EventEnvelope] = []
        self._subscribers: List[Callable] = []
        self._load_from_disk()

    def _load_from_disk(self):
        """Load events from disk."""
        event_file = self._storage_path / "events.jsonl"
        if event_file.exists():
            with open(event_file, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    event = Event(**data['event'])
                    envelope = EventEnvelope(
                        event=event,
                        sequence_number=data['sequence_number'],
                        checksum=data['checksum'],
                    )
                    self._events.append(envelope)
                    self._sequence = max(self._sequence, data['sequence_number'])
            logger.info(f"Loaded {len(self._events)} events from disk")

    def _save_to_disk(self, envelope: EventEnvelope):
        """Append event to disk."""
        event_file = self._storage_path / "events.jsonl"
        with open(event_file, 'a') as f:
            f.write(json.dumps({
                'event': {
                    'id': envelope.event.id,
                    'type': envelope.event.type,
                    'aggregate_id': envelope.event.aggregate_id,
                    'payload': envelope.event.payload,
                    'timestamp': envelope.event.timestamp,
                    'version': envelope.event.version,
                },
                'sequence_number': envelope.sequence_number,
                'checksum': envelope.checksum,
            }) + '\n')

    def append(self, event: Event) -> EventEnvelope:
        """Append event to store."""
        self._sequence += 1
        
        # Simple checksum
        import hashlib
        checksum = hashlib.sha256(
            f"{event.id}:{event.type}:{event.timestamp}".encode()
        ).hexdigest()[:16]
        
        envelope = EventEnvelope(
            event=event,
            sequence_number=self._sequence,
            checksum=checksum,
        )
        
        self._events.append(envelope)
        self._save_to_disk(envelope)
        
        # Notify subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"Event subscriber error: {e}")
        
        logger.debug(f"Event appended: {event.type} (seq: {self._sequence})")
        return envelope

    def get_events(
        self,
        aggregate_id: Optional[str] = None,
        event_type: Optional[str] = None,
        from_sequence: int = 0,
        limit: int = 100,
    ) -> List[EventEnvelope]:
        """Query events."""
        results = []
        for envelope in self._events:
            if envelope.sequence_number < from_sequence:
                continue
            if aggregate_id and envelope.event.aggregate_id != aggregate_id:
                continue
            if event_type and envelope.event.type != event_type:
                continue
            results.append(envelope)
            if len(results) >= limit:
                break
        return results

    def subscribe(self, handler: Callable):
        """Subscribe to all events."""
        self._subscribers.append(handler)
        logger.info("Event subscriber registered")

    def get_stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        return {
            "total_events": len(self._events),
            "current_sequence": self._sequence,
            "subscribers": len(self._subscribers),
            "storage_path": str(self._storage_path),
        }


class CQRSBus:
    """Main CQRS event bus combining commands, queries, and events."""

    def __init__(self, event_store: Optional[EventStore] = None):
        self._command_handler = CommandHandler()
        self._query_handler = QueryHandler()
        self._event_store = event_store or EventStore()

    def command(self, command_type: str, payload: Dict, metadata: Optional[Dict] = None) -> Command:
        """Create and dispatch command."""
        import uuid
        command = Command(
            id=str(uuid.uuid4())[:8],
            type=command_type,
            payload=payload,
            metadata=metadata or {},
        )
        return command

    def query(self, query_type: str, filters: Optional[Dict] = None) -> Query:
        """Create query."""
        import uuid
        return Query(
            id=str(uuid.uuid4())[:8],
            type=query_type,
            filters=filters or {},
        )

    def event(self, event_type: str, aggregate_id: str, payload: Dict) -> Event:
        """Create and store event."""
        import uuid
        event = Event(
            id=str(uuid.uuid4())[:8],
            type=event_type,
            aggregate_id=aggregate_id,
            payload=payload,
        )
        self._event_store.append(event)
        return event

    def register_command(self, command_type: str, handler: Callable):
        self._command_handler.register(command_type, handler)

    def register_query(self, query_type: str, handler: Callable):
        self._query_handler.register(query_type, handler)

    async def execute(self, command_or_query) -> Any:
        """Execute command or query."""
        if isinstance(command_or_query, Command):
            return await self._command_handler.handle(command_or_query)
        elif isinstance(command_or_query, Query):
            return await self._query_handler.handle(command_or_query)
        else:
            raise ValueError("Must be Command or Query")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "event_store": self._event_store.get_stats(),
        }


# Global default CQRS bus
default_cqrs_bus: Optional[CQRSBus] = None


def init_cqrs_bus(storage_path: str = "/config/events") -> CQRSBus:
    """Initialize global CQRS bus."""
    global default_cqrs_bus
    event_store = EventStore(storage_path=storage_path)
    default_cqrs_bus = CQRSBus(event_store=event_store)
    return default_cqrs_bus
