"""Conflict Resolver — Sync conflict detection and resolution for Multi-Home Sync.

Supports multiple resolution strategies:
- LAST_WRITE_WINS: newest timestamp wins
- PRIMARY_WINS: primary home always wins
- MERGE: deep merge of dicts/arrays
- MANUAL: flagged for user resolution

Each detected conflict is persisted to disk and can be resolved
via the REST API.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------


class ConflictStrategy(str, Enum):
    """Built-in conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    PRIMARY_WINS = "primary_wins"
    MERGE = "merge"
    MANUAL = "manual"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"


class ConflictSeverity(str, Enum):
    """Severity level for conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictType(str, Enum):
    """Type of conflict."""
    VALUE_MISMATCH = "value_mismatch"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    SCHEMA_CONFLICT = "schema_conflict"
    DELETION_CONFLICT = "deletion_conflict"


class Conflict:


# -----------------------------------------------------------------------------


@dataclass
class ConflictRecord:
    """Immutable record of a detected sync conflict."""
    id: str
    entity_id: str
    field_path: str
    local_value: Any
    remote_value: Any
    local_timestamp: str
    remote_timestamp: str
    strategy: ConflictStrategy
    resolution: Optional[str] = None
    resolved_value: Any = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "field_path": self.field_path,
            "local_value": self.local_value,
            "remote_value": self.remote_value,
            "local_timestamp": self.local_timestamp,
            "remote_timestamp": self.remote_timestamp,
            "strategy": self.strategy.value,
            "resolution": self.resolution,
            "resolved_value": self.resolved_value,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConflictRecord":
        return cls(
            id=d["id"],
            entity_id=d["entity_id"],
            field_path=d["field_path"],
            local_value=d["local_value"],
            remote_value=d["remote_value"],
            local_timestamp=d["local_timestamp"],
            remote_timestamp=d["remote_timestamp"],
            strategy=ConflictStrategy(d.get("strategy", "last_write_wins")),
            resolution=d.get("resolution"),
            resolved_value=d.get("resolved_value"),
            resolved_by=d.get("resolved_by"),
            resolved_at=d.get("resolved_at"),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


# -----------------------------------------------------------------------------


class ConflictResolver:
    """Thread-safe conflict detection and resolution engine.

    Each home instance keeps its own resolver. The strategy can be
    configured globally or per-entity-type.
    """

    STORAGE_FILE = "/data/multihome/conflicts.json"

    def __init__(
        self,
        home_id: str,
        default_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS,
        storage_path: Optional[str] = None,
    ):
        self.home_id = home_id
        self.default_strategy = default_strategy
        self._storage_path = storage_path or self.STORAGE_FILE
        self._lock = threading.RLock()
        self._conflicts: dict[str, ConflictRecord] = {}
        self._strategy_overrides: dict[str, ConflictStrategy] = {}  # per entity type
        self._on_conflict_callbacks: list[Callable[[ConflictRecord], None]] = []
        self._load()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        path = Path(self._storage_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for raw in data.get("conflicts", []):
                    rec = ConflictRecord.from_dict(raw)
                    self._conflicts[rec.id] = rec
                logger.info("ConflictResolver loaded: %d conflicts", len(self._conflicts))
            except Exception:
                logger.exception("Failed to load conflicts, starting fresh")

    def _save(self) -> None:
        try:
            Path(self._storage_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w") as f:
                json.dump(
                    {
                        "conflicts": [c.to_dict() for c in self._conflicts.values()],
                    },
                    f,
                    indent=2,
                    default=str,
                )
        except Exception:
            logger.exception("Failed to save conflicts")

    # -------------------------------------------------------------------------
    # Detection
    # -------------------------------------------------------------------------

    def detect_conflict(
        self,
        entity_id: str,
        field_path: str,
        local_value: Any,
        remote_value: Any,
        local_timestamp: str,
        remote_timestamp: str,
    ) -> bool:
        """Detect whether two values are in conflict.

        Returns True if the values differ in a meaningful way.
        """
        if local_value == remote_value:
            return False
        # Simple equality check; sub-classes can implement deep equality
        return True

    def register_conflict(
        self,
        entity_id: str,
        field_path: str,
        local_value: Any,
        remote_value: Any,
        local_timestamp: str,
        remote_timestamp: str,
        strategy: Optional[ConflictStrategy] = None,
    ) -> ConflictRecord:
        """Create and persist a new conflict record."""
        with self._lock:
            record = ConflictRecord(
                id=str(uuid.uuid4()),
                entity_id=entity_id,
                field_path=field_path,
                local_value=local_value,
                remote_value=remote_value,
                local_timestamp=local_timestamp,
                remote_timestamp=remote_timestamp,
                strategy=strategy or self.default_strategy,
            )
            self._conflicts[record.id] = record
            self._save()

            for cb in self._on_conflict_callbacks:
                try:
                    cb(record)
                except Exception:
                    logger.exception("Error in conflict callback")

            logger.info(
                "Conflict registered: entity=%s field=%s id=%s",
                entity_id, field_path, record.id,
            )
            return record

    # -------------------------------------------------------------------------
    # Resolution
    # -------------------------------------------------------------------------

    def resolve(
        self,
        conflict_id: str,
        resolution: Optional[str] = None,
        manual_value: Any = None,
        resolved_by: Optional[str] = None,
    ) -> Optional[Any]:
        """Resolve a conflict by the given strategy or manually.

        Returns the resolved value, or None if not found.
        """
        with self._lock:
            record = self._conflicts.get(conflict_id)
            if not record:
                return None

            strategy_str = resolution or record.strategy.value
            strategy = ConflictStrategy(strategy_str)

            if strategy == ConflictStrategy.MANUAL:
                if manual_value is None:
                    return None  # Manual requires explicit value
                resolved_value = manual_value
            else:
                resolved_value = self._apply_strategy(
                    strategy,
                    record.local_value,
                    record.remote_value,
                    record.local_timestamp,
                    record.remote_timestamp,
                )

            record.resolution = strategy.value
            record.resolved_value = resolved_value
            record.resolved_by = resolved_by or self.home_id
            record.resolved_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return resolved_value

    def resolve_auto(self, conflict_id: str) -> Optional[Any]:
        """Auto-resolve a conflict using its configured strategy."""
        return self.resolve(conflict_id)

    # -------------------------------------------------------------------------
    # Strategy implementations
    # -------------------------------------------------------------------------

    def _apply_strategy(
        self,
        strategy: ConflictStrategy,
        local: Any,
        remote: Any,
        local_ts: str,
        remote_ts: str,
    ) -> Any:
        """Apply the given resolution strategy."""
        if strategy == ConflictStrategy.LAST_WRITE_WINS:
            return self._last_write_wins(local, remote, local_ts, remote_ts)
        elif strategy == ConflictStrategy.PRIMARY_WINS:
            return self._primary_wins(local, remote)
        elif strategy == ConflictStrategy.MERGE:
            return self._merge(local, remote)
        elif strategy == ConflictStrategy.LOCAL_WINS:
            return local
        elif strategy == ConflictStrategy.REMOTE_WINS:
            return remote
        else:
            # Default: newest wins
            return self._last_write_wins(local, remote, local_ts, remote_ts)

    def _last_write_wins(
        self,
        local: Any,
        remote: Any,
        local_ts: str,
        remote_ts: str,
    ) -> Any:
        """Return whichever value has the newer timestamp."""
        try:
            local_dt = datetime.fromisoformat(local_ts)
            remote_dt = datetime.fromisoformat(remote_ts)
            return local if local_dt >= remote_dt else remote
        except (ValueError, TypeError):
            # Fallback to local
            return local

    def _primary_wins(self, local: Any, remote: Any) -> Any:
        """Primary home (this instance) always wins."""
        # This home's value is always local
        return local

    def _merge(self, local: Any, remote: Any) -> Any:
        """Deep merge: prefer non-null values, concatenate lists."""
        return self._deep_merge(deepcopy(local), deepcopy(remote))

    def _deep_merge(self, base: Any, incoming: Any) -> Any:
        """Recursively merge incoming into base, returning merged result."""
        if not isinstance(base, dict) or not isinstance(incoming, dict):
            # Non-dict: incoming wins if base is None/empty
            if base in (None, "") and incoming not in (None, ""):
                return incoming
            return base

        result = dict(base)
        for k, v in incoming.items():
            if k in result:
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    # -------------------------------------------------------------------------
    # Per-entity strategy overrides
    # -------------------------------------------------------------------------

    def set_strategy_for_entity(
        self,
        entity_type: str,
        strategy: ConflictStrategy,
    ) -> None:
        """Override the default strategy for a specific entity type."""
        with self._lock:
            self._strategy_overrides[entity_type] = strategy

    def get_strategy_for_entity(self, entity_type: str) -> ConflictStrategy:
        return self._strategy_overrides.get(entity_type, self.default_strategy)

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def on_conflict(self, callback: Callable[[ConflictRecord], None]) -> None:
        """Register a callback invoked whenever a new conflict is registered."""
        self._on_conflict_callbacks.append(callback)

    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------

    def get_conflict(self, conflict_id: str) -> Optional[ConflictRecord]:
        with self._lock:
            return self._conflicts.get(conflict_id)

    def list_active(self) -> list[ConflictRecord]:
        """Return unresolved conflicts."""
        with self._lock:
            return [c for c in self._conflicts.values() if c.resolution is None]

    def list_resolved(self) -> list[ConflictRecord]:
        """Return resolved conflicts."""
        with self._lock:
            return [c for c in self._conflicts.values() if c.resolution is not None]

    def count_active(self) -> int:
        return len(self.list_active())

    def clear_resolved(self, older_than_days: int = 7) -> int:
        """Remove resolved conflicts older than N days. Returns count removed."""
        cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 86400
        removed = 0
        with self._lock:
            to_remove = [
                cid for cid, c in self._conflicts.items()
                if c.resolved_at and c.resolved_at < cutoff
            ]
            for cid in to_remove:
                del self._conflicts[cid]
            removed = len(to_remove)
            self._save()
        return removed
