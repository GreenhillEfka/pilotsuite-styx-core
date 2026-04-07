"""Events module — PilotSuite Core.

Event bus, propagation, and write-ahead log for semantic events.
"""
from copilot_core.events.bus import (
    EventBusEngine,
    Event,
    EventPriority,
    EventStatus,
    Subscription,
    create_event_bus_engine,
)

from copilot_core.events.propagation import (
    EventPropagationEngine,
    PropagationEvent,
    DeliveryGuarantee,
    PropagationStatus,
    DeadLetterQueue,
    DeadLetterEntry,
    RetryManager,
    RetryConfig,
    RetryStrategy,
    SequenceManager,
    DeduplicationTracker,
    PropagationTarget,
    CallbackTarget,
    get_propagation_engine,
    reset_propagation_engine,
)

from copilot_core.events.wal import (
    WriteAheadLog,
    WALEntry,
    log_semantic_event,
    wal_write,
    get_wal,
)

__all__ = [
    # Bus
    "EventBusEngine",
    "Event",
    "EventPriority",
    "EventStatus",
    "Subscription",
    "create_event_bus_engine",
    # Propagation
    "EventPropagationEngine",
    "PropagationEvent",
    "DeliveryGuarantee",
    "PropagationStatus",
    "DeadLetterQueue",
    "DeadLetterEntry",
    "RetryManager",
    "RetryConfig",
    "RetryStrategy",
    "SequenceManager",
    "DeduplicationTracker",
    "PropagationTarget",
    "CallbackTarget",
    "get_propagation_engine",
    "reset_propagation_engine",
    # WAL
    "WriteAheadLog",
    "SemanticEvent",
    "log_semantic_event",
    "get_wal",
]
