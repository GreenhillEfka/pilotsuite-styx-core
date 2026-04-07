"""Weather Analytics Store — Slice 51."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    WeatherAnalyticsSummaryV1,
    WeatherEffectivenessMetricsV1,
    WeatherEventType,
    WeatherDataSource,
    WeatherObservationEntryV1,
    WeatherObservationHistoryV1,
    WeatherZonePatternEntryV1,
    WeatherZonePatternsV1,
)


class WeatherAnalyticsStore:
    """Store für Weather-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/weather_analytics.db"):
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
            CREATE TABLE IF NOT EXISTS weather_observation_history (
                entry_id TEXT PRIMARY KEY,
                zone_id TEXT NOT NULL,
                zone_name TEXT,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                temperature_celsius REAL,
                humidity_percent REAL,
                wind_speed_kmh REAL,
                precipitation_mm REAL,
                pressure_hpa REAL,
                uv_index REAL,
                air_quality_index INTEGER,
                alert_triggered INTEGER NOT NULL DEFAULT 0,
                notification_sent INTEGER NOT NULL DEFAULT 0,
                automation_triggered INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Zone patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_zone_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                zone_name TEXT NOT NULL,
                total_observations INTEGER NOT NULL DEFAULT 0,
                temperature_events INTEGER NOT NULL DEFAULT 0,
                precipitation_events INTEGER NOT NULL DEFAULT 0,
                wind_events INTEGER NOT NULL DEFAULT 0,
                alert_events INTEGER NOT NULL DEFAULT 0,
                avg_temperature_celsius REAL,
                min_temperature_celsius REAL,
                max_temperature_celsius REAL,
                avg_humidity_percent REAL,
                avg_wind_speed_kmh REAL,
                total_precipitation_mm REAL,
                observations_last_24_hours INTEGER NOT NULL DEFAULT 0,
                observations_last_7_days INTEGER NOT NULL DEFAULT 0,
                most_common_event_type TEXT,
                most_common_source TEXT,
                peak_alert_hour INTEGER,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_observations_analyzed INTEGER DEFAULT 0,
                observations_by_type TEXT,
                observations_by_source TEXT,
                alert_accuracy_rate REAL,
                notification_delivery_rate REAL DEFAULT 0.0,
                automation_trigger_rate REAL DEFAULT 0.0,
                avg_observations_per_zone REAL DEFAULT 0.0,
                zones_with_regular_data INTEGER DEFAULT 0,
                zones_with_rare_data INTEGER DEFAULT 0,
                peak_weather_time TEXT,
                forecast_accuracy_score REAL,
                engagement_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO weather_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def _compute_entry_hash(self, entry: WeatherObservationEntryV1) -> str:
        data = f"{entry.entry_id}:{entry.zone_id}:{entry.event_type}:{entry.observed_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def add_observation_entry(self, entry: WeatherObservationEntryV1) -> None:
        """Weather-Observation-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO weather_observation_history 
            (entry_id, zone_id, zone_name, event_type, source, 
             temperature_celsius, humidity_percent, wind_speed_kmh, 
             precipitation_mm, pressure_hpa, uv_index, air_quality_index,
             alert_triggered, notification_sent, automation_triggered, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.zone_id, entry.zone_name, entry.event_type, entry.source,
            entry.temperature_celsius, entry.humidity_percent, entry.wind_speed_kmh,
            entry.precipitation_mm, entry.pressure_hpa, entry.uv_index, entry.air_quality_index,
            1 if entry.alert_triggered else 0,
            1 if entry.notification_sent else 0,
            1 if entry.automation_triggered else 0,
            entry.observed_at
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_observation_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        zone_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> WeatherObservationHistoryV1:
        """Weather-Observation-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, zone_id, zone_name, event_type, source,
                   temperature_celsius, humidity_percent, wind_speed_kmh,
                   precipitation_mm, pressure_hpa, uv_index, air_quality_index,
                   alert_triggered, notification_sent, automation_triggered, observed_at
            FROM weather_observation_history
            WHERE observed_at >= ? AND observed_at <= ?
        """
        params = [query_start, query_end]

        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[WeatherObservationEntryV1] = []
        total_alerts = 0
        total_notifications = 0
        total_automations = 0
        temperatures: List[float] = []
        humidities: List[float] = []

        for row in rows:
            alert_triggered = bool(row[12])
            notification_sent = bool(row[13])
            automation_triggered = bool(row[14])
            temp = row[5]
            humidity = row[6]

            if alert_triggered:
                total_alerts += 1
            if notification_sent:
                total_notifications += 1
            if automation_triggered:
                total_automations += 1
            if temp is not None:
                temperatures.append(temp)
            if humidity is not None:
                humidities.append(humidity)

            entries.append(
                WeatherObservationEntryV1(
                    entry_id=row[0],
                    zone_id=row[1],
                    zone_name=row[2],
                    event_type=row[3],
                    source=row[4],
                    temperature_celsius=temp,
                    humidity_percent=humidity,
                    wind_speed_kmh=row[7],
                    precipitation_mm=row[8],
                    pressure_hpa=row[9],
                    uv_index=row[10],
                    air_quality_index=row[11],
                    alert_triggered=alert_triggered,
                    notification_sent=notification_sent,
                    automation_triggered=automation_triggered,
                    observed_at=row[15],
                )
            )

        avg_temp = sum(temperatures) / len(temperatures) if temperatures else None
        avg_humidity = sum(humidities) / len(humidities) if humidities else None

        return WeatherObservationHistoryV1(
            entries=entries,
            total_observations=len(entries),
            total_alerts=total_alerts,
            total_notifications=total_notifications,
            total_automations=total_automations,
            avg_temperature_celsius=avg_temp,
            avg_humidity_percent=avg_humidity,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_zone_patterns(
        self,
        zone_ids: Optional[List[str]] = None,
    ) -> WeatherZonePatternsV1:
        """Zone-spezifische Weather-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        twentyfour_hours_ago = (now - timedelta(hours=24)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # Alle Zonen mit Weather-Observations laden
        query = """
            SELECT DISTINCT zone_id, zone_name FROM weather_observation_history
        """
        if zone_ids:
            placeholders = ",".join("?" * len(zone_ids))
            query += f" WHERE zone_id IN ({placeholders})"
            cursor.execute(query, zone_ids)
        else:
            cursor.execute(query)

        zone_rows = cursor.fetchall()

        patterns: List[WeatherZonePatternEntryV1] = []
        zones_with_data = 0

        for zone_id, zone_name in zone_rows:
            # Total observations
            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ?",
                (zone_id,)
            )
            total_observations = cursor.fetchone()[0]

            if total_observations == 0:
                continue

            zones_with_data += 1

            # Temperature events
            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ? AND event_type = 'temperature_change'",
                (zone_id,)
            )
            temperature_events = cursor.fetchone()[0]

            # Precipitation events
            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ? AND event_type = 'precipitation'",
                (zone_id,)
            )
            precipitation_events = cursor.fetchone()[0]

            # Wind events
            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ? AND event_type IN ('wind_alert', 'storm_warning')",
                (zone_id,)
            )
            wind_events = cursor.fetchone()[0]

            # Alert events (all alert types)
            cursor.execute(
                """
                SELECT COUNT(*) FROM weather_observation_history 
                WHERE zone_id = ? AND alert_triggered = 1
                """,
                (zone_id,)
            )
            alert_events = cursor.fetchone()[0]

            # Avg/min/max temperature
            cursor.execute(
                "SELECT AVG(temperature_celsius), MIN(temperature_celsius), MAX(temperature_celsius) FROM weather_observation_history WHERE zone_id = ? AND temperature_celsius IS NOT NULL",
                (zone_id,)
            )
            temp_stats = cursor.fetchone()
            avg_temp = temp_stats[0]
            min_temp = temp_stats[1]
            max_temp = temp_stats[2]

            # Avg humidity
            cursor.execute(
                "SELECT AVG(humidity_percent) FROM weather_observation_history WHERE zone_id = ? AND humidity_percent IS NOT NULL",
                (zone_id,)
            )
            avg_humidity = cursor.fetchone()[0]

            # Avg wind speed
            cursor.execute(
                "SELECT AVG(wind_speed_kmh) FROM weather_observation_history WHERE zone_id = ? AND wind_speed_kmh IS NOT NULL",
                (zone_id,)
            )
            avg_wind = cursor.fetchone()[0]

            # Total precipitation
            cursor.execute(
                "SELECT SUM(precipitation_mm) FROM weather_observation_history WHERE zone_id = ? AND precipitation_mm IS NOT NULL",
                (zone_id,)
            )
            total_precip = cursor.fetchone()[0]

            # Observations last 24 hours / 7 days
            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ? AND observed_at >= ?",
                (zone_id, twentyfour_hours_ago)
            )
            obs_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM weather_observation_history WHERE zone_id = ? AND observed_at >= ?",
                (zone_id, seven_days_ago)
            )
            obs_7d = cursor.fetchone()[0]

            # Most common event type
            cursor.execute(
                """
                SELECT event_type, COUNT(*) as cnt 
                FROM weather_observation_history 
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
                FROM weather_observation_history 
                WHERE zone_id = ? 
                GROUP BY source 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (zone_id,)
            )
            most_common_source = cursor.fetchone()
            most_common_source_val = most_common_source[0] if most_common_source else None

            # Peak alert hour
            cursor.execute(
                """
                SELECT strftime('%H', observed_at) as hour, COUNT(*) as cnt
                FROM weather_observation_history
                WHERE zone_id = ? AND alert_triggered = 1
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (zone_id,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            patterns.append(
                WeatherZonePatternEntryV1(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    total_observations=total_observations,
                    temperature_events=temperature_events,
                    precipitation_events=precipitation_events,
                    wind_events=wind_events,
                    alert_events=alert_events,
                    avg_temperature_celsius=avg_temp,
                    min_temperature_celsius=min_temp,
                    max_temperature_celsius=max_temp,
                    avg_humidity_percent=avg_humidity,
                    avg_wind_speed_kmh=avg_wind,
                    total_precipitation_mm=total_precip,
                    observations_last_24_hours=obs_24h,
                    observations_last_7_days=obs_7d,
                    most_common_event_type=most_common_event_type,
                    most_common_source=most_common_source_val,
                    peak_alert_hour=peak_hour,
                )
            )

        conn.close()

        total_zones = len(zone_rows)

        return WeatherZonePatternsV1(
            patterns=patterns,
            total_zones=total_zones,
            zones_with_weather_data=zones_with_data,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> WeatherEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total observations analyzed
        cursor.execute("SELECT COUNT(*) FROM weather_observation_history")
        total_observations = cursor.fetchone()[0]

        # Observations by type
        cursor.execute(
            """
            SELECT event_type, COUNT(*) as cnt 
            FROM weather_observation_history 
            GROUP BY event_type
            """
        )
        observations_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Observations by source
        cursor.execute(
            """
            SELECT source, COUNT(*) as cnt 
            FROM weather_observation_history 
            GROUP BY source
            """
        )
        observations_by_source = {row[0]: row[1] for row in cursor.fetchall()}

        # Alert accuracy rate (placeholder - would need user feedback)
        alert_accuracy_rate = None

        # Notification delivery rate
        cursor.execute("SELECT COUNT(*) FROM weather_observation_history WHERE notification_sent = 1")
        notifications_sent = cursor.fetchone()[0]
        notification_delivery_rate = notifications_sent / total_observations if total_observations > 0 else 0.0

        # Automation trigger rate
        cursor.execute("SELECT COUNT(*) FROM weather_observation_history WHERE automation_triggered = 1")
        automations_triggered = cursor.fetchone()[0]
        automation_trigger_rate = automations_triggered / total_observations if total_observations > 0 else 0.0

        # Zones with regular vs rare data (regular = >20 observations, rare = <=20)
        cursor.execute(
            """
            SELECT zone_id, COUNT(*) as cnt 
            FROM weather_observation_history 
            GROUP BY zone_id
            """
        )
        zone_counts = cursor.fetchall()
        zones_regular = sum(1 for _, cnt in zone_counts if cnt > 20)
        zones_rare = sum(1 for _, cnt in zone_counts if cnt <= 20)

        # Avg observations per zone
        total_zones = len(zone_counts)
        avg_observations_per_zone = total_observations / total_zones if total_zones > 0 else 0.0

        # Peak weather time
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', observed_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', observed_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', observed_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                COUNT(*) as cnt
            FROM weather_observation_history
            GROUP BY time_of_day
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        peak_time_row = cursor.fetchone()
        peak_weather_time = peak_time_row[0] if peak_time_row else None

        # Forecast accuracy score (placeholder)
        forecast_accuracy_score = None

        # Engagement score (composite)
        engagement_score = min(
            1.0,
            (total_observations / 100) * 0.3
            + notification_delivery_rate * 0.2
            + automation_trigger_rate * 0.3
            + (zones_regular / max(1, zones_regular + zones_rare)) * 0.2,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE weather_effectiveness_metrics 
            SET total_observations_analyzed = ?,
                observations_by_type = ?,
                observations_by_source = ?,
                alert_accuracy_rate = ?,
                notification_delivery_rate = ?,
                automation_trigger_rate = ?,
                avg_observations_per_zone = ?,
                zones_with_regular_data = ?,
                zones_with_rare_data = ?,
                peak_weather_time = ?,
                forecast_accuracy_score = ?,
                engagement_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_observations,
                str(observations_by_type),
                str(observations_by_source),
                alert_accuracy_rate,
                notification_delivery_rate,
                automation_trigger_rate,
                avg_observations_per_zone,
                zones_regular,
                zones_rare,
                peak_weather_time,
                forecast_accuracy_score,
                engagement_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return WeatherEffectivenessMetricsV1(
            total_observations_analyzed=total_observations,
            observations_by_type=observations_by_type,
            observations_by_source=observations_by_source,
            alert_accuracy_rate=alert_accuracy_rate,
            notification_delivery_rate=notification_delivery_rate,
            automation_trigger_rate=automation_trigger_rate,
            avg_observations_per_zone=avg_observations_per_zone,
            zones_with_regular_data=zones_regular,
            zones_with_rare_data=zones_rare,
            peak_weather_time=peak_weather_time,
            forecast_accuracy_score=forecast_accuracy_score,
            engagement_score=engagement_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> WeatherAnalyticsSummaryV1:
        """Zusammenfassung aller Weather-Analytics."""
        usage = self.build_observation_history()
        patterns = self.build_zone_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return WeatherAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_weather_analytics_store: Optional[WeatherAnalyticsStore] = None


def get_weather_analytics_store() -> WeatherAnalyticsStore:
    """WeatherAnalyticsStore-Singleton holen."""
    global _weather_analytics_store
    if _weather_analytics_store is None:
        _weather_analytics_store = WeatherAnalyticsStore()
    return _weather_analytics_store
