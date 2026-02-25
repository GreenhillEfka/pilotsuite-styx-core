"""
Mood Service — Per-Zone Comfort/Frugality/Joy Scoring

Synthesizes MediaContext and Habitus signals to provide context-aware
mood metrics that inform automation suggestion quality and relevance.

Mood State:
- comfort: (0–1) how comfortable the zone is (temp, light, activity)
- frugality: (0–1) user preference for resource efficiency (time-of-day, patterns)
- joy: (0–1) entertainment/enjoyment level (music, TV, social context)

Each zone maintains independent mood state updated every 30s or on signal changes.
Mood history is persisted to SQLite for trend analysis and restart resilience.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Persistence config
MOOD_DB_PATH = os.environ.get("COPILOT_MOOD_DB", "/data/mood_history.db")
MAX_HISTORY_ENTRIES = 50_000  # ~35 days at 1 entry/min per zone
SAVE_THROTTLE_SECONDS = 60  # Don't save the same zone more often than this
HISTORY_RETENTION_DAYS = 30


@dataclass
class ZoneMoodSnapshot:
    """Single zone's mood state at a point in time."""

    zone_id: str
    timestamp: float
    comfort: float  # 0–1, how comfortable the zone feels
    frugality: float  # 0–1, resource-efficiency preference
    joy: float  # 0–1, entertainment/enjoyment level

    # Metadata for debugging/explanation
    media_active: bool  # music or TV playing
    media_primary: Optional[str]  # now-playing title
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    occupancy_level: str  # "empty", "low", "medium", "high"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        d = asdict(self)
        d["timestamp"] = int(d["timestamp"])
        return d


