"""Versioned State Updates for Core↔HA Synchronization.

Implements Monotonic Sequence Numbers per Entity-Typ:
- HabitusZone, RoomContext, DeviceLink
- State updates carry `state_version`; stale updates are discarded
- 409 Conflict response includes current state for client retry

Auto-Retry with Exponential Backoff (default):
- First retry: 100ms
- Max retries: 5
- Backoff multiplier: 2x
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Generic
from enum import Enum
import hashlib

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class ConflictResolution(str, Enum):
    """How to handle version conflicts."""
    HIGHER_WINS = "higher_wins"  # Default
    SERVER_WINS = "server_wins"
    CLIENT_WINS = "client_wins"
    MANUAL = "manual"  # Phase 2


@dataclass
class VersionedState:
    """Base class for versioned entities."""
    entity_id: str
    state_version: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_by: str = ""

    def bump_version(self) -> None:
        self.state_version += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionedState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ConflictInfo:
    """Conflict details returned with 409."""
    entity_id: str
    client_version: int
    server_version: int
    client_state: Dict[str, Any]
    server_state: Dict[str, Any]
    resolution: ConflictResolution
    conflict_id: str = field(default_factory=lambda: hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:12])


@dataclass
class StateUpdateResult:
    """Result of a state update attempt."""
    success: bool
    new_version: Optional[int] = None
    conflict: Optional[ConflictInfo] = None
    retry_after_ms: Optional[int] = None
    state: Optional[Dict[str, Any]] = None


class VersionedStateStore:
    """In-memory versioned state store with conflict detection."""

    def __init__(self):
        self._states: Dict[str, VersionedState] = {}
        self._lock = asyncio.Lock()

    async def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get current state."""
        async with self._lock:
            entity = self._states.get(entity_id)
            if entity is None:
                return None
            return entity.to_dict()

    async def update(
        self,
        entity_id: str,
        client_version: int,
        new_state: Dict[str, Any],
        updated_by: str = "unknown",
    ) -> StateUpdateResult:
        """Update with version check. Returns result with conflict if mismatch."""
        async with self._lock:
            current = self._states.get(entity_id)

            if current is None:
                # New entity — accept with version 1
                entity = VersionedState(
                    entity_id=entity_id,
                    state_version=1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    updated_by=updated_by,
                )
                entity.__dict__.update({k: v for k, v in new_state.items()
                                       if k in VersionedState.__dataclass_fields__})
                self._states[entity_id] = entity
                return StateUpdateResult(success=True, new_version=1, state=entity.to_dict())

            if client_version < current.state_version:
                # Stale update — reject with 409
                conflict = ConflictInfo(
                    entity_id=entity_id,
                    client_version=client_version,
                    server_version=current.state_version,
                    client_state=new_state,
                    server_state=current.to_dict(),
                    resolution=ConflictResolution.HIGHER_WINS,
                )
                return StateUpdateResult(
                    success=False,
                    conflict=conflict,
                    new_version=current.state_version,
                    state=current.to_dict(),
                )

            # Accept update
            current.bump_version()
            current.updated_by = updated_by
            for k, v in new_state.items():
                if k in VersionedState.__dataclass_fields__:
                    continue
                if hasattr(current, k):
                    setattr(current, k, v)

            return StateUpdateResult(
                success=True,
                new_version=current.state_version,
                state=current.to_dict(),
            )

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._states.items()}


# ─── HA-Side Retry Client ────────────────────────────────────────────────────

DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_DELAY_MS = 100
DEFAULT_BACKOFF_MULTIPLIER = 2.0


class HAStateSyncClient:
    """Home Assistant sync client with versioned state + auto-retry."""

    def __init__(
        self,
        core_url: str,
        ha_token: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay_ms: int = DEFAULT_INITIAL_DELAY_MS,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    ):
        self.core_url = core_url.rstrip("/")
        self.ha_token = ha_token
        self.max_retries = max_retries
        self.initial_delay_ms = initial_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self._local_version_store: Dict[str, int] = {}  # entity_id → last known version

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

    async def push_state(
        self,
        entity_id: str,
        state: Dict[str, Any],
        entity_type: str = "unknown",
    ) -> StateUpdateResult:
        """Push state to Core with auto-retry on 409."""
        import requests

        client_version = self._local_version_store.get(entity_id, 0)
        url = f"{self.core_url}/api/v1/sync/state/{entity_id}"

        payload = {
            "entity_type": entity_type,
            "client_version": client_version,
            "state": state,
            "updated_by": "ha",
        }

        delay_ms = self.initial_delay_ms
        last_error: Optional[str] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=self._headers(), timeout=10)

                if resp.status_code == 200:
                    result = resp.json()
                    new_version = result.get("state_version", client_version + 1)
                    self._local_version_store[entity_id] = new_version
                    return StateUpdateResult(
                        success=True,
                        new_version=new_version,
                        state=result.get("state"),
                    )

                elif resp.status_code == 409:
                    # Conflict — fetch fresh state and retry
                    conflict_data = resp.json()
                    server_version = conflict_data.get("server_version", 0)
                    self._local_version_store[entity_id] = server_version

                    if attempt >= self.max_retries:
                        return StateUpdateResult(
                            success=False,
                            conflict=ConflictInfo(
                                entity_id=entity_id,
                                client_version=client_version,
                                server_version=server_version,
                                client_state=state,
                                server_state=conflict_data.get("server_state", {}),
                                resolution=ConflictResolution.HIGHER_WINS,
                            ),
                            new_version=server_version,
                            state=conflict_data.get("server_state"),
                        )

                    _LOGGER.debug(
                        "Conflict on %s (v%d vs v%d), retry %d in %dms",
                        entity_id, client_version, server_version, attempt + 1, delay_ms,
                    )
                    await asyncio.sleep(delay_ms / 1000)
                    delay_ms = int(delay_ms * self.backoff_multiplier)
                    # Update client version to server version before retry
                    client_version = server_version
                    payload["client_version"] = client_version
                    payload["state"] = conflict_data.get("server_state", state)

                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text}"
                    break

            except requests.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    await asyncio.sleep(delay_ms / 1000)
                    delay_ms = int(delay_ms * self.backoff_multiplier)
                else:
                    break

        return StateUpdateResult(success=False, conflict=None, retry_after_ms=delay_ms)


# Singleton store
_state_store: Optional[VersionedStateStore] = None


def get_versioned_state_store() -> VersionedStateStore:
    global _state_store
    if _state_store is None:
        _state_store = VersionedStateStore()
    return _state_store
