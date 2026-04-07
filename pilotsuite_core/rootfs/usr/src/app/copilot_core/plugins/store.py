"""Plugin Registry Store — persists plugin registrations and enabled state to disk."""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------

@dataclass
class PluginRecord:
    """A persisted plugin registration record."""

    plugin_id: str
    name: str
    version: str
    enabled: bool = False
    config: dict[str, Any] = field(default_factory=dict)
    enabled_at: Optional[str] = None
    error_message: Optional[str] = None
    order: int = 0  # load order priority

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginRecord":
        return cls(
            plugin_id=data["plugin_id"],
            name=data["name"],
            version=data["version"],
            enabled=data.get("enabled", False),
            config=data.get("config", {}),
            enabled_at=data.get("enabled_at"),
            error_message=data.get("error_message"),
            order=data.get("order", 0),
        )


# ------------------------------------------------------------------
# Store implementation
# ------------------------------------------------------------------

class PluginStore:
    """Thread-safe, file-backed plugin registry.

    Persists:
    - Which plugins are registered
    - Which are currently enabled
    - Per-plugin configuration
    - Error messages from last failure

    The store is append-optimised: reads are from a single JSON file,
    writes take a full lock + rewrite.
    """

    _DEFAULT_FILENAME = "plugin_registry.json"

    def __init__(
        self,
        store_path: str | Path | None = None,
        *,
        lock: bool = True,
    ) -> None:
        self._path = Path(store_path) if store_path else self._default_store_path()
        self._lock = threading.RLock() if lock else _DummyLock()
        self._cache: dict[str, PluginRecord] = {}
        self._dirty = False
        self._ensure_directory()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_store_path() -> Path:
        base = os.environ.get("PILOTSUITE_DATA", "/data")
        return Path(base) / "plugin_registry.json"

    def _ensure_directory(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------
    def register(self, record: PluginRecord) -> None:
        """Add or update a plugin record."""
        with self._lock:
            self._cache[record.plugin_id] = record
            self._dirty = True
            logger.debug("Plugin registered in store: %s", record.plugin_id)

    def unregister(self, plugin_id: str) -> bool:
        """Remove a plugin from the registry. Returns True if it existed."""
        with self._lock:
            if plugin_id in self._cache:
                del self._cache[plugin_id]
                self._dirty = True
                logger.debug("Plugin unregistered from store: %s", plugin_id)
                return True
            return False

    def get(self, plugin_id: str) -> Optional[PluginRecord]:
        """Retrieve a single plugin record."""
        with self._lock:
            return self._cache.get(plugin_id)

    def get_all(self) -> list[PluginRecord]:
        """Return all registered plugin records."""
        with self._lock:
            return list(self._cache.values())

    def get_enabled_ids(self) -> list[str]:
        """Return IDs of all plugins currently enabled in the store."""
        with self._lock:
            return [r.plugin_id for r in self._cache.values() if r.enabled]

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        """Enable or disable a plugin in the registry."""
        with self._lock:
            record = self._cache.get(plugin_id)
            if record is None:
                return False
            record.enabled = enabled
            record.enabled_at = datetime.now(timezone.utc).isoformat() if enabled else None
            self._dirty = True
            logger.debug("Plugin %s enabled=%s in store", plugin_id, enabled)
            return True

    def update_config(self, plugin_id: str, config: dict[str, Any]) -> bool:
        """Merge a dict into a plugin's stored config."""
        with self._lock:
            record = self._cache.get(plugin_id)
            if record is None:
                return False
            record.config.update(config)
            self._dirty = True
            return True

    def set_error(self, plugin_id: str, error_message: str) -> None:
        """Record the last error for a plugin."""
        with self._lock:
            record = self._cache.get(plugin_id)
            if record is None:
                return
            record.error_message = error_message
            self._dirty = True

    def set_order(self, plugin_id: str, order: int) -> bool:
        """Set load-order priority for a plugin."""
        with self._lock:
            record = self._cache.get(plugin_id)
            if record is None:
                return False
            record.order = order
            self._dirty = True
            return True

    def sorted_by_order(self) -> list[PluginRecord]:
        """Return all records sorted by load-order ascending."""
        with self._lock:
            return sorted(self._cache.values(), key=lambda r: r.order)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self) -> None:
        """Write the current cache to disk."""
        with self._lock:
            if not self._dirty:
                return
            self._persist_unlocked()

    def load(self) -> None:
        """Load the registry from disk into the cache."""
        with self._lock:
            if not self._path.exists():
                return
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load plugin store from %s: %s", self._path, exc)
                return

            records = data.get("plugins", {})
            self._cache = {
                pid: PluginRecord.from_dict(rec)
                for pid, rec in records.items()
            }
            self._dirty = False
            logger.info("Plugin store loaded: %d plugins", len(self._cache))

    def _persist_unlocked(self) -> None:
        """Must be called with _lock held."""
        records = {pid: rec.to_dict() for pid, rec in self._cache.items()}
        payload = {"version": 1, "plugins": records}
        tmp_path = self._path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            tmp_path.replace(self._path)
            self._dirty = False
            logger.debug("Plugin store persisted to %s", self._path)
        except OSError as exc:
            logger.error("Failed to persist plugin store to %s: %s", self._path, exc)

    # ------------------------------------------------------------------
    # Admin helpers
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Remove all records (use with care)."""
        with self._lock:
            self._cache.clear()
            self._dirty = True

    def count(self) -> int:
        """Number of registered plugins."""
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        with self._lock:
            return {
                "total": len(self._cache),
                "enabled": sum(1 for r in self._cache.values() if r.enabled),
                "errors": sum(1 for r in self._cache.values() if r.error_message),
            }


class _DummyLock:
    """A no-op lock for single-threaded or test environments."""

    def __enter__(self) -> "_DummyLock":
        return self

    def __exit__(self, *_: Any) -> None:
        pass
