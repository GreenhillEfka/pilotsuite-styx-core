"""State Consistency Management for PilotSuite Core.

This package provides state versioning, optimistic locking, conflict detection
and resolution, and partition reconciliation for distributed state management.
"""

from .consistency import (
    StateConsistencyManager,
    VersionedState,
    VectorClock,
    StateConflict,
    ConflictStrategy,
    ConsistencyLevel,
    ReconciliationResult,
)

__all__ = [
    "StateConsistencyManager",
    "VersionedState",
    "VectorClock",
    "StateConflict",
    "ConflictStrategy",
    "ConsistencyLevel",
    "ReconciliationResult",
]
