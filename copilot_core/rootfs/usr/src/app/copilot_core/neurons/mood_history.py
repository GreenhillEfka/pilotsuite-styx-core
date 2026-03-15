"""Mood Snapshot Persistence -- SQLite-backed time-series storage for mood evaluations.

Stores mood evaluation results as snapshots so historical trend analysis
and pattern discovery become possible. Without this, mood evaluations are
computed on-the-fly and lost after the API response.

Schema:
    mood_snapshots(id INTEGER PRIMARY KEY, ts TEXT, mood TEXT,
                   confidence REAL, mood_values TEXT, zone_context TEXT)

Usage:
    store = get_mood_history_store()
    store.record_snapshot("relax", 0.85, {"relax": 0.85, "focus": 0.3})
    recent = store.get_recent(hours=24)
    trend = store.get_trend(hours=24)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

# Default retention: 7 days
_DEFAULT_RETENTION_DAYS = 7

# Minimum interval between snapshots (seconds)
_MIN_RECORD_INTERVAL_S = 300  # 5 minutes


class MoodHistoryStore:
    """SQLite-backed time-series storage for mood evaluation snapshots.

    Thread-safe via write lock (same pattern as BrainGraphStore).
    Auto-cleans old snapshots beyond retention period.
    Rate-limits recording to at most once per 5 minutes.
    """

    def __init__(
        self,
        db_path: str = "/data/mood_history.db",
        retention_days: Optional[int] = None,
        min_interval_s: int = _MIN_RECORD_INTERVAL_S,
    ):
        self.db_path = self._resolve_db_path(Path(db_path))
        self.retention_days = retention_days or int(
            os.environ.get("MOOD_HISTORY_RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS))
        )
        self.min_interval_s = min_interval_s
        self._write_lock = threading.Lock()
        self._last_record_ts: float = 0.0
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_db_path(configured_path: Path) -> Path:
        """Resolve a writable SQLite path with fallback."""
        try:
            configured_path.parent.mkdir(parents=True, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = Path(os.environ.get("COPILOT_MOOD_HISTORY_DB_DIR", "/tmp"))
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / configured_path.name
            _LOGGER.warning(
                "MoodHistoryStore path %s not writable, using fallback %s",
                configured_path,
                fallback_path,
            )
            return fallback_path

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection with proper pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create table and indices if they don't exist."""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS mood_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    mood TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    mood_values TEXT NOT NULL,
                    zone_context TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mood_snapshots_ts
                    ON mood_snapshots (ts);
                CREATE INDEX IF NOT EXISTS idx_mood_snapshots_mood
                    ON mood_snapshots (mood);
            """)
        _LOGGER.info("MoodHistoryStore initialized at %s", self.db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_snapshot(
        self,
        mood: str,
        confidence: float,
        mood_values: Dict[str, float],
        zone_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a mood evaluation snapshot.

        Rate-limited: silently skips if called within ``min_interval_s``
        of the previous recording.

        Args:
            mood: Dominant mood name (e.g. "relax", "focus").
            confidence: Confidence score 0.0-1.0.
            mood_values: Full mood vector {mood_name: value}.
            zone_context: Optional zone/area context dict.

        Returns:
            True if recorded, False if skipped (rate limit or error).
        """
        now = time.monotonic()
        if now - self._last_record_ts < self.min_interval_s:
            _LOGGER.debug("Mood snapshot skipped (rate limit)")
            return False

        ts = datetime.now(timezone.utc).isoformat()

        try:
            with self._write_lock, self._connect() as conn:
                conn.execute(
                    """INSERT INTO mood_snapshots (ts, mood, confidence, mood_values, zone_context)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        ts,
                        mood,
                        confidence,
                        json.dumps(mood_values),
                        json.dumps(zone_context) if zone_context else None,
                    ),
                )
            self._last_record_ts = now
            _LOGGER.debug("Recorded mood snapshot: %s (%.2f)", mood, confidence)
            return True
        except Exception:
            _LOGGER.exception("Failed to record mood snapshot")
            return False

    def get_recent(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Return snapshots from the last *hours* hours.

        Args:
            hours: Look-back window in hours (default 24).

        Returns:
            List of snapshot dicts ordered by timestamp ascending.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM mood_snapshots WHERE ts >= ? ORDER BY ts ASC",
                    (cutoff,),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
        except Exception:
            _LOGGER.exception("Failed to get recent mood snapshots")
            return []

    def get_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Return mood distribution and statistics over a time period.

        Args:
            hours: Look-back window in hours (default 24).

        Returns:
            Dict with keys:
                count: total snapshots in period
                distribution: {mood: count}
                dominant_mood: most frequent mood
                avg_confidence: average confidence across snapshots
                period_hours: requested window
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            with self._connect() as conn:
                # Distribution
                dist_rows = conn.execute(
                    """SELECT mood, COUNT(*) as cnt, AVG(confidence) as avg_conf
                       FROM mood_snapshots WHERE ts >= ?
                       GROUP BY mood ORDER BY cnt DESC""",
                    (cutoff,),
                ).fetchall()

                total_row = conn.execute(
                    "SELECT COUNT(*), AVG(confidence) FROM mood_snapshots WHERE ts >= ?",
                    (cutoff,),
                ).fetchone()

            distribution = {r["mood"]: r["cnt"] for r in dist_rows}
            total = total_row[0] or 0
            avg_confidence = round(total_row[1] or 0.0, 3)
            dominant = dist_rows[0]["mood"] if dist_rows else "unknown"

            return {
                "count": total,
                "distribution": distribution,
                "dominant_mood": dominant,
                "avg_confidence": avg_confidence,
                "period_hours": hours,
            }
        except Exception:
            _LOGGER.exception("Failed to get mood trend")
            return {
                "count": 0,
                "distribution": {},
                "dominant_mood": "unknown",
                "avg_confidence": 0.0,
                "period_hours": hours,
            }

    def cleanup(self) -> int:
        """Remove snapshots older than retention period.

        Returns:
            Number of rows deleted.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        ).isoformat()
        try:
            with self._write_lock, self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM mood_snapshots WHERE ts < ?", (cutoff,)
                )
                deleted = cursor.rowcount
                if deleted:
                    _LOGGER.info("Cleaned up %d old mood snapshots", deleted)
                return deleted
        except Exception:
            _LOGGER.exception("Failed to cleanup mood snapshots")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Return basic statistics about the store."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*), MIN(ts), MAX(ts) FROM mood_snapshots"
                ).fetchone()
            return {
                "total_snapshots": row[0] or 0,
                "oldest": row[1],
                "newest": row[2],
                "retention_days": self.retention_days,
                "db_path": str(self.db_path),
            }
        except Exception:
            _LOGGER.exception("Failed to get mood history stats")
            return {"total_snapshots": 0, "retention_days": self.retention_days}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to an API-friendly dict."""
        return {
            "id": row["id"],
            "ts": row["ts"],
            "mood": row["mood"],
            "confidence": row["confidence"],
            "mood_values": json.loads(row["mood_values"]),
            "zone_context": json.loads(row["zone_context"]) if row["zone_context"] else None,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store_instance: Optional[MoodHistoryStore] = None
_store_lock = threading.Lock()


def get_mood_history_store(
    db_path: str = "/data/mood_history.db",
) -> MoodHistoryStore:
    """Get or create the singleton MoodHistoryStore.

    Uses double-checked locking for thread safety (same pattern as
    LLMProvider / ModuleRegistry).
    """
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = MoodHistoryStore(db_path=db_path)
    return _store_instance


def reset_mood_history_store() -> None:
    """Reset the singleton (for testing)."""
    global _store_instance
    _store_instance = None


__all__ = [
    "MoodHistoryStore",
    "get_mood_history_store",
    "reset_mood_history_store",
]
