"""
Module Registry -- Persistent module state management.

Tracks per-module state (active/learning/off) with SQLite persistence.
The dashboard UI and API use this to control which modules are active.

States (Autonomy-Ready):
  - active:   Module fully operational. Suggestions are AUTO-APPLIED when
              BOTH involved modules (source + target) are in active mode
              (double-safety: no auto-apply unless both sides agree).
  - learning: Observation mode. Module collects data AND generates
              suggestions for MANUAL APPROVAL (user must accept/reject).
  - off:      Module is disabled entirely (no data collection, no output).

This 3-tier system enables a gradual path to autonomy:
  1. Start all modules in "learning" to observe without acting
  2. Promote trusted modules to "active" for auto-apply
  3. Both source AND target must be "active" for auto-apply (double-safety)

Thread-safe singleton with SQLite persistence under /data/.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

_LOGGER = logging.getLogger(__name__)

DB_PATH = os.environ.get("MODULE_STATES_DB", "/data/module_states.db")

VALID_STATES = frozenset({"active", "learning", "off"})
DEFAULT_STATE = "active"


class ModuleRegistry:
    """Thread-safe, singleton module state registry with SQLite persistence.

    Usage::

        registry = ModuleRegistry.get_instance()
        registry.set_state("mood_engine", "learning")
        assert registry.is_learning("mood_engine")
    """

    _instance: Optional[ModuleRegistry] = None
    _instance_lock = threading.Lock()

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        _LOGGER.info("ModuleRegistry initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, db_path: str | None = None) -> ModuleRegistry:
        """Return the singleton ModuleRegistry, creating it on first call.

        Uses double-checked locking for thread safety.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Reset the singleton (testing only)."""
        with cls._instance_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the module_states table if it does not exist."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS module_states (
                        module_id   TEXT PRIMARY KEY,
                        state       TEXT NOT NULL DEFAULT 'active',
                        updated_at  TEXT NOT NULL
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        """Return current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection (caller must close)."""
        return sqlite3.connect(self._db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self, module_id: str) -> str:
        """Return the state of *module_id*.

        Returns ``"active"`` if the module has never been explicitly configured.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT state FROM module_states WHERE module_id = ?",
                    (module_id,),
                ).fetchone()
                return row[0] if row else DEFAULT_STATE
            finally:
                conn.close()

    def set_state(self, module_id: str, state: str) -> bool:
        """Persist a new state for *module_id*.

        Args:
            module_id: Identifier of the module (e.g. ``"mood_engine"``).
            state: One of ``"active"``, ``"learning"``, ``"off"``.

        Returns:
            ``True`` if the state was accepted and persisted,
            ``False`` if *state* is invalid.
        """
        if state not in VALID_STATES:
            _LOGGER.warning(
                "Rejected invalid state %r for module %s (valid: %s)",
                state, module_id, ", ".join(sorted(VALID_STATES)),
            )
            return False

        now = self._now_iso()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO module_states (module_id, state, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(module_id) DO UPDATE
                        SET state = excluded.state,
                            updated_at = excluded.updated_at
                    """,
                    (module_id, state, now),
                )
                conn.commit()
                _LOGGER.info("Module %s -> %s", module_id, state)
                return True
            except sqlite3.Error:
                _LOGGER.exception("Failed to persist state for %s", module_id)
                return False
            finally:
                conn.close()

    def get_all_states(self) -> Dict[str, str]:
        """Return a mapping of every explicitly-configured module to its state.

        Modules that have never been configured will *not* appear here
        (their implicit state is ``"active"``).
        """
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    "SELECT module_id, state FROM module_states ORDER BY module_id"
                ).fetchall()
                return {module_id: state for module_id, state in rows}
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Convenience predicates
    # ------------------------------------------------------------------

    def is_active(self, module_id: str) -> bool:
        """Return ``True`` if the module is in ``"active"`` state."""
        return self.get_state(module_id) == "active"

    def is_learning(self, module_id: str) -> bool:
        """Return ``True`` if the module is in ``"learning"`` state."""
        return self.get_state(module_id) == "learning"

    def is_off(self, module_id: str) -> bool:
        """Return ``True`` if the module is in ``"off"`` state."""
        return self.get_state(module_id) == "off"

    # ------------------------------------------------------------------
    # Autonomy helpers (v3.1.0)
    # ------------------------------------------------------------------

    def should_auto_apply(self, source_module: str, target_module: str) -> bool:
        """Return ``True`` if a suggestion from *source_module* targeting
        *target_module* should be automatically applied.

        Double-safety: BOTH modules must be in ``"active"`` state.
        This prevents unintended autonomous actions when only one side
        has been promoted to active.
        """
        return self.is_active(source_module) and self.is_active(target_module)

    def should_suggest(self, module_id: str) -> bool:
        """Return ``True`` if *module_id* should generate suggestions.

        Both ``"active"`` and ``"learning"`` modules generate suggestions.
        The difference: active suggestions may be auto-applied (if the
        target is also active), while learning suggestions require manual
        approval.
        """
        state = self.get_state(module_id)
        return state in ("active", "learning")

    def should_collect_data(self, module_id: str) -> bool:
        """Return ``True`` if *module_id* should collect/observe data.

        Both ``"active"`` and ``"learning"`` modules collect data.
        Only ``"off"`` modules are fully silent.
        """
        return not self.is_off(module_id)

    def get_suggestion_mode(self, source_module: str,
                            target_module: str) -> str:
        """Determine how to handle a suggestion from *source* to *target*.

        Returns:
            ``"auto_apply"`` -- both active, execute immediately
            ``"manual"``     -- at least one in learning, queue for approval
            ``"suppress"``   -- at least one is off, discard
        """
        src_state = self.get_state(source_module)
        tgt_state = self.get_state(target_module)

        if src_state == "off" or tgt_state == "off":
            return "suppress"
        if src_state == "active" and tgt_state == "active":
            return "auto_apply"
        return "manual"
