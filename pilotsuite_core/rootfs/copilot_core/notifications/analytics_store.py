"""Notifications Analytics Store — Slice 52."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    NotificationAnalyticsSummaryV1,
    NotificationChannel,
    NotificationChannelPatternEntryV1,
    NotificationChannelPatternsV1,
    NotificationDeliveryEntryV1,
    NotificationDeliveryHistoryV1,
    NotificationEffectivenessMetricsV1,
    NotificationType,
)


class NotificationAnalyticsStore:
    """Store für Notification-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/notification_analytics.db"):
        self.db_path = db_path
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        self._init_db()

    def _init_db(self) -> None:
        """Datenbank-Schema initialisieren."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delivery history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_delivery_history (
                entry_id TEXT PRIMARY KEY,
                notification_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                zone_id TEXT,
                zone_name TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                sent_at TEXT,
                delivered_at TEXT,
                read_at TEXT,
                acknowledged_at TEXT,
                failed_reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Channel patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_channel_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT UNIQUE NOT NULL,
                total_notifications INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                delivered_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                read_count INTEGER NOT NULL DEFAULT 0,
                acknowledged_count INTEGER NOT NULL DEFAULT 0,
                avg_delivery_time_seconds REAL,
                failure_rate REAL NOT NULL DEFAULT 0.0,
                most_common_type TEXT,
                peak_delivery_hour INTEGER,
                notifications_last_24_hours INTEGER NOT NULL DEFAULT 0,
                notifications_last_7_days INTEGER NOT NULL DEFAULT 0,
                unique_recipients INTEGER NOT NULL DEFAULT 0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_notifications_analyzed INTEGER DEFAULT 0,
                notifications_by_type TEXT,
                notifications_by_channel TEXT,
                overall_delivery_rate REAL DEFAULT 0.0,
                overall_read_rate REAL DEFAULT 0.0,
                overall_ack_rate REAL DEFAULT 0.0,
                avg_delivery_time_by_channel TEXT,
                failure_rate_by_type TEXT,
                zones_with_notifications INTEGER DEFAULT 0,
                peak_notification_time TEXT,
                engagement_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO notification_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def add_delivery_entry(self, entry: NotificationDeliveryEntryV1) -> None:
        """Notification-Delivery-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO notification_delivery_history 
            (entry_id, notification_id, channel, notification_type, recipient_id,
             zone_id, zone_name, title, body, priority, status,
             sent_at, delivered_at, read_at, acknowledged_at, failed_reason, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.notification_id, entry.channel, entry.notification_type,
            entry.recipient_id, entry.zone_id, entry.zone_name, entry.title, entry.body,
            entry.priority, entry.status, entry.sent_at, entry.delivered_at,
            entry.read_at, entry.acknowledged_at, entry.failed_reason, entry.retry_count
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_delivery_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        channel: Optional[str] = None,
        notification_type: Optional[str] = None,
        zone_id: Optional[str] = None,
        limit: int = 100,
    ) -> NotificationDeliveryHistoryV1:
        """Notification-Delivery-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, notification_id, channel, notification_type, recipient_id,
                   zone_id, zone_name, title, body, priority, status,
                   sent_at, delivered_at, read_at, acknowledged_at, failed_reason, retry_count
            FROM notification_delivery_history
            WHERE created_at >= ? AND created_at <= ?
        """
        params = [query_start, query_end]

        if channel:
            query += " AND channel = ?"
            params.append(channel)

        if notification_type:
            query += " AND notification_type = ?"
            params.append(notification_type)

        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[NotificationDeliveryEntryV1] = []
        total_sent = 0
        total_delivered = 0
        total_failed = 0
        total_read = 0
        total_acknowledged = 0
        delivery_times: List[float] = []

        for row in rows:
            status = row[10]
            sent_at = row[11]
            delivered_at = row[12]

            if status in ("sent", "delivered", "read", "acknowledged"):
                total_sent += 1
            if status in ("delivered", "read", "acknowledged"):
                total_delivered += 1
            if status == "failed":
                total_failed += 1
            if status == "read":
                total_read += 1
            if status == "acknowledged":
                total_acknowledged += 1

            # Calculate delivery time if both sent and delivered timestamps exist
            if sent_at and delivered_at:
                try:
                    sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
                    delivered_dt = datetime.fromisoformat(delivered_at.replace("Z", "+00:00"))
                    delivery_time = (delivered_dt - sent_dt).total_seconds()
                    if delivery_time >= 0:
                        delivery_times.append(delivery_time)
                except (ValueError, TypeError):
                    pass

            entries.append(
                NotificationDeliveryEntryV1(
                    entry_id=row[0],
                    notification_id=row[1],
                    channel=row[2],
                    notification_type=row[3],
                    recipient_id=row[4],
                    zone_id=row[5],
                    zone_name=row[6],
                    title=row[7],
                    body=row[8],
                    priority=row[9],
                    status=status,
                    sent_at=sent_at,
                    delivered_at=delivered_at,
                    read_at=row[13],
                    acknowledged_at=row[14],
                    failed_reason=row[15],
                    retry_count=row[16],
                )
            )

        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else None

        return NotificationDeliveryHistoryV1(
            entries=entries,
            total_notifications=len(entries),
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_failed=total_failed,
            total_read=total_read,
            total_acknowledged=total_acknowledged,
            avg_delivery_time_seconds=avg_delivery_time,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_channel_patterns(
        self,
        channels: Optional[List[str]] = None,
    ) -> NotificationChannelPatternsV1:
        """Channel-spezifische Notification-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        twentyfour_hours_ago = (now - timedelta(hours=24)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # Alle Channels mit Notifications laden
        query = """
            SELECT DISTINCT channel FROM notification_delivery_history
        """
        if channels:
            placeholders = ",".join("?" * len(channels))
            query += f" WHERE channel IN ({placeholders})"
            cursor.execute(query, channels)
        else:
            cursor.execute(query)

        channel_rows = cursor.fetchall()

        patterns: List[NotificationChannelPatternEntryV1] = []
        channels_with_activity = 0

        for (channel,) in channel_rows:
            # Total notifications
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ?",
                (channel,)
            )
            total_notifications = cursor.fetchone()[0]

            if total_notifications == 0:
                continue

            channels_with_activity += 1

            # Sent count
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND status IN ('sent', 'delivered', 'read', 'acknowledged')",
                (channel,)
            )
            sent_count = cursor.fetchone()[0]

            # Delivered count
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND status IN ('delivered', 'read', 'acknowledged')",
                (channel,)
            )
            delivered_count = cursor.fetchone()[0]

            # Failed count
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND status = 'failed'",
                (channel,)
            )
            failed_count = cursor.fetchone()[0]

            # Read count
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND status = 'read'",
                (channel,)
            )
            read_count = cursor.fetchone()[0]

            # Acknowledged count
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND status = 'acknowledged'",
                (channel,)
            )
            acknowledged_count = cursor.fetchone()[0]

            # Avg delivery time
            cursor.execute(
                """
                SELECT AVG(
                    (julianday(delivered_at) - julianday(sent_at)) * 86400
                )
                FROM notification_delivery_history
                WHERE channel = ? AND sent_at IS NOT NULL AND delivered_at IS NOT NULL
                """,
                (channel,)
            )
            avg_delivery_time = cursor.fetchone()[0]

            # Failure rate
            failure_rate = failed_count / total_notifications if total_notifications > 0 else 0.0

            # Most common type
            cursor.execute(
                """
                SELECT notification_type, COUNT(*) as cnt 
                FROM notification_delivery_history 
                WHERE channel = ? 
                GROUP BY notification_type 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (channel,)
            )
            most_common_type_row = cursor.fetchone()
            most_common_type = most_common_type_row[0] if most_common_type_row else None

            # Peak delivery hour
            cursor.execute(
                """
                SELECT strftime('%H', delivered_at) as hour, COUNT(*) as cnt
                FROM notification_delivery_history
                WHERE channel = ? AND delivered_at IS NOT NULL
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (channel,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            # Notifications last 24 hours / 7 days
            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND created_at >= ?",
                (channel, twentyfour_hours_ago)
            )
            notifications_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM notification_delivery_history WHERE channel = ? AND created_at >= ?",
                (channel, seven_days_ago)
            )
            notifications_7d = cursor.fetchone()[0]

            # Unique recipients
            cursor.execute(
                "SELECT COUNT(DISTINCT recipient_id) FROM notification_delivery_history WHERE channel = ?",
                (channel,)
            )
            unique_recipients = cursor.fetchone()[0]

            patterns.append(
                NotificationChannelPatternEntryV1(
                    channel=channel,
                    total_notifications=total_notifications,
                    sent_count=sent_count,
                    delivered_count=delivered_count,
                    failed_count=failed_count,
                    read_count=read_count,
                    acknowledged_count=acknowledged_count,
                    avg_delivery_time_seconds=avg_delivery_time,
                    failure_rate=failure_rate,
                    most_common_type=most_common_type,
                    peak_delivery_hour=peak_hour,
                    notifications_last_24_hours=notifications_24h,
                    notifications_last_7_days=notifications_7d,
                    unique_recipients=unique_recipients,
                )
            )

        conn.close()

        total_channels = len(channel_rows)

        return NotificationChannelPatternsV1(
            patterns=patterns,
            total_channels=total_channels,
            channels_with_activity=channels_with_activity,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> NotificationEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total notifications analyzed
        cursor.execute("SELECT COUNT(*) FROM notification_delivery_history")
        total_notifications = cursor.fetchone()[0]

        # Notifications by type
        cursor.execute(
            """
            SELECT notification_type, COUNT(*) as cnt 
            FROM notification_delivery_history 
            GROUP BY notification_type
            """
        )
        notifications_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Notifications by channel
        cursor.execute(
            """
            SELECT channel, COUNT(*) as cnt 
            FROM notification_delivery_history 
            GROUP BY channel
            """
        )
        notifications_by_channel = {row[0]: row[1] for row in cursor.fetchall()}

        # Overall delivery rate
        cursor.execute(
            "SELECT COUNT(*) FROM notification_delivery_history WHERE status IN ('delivered', 'read', 'acknowledged')"
        )
        delivered_count = cursor.fetchone()[0]
        overall_delivery_rate = delivered_count / total_notifications if total_notifications > 0 else 0.0

        # Overall read rate
        cursor.execute(
            "SELECT COUNT(*) FROM notification_delivery_history WHERE status IN ('read', 'acknowledged')"
        )
        read_count = cursor.fetchone()[0]
        overall_read_rate = read_count / total_notifications if total_notifications > 0 else 0.0

        # Overall ack rate
        cursor.execute(
            "SELECT COUNT(*) FROM notification_delivery_history WHERE status = 'acknowledged'"
        )
        ack_count = cursor.fetchone()[0]
        overall_ack_rate = ack_count / total_notifications if total_notifications > 0 else 0.0

        # Avg delivery time by channel
        cursor.execute(
            """
            SELECT channel, AVG(
                (julianday(delivered_at) - julianday(sent_at)) * 86400
            )
            FROM notification_delivery_history
            WHERE sent_at IS NOT NULL AND delivered_at IS NOT NULL
            GROUP BY channel
            """
        )
        avg_delivery_time_by_channel = {
            row[0]: row[1] for row in cursor.fetchall() if row[1] is not None
        }

        # Failure rate by type
        cursor.execute(
            """
            SELECT notification_type, 
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as failure_rate
            FROM notification_delivery_history
            GROUP BY notification_type
            """
        )
        failure_rate_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Zones with notifications
        cursor.execute(
            "SELECT COUNT(DISTINCT zone_id) FROM notification_delivery_history WHERE zone_id IS NOT NULL"
        )
        zones_with_notifications = cursor.fetchone()[0]

        # Peak notification time
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', delivered_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', delivered_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', delivered_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                COUNT(*) as cnt
            FROM notification_delivery_history
            WHERE delivered_at IS NOT NULL
            GROUP BY time_of_day
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        peak_time_row = cursor.fetchone()
        peak_notification_time = peak_time_row[0] if peak_time_row else None

        # Engagement score (composite)
        engagement_score = min(
            1.0,
            overall_delivery_rate * 0.3
            + overall_read_rate * 0.3
            + overall_ack_rate * 0.2
            + (zones_with_notifications / max(1, zones_with_notifications + 1)) * 0.2,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE notification_effectiveness_metrics 
            SET total_notifications_analyzed = ?,
                notifications_by_type = ?,
                notifications_by_channel = ?,
                overall_delivery_rate = ?,
                overall_read_rate = ?,
                overall_ack_rate = ?,
                avg_delivery_time_by_channel = ?,
                failure_rate_by_type = ?,
                zones_with_notifications = ?,
                peak_notification_time = ?,
                engagement_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_notifications,
                str(notifications_by_type),
                str(notifications_by_channel),
                overall_delivery_rate,
                overall_read_rate,
                overall_ack_rate,
                str(avg_delivery_time_by_channel),
                str(failure_rate_by_type),
                zones_with_notifications,
                peak_notification_time,
                engagement_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return NotificationEffectivenessMetricsV1(
            total_notifications_analyzed=total_notifications,
            notifications_by_type=notifications_by_type,
            notifications_by_channel=notifications_by_channel,
            overall_delivery_rate=overall_delivery_rate,
            overall_read_rate=overall_read_rate,
            overall_ack_rate=overall_ack_rate,
            avg_delivery_time_by_channel=avg_delivery_time_by_channel,
            failure_rate_by_type=failure_rate_by_type,
            zones_with_notifications=zones_with_notifications,
            peak_notification_time=peak_notification_time,
            engagement_score=engagement_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> NotificationAnalyticsSummaryV1:
        """Zusammenfassung aller Notification-Analytics."""
        usage = self.build_delivery_history()
        patterns = self.build_channel_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return NotificationAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_notification_analytics_store: Optional[NotificationAnalyticsStore] = None


def get_notification_analytics_store() -> NotificationAnalyticsStore:
    """NotificationAnalyticsStore-Singleton holen."""
    global _notification_analytics_store
    if _notification_analytics_store is None:
        _notification_analytics_store = NotificationAnalyticsStore()
    return _notification_analytics_store
