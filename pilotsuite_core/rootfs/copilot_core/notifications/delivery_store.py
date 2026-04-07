"""
Notification Delivery Store — Slice 68.

SQLite-backed store for notification delivery tracking with revision support.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .delivery_contracts import (
    DeliveryAttemptV1,
    DeliveryDeltaV1,
    DeliveryMode,
    DeliveryStatus,
    DeliverySummaryV1,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationDeliveryV1,
    NotificationV1,
)


class NotificationDeliveryStore:
    """Store for notification delivery records."""
    
    def __init__(self, db_path: str = "/data/notification_delivery.db"):
        self.db_path = db_path
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                priority TEXT NOT NULL,
                channel TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                zone_id TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                data TEXT,
                action_url TEXT,
                action_data TEXT,
                idempotency_key TEXT,
                ttl_seconds INTEGER,
                created_at TEXT NOT NULL,
                scheduled_at TEXT,
                expires_at TEXT,
                revision INTEGER DEFAULT 1
            )
        """)
        
        # Deliveries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                delivery_id TEXT PRIMARY KEY,
                notification_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                delivery_mode TEXT NOT NULL,
                sent_at TEXT,
                delivered_at TEXT,
                read_at TEXT,
                acknowledged_at TEXT,
                failed_at TEXT,
                cancelled_at TEXT,
                rate_limited_at TEXT,
                quiet_hours_applied INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                next_retry_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revision INTEGER DEFAULT 1,
                FOREIGN KEY (notification_id) REFERENCES notifications(notification_id)
            )
        """)
        
        # Delivery attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_attempts (
                attempt_id TEXT PRIMARY KEY,
                delivery_id TEXT NOT NULL,
                notification_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                error_code TEXT,
                retry_count INTEGER DEFAULT 0,
                response_data TEXT,
                latency_ms INTEGER,
                FOREIGN KEY (delivery_id) REFERENCES deliveries(delivery_id)
            )
        """)
        
        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_user_id 
            ON deliveries(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_channel 
            ON deliveries(channel)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_status 
            ON deliveries(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_created_at 
            ON deliveries(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_notification_id 
            ON deliveries(notification_id)
        """)
        
        conn.commit()
        conn.close()
    
    def _increment_revision(self) -> int:
        """Increment and return new revision."""
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc)
        return self._revision
    
    def save_notification(self, notification: NotificationV1) -> None:
        """Save notification to store."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO notifications (
                notification_id, type, priority, channel, recipient_id, user_id, zone_id,
                title, body, data, action_url, action_data, idempotency_key,
                ttl_seconds, created_at, scheduled_at, expires_at, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            notification.notification_id,
            notification.type.value,
            notification.priority.value,
            notification.channel.value,
            notification.recipient_id,
            notification.user_id,
            notification.zone_id,
            notification.title,
            notification.body,
            str(notification.data) if notification.data else None,
            notification.action_url,
            str(notification.action_data) if notification.action_data else None,
            notification.idempotency_key,
            notification.ttl_seconds,
            notification.created_at.isoformat(),
            notification.scheduled_at.isoformat() if notification.scheduled_at else None,
            notification.expires_at.isoformat() if notification.expires_at else None,
            self._increment_revision(),
        ))
        
        conn.commit()
        conn.close()
    
    def save_delivery(self, delivery: NotificationDeliveryV1) -> None:
        """Save delivery record to store."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO deliveries (
                delivery_id, notification_id, user_id, channel, recipient_id,
                status, priority, delivery_mode, sent_at, delivered_at, read_at,
                acknowledged_at, failed_at, cancelled_at, rate_limited_at,
                quiet_hours_applied, retry_count, max_retries, next_retry_at,
                created_at, updated_at, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            delivery.delivery_id,
            delivery.notification_id,
            delivery.user_id,
            delivery.channel.value,
            delivery.recipient_id,
            delivery.status.value,
            delivery.priority.value,
            delivery.delivery_mode.value,
            delivery.sent_at.isoformat() if delivery.sent_at else None,
            delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            delivery.read_at.isoformat() if delivery.read_at else None,
            delivery.acknowledged_at.isoformat() if delivery.acknowledged_at else None,
            delivery.failed_at.isoformat() if delivery.failed_at else None,
            delivery.cancelled_at.isoformat() if delivery.cancelled_at else None,
            delivery.rate_limited_at.isoformat() if delivery.rate_limited_at else None,
            1 if delivery.quiet_hours_applied else 0,
            delivery.retry_count,
            delivery.max_retries,
            delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            delivery.created_at.isoformat(),
            delivery.updated_at.isoformat(),
            self._increment_revision(),
        ))
        
        # Save attempts
        for attempt in delivery.attempts:
            cursor.execute("""
                INSERT OR REPLACE INTO delivery_attempts (
                    attempt_id, delivery_id, notification_id, channel, status,
                    attempted_at, completed_at, error_message, error_code,
                    retry_count, response_data, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt.attempt_id,
                delivery.delivery_id,
                delivery.notification_id,
                attempt.channel.value,
                attempt.status.value,
                attempt.attempted_at.isoformat(),
                attempt.completed_at.isoformat() if attempt.completed_at else None,
                attempt.error_message,
                attempt.error_code,
                attempt.retry_count,
                str(attempt.response_data) if attempt.response_data else None,
                attempt.latency_ms,
            ))
        
        conn.commit()
        conn.close()
    
    def get_delivery(self, delivery_id: str) -> Optional[NotificationDeliveryV1]:
        """Get delivery by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM deliveries WHERE delivery_id = ?
        """, (delivery_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_delivery(row)
    
    def get_deliveries_by_user(self, user_id: str, limit: int = 100, 
                                offset: int = 0) -> List[NotificationDeliveryV1]:
        """Get deliveries for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM deliveries 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_delivery(row) for row in rows]
    
    def get_deliveries_by_status(self, status: DeliveryStatus, 
                                  limit: int = 100) -> List[NotificationDeliveryV1]:
        """Get deliveries by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM deliveries 
            WHERE status = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (status.value, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_delivery(row) for row in rows]
    
    def get_pending_deliveries(self, limit: int = 100) -> List[NotificationDeliveryV1]:
        """Get pending deliveries for processing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM deliveries 
            WHERE status IN ('pending', 'queued', 'retrying') 
            ORDER BY created_at ASC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_delivery(row) for row in rows]
    
    def _row_to_delivery(self, row: tuple) -> NotificationDeliveryV1:
        """Convert database row to NotificationDeliveryV1."""
        return NotificationDeliveryV1(
            delivery_id=row[0],
            notification_id=row[1],
            user_id=row[2],
            channel=NotificationChannel(row[3]),
            recipient_id=row[4],
            status=DeliveryStatus(row[5]),
            priority=NotificationPriority(row[6]),
            delivery_mode=DeliveryMode(row[7]),
            sent_at=datetime.fromisoformat(row[8]) if row[8] else None,
            delivered_at=datetime.fromisoformat(row[9]) if row[9] else None,
            read_at=datetime.fromisoformat(row[10]) if row[10] else None,
            acknowledged_at=datetime.fromisoformat(row[11]) if row[11] else None,
            failed_at=datetime.fromisoformat(row[12]) if row[12] else None,
            cancelled_at=datetime.fromisoformat(row[13]) if row[13] else None,
            rate_limited_at=datetime.fromisoformat(row[14]) if row[14] else None,
            quiet_hours_applied=bool(row[15]),
            retry_count=row[16],
            max_retries=row[17],
            next_retry_at=datetime.fromisoformat(row[18]) if row[18] else None,
            created_at=datetime.fromisoformat(row[19]),
            updated_at=datetime.fromisoformat(row[20]),
            revision=row[21],
        )
    
    def get_summary(self, since_revision: Optional[int] = None) -> DeliverySummaryV1:
        """Get delivery summary with optional delta support."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM deliveries")
        total_deliveries = cursor.fetchone()[0]
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM deliveries GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Count by channel
        cursor.execute("""
            SELECT channel, COUNT(*) FROM deliveries GROUP BY channel
        """)
        by_channel = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Count by priority
        cursor.execute("""
            SELECT priority, COUNT(*) FROM deliveries GROUP BY priority
        """)
        by_priority = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get notification types
        cursor.execute("""
            SELECT n.type, COUNT(*) 
            FROM deliveries d 
            JOIN notifications n ON d.notification_id = n.notification_id 
            GROUP BY n.type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average latency (from attempts)
        cursor.execute("""
            SELECT AVG(latency_ms) FROM delivery_attempts WHERE latency_ms IS NOT NULL
        """)
        avg_latency = cursor.fetchone()[0]
        
        conn.close()
        
        return DeliverySummaryV1(
            total_notifications=total_deliveries,
            total_deliveries=total_deliveries,
            by_status=by_status,
            by_channel=by_channel,
            by_type=by_type,
            by_priority=by_priority,
            pending_count=by_status.get('pending', 0),
            queued_count=by_status.get('queued', 0),
            rate_limited_count=by_status.get('rate_limited', 0),
            sent_count=by_status.get('sent', 0),
            delivered_count=by_status.get('delivered', 0),
            read_count=by_status.get('read', 0),
            acknowledged_count=by_status.get('acknowledged', 0),
            failed_count=by_status.get('failed', 0),
            cancelled_count=by_status.get('cancelled', 0),
            avg_delivery_latency_ms=avg_latency,
            latest_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )
    
    def get_delta(self, since_revision: int) -> DeliveryDeltaV1:
        """Get delta since revision."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM deliveries 
            WHERE revision > ? 
            ORDER BY updated_at DESC 
            LIMIT 100
        """, (since_revision,))
        
        rows = cursor.fetchall()
        conn.close()
        
        changes = []
        for row in rows:
            delivery = self._row_to_delivery(row)
            changes.append(delivery.to_dict())
        
        return DeliveryDeltaV1(
            has_changes=len(changes) > 0,
            revision=self._revision,
            changes_since_revision=changes,
        )
    
    def update_delivery_status(self, delivery_id: str, status: DeliveryStatus,
                                extra_fields: Optional[Dict[str, Any]] = None) -> bool:
        """Update delivery status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        fields = ["status = ?", "updated_at = ?", "revision = ?"]
        values = [status.value, now, self._increment_revision()]
        
        # Add extra fields
        if extra_fields:
            for key, value in extra_fields.items():
                fields.append(f"{key} = ?")
                if isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)
        
        values.append(delivery_id)
        
        cursor.execute(f"""
            UPDATE deliveries 
            SET {', '.join(fields)} 
            WHERE delivery_id = ?
        """, values)
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def mark_delivered(self, delivery_id: str) -> bool:
        """Mark delivery as delivered."""
        return self.update_delivery_status(
            delivery_id, 
            DeliveryStatus.DELIVERED,
            {"delivered_at": datetime.now(timezone.utc)}
        )
    
    def mark_read(self, delivery_id: str) -> bool:
        """Mark delivery as read."""
        return self.update_delivery_status(
            delivery_id,
            DeliveryStatus.READ,
            {"read_at": datetime.now(timezone.utc)}
        )
    
    def mark_acknowledged(self, delivery_id: str) -> bool:
        """Mark delivery as acknowledged."""
        return self.update_delivery_status(
            delivery_id,
            DeliveryStatus.ACKNOWLEDGED,
            {"acknowledged_at": datetime.now(timezone.utc)}
        )


# Global store instance
_delivery_store: Optional[NotificationDeliveryStore] = None


def get_notification_delivery_store(db_path: str = "/data/notification_delivery.db") -> NotificationDeliveryStore:
    """Get or create delivery store instance."""
    global _delivery_store
    if _delivery_store is None:
        _delivery_store = NotificationDeliveryStore(db_path)
    return _delivery_store
