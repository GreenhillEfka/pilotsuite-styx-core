"""
User Profiles -- Per-user preference tracking linked to HA person entities.

Each person.* entity in HA gets their own profile with learned preferences.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("USER_PROFILES_DB", "/data/user_profiles.db")


class UserProfileManager:
    """Manage per-user profiles backed by SQLite.

    Profiles are keyed by HA ``person.*`` entity IDs and store learned
    preferences, suggestion history, and feedback statistics.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_db()
        logger.info("UserProfileManager initialized at %s", self._db_path)

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS profiles (
                        person_id    TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL DEFAULT '',
                        preferences  TEXT NOT NULL DEFAULT '{}',
                        suggestion_history TEXT NOT NULL DEFAULT '[]',
                        created_at   TEXT NOT NULL,
                        updated_at   TEXT NOT NULL
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _ensure_profile(self, conn: sqlite3.Connection, person_id: str) -> None:
        """Create a stub profile if none exists yet."""
        row = conn.execute(
            "SELECT 1 FROM profiles WHERE person_id = ?", (person_id,)
        ).fetchone()
        if row is None:
            now = self._now_iso()
            conn.execute(
                "INSERT INTO profiles (person_id, display_name, preferences, "
                "suggestion_history, created_at, updated_at) "
                "VALUES (?, ?, '{}', '[]', ?, ?)",
                (person_id, person_id, now, now),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_profile(self, person_id: str) -> Dict[str, Any]:
        """Return the full profile dict for *person_id*."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                self._ensure_profile(conn, person_id)
                row = conn.execute(
                    "SELECT person_id, display_name, preferences, "
                    "suggestion_history, created_at, updated_at "
                    "FROM profiles WHERE person_id = ?",
                    (person_id,),
                ).fetchone()
                if row is None:
                    return {}
                return {
                    "person_id": row[0],
                    "display_name": row[1],
                    "preferences": json.loads(row[2]),
                    "suggestion_history": json.loads(row[3]),
                    "created_at": row[4],
                    "updated_at": row[5],
                }
            finally:
                conn.close()

    def update_preference(
        self, person_id: str, key: str, value: Any, weight: float = 1.0
    ) -> None:
        """Set or update a single preference key for *person_id*."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                self._ensure_profile(conn, person_id)
                row = conn.execute(
                    "SELECT preferences FROM profiles WHERE person_id = ?",
                    (person_id,),
                ).fetchone()
                prefs: dict = json.loads(row[0]) if row else {}
                prefs[key] = {"value": value, "weight": weight}
                now = self._now_iso()
                conn.execute(
                    "UPDATE profiles SET preferences = ?, updated_at = ? "
                    "WHERE person_id = ?",
                    (json.dumps(prefs), now, person_id),
                )
                conn.commit()
                logger.debug("Preference %s updated for %s", key, person_id)
            finally:
                conn.close()

    def get_active_users(
        self, hass_states: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Return profiles of persons currently at home.

        If *hass_states* is provided it should be a list of HA state dicts
        for ``person.*`` entities.  Persons whose state is ``home`` are
        considered active.  Without *hass_states* all known profiles are
        returned.
        """
        if hass_states is None:
            with self._lock:
                conn = sqlite3.connect(self._db_path)
                try:
                    rows = conn.execute(
                        "SELECT person_id FROM profiles"
                    ).fetchall()
                    return [self.get_profile(r[0]) for r in rows]
                finally:
                    conn.close()

        home_ids = {
            s["entity_id"]
            for s in hass_states
            if s.get("entity_id", "").startswith("person.")
            and s.get("state") == "home"
        }
        return [self.get_profile(pid) for pid in home_ids]

    def get_suggestions_for_user(self, person_id: str) -> List[Dict[str, Any]]:
        """Return the suggestion history for *person_id*."""
        profile = self.get_profile(person_id)
        return profile.get("suggestion_history", [])

    def record_feedback(
        self, person_id: str, suggestion_id: str, action: str
    ) -> None:
        """Record user feedback (accept / reject / dismiss) for a suggestion."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                self._ensure_profile(conn, person_id)
                row = conn.execute(
                    "SELECT suggestion_history FROM profiles WHERE person_id = ?",
                    (person_id,),
                ).fetchone()
                history: list = json.loads(row[0]) if row else []
                history.append(
                    {
                        "suggestion_id": suggestion_id,
                        "action": action,
                        "timestamp": self._now_iso(),
                    }
                )
                # Keep last 500 entries
                history = history[-500:]
                now = self._now_iso()
                conn.execute(
                    "UPDATE profiles SET suggestion_history = ?, updated_at = ? "
                    "WHERE person_id = ?",
                    (json.dumps(history), now, person_id),
                )
                conn.commit()
                logger.debug(
                    "Feedback recorded for %s: suggestion=%s action=%s",
                    person_id,
                    suggestion_id,
                    action,
                )
            finally:
                conn.close()
