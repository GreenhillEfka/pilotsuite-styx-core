"""Mood Service v3.0 — Unified Persistence + Query Layer.

Combines zone-based mood profiles with SQLite persistence, trend analysis,
and suggestion relevance scoring.

Persistence:
- SQLite WAL mode for concurrent read/write
- Per-zone mood history (30-day rolling window)
- Throttled writes (max 1/min per zone)
- Startup recovery from last known state

Query API:
- Current mood per zone / all zones
- History for trend analysis and RAG context
- Suggestion relevance multipliers
- Energy-saving suppression checks
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from .models import (
    MoodDimensions,
    MoodState,
    MoodSystemConfig,
    ZoneMoodProfile,
)

logger = logging.getLogger(__name__)

# Persistence defaults
MOOD_DB_PATH = os.environ.get("COPILOT_MOOD_DB", "/data/mood_history.db")
MAX_HISTORY_ENTRIES = 50_000
SAVE_THROTTLE_SECONDS = 60
HISTORY_RETENTION_DAYS = 30


class MoodService:
    """Unified mood persistence and query service.

    Thread-safe: all DB access is serialized through ``_lock``.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[MoodSystemConfig] = None,
    ):
        self._config = config or MoodSystemConfig()
        self._zone_profiles: Dict[str, ZoneMoodProfile] = {}
        self._db_path = self._resolve_db_path(db_path or MOOD_DB_PATH)
        self._lock = threading.Lock()
        self._last_save_ts: Dict[str, float] = {}
        self._save_count: int = 0

        self._init_db()
        self._load_latest_profiles()

        logger.info("MoodService v3.0 initialized (db=%s)", self._db_path)

    # ── SQLite Persistence ──────────────────────────────────────────────

    def _resolve_db_path(self, configured_path: str) -> str:
        db_dir = os.path.dirname(configured_path) or "."
        try:
            os.makedirs(db_dir, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = os.environ.get("COPILOT_MOOD_DB_DIR", "/tmp")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback = os.path.join(
                fallback_dir, os.path.basename(configured_path) or "mood_history.db"
            )
            logger.warning("Mood DB %s not writable, fallback %s", configured_path, fallback)
            return fallback

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS mood_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'neutral',
                    comfort REAL NOT NULL DEFAULT 0.5,
                    frugality REAL NOT NULL DEFAULT 0.5,
                    joy REAL NOT NULL DEFAULT 0.5,
                    energy REAL NOT NULL DEFAULT 0.5,
                    stress REAL NOT NULL DEFAULT 0.0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    media_active INTEGER NOT NULL DEFAULT 0,
                    media_primary TEXT,
                    time_of_day TEXT NOT NULL DEFAULT 'afternoon',
                    occupancy_level TEXT NOT NULL DEFAULT 'low',
                    motion_recent INTEGER NOT NULL DEFAULT 0,
                    ambient_dark INTEGER NOT NULL DEFAULT 0,
                    quiet_hours INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_mood_zone_ts
                    ON mood_profiles(zone_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_mood_ts
                    ON mood_profiles(timestamp);
                CREATE INDEX IF NOT EXISTS idx_mood_state
                    ON mood_profiles(zone_id, state);
            """)
            conn.commit()
        except Exception:
            logger.exception("Failed to initialize mood DB at %s", self._db_path)
            raise
        finally:
            if conn is not None:
                conn.close()

    def _load_latest_profiles(self) -> None:
        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            rows = conn.execute("""
                SELECT zone_id, timestamp, state, comfort, frugality, joy,
                       energy, stress, confidence, media_active, media_primary,
                       time_of_day, occupancy_level, motion_recent, ambient_dark,
                       quiet_hours
                FROM mood_profiles
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY zone_id ORDER BY timestamp DESC
                        ) AS rn
                        FROM mood_profiles
                    ) WHERE rn = 1
                )
            """).fetchall()

            for row in rows:
                profile = ZoneMoodProfile(
                    zone_id=row[0],
                    state=MoodState.from_str(row[2] or "neutral"),
                    dimensions=MoodDimensions(
                        comfort=float(row[3] or 0.5),
                        frugality=float(row[4] or 0.5),
                        joy=float(row[5] or 0.5),
                        energy=float(row[6] or 0.5),
                        stress=float(row[7] or 0.0),
                    ),
                    confidence=float(row[8] or 0.0),
                    media_playing=bool(row[9]),
                    media_primary=row[10],
                    time_of_day=row[11] or "afternoon",
                    occupancy_level=row[12] or "low",
                    motion_recent=bool(row[13]),
                    ambient_dark=bool(row[14]),
                    quiet_hours=bool(row[15]),
                )
                self._zone_profiles[profile.zone_id] = profile

            if rows:
                logger.info("Restored mood profiles for %d zones from DB", len(rows))
        except Exception:
            logger.exception("Failed to load mood history from DB")
        finally:
            if conn is not None:
                conn.close()

    def persist_profile(self, profile: ZoneMoodProfile) -> None:
        """Save a mood profile to DB (throttled per zone)."""
        now = time.time()
        throttle = self._config.save_throttle_seconds
        last = self._last_save_ts.get(profile.zone_id, 0)
        if now - last < throttle:
            return

        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            conn.execute(
                "INSERT INTO mood_profiles "
                "(zone_id, timestamp, state, comfort, frugality, joy, energy, stress, "
                "confidence, media_active, media_primary, time_of_day, occupancy_level, "
                "motion_recent, ambient_dark, quiet_hours) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    profile.zone_id,
                    profile.timestamp.timestamp(),
                    profile.state.value,
                    round(profile.dimensions.comfort, 4),
                    round(profile.dimensions.frugality, 4),
                    round(profile.dimensions.joy, 4),
                    round(profile.dimensions.energy, 4),
                    round(profile.dimensions.stress, 4),
                    round(profile.confidence, 4),
                    int(profile.media_playing),
                    profile.media_primary,
                    profile.time_of_day,
                    profile.occupancy_level,
                    int(profile.motion_recent),
                    int(profile.ambient_dark),
                    int(profile.quiet_hours),
                ),
            )
            conn.commit()
            self._last_save_ts[profile.zone_id] = now
            self._save_count += 1

            if self._save_count % 100 == 0:
                try:
                    self._prune_old(conn)
                except Exception:
                    logger.exception("Failed to prune old mood entries")
        except Exception:
            logger.exception("Failed to persist mood profile for %s", profile.zone_id)
        finally:
            if conn is not None:
                conn.close()

    def _prune_old(self, conn: sqlite3.Connection) -> None:
        retention = self._config.history_retention_days
        cutoff = time.time() - (retention * 86400)
        conn.execute("DELETE FROM mood_profiles WHERE timestamp < ?", (cutoff,))
        count = conn.execute("SELECT COUNT(*) FROM mood_profiles").fetchone()[0]
        max_entries = self._config.max_history_entries
        if count > max_entries:
            excess = count - max_entries
            conn.execute(
                "DELETE FROM mood_profiles WHERE id IN "
                "(SELECT id FROM mood_profiles ORDER BY timestamp ASC LIMIT ?)",
                (excess,),
            )
        conn.commit()

    # ── Update API ──────────────────────────────────────────────────────

    def update_zone_profile(self, profile: ZoneMoodProfile) -> None:
        """Update in-memory profile and persist to DB."""
        with self._lock:
            self._zone_profiles[profile.zone_id] = profile
        self.persist_profile(profile)

    def update_zone_mood(self, zone_id: str, data: Dict[str, Any]) -> None:
        """Update zone mood from external data (e.g., neuron pipeline).

        Accepts partial updates: only provided fields are changed.
        """
        with self._lock:
            current = self._zone_profiles.get(zone_id)
            if not current:
                current = ZoneMoodProfile(zone_id=zone_id)

            if "dominant_mood" in data:
                current.state = MoodState.from_str(str(data["dominant_mood"]))
            if "confidence" in data:
                try:
                    current.confidence = float(data["confidence"])
                except (ValueError, TypeError):
                    pass

            dims = data.get("dimensions", {})
            if isinstance(dims, dict):
                for dim_name in ("comfort", "frugality", "joy", "energy", "stress"):
                    if dim_name in dims:
                        try:
                            setattr(current.dimensions, dim_name, float(dims[dim_name]))
                        except (ValueError, TypeError):
                            pass
                current.dimensions.clamp()

            self._zone_profiles[zone_id] = current
        self.persist_profile(current)

    def update_from_media_context(self, media_snapshot: Dict[str, Any]) -> None:
        """Update mood based on MediaContext snapshot (backwards compat)."""
        if not media_snapshot:
            return
        music_active = media_snapshot.get("music_active", False)
        tv_active = media_snapshot.get("tv_active", False)
        media_active = music_active or tv_active

        primary = media_snapshot.get("primary_player")
        if not primary:
            return

        area_id = primary.get("area", "unknown")
        media_title = primary.get("media_title", "")
        joy_boost = 0.7 if music_active else (0.3 if tv_active else 0.0)

        with self._lock:
            current = self._zone_profiles.get(area_id)
            if not current:
                current = ZoneMoodProfile(zone_id=area_id)

            alpha = 0.3
            current.dimensions.joy = current.dimensions.joy * (1 - alpha) + joy_boost * alpha
            current.dimensions.clamp()
            current.media_playing = media_active
            current.media_primary = media_title
            self._zone_profiles[area_id] = current
        self.persist_profile(current)

    def update_from_habitus(self, habitus_context: Dict[str, Any]) -> None:
        """Update mood based on Habitus context (backwards compat)."""
        if not habitus_context:
            return
        tod = habitus_context.get("time_of_day", "afternoon")
        try:
            frug = float(habitus_context.get("frugality_score", 0.5))
        except (ValueError, TypeError):
            frug = 0.5
        occ = habitus_context.get("zone_activity_level", "low")

        comfort_by_time = {"morning": 0.6, "afternoon": 0.5, "evening": 0.8, "night": 0.2}
        comfort = comfort_by_time.get(tod, 0.5)
        joy_base = 0.4 if occ == "high" else 0.2
        if tod in ("evening", "night"):
            joy_base += 0.2

        alpha = 0.3
        with self._lock:
            profiles_snapshot = list(self._zone_profiles.values())
        for profile in profiles_snapshot:
            profile.dimensions.comfort = profile.dimensions.comfort * (1 - alpha) + comfort * alpha
            profile.dimensions.frugality = profile.dimensions.frugality * (1 - alpha) + frug * alpha
            profile.dimensions.joy = profile.dimensions.joy * (1 - alpha) + joy_base * alpha
            profile.dimensions.clamp()
            profile.time_of_day = tod
            profile.occupancy_level = occ
            with self._lock:
                self._zone_profiles[profile.zone_id] = profile
            self.persist_profile(profile)

    # ── Query API ───────────────────────────────────────────────────────

    def get_zone_profile(self, zone_id: str) -> Optional[ZoneMoodProfile]:
        with self._lock:
            return self._zone_profiles.get(zone_id)

    def get_zone_mood(self, zone_id: str) -> Optional[ZoneMoodProfile]:
        """Alias for backwards compatibility."""
        return self.get_zone_profile(zone_id)

    def get_all_zone_profiles(self) -> Dict[str, ZoneMoodProfile]:
        with self._lock:
            return dict(self._zone_profiles)

    def get_all_zone_moods(self) -> Dict[str, ZoneMoodProfile]:
        """Alias for backwards compatibility."""
        return self.get_all_zone_profiles()

    def get_mood_history(
        self, zone_id: str, hours: int = 24, limit: int = 500
    ) -> List[Dict[str, Any]]:
        hours = max(1, min(hours, 8760))
        limit = max(1, min(limit, 10_000))
        cutoff = time.time() - (hours * 3600)
        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            rows = conn.execute(
                "SELECT timestamp, state, comfort, frugality, joy, energy, stress, "
                "confidence, time_of_day, occupancy_level "
                "FROM mood_profiles "
                "WHERE zone_id = ? AND timestamp > ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (zone_id, cutoff, limit),
            ).fetchall()
            return [
                {
                    "timestamp": int(r[0]),
                    "state": r[1],
                    "comfort": round(r[2], 3),
                    "frugality": round(r[3], 3),
                    "joy": round(r[4], 3),
                    "energy": round(r[5], 3),
                    "stress": round(r[6], 3),
                    "confidence": round(r[7], 3),
                    "time_of_day": r[8],
                    "occupancy_level": r[9],
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to query mood history for %s", zone_id)
            return []
        finally:
            if conn is not None:
                conn.close()

    def get_state_distribution(
        self, zone_id: str, hours: int = 24
    ) -> Dict[str, int]:
        """Get mood state distribution for a zone over a time period."""
        hours = max(1, min(hours, 8760))
        cutoff = time.time() - (hours * 3600)
        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=5.0)
            rows = conn.execute(
                "SELECT state, COUNT(*) FROM mood_profiles "
                "WHERE zone_id = ? AND timestamp > ? "
                "GROUP BY state",
                (zone_id, cutoff),
            ).fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception:
            logger.exception("Failed to query state distribution for %s", zone_id)
            return {}
        finally:
            if conn is not None:
                conn.close()

    def should_suppress_energy_saving(self, zone_id: str) -> bool:
        profile = self.get_zone_profile(zone_id)
        if not profile:
            return False
        if profile.dimensions.joy > 0.6:
            return True
        if profile.dimensions.comfort > 0.7 and profile.dimensions.frugality < 0.5:
            return True
        return False

    def get_suggestion_relevance_multiplier(
        self, zone_id: str, suggestion_type: str
    ) -> float:
        profile = self.get_zone_profile(zone_id)
        if not profile:
            return 1.0

        dims = profile.dimensions
        if suggestion_type == "energy_saving":
            return max(0.0, (1 - dims.joy) * dims.frugality)
        elif suggestion_type == "comfort":
            return dims.comfort
        elif suggestion_type == "entertainment":
            return dims.joy
        elif suggestion_type == "security":
            return 1.0
        elif suggestion_type == "focus":
            return 1.0 - dims.stress
        return 1.0

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            profiles = list(self._zone_profiles.values())
        if not profiles:
            return {
                "zones": 0,
                "average_comfort": 0.5,
                "average_frugality": 0.5,
                "average_joy": 0.5,
                "average_energy": 0.5,
                "average_stress": 0.0,
                "zones_with_media": 0,
            }

        n = len(profiles)
        return {
            "zones": n,
            "average_comfort": round(sum(p.dimensions.comfort for p in profiles) / n, 2),
            "average_frugality": round(sum(p.dimensions.frugality for p in profiles) / n, 2),
            "average_joy": round(sum(p.dimensions.joy for p in profiles) / n, 2),
            "average_energy": round(sum(p.dimensions.energy for p in profiles) / n, 2),
            "average_stress": round(sum(p.dimensions.stress for p in profiles) / n, 2),
            "zones_with_media": sum(1 for p in profiles if p.media_playing),
            "zone_breakdown": {p.zone_id: p.to_dict() for p in profiles},
        }
