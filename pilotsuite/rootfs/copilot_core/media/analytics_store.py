"""Music/Media Analytics Store — Slice 49."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    MusicAnalyticsSummaryV1,
    MusicEffectivenessMetricsV1,
    MusicMediaType,
    MusicSource,
    MusicUsageEntryV1,
    MusicUsageHistoryV1,
    MusicZonePatternEntryV1,
    MusicZonePatternsV1,
)


class MusicAnalyticsStore:
    """Store für Music-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/music_analytics.db"):
        self.db_path = db_path
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        self._init_db()

    def _init_db(self) -> None:
        """Datenbank-Schema initialisieren."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Usage history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_usage_history (
                entry_id TEXT PRIMARY KEY,
                zone_id TEXT NOT NULL,
                zone_name TEXT,
                media_type TEXT NOT NULL,
                media_id TEXT NOT NULL,
                media_name TEXT NOT NULL,
                player_id TEXT,
                source TEXT NOT NULL,
                volume INTEGER NOT NULL,
                duration_seconds INTEGER,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Zone patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_zone_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                zone_name TEXT NOT NULL,
                total_sessions INTEGER NOT NULL DEFAULT 0,
                avg_session_duration_seconds REAL,
                most_used_media_type TEXT,
                most_common_source TEXT,
                avg_volume REAL NOT NULL DEFAULT 0.0,
                peak_listening_hour INTEGER,
                sessions_last_7_days INTEGER NOT NULL DEFAULT 0,
                sessions_last_30_days INTEGER NOT NULL DEFAULT 0,
                favorite_media TEXT,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_sessions_analyzed INTEGER DEFAULT 0,
                sessions_by_source TEXT,
                auto_presence_acceptance_rate REAL DEFAULT 0.0,
                schedule_reliability REAL DEFAULT 0.0,
                avg_volume_by_time_of_day TEXT,
                zones_with_regular_usage INTEGER DEFAULT 0,
                zones_with_rare_usage INTEGER DEFAULT 0,
                favorite_diversity_score REAL DEFAULT 0.0,
                engagement_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO music_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def _compute_entry_hash(self, entry: MusicUsageEntryV1) -> str:
        data = f"{entry.entry_id}:{entry.zone_id}:{entry.started_at}:{entry.media_id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add_usage_entry(self, entry: MusicUsageEntryV1) -> None:
        """Music-Usage-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO music_usage_history 
            (entry_id, zone_id, zone_name, media_type, media_id, media_name, 
             player_id, source, volume, duration_seconds, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.zone_id, entry.zone_name, entry.media_type,
            entry.media_id, entry.media_name, entry.player_id, entry.source,
            entry.volume, entry.duration_seconds, entry.started_at, entry.ended_at
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_usage_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        zone_id: Optional[str] = None,
        media_type: Optional[str] = None,
        limit: int = 100,
    ) -> MusicUsageHistoryV1:
        """Music-Usage-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, zone_id, zone_name, media_type, media_id, media_name,
                   player_id, source, volume, duration_seconds, started_at, ended_at
            FROM music_usage_history
            WHERE started_at >= ? AND started_at <= ?
        """
        params = [query_start, query_end]

        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)

        if media_type:
            query += " AND media_type = ?"
            params.append(media_type)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[MusicUsageEntryV1] = []
        total_duration = 0
        total_sonos = 0
        total_musikwolke = 0
        durations: List[int] = []

        for row in rows:
            duration = row[9]
            if duration:
                total_duration += duration
                durations.append(duration)

            if row[3] in ["sonos_favorite", "sonos_radio", "sonos_playlist"]:
                total_sonos += 1
            elif row[3] == "musikwolke":
                total_musikwolke += 1

            entries.append(
                MusicUsageEntryV1(
                    entry_id=row[0],
                    zone_id=row[1],
                    zone_name=row[2],
                    media_type=row[3],
                    media_id=row[4],
                    media_name=row[5],
                    player_id=row[6],
                    source=row[7],
                    volume=row[8],
                    duration_seconds=duration,
                    started_at=row[10],
                    ended_at=row[11],
                )
            )

        avg_duration = sum(durations) / len(durations) if durations else None

        return MusicUsageHistoryV1(
            entries=entries,
            total_sessions=len(entries),
            total_duration_seconds=total_duration,
            avg_duration_seconds=avg_duration,
            total_sonos_sessions=total_sonos,
            total_musikwolke_sessions=total_musikwolke,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_zone_patterns(
        self,
        zone_ids: Optional[List[str]] = None,
    ) -> MusicZonePatternsV1:
        """Zone-spezifische Music-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        seven_days_ago = (now - timedelta(days=7)).isoformat()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()

        # Alle Zonen mit Music-Sessions laden
        query = """
            SELECT DISTINCT zone_id, zone_name FROM music_usage_history
        """
        if zone_ids:
            placeholders = ",".join("?" * len(zone_ids))
            query += f" WHERE zone_id IN ({placeholders})"
            cursor.execute(query, zone_ids)
        else:
            cursor.execute(query)

        zone_rows = cursor.fetchall()

        patterns: List[MusicZonePatternEntryV1] = []
        zones_with_music = 0

        for zone_id, zone_name in zone_rows:
            # Total sessions
            cursor.execute(
                "SELECT COUNT(*) FROM music_usage_history WHERE zone_id = ?",
                (zone_id,)
            )
            total_sessions = cursor.fetchone()[0]

            if total_sessions == 0:
                continue

            zones_with_music += 1

            # Avg duration
            cursor.execute(
                "SELECT AVG(duration_seconds) FROM music_usage_history WHERE zone_id = ? AND duration_seconds IS NOT NULL",
                (zone_id,)
            )
            avg_duration = cursor.fetchone()[0]

            # Most used media type
            cursor.execute(
                """
                SELECT media_type, COUNT(*) as cnt 
                FROM music_usage_history 
                WHERE zone_id = ? 
                GROUP BY media_type 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (zone_id,)
            )
            most_used_media = cursor.fetchone()
            most_used_media_type = most_used_media[0] if most_used_media else None

            # Most common source
            cursor.execute(
                """
                SELECT source, COUNT(*) as cnt 
                FROM music_usage_history 
                WHERE zone_id = ? 
                GROUP BY source 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (zone_id,)
            )
            most_common_source = cursor.fetchone()
            most_common_source_val = most_common_source[0] if most_common_source else None

            # Avg volume
            cursor.execute(
                "SELECT AVG(volume) FROM music_usage_history WHERE zone_id = ?",
                (zone_id,)
            )
            avg_volume = cursor.fetchone()[0] or 0.0

            # Peak listening hour
            cursor.execute(
                """
                SELECT strftime('%H', started_at) as hour, COUNT(*) as cnt
                FROM music_usage_history
                WHERE zone_id = ?
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (zone_id,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            # Sessions last 7/30 days
            cursor.execute(
                "SELECT COUNT(*) FROM music_usage_history WHERE zone_id = ? AND started_at >= ?",
                (zone_id, seven_days_ago)
            )
            sessions_7d = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM music_usage_history WHERE zone_id = ? AND started_at >= ?",
                (zone_id, thirty_days_ago)
            )
            sessions_30d = cursor.fetchone()[0]

            # Favorite media (top 3)
            cursor.execute(
                """
                SELECT media_name, COUNT(*) as cnt 
                FROM music_usage_history 
                WHERE zone_id = ? 
                GROUP BY media_name 
                ORDER BY cnt DESC 
                LIMIT 3
                """,
                (zone_id,)
            )
            favorite_media = [row[0] for row in cursor.fetchall()]

            patterns.append(
                MusicZonePatternEntryV1(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    total_sessions=total_sessions,
                    avg_session_duration_seconds=avg_duration,
                    most_used_media_type=most_used_media_type,
                    most_common_source=most_common_source_val,
                    avg_volume=avg_volume,
                    peak_listening_hour=peak_hour,
                    sessions_last_7_days=sessions_7d,
                    sessions_last_30_days=sessions_30d,
                    favorite_media=favorite_media,
                )
            )

        conn.close()

        # Get total zones from zone_truth if available
        total_zones = len(zone_rows)

        return MusicZonePatternsV1(
            patterns=patterns,
            total_zones=total_zones,
            zones_with_music=zones_with_music,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> MusicEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total sessions analyzed
        cursor.execute("SELECT COUNT(*) FROM music_usage_history")
        total_sessions = cursor.fetchone()[0]

        # Sessions by source
        cursor.execute(
            """
            SELECT source, COUNT(*) as cnt 
            FROM music_usage_history 
            GROUP BY source
            """
        )
        sessions_by_source = {row[0]: row[1] for row in cursor.fetchall()}

        # Auto presence acceptance rate (simplified: presence sessions / total)
        auto_presence_count = sessions_by_source.get("auto_presence", 0)
        auto_presence_acceptance_rate = (
            auto_presence_count / total_sessions if total_sessions > 0 else 0.0
        )

        # Schedule reliability (simplified: schedule sessions that completed / total schedule)
        schedule_count = sessions_by_source.get("schedule", 0)
        schedule_reliability = 0.5  # Placeholder

        # Avg volume by time of day
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', started_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', started_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', started_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                AVG(volume) as avg_volume
            FROM music_usage_history
            GROUP BY time_of_day
            """
        )
        avg_volume_by_time = {row[0]: row[1] for row in cursor.fetchall()}

        # Zones with regular vs rare usage (regular = >5 sessions, rare = <=5)
        cursor.execute(
            """
            SELECT zone_id, COUNT(*) as cnt 
            FROM music_usage_history 
            GROUP BY zone_id
            """
        )
        zone_counts = cursor.fetchall()
        zones_regular = sum(1 for _, cnt in zone_counts if cnt > 5)
        zones_rare = sum(1 for _, cnt in zone_counts if cnt <= 5)

        # Favorite diversity score (unique media / total sessions)
        cursor.execute("SELECT COUNT(DISTINCT media_id) FROM music_usage_history")
        unique_media = cursor.fetchone()[0]
        diversity_score = unique_media / total_sessions if total_sessions > 0 else 0.0

        # Engagement score (composite)
        engagement_score = min(
            1.0,
            (total_sessions / 100) * 0.3
            + auto_presence_acceptance_rate * 0.3
            + diversity_score * 0.2
            + (zones_regular / max(1, zones_regular + zones_rare)) * 0.2,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE music_effectiveness_metrics 
            SET total_sessions_analyzed = ?,
                sessions_by_source = ?,
                auto_presence_acceptance_rate = ?,
                schedule_reliability = ?,
                avg_volume_by_time_of_day = ?,
                zones_with_regular_usage = ?,
                zones_with_rare_usage = ?,
                favorite_diversity_score = ?,
                engagement_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_sessions,
                str(sessions_by_source),
                auto_presence_acceptance_rate,
                schedule_reliability,
                str(avg_volume_by_time),
                zones_regular,
                zones_rare,
                diversity_score,
                engagement_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return MusicEffectivenessMetricsV1(
            total_sessions_analyzed=total_sessions,
            sessions_by_source=sessions_by_source,
            auto_presence_acceptance_rate=auto_presence_acceptance_rate,
            schedule_reliability=schedule_reliability,
            avg_volume_by_time_of_day=avg_volume_by_time,
            zones_with_regular_usage=zones_regular,
            zones_with_rare_usage=zones_rare,
            favorite_diversity_score=diversity_score,
            engagement_score=engagement_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> MusicAnalyticsSummaryV1:
        """Zusammenfassung aller Music-Analytics."""
        usage = self.build_usage_history()
        patterns = self.build_zone_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return MusicAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_music_analytics_store: Optional[MusicAnalyticsStore] = None


def get_music_analytics_store() -> MusicAnalyticsStore:
    """MusicAnalyticsStore-Singleton holen."""
    global _music_analytics_store
    if _music_analytics_store is None:
        _music_analytics_store = MusicAnalyticsStore()
    return _music_analytics_store
