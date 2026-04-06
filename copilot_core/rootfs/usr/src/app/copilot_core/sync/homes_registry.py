"""Homes Registry — Persistent registration of home instances for Multi-Home Sync.

Manages the inventory of known home instances (primary, vacation, office, secondary)
with their connectivity metadata, authentication tokens, and status tracking.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HomeType(str, Enum):
    """Types of home locations."""
    PRIMARY = "primary"
    VACATION = "vacation"
    OFFICE = "office"
    SECONDARY = "secondary"


class HomeStatus(str, Enum):
    """Connectivity status of a home instance."""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    UNREACHABLE = "unreachable"


@dataclass
class HomeRegistration:
    """Registered home instance with connectivity metadata."""
    home_id: str
    name: str
    home_type: HomeType
    base_url: str
    auth_token: str = ""
    is_primary: bool = False
    is_active: bool = True
    status: HomeStatus = HomeStatus.OFFLINE
    last_seen: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    sync_interval_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self, include_token: bool = False) -> dict[str, Any]:
        """Serialize, optionally stripping the auth token."""
        d = {
            "home_id": self.home_id,
            "name": self.name,
            "home_type": self.home_type.value,
            "base_url": self.base_url,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_interval_seconds": self.sync_interval_seconds,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
        }
        if include_token:
            d["auth_token"] = self.auth_token
        return d


# Alias for role-based filtering
HomeRole = HomeType


@dataclass
class SyncPair:
    """Represents a sync pair between two homes."""
    home_a: str
    home_b: str
    enabled: bool = True
    scope: str = "all"
    last_sync: Optional[datetime] = None


class HomesRegistry:
    """Thread-safe registry of registered home instances.

    Persists registrations to JSON. Loads on init; auto-saves on mutations.
    Supports primary-home designation (only one primary at a time).
    """

    def __init__(self, storage_path: str = "/data/multihome/homes_registry.json"):
        self._lock = threading.RLock()
        self._storage_path = storage_path
        self._homes: dict[str, HomeRegistration] = {}
        self._primary_home_id: str = ""
        self._load()

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        """Load registry from disk, creating the directory if needed."""
        path = Path(self._storage_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for raw in data.get("homes", []):
                    reg = self._deserialize(raw)
                    self._homes[reg.home_id] = reg
                self._primary_home_id = data.get("primary_home_id", "")
                logger.info("HomesRegistry loaded: %d homes", len(self._homes))
            except Exception:
                logger.exception("Failed to load homes registry, starting fresh")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        """Persist registry to disk."""
        try:
            data = {
                "primary_home_id": self._primary_home_id,
                "homes": [self._serialize(r) for r in self._homes.values()],
            }
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            logger.exception("Failed to save homes registry")

    @staticmethod
    def _deserialize(raw: dict) -> HomeRegistration:
        """Reconstruct a HomeRegistration from stored JSON."""
        return HomeRegistration(
            home_id=raw["home_id"],
            name=raw["name"],
            home_type=HomeType(raw["home_type"]),
            base_url=raw["base_url"],
            auth_token=raw.get("auth_token", ""),
            is_primary=raw.get("is_primary", False),
            is_active=raw.get("is_active", True),
            status=HomeStatus(raw.get("status", "offline")),
            last_seen=datetime.fromisoformat(raw["last_seen"]) if raw.get("last_seen") else None,
            last_sync=datetime.fromisoformat(raw["last_sync"]) if raw.get("last_sync") else None,
            sync_interval_seconds=raw.get("sync_interval_seconds", 300),
            metadata=raw.get("metadata", {}),
            registered_at=datetime.fromisoformat(raw["registered_at"])
            if raw.get("registered_at")
            else datetime.now(timezone.utc),
        )

    @staticmethod
    def _serialize(reg: HomeRegistration) -> dict:
        """Flatten a HomeRegistration for JSON serialization."""
        return {
            "home_id": reg.home_id,
            "name": reg.name,
            "home_type": reg.home_type.value,
            "base_url": reg.base_url,
            "auth_token": reg.auth_token,
            "is_primary": reg.is_primary,
            "is_active": reg.is_active,
            "status": reg.status.value,
            "last_seen": reg.last_seen.isoformat() if reg.last_seen else None,
            "last_sync": reg.last_sync.isoformat() if reg.last_sync else None,
            "sync_interval_seconds": reg.sync_interval_seconds,
            "metadata": reg.metadata,
            "registered_at": reg.registered_at.isoformat(),
        }

    # -------------------------------------------------------------------------
    # CRUD operations
    # -------------------------------------------------------------------------

    def register(
        self,
        home_id: str,
        name: str,
        home_type: HomeType,
        base_url: str,
        auth_token: str = "",
        is_primary: bool = False,
        sync_interval_seconds: int = 300,
        metadata: Optional[dict[str, Any]] = None,
    ) -> HomeRegistration:
        """Register (or update) a home instance."""
        with self._lock:
            if home_id in self._homes:
                # Update existing
                reg = self._homes[home_id]
                reg.name = name
                reg.home_type = home_type
                reg.base_url = base_url
                reg.auth_token = auth_token or reg.auth_token
                reg.sync_interval_seconds = sync_interval_seconds
                reg.metadata = metadata or reg.metadata
            else:
                reg = HomeRegistration(
                    home_id=home_id,
                    name=name,
                    home_type=home_type,
                    base_url=base_url,
                    auth_token=auth_token,
                    is_primary=is_primary,
                    sync_interval_seconds=sync_interval_seconds,
                    metadata=metadata or {},
                )
                self._homes[home_id] = reg

            if is_primary:
                self._demote_others(exclude=home_id)
                reg.is_primary = True
                self._primary_home_id = home_id

            self._save()
            return reg

    def unregister(self, home_id: str) -> bool:
        """Remove a home from the registry."""
        with self._lock:
            if home_id not in self._homes:
                return False
            del self._homes[home_id]
            if self._primary_home_id == home_id:
                self._primary_home_id = ""
            self._save()
            return True

    def get(self, home_id: str) -> Optional[HomeRegistration]:
        """Return a registration by id, or None."""
        with self._lock:
            return self._homes.get(home_id)

    def list_all(self) -> list[HomeRegistration]:
        """Return all registrations sorted by name."""
        with self._lock:
            return sorted(self._homes.values(), key=lambda r: r.name)

    def list_active(self) -> list[HomeRegistration]:
        """Return only active registrations."""
        with self._lock:
            return [r for r in self._homes.values() if r.is_active]

    @property
    def primary_home_id(self) -> str:
        with self._lock:
            return self._primary_home_id

    def get_primary(self) -> Optional[HomeRegistration]:
        with self._lock:
            return self._homes.get(self._primary_home_id)

    def update_status(
        self,
        home_id: str,
        status: HomeStatus,
        last_seen: Optional[datetime] = None,
    ) -> bool:
        """Update connectivity status of a home."""
        with self._lock:
            reg = self._homes.get(home_id)
            if not reg:
                return False
            reg.status = status
            if last_seen:
                reg.last_seen = last_seen
            self._save()
            return True

    def update_last_sync(self, home_id: str) -> bool:
        """Mark a successful sync for a home."""
        with self._lock:
            reg = self._homes.get(home_id)
            if not reg:
                return False
            now = datetime.now(timezone.utc)
            reg.last_sync = now
            reg.last_seen = now
            reg.status = HomeStatus.ONLINE
            self._save()
            return True

    def set_active(self, home_id: str, is_active: bool) -> bool:
        """Enable or disable a home."""
        with self._lock:
            reg = self._homes.get(home_id)
            if not reg:
                return False
            reg.is_active = is_active
            self._save()
            return True

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _demote_others(self, exclude: str) -> None:
        """Remove primary flag from all homes except `exclude`."""
        for hid, reg in self._homes.items():
            if hid != exclude and reg.is_primary:
                reg.is_primary = False
