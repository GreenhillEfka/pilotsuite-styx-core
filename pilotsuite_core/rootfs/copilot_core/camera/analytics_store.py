"""Camera Analytics Store — Slice 50."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    CameraAnalyticsSummaryV1,
    CameraEffectivenessMetricsV1,
    CameraEventType,
    CameraSource,
    CameraUsageEntryV1,
    CameraUsageHistoryV1,
    CameraZonePatternEntryV1,
    CameraZonePatternsV1,
)


class CameraAnalyticsStore:
    """Store für Camera-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/camera_analytics.db"):
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
            CREATE TABLE IF NOT EXISTS camera_usage_history (
                entry_id TEXT PRIMARY KEY,
                zone_id TEXT NOT NULL,
                zone_name TEXT,
                camera_id TEXT NOT NULL,
                camera_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                snapshot_taken INTEGER NOT NULL DEFAULT 0,
                recording_started INTEGER NOT NULL DEFAULT 0,
                recording_duration_seconds INTEGER,
                thumbnail_generated INTEGER NOT NULL DEFAULT 0,
                notification_sent INTEGER NOT NULL DEFAULT 0,
                processed_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Zone patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_zone_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                zone_name TEXT NOT NULL,
                total_events INTEGER NOT NULL DEFAULT 0,
                motion_events INTEGER NOT NULL DEFAULT 0,
                person_events INTEGER NOT NULL DEFAULT 0,
                vehicle_events INTEGER NOT NULL DEFAULT 0,
                sound_events INTEGER NOT NULL DEFAULT 0,
                doorbell_events INTEGER NOT NULL DEFAULT 0,
                snapshots_taken INTEGER NOT NULL DEFAULT 0,
                recordings_started INTEGER NOT NULL DEFAULT 0,
                avg_recording_duration_seconds REAL,
                peak_activity_hour INTEGER,
                events_last_24_hours INTEGER NOT NULL DEFAULT 0,
                events_last_7_days INTEGER NOT NULL DEFAULT 0,
                most_common_event_type TEXT,
                most_common_source TEXT,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_events_analyzed INTEGER DEFAULT 0,
                events_by_type TEXT,
                events_by_source TEXT,
                motion_to_person_ratio REAL DEFAULT 0.0,
                false_positive_rate REAL,
                notification_delivery_rate REAL DEFAULT 0.0,
                snapshot_capture_rate REAL DEFAULT 0.0,
                recording_trigger_rate REAL DEFAULT 0.0,
                avg_events_per_zone REAL DEFAULT 0.0,
                zones_with_regular_activity INTEGER DEFAULT 0,
                zones_with_rare_activity INTEGER DEFAULT 0,
                peak_activity_time TEXT,
                engagement_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO camera_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def _compute_entry_hash(self, entry: CameraUsageEntryV1) -> str:
        data = f"{entry.entry_id}:{entry.zone_id}:{entry.camera_id}:{entry.processed_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add_usage_entry(self, entry: CameraUsageEntryV1) -> None:
        """Camera-Usage-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO camera_usage_history 
            (entry_id, zone_id, zone_name, camera_id, camera_name, 
             event_type, source, snapshot_taken, recording_started, 
             recording_duration_seconds, thumbnail_generated, notification_sent, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.zone_id, entry.zone_name, entry.camera_id,
            entry.camera_name, entry.event_type, entry.source,
            1 if entry.snapshot_taken else 0,
            1 if entry.recording_started else 0,
            entry.recording_duration_seconds,
            1 if entry.thumbnail_generated else 0,
            1 if entry.notification_sent else 0,
            entry.processed_at
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_usage_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        zone_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> CameraUsageHistoryV1:
        """Camera-Usage-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, zone_id, zone_name, camera_id, camera_name,
                   event_type, source, snapshot_taken, recording_started,
                   recording_duration_seconds, thumbnail_generated, notification_sent, processed_at
            FROM camera_usage_history
            WHERE processed_at >= ? AND processed_at <= ?
        """
        params = [query_start, query_end]

        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY processed_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[CameraUsageEntryV1] = []
        total_snapshots = 0
        total_recordings = 0
        total_duration = 0
        durations: List[int] = []

        for row in rows:
            snapshot_taken = bool(row[7])
            recording_started = bool(row[8])
            duration = row[9]

            if snapshot_taken:
                total_snapshots += 1
            if recording_started:
                total_recordings += 1
            if duration:
                total_duration += duration
                durations.append(duration)

            entries.append(
                CameraUsageEntryV1(
                    entry_id=row[0],
                    zone_id=row[1],
                    zone_name=row[2],
                    camera_id=row[3],
                    camera_name=row[4],
                    event_type=row[5],
                    source=row[6],
                    snapshot_taken=snapshot_taken,
                    recording_started=recording_started,
                    recording_duration_seconds=duration,
                    thumbnail_generated=bool(row[10]),
                    notification_sent=bool(row[11]),
                    processed_at=row[12],
                )
            )

        avg_duration = sum(durations) / len(durations) if durations else None

        return CameraUsageHistoryV1(
            entries=entries,
            total_events=len(entries),
            total_snapshots=total_snapshots,
            total_recordings=total_recordings,
            total_recording_duration_seconds=total_duration,
            avg_recording_duration_seconds=avg_duration,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_zone_patterns(
        self,
        zone_ids: Optional[List[str]] = None,
    ) -> CameraZonePatternsV1:
        """Zone-spezifische Camera-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        twentyfour_hours_ago = (now - timedelta(hours=24)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # Alle Zonen mit Camera-Events laden
        query = """
            SELECT DISTINCT zone_id, zone_name FROM camera_usage_history
        """
        if zone_ids:
            placeholders = ",".join("?" * len(zone_ids))
            query += f" WHERE zone_id IN ({placeholders})"
            cursor.execute(query, zone_ids)
        else:
            cursor.execute(query)

        zone_rows = cursor.fetchall()

        patterns: List[CameraZonePatternEntryV1] = []
        zones_with_activity = 0

        for zone_id, zone_name in zone_rows:
            # Total events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ?",
                (zone_id,)
            )
            total_events = cursor.fetchone()[0]

            if total_events == 0:
                continue

            zones_with_activity += 1

            # Motion events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND event_type = 'motion_detected'",
                (zone_id,)
            )
            motion_events = cursor.fetchone()[0]

            # Person events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND event_type = 'person_detected'",
                (zone_id,)
            )
            person_events = cursor.fetchone()[0]

            # Vehicle events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND event_type = 'vehicle_detected'",
                (zone_id,)
            )
            vehicle_events = cursor.fetchone()[0]

            # Sound events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND event_type = 'sound_detected'",
                (zone_id,)
            )
            sound_events = cursor.fetchone()[0]

            # Doorbell events
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND event_type = 'doorbell_pressed'",
                (zone_id,)
            )
            doorbell_events = cursor.fetchone()[0]

            # Snapshots taken
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND snapshot_taken = 1",
                (zone_id,)
            )
            snapshots_taken = cursor.fetchone()[0]

            # Recordings started
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND recording_started = 1",
                (zone_id,)
            )
            recordings_started = cursor.fetchone()[0]

            # Avg recording duration
            cursor.execute(
                "SELECT AVG(recording_duration_seconds) FROM camera_usage_history WHERE zone_id = ? AND recording_duration_seconds IS NOT NULL",
                (zone_id,)
            )
            avg_duration = cursor.fetchone()[0]

            # Peak activity hour
            cursor.execute(
                """
                SELECT strftime('%H', processed_at) as hour, COUNT(*) as cnt
                FROM camera_usage_history
                WHERE zone_id = ?
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (zone_id,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            # Events last 24 hours / 7 days
            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND processed_at >= ?",
                (zone_id, twentyfour_hours_ago)
            )
            events_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM camera_usage_history WHERE zone_id = ? AND processed_at >= ?",
                (zone_id, seven_days_ago)
            )
            events_7d = cursor.fetchone()[0]

            # Most common event type
            cursor.execute(
                """
                SELECT event_type, COUNT(*) as cnt 
                FROM camera_usage_history 
                WHERE zone_id = ? 
                GROUP BY event_type 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (zone_id,)
            )
            most_common_event = cursor.fetchone()
            most_common_event_type = most_common_event[0] if most_common_event else None

            # Most common source
            cursor.execute(
                """
                SELECT source, COUNT(*) as cnt 
                FROM camera_usage_history 
                WHERE zone_id = ? 
                GROUP BY source 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (zone_id,)
            )
            most_common_source = cursor.fetchone()
            most_common_source_val = most_common_source[0] if most_common_source else None

            patterns.append(
                CameraZonePatternEntryV1(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    total_events=total_events,
                    motion_events=motion_events,
                    person_events=person_events,
                    vehicle_events=vehicle_events,
                    sound_events=sound_events,
                    doorbell_events=doorbell_events,
                    snapshots_taken=snapshots_taken,
                    recordings_started=recordings_started,
                    avg_recording_duration_seconds=avg_duration,
                    peak_activity_hour=peak_hour,
                    events_last_24_hours=events_24h,
                    events_last_7_days=events_7d,
                    most_common_event_type=most_common_event_type,
                    most_common_source=most_common_source_val,
                )
            )

        conn.close()

        total_zones = len(zone_rows)

        return CameraZonePatternsV1(
            patterns=patterns,
            total_zones=total_zones,
            zones_with_camera_activity=zones_with_activity,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> CameraEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total events analyzed
        cursor.execute("SELECT COUNT(*) FROM camera_usage_history")
        total_events = cursor.fetchone()[0]

        # Events by type
        cursor.execute(
            """
            SELECT event_type, COUNT(*) as cnt 
            FROM camera_usage_history 
            GROUP BY event_type
            """
        )
        events_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Events by source
        cursor.execute(
            """
            SELECT source, COUNT(*) as cnt 
            FROM camera_usage_history 
            GROUP BY source
            """
        )
        events_by_source = {row[0]: row[1] for row in cursor.fetchall()}

        # Motion to person ratio
        motion_count = events_by_type.get("motion_detected", 0)
        person_count = events_by_type.get("person_detected", 0)
        motion_to_person_ratio = person_count / motion_count if motion_count > 0 else 0.0

        # False positive rate (placeholder - would need user feedback)
        false_positive_rate = None

        # Notification delivery rate
        cursor.execute("SELECT COUNT(*) FROM camera_usage_history WHERE notification_sent = 1")
        notifications_sent = cursor.fetchone()[0]
        notification_delivery_rate = notifications_sent / total_events if total_events > 0 else 0.0

        # Snapshot capture rate
        cursor.execute("SELECT COUNT(*) FROM camera_usage_history WHERE snapshot_taken = 1")
        snapshots = cursor.fetchone()[0]
        snapshot_capture_rate = snapshots / total_events if total_events > 0 else 0.0

        # Recording trigger rate
        cursor.execute("SELECT COUNT(*) FROM camera_usage_history WHERE recording_started = 1")
        recordings = cursor.fetchone()[0]
        recording_trigger_rate = recordings / total_events if total_events > 0 else 0.0

        # Zones with regular vs rare activity (regular = >10 events, rare = <=10)
        cursor.execute(
            """
            SELECT zone_id, COUNT(*) as cnt 
            FROM camera_usage_history 
            GROUP BY zone_id
            """
        )
        zone_counts = cursor.fetchall()
        zones_regular = sum(1 for _, cnt in zone_counts if cnt > 10)
        zones_rare = sum(1 for _, cnt in zone_counts if cnt <= 10)

        # Avg events per zone
        total_zones = len(zone_counts)
        avg_events_per_zone = total_events / total_zones if total_zones > 0 else 0.0

        # Peak activity time
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', processed_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', processed_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', processed_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                COUNT(*) as cnt
            FROM camera_usage_history
            GROUP BY time_of_day
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        peak_time_row = cursor.fetchone()
        peak_activity_time = peak_time_row[0] if peak_time_row else None

        # Engagement score (composite)
        engagement_score = min(
            1.0,
            (total_events / 100) * 0.3
            + notification_delivery_rate * 0.2
            + snapshot_capture_rate * 0.2
            + (zones_regular / max(1, zones_regular + zones_rare)) * 0.3,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE camera_effectiveness_metrics 
            SET total_events_analyzed = ?,
                events_by_type = ?,
                events_by_source = ?,
                motion_to_person_ratio = ?,
                false_positive_rate = ?,
                notification_delivery_rate = ?,
                snapshot_capture_rate = ?,
                recording_trigger_rate = ?,
                avg_events_per_zone = ?,
                zones_with_regular_activity = ?,
                zones_with_rare_activity = ?,
                peak_activity_time = ?,
                engagement_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_events,
                str(events_by_type),
                str(events_by_source),
                motion_to_person_ratio,
                false_positive_rate,
                notification_delivery_rate,
                snapshot_capture_rate,
                recording_trigger_rate,
                avg_events_per_zone,
                zones_regular,
                zones_rare,
                peak_activity_time,
                engagement_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return CameraEffectivenessMetricsV1(
            total_events_analyzed=total_events,
            events_by_type=events_by_type,
            events_by_source=events_by_source,
            motion_to_person_ratio=motion_to_person_ratio,
            false_positive_rate=false_positive_rate,
            notification_delivery_rate=notification_delivery_rate,
            snapshot_capture_rate=snapshot_capture_rate,
            recording_trigger_rate=recording_trigger_rate,
            avg_events_per_zone=avg_events_per_zone,
            zones_with_regular_activity=zones_regular,
            zones_with_rare_activity=zones_rare,
            peak_activity_time=peak_activity_time,
            engagement_score=engagement_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> CameraAnalyticsSummaryV1:
        """Zusammenfassung aller Camera-Analytics."""
        usage = self.build_usage_history()
        patterns = self.build_zone_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return CameraAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_camera_analytics_store: Optional[CameraAnalyticsStore] = None


def get_camera_analytics_store() -> CameraAnalyticsStore:
    """CameraAnalyticsStore-Singleton holen."""
    global _camera_analytics_store
    if _camera_analytics_store is None:
        _camera_analytics_store = CameraAnalyticsStore()
    return _camera_analytics_store