class MoodService:
    """Aggregated mood scoring from MediaContext and Habitus signals.

    Persists mood snapshots to SQLite for:
    - Restart resilience (last known mood per zone restored on startup)
    - Trend analysis (30-day rolling history)
    - Learning context (RAG can query mood patterns)
    """

    def __init__(self, db_path: str = None):
        """Initialize mood service with SQLite persistence."""
        self._zone_moods: Dict[str, ZoneMoodSnapshot] = {}
        self._last_update: float = 0
        self._update_interval_seconds = 30
        self._db_path = self._resolve_db_path(db_path or MOOD_DB_PATH)
        self._lock = threading.Lock()
        self._last_save_ts: Dict[str, float] = {}  # zone_id -> last save timestamp
        self._save_count: int = 0  # Global save counter for periodic prune

        self._init_db()
        self._load_latest_moods()

        logger.info("MoodService initialized (persistent at %s)", self._db_path)

    # ── SQLite Persistence ──────────────────────────────────────────────

    def _resolve_db_path(self, configured_path: str) -> str:
        """Resolve writable DB path with fallback outside add-on runtime."""
        db_dir = os.path.dirname(configured_path) or "."
        try:
            os.makedirs(db_dir, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = os.environ.get("COPILOT_MOOD_DB_DIR", "/tmp")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback_path = os.path.join(
                fallback_dir,
                os.path.basename(configured_path) or "mood_history.db",
            )
            logger.warning(
                "Mood DB path %s not writable, using fallback %s",
                configured_path,
                fallback_path,
            )
            return fallback_path

    def _init_db(self):
        """Create mood_snapshots table if it doesn't exist."""
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS mood_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        zone_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        comfort REAL NOT NULL,
                        frugality REAL NOT NULL,
                        joy REAL NOT NULL,
                        media_active INTEGER NOT NULL DEFAULT 0,
                        media_primary TEXT,
                        time_of_day TEXT NOT NULL DEFAULT 'afternoon',
                        occupancy_level TEXT NOT NULL DEFAULT 'low'
                    );
                    CREATE INDEX IF NOT EXISTS idx_mood_zone_ts
                        ON mood_snapshots(zone_id, timestamp DESC);
                    CREATE INDEX IF NOT EXISTS idx_mood_ts
                        ON mood_snapshots(timestamp);
                """)
                conn.commit()
            finally:
                conn.close()

    def _load_latest_moods(self):
        """Restore last known mood per zone from DB on startup."""
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                # Get latest snapshot per zone using window function
                rows = conn.execute("""
                    SELECT zone_id, timestamp, comfort, frugality, joy,
                           media_active, media_primary, time_of_day, occupancy_level
                    FROM mood_snapshots
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (
                                PARTITION BY zone_id ORDER BY timestamp DESC
                            ) AS rn
                            FROM mood_snapshots
                        ) WHERE rn = 1
                    )
                """).fetchall()

                for row in rows:
                    snapshot = ZoneMoodSnapshot(
                        zone_id=row[0],
                        timestamp=row[1],
                        comfort=row[2],
                        frugality=row[3],
                        joy=row[4],
                        media_active=bool(row[5]),
                        media_primary=row[6],
                        time_of_day=row[7],
                        occupancy_level=row[8],
                    )
                    self._zone_moods[snapshot.zone_id] = snapshot

                if rows:
                    logger.info("Restored mood state for %d zones from DB", len(rows))
            except Exception:
                logger.exception("Failed to load mood history from DB")
            finally:
                conn.close()

    def _persist_snapshot(self, snapshot: ZoneMoodSnapshot) -> None:
        """Save a mood snapshot to DB (throttled per zone)."""
        now = time.time()
        last = self._last_save_ts.get(snapshot.zone_id, 0)
        if now - last < SAVE_THROTTLE_SECONDS:
            return  # Throttled — skip this save

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO mood_snapshots "
                    "(zone_id, timestamp, comfort, frugality, joy, "
                    "media_active, media_primary, time_of_day, occupancy_level) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        snapshot.zone_id,
                        snapshot.timestamp,
                        round(snapshot.comfort, 4),
                        round(snapshot.frugality, 4),
                        round(snapshot.joy, 4),
                        int(snapshot.media_active),
                        snapshot.media_primary,
                        snapshot.time_of_day,
                        snapshot.occupancy_level,
                    ),
                )
                conn.commit()
                self._last_save_ts[snapshot.zone_id] = now
                self._save_count += 1

                # Prune old entries periodically (every 100th save)
                if self._save_count % 100 == 0:
                    self._prune_old(conn)
            except Exception:
                logger.exception("Failed to persist mood snapshot for %s", snapshot.zone_id)
            finally:
                conn.close()

    def _prune_old(self, conn: sqlite3.Connection) -> None:
        """Remove entries older than retention period and enforce max count."""
        cutoff = time.time() - (HISTORY_RETENTION_DAYS * 86400)
        conn.execute("DELETE FROM mood_snapshots WHERE timestamp < ?", (cutoff,))

        count = conn.execute("SELECT COUNT(*) FROM mood_snapshots").fetchone()[0]
        if count > MAX_HISTORY_ENTRIES:
            excess = count - MAX_HISTORY_ENTRIES
            conn.execute(
                "DELETE FROM mood_snapshots WHERE id IN "
                "(SELECT id FROM mood_snapshots ORDER BY timestamp ASC LIMIT ?)",
                (excess,),
            )
        conn.commit()

    def get_mood_history(
        self, zone_id: str, hours: int = 24, limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Get mood history for a zone (for trend analysis / RAG)."""
        cutoff = time.time() - (hours * 3600)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    "SELECT timestamp, comfort, frugality, joy, time_of_day, occupancy_level "
                    "FROM mood_snapshots "
                    "WHERE zone_id = ? AND timestamp > ? "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (zone_id, cutoff, limit),
                ).fetchall()
                return [
                    {
                        "timestamp": int(r[0]),
                        "comfort": round(r[1], 3),
                        "frugality": round(r[2], 3),
                        "joy": round(r[3], 3),
                        "time_of_day": r[4],
                        "occupancy_level": r[5],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    # ── Mood Update Logic ───────────────────────────────────────────────

    def update_from_media_context(self, media_snapshot: Dict[str, Any]) -> None:
        """Update mood based on MediaContext snapshot.

        Args:
            media_snapshot: {
                "music_active": bool,
                "tv_active": bool,
                "primary_player": {"entity_id", "state", "media_title", "area"},
                "players": [...]
            }
        """
        if not media_snapshot:
            return

        # Aggregate music + TV signals
        music_active = media_snapshot.get("music_active", False)
        tv_active = media_snapshot.get("tv_active", False)
        media_active = music_active or tv_active

        primary = media_snapshot.get("primary_player")
        if primary:
            area_id = primary.get("area", "unknown")
            media_title = primary.get("media_title", "")

            # Boost joy when music is active
            joy_boost = 0.7 if music_active else (0.3 if tv_active else 0.0)

            # Update zone mood
            self._update_zone_mood(
                area_id,
                joy=joy_boost,
                media_active=media_active,
                media_primary=media_title
            )

    def update_from_habitus(self, habitus_context: Dict[str, Any]) -> None:
        """Update mood based on Habitus patterns.

        Args:
            habitus_context: {
                "time_of_day": "morning|afternoon|evening|night",
                "zone_activity_level": "low|medium|high",
                "recent_patterns": [...],
                "frugality_score": 0–1
            }
        """
        if not habitus_context:
            return

        time_of_day = habitus_context.get("time_of_day", "afternoon")
        frugality = habitus_context.get("frugality_score", 0.5)
        occupancy = habitus_context.get("zone_activity_level", "low")

        # Morning/evening = higher comfort preference
        # Night = lower comfort (sleeping), higher frugality
        comfort_by_time = {
            "morning": 0.6,
            "afternoon": 0.5,
            "evening": 0.8,
            "night": 0.2
        }
        comfort = comfort_by_time.get(time_of_day, 0.5)

        # High occupancy + evening = high joy baseline
        joy_baseline = 0.4 if occupancy == "high" else 0.2
        if time_of_day in ("evening", "night"):
            joy_baseline += 0.2

        # Update all known zones with time-of-day context
        for zone_id in self._zone_moods.keys():
            self._update_zone_mood(
                zone_id,
                comfort=comfort,
                frugality=frugality,
                joy=joy_baseline,
                time_of_day=time_of_day,
                occupancy_level=occupancy
            )

    def _update_zone_mood(
        self,
        zone_id: str,
        comfort: Optional[float] = None,
        frugality: Optional[float] = None,
        joy: Optional[float] = None,
        media_active: Optional[bool] = None,
        media_primary: Optional[str] = None,
        time_of_day: Optional[str] = None,
        occupancy_level: Optional[str] = None,
    ) -> None:
        """Update a single zone's mood, preserving existing values."""

        current = self._zone_moods.get(zone_id)
        if not current:
            # Initialize new zone
            current = ZoneMoodSnapshot(
                zone_id=zone_id,
                timestamp=time.time(),
                comfort=0.5,
                frugality=0.5,
                joy=0.5,
                media_active=False,
                media_primary=None,
                time_of_day="afternoon",
                occupancy_level="low"
            )

        # Update with new values (exponential smoothing for continuity)
        alpha = 0.3  # smoothing factor

        if comfort is not None:
            current.comfort = current.comfort * (1 - alpha) + comfort * alpha
        if frugality is not None:
            current.frugality = current.frugality * (1 - alpha) + frugality * alpha
        if joy is not None:
            current.joy = current.joy * (1 - alpha) + joy * alpha

        if media_active is not None:
            current.media_active = media_active
        if media_primary is not None:
            current.media_primary = media_primary
        if time_of_day is not None:
            current.time_of_day = time_of_day
        if occupancy_level is not None:
            current.occupancy_level = occupancy_level

        current.timestamp = time.time()
        self._zone_moods[zone_id] = current
        logger.debug(f"Updated {zone_id} mood: comfort={current.comfort:.2f}, "
                    f"frugality={current.frugality:.2f}, joy={current.joy:.2f}")

        # Persist to SQLite (throttled)
        self._persist_snapshot(current)

    # ── Query Methods ───────────────────────────────────────────────────

    def get_zone_mood(self, zone_id: str) -> Optional[ZoneMoodSnapshot]:
        """Get current mood snapshot for a zone."""
        return self._zone_moods.get(zone_id)

    def get_all_zone_moods(self) -> Dict[str, ZoneMoodSnapshot]:
        """Get all current zone moods."""
        return dict(self._zone_moods)

    def should_suppress_energy_saving(self, zone_id: str) -> bool:
        """Check if energy-saving automation should be suppressed in this zone.

        Returns True if user is likely enjoying entertainment (joy > 0.6)
        or if comfort is priority (comfort > 0.7).
        """
        mood = self.get_zone_mood(zone_id)
        if not mood:
            return False

        # Suppress energy-saving during entertainment
        if mood.joy > 0.6:
            return True

        # Suppress if comfort is prioritized
        if mood.comfort > 0.7 and mood.frugality < 0.5:
            return True

        return False

    def get_suggestion_relevance_multiplier(self, zone_id: str, suggestion_type: str) -> float:
        """Get a multiplier for suggestion relevance based on current mood.

        Used to weight candidate suggestions:
        - energy_saving: multiplied by (1 - joy) * frugality
        - comfort: multiplied by comfort
        - entertainment: multiplied by joy

        Args:
            zone_id: Target zone
            suggestion_type: "energy_saving", "comfort", "entertainment", "security"

        Returns:
            0–1 multiplier for suggestion confidence/relevance
        """
        mood = self.get_zone_mood(zone_id)
        if not mood:
            return 1.0  # Default: fully relevant if no mood data

        if suggestion_type == "energy_saving":
            # Less relevant if joy is high or frugality is low
            return max(0.0, (1 - mood.joy) * mood.frugality)

        elif suggestion_type == "comfort":
            # More relevant if comfort is priority
            return mood.comfort

        elif suggestion_type == "entertainment":
            # More relevant if joy is high
            return mood.joy

        elif suggestion_type == "security":
            # Security is always relevant (independent of mood)
            return 1.0

        # Default
        return 1.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary stats across all zones."""
        if not self._zone_moods:
            return {
                "zones": 0,
                "average_comfort": 0.5,
                "average_frugality": 0.5,
                "average_joy": 0.5,
                "zones_with_media": 0
            }

        moods = list(self._zone_moods.values())
        avg_comfort = sum(m.comfort for m in moods) / len(moods)
        avg_frugality = sum(m.frugality for m in moods) / len(moods)
        avg_joy = sum(m.joy for m in moods) / len(moods)
        media_zones = sum(1 for m in moods if m.media_active)

        return {
            "zones": len(moods),
            "average_comfort": round(avg_comfort, 2),
            "average_frugality": round(avg_frugality, 2),
            "average_joy": round(avg_joy, 2),
            "zones_with_media": media_zones,
            "zone_breakdown": {
                zone_id: mood.to_dict()
                for zone_id, mood in self._zone_moods.items()
            }
        }
