"""Calendar Notification Surface — Proactive Suggestions as Notifications.

Follows the same pattern as Action Closure and Proposal Lifecycle notifications:
- Revision tracking for delta polling
- Dispatch/Claim/Receipt/Settlement surfaces for workers
- Integration with notification delivery engine
"""

import sqlite3
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class CalendarNotificationType(str, Enum):
    """Calendar notification types."""
    BREAK_REMINDER = "break_reminder"
    MEETING_PREP = "meeting_prep"
    FOCUS_BLOCK = "focus_block"
    ALARM_ADJUSTMENT = "alarm_adjustment"
    LIGHTING_SCENE = "lighting_scene"
    STRESS_RELIEF = "stress_relief"
    LUNCH_REMINDER = "lunch_reminder"
    END_OF_DAY_WRAP = "end_of_day_wrap"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CalendarNotificationV1:
    """Calendar notification record."""
    notification_id: str
    suggestion_id: str
    notification_type: str
    priority: str
    title: str
    message: str
    zone_id: Optional[str]
    event_id: Optional[str]
    created_at: str
    expires_at: Optional[str]
    status: str  # pending, sent, delivered, read, acknowledged, dismissed
    revision: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarNotificationDigestV1:
    """Digest of calendar notifications for workers."""
    notifications: List[CalendarNotificationV1]
    total_count: int
    pending_count: int
    revision: int
    latest_change_at: str
    has_changes: bool = False


@dataclass
class CalendarNotificationDispatchCandidateV1:
    """Dispatch candidate for notification workers."""
    dispatch_id: str
    notification_id: str
    suggestion_id: str
    notification_type: str
    priority: str
    delivery_mode: str  # immediate, scheduled, digest
    zone_id: Optional[str]
    event_id: Optional[str]
    title: str
    message: str
    metadata: Dict[str, Any]
    created_at: str
    revision: int


@dataclass
class CalendarNotificationDispatchV1:
    """Dispatch bundle for workers."""
    candidates: List[CalendarNotificationDispatchCandidateV1]
    total_count: int
    revision: int
    cursor: str


@dataclass
class CalendarNotificationClaimV1:
    """Worker claim for a notification dispatch."""
    claim_id: str
    dispatch_id: str
    notification_id: str
    claimed_by: str
    claimed_at: str
    lease_seconds: int
    expires_at: str
    status: str  # active, released, settled
    settlement: Optional[Dict[str, Any]] = None


@dataclass
class CalendarNotificationClaimSummaryV1:
    """Summary of calendar notification claims."""
    claims: List[CalendarNotificationClaimV1]
    total_count: int
    active_count: int
    expired_count: int
    reassignable_count: int
    revision: int
    latest_change_at: str


@dataclass
class CalendarNotificationReceiptV1:
    """Delivery receipt for a notification."""
    receipt_id: str
    dispatch_id: str
    notification_id: str
    delivery_status: str  # sent, delivered, failed
    delivered_at: Optional[str]
    read_at: Optional[str]
    acknowledged_at: Optional[str]
    failure_reason: Optional[str]
    retry_count: int
    next_retry_at: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarNotificationReceiptSummaryV1:
    """Summary of calendar notification receipts."""
    receipts: List[CalendarNotificationReceiptV1]
    total_count: int
    delivered_count: int
    failed_count: int
    pending_count: int
    revision: int
    latest_change_at: str


class CalendarNotificationStore:
    """SQLite-backed store for calendar notifications."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "storage" / "calendar_notifications.db")
        self.db_path = db_path
        self._revision = 0
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    suggestion_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    zone_id TEXT,
                    event_id TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    revision INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS dispatch_claims (
                    claim_id TEXT PRIMARY KEY,
                    dispatch_id TEXT NOT NULL,
                    notification_id TEXT NOT NULL,
                    claimed_by TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    lease_seconds INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    settlement TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS delivery_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    dispatch_id TEXT NOT NULL,
                    notification_id TEXT NOT NULL,
                    delivery_status TEXT NOT NULL,
                    delivered_at TEXT,
                    read_at TEXT,
                    acknowledged_at TEXT,
                    failure_reason TEXT,
                    retry_count INTEGER DEFAULT 0,
                    next_retry_at TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE TABLE IF NOT EXISTS notification_revision (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
                CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);
                CREATE INDEX IF NOT EXISTS idx_notifications_priority ON notifications(priority);
                CREATE INDEX IF NOT EXISTS idx_claims_status ON dispatch_claims(status);
                CREATE INDEX IF NOT EXISTS idx_claims_expires ON dispatch_claims(expires_at);
                CREATE INDEX IF NOT EXISTS idx_receipts_status ON delivery_receipts(delivery_status);
                
                INSERT OR IGNORE INTO notification_revision (id, revision) VALUES (1, 0);
            """)
            conn.commit()
    
    def _increment_revision(self) -> int:
        """Increment and return new revision."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE notification_revision SET revision = revision + 1, updated_at = datetime('now') WHERE id = 1")
            conn.commit()
            cursor = conn.execute("SELECT revision FROM notification_revision WHERE id = 1")
            self._revision = cursor.fetchone()[0]
            return self._revision
    
    def _get_revision(self) -> int:
        """Get current revision."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT revision FROM notification_revision WHERE id = 1")
            return cursor.fetchone()[0]
    
    def create_notification(self, suggestion_id: str, notification_type: str, priority: str,
                           title: str, message: str, zone_id: Optional[str] = None,
                           event_id: Optional[str] = None, expires_at: Optional[str] = None,
                           metadata: Optional[Dict] = None) -> CalendarNotificationV1:
        """Create a new calendar notification."""
        notification_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        revision = self._increment_revision()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO notifications 
                (notification_id, suggestion_id, notification_type, priority, title, message, 
                 zone_id, event_id, created_at, expires_at, status, revision, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (
                notification_id, suggestion_id, notification_type, priority, title, message,
                zone_id, event_id, now, expires_at, revision, json.dumps(metadata or {}),
            ))
            conn.commit()
        
        return CalendarNotificationV1(
            notification_id=notification_id,
            suggestion_id=suggestion_id,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            zone_id=zone_id,
            event_id=event_id,
            created_at=now,
            expires_at=expires_at,
            status="pending",
            revision=revision,
            metadata=metadata or {},
        )
    
    def update_notification_status(self, notification_id: str, status: str) -> None:
        """Update notification status."""
        revision = self._increment_revision()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE notifications 
                SET status = ?, revision = ?, updated_at = datetime('now')
                WHERE notification_id = ?
            """, (status, revision, notification_id))
            conn.commit()
    
    def get_digest(self, since_revision: Optional[int] = None, 
                   status_filter: Optional[str] = None) -> CalendarNotificationDigestV1:
        """Get notification digest for workers."""
        current_revision = self._get_revision()
        has_changes = since_revision is not None and since_revision < current_revision
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM notifications WHERE 1=1"
            params = []
            
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            
            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)
            
            query += " ORDER BY created_at DESC LIMIT 100"
            
            cursor = conn.execute(query, params)
            notifications = []
            for row in cursor.fetchall():
                notifications.append(CalendarNotificationV1(
                    notification_id=row["notification_id"],
                    suggestion_id=row["suggestion_id"],
                    notification_type=row["notification_type"],
                    priority=row["priority"],
                    title=row["title"],
                    message=row["message"],
                    zone_id=row["zone_id"],
                    event_id=row["event_id"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    status=row["status"],
                    revision=row["revision"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                ))
        
        pending_count = sum(1 for n in notifications if n.status == "pending")
        
        return CalendarNotificationDigestV1(
            notifications=notifications,
            total_count=len(notifications),
            pending_count=pending_count,
            revision=current_revision,
            latest_change_at=datetime.now().isoformat(),
            has_changes=has_changes,
        )
    
    def create_dispatch_candidate(self, notification: CalendarNotificationV1, 
                                  delivery_mode: str = "immediate") -> CalendarNotificationDispatchCandidateV1:
        """Create a dispatch candidate from a notification."""
        dispatch_id = str(uuid.uuid4())
        
        return CalendarNotificationDispatchCandidateV1(
            dispatch_id=dispatch_id,
            notification_id=notification.notification_id,
            suggestion_id=notification.suggestion_id,
            notification_type=notification.notification_type,
            priority=notification.priority,
            delivery_mode=delivery_mode,
            zone_id=notification.zone_id,
            event_id=notification.event_id,
            title=notification.title,
            message=notification.message,
            metadata=notification.metadata,
            created_at=notification.created_at,
            revision=notification.revision,
        )
    
    def claim_dispatch(self, dispatch_id: str, notification_id: str, claimed_by: str, 
                       lease_seconds: int = 300) -> CalendarNotificationClaimV1:
        """Claim a dispatch for processing."""
        claim_id = str(uuid.uuid4())
        now = datetime.now()
        expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
        revision = self._increment_revision()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO dispatch_claims 
                (claim_id, dispatch_id, notification_id, claimed_by, claimed_at, lease_seconds, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (claim_id, dispatch_id, notification_id, claimed_by, now.isoformat(), lease_seconds, expires_at))
            conn.commit()
        
        return CalendarNotificationClaimV1(
            claim_id=claim_id,
            dispatch_id=dispatch_id,
            notification_id=notification_id,
            claimed_by=claimed_by,
            claimed_at=now.isoformat(),
            lease_seconds=lease_seconds,
            expires_at=expires_at,
            status="active",
        )
    
    def release_claim(self, claim_id: str) -> None:
        """Release a claim without settlement."""
        revision = self._increment_revision()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE dispatch_claims 
                SET status = 'released', updated_at = datetime('now')
                WHERE claim_id = ?
            """, (claim_id,))
            conn.execute("""
                UPDATE notification_revision SET revision = ?, updated_at = datetime('now') WHERE id = 1
            """, (revision,))
            conn.commit()
    
    def settle_claim(self, claim_id: str, settlement: Dict[str, Any]) -> None:
        """Settle a claim with result."""
        revision = self._increment_revision()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE dispatch_claims 
                SET status = 'settled', settlement = ?, updated_at = datetime('now')
                WHERE claim_id = ?
            """, (json.dumps(settlement), claim_id))
            conn.execute("""
                UPDATE notification_revision SET revision = ?, updated_at = datetime('now') WHERE id = 1
            """, (revision,))
            conn.commit()
    
    def get_claim_summary(self, since_revision: Optional[int] = None) -> CalendarNotificationClaimSummaryV1:
        """Get summary of all claims."""
        current_revision = self._get_revision()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM dispatch_claims ORDER BY claimed_at DESC LIMIT 100"
            cursor = conn.execute(query)
            
            claims = []
            active_count = 0
            expired_count = 0
            reassignable_count = 0
            now = datetime.now()
            
            for row in cursor.fetchall():
                claim = CalendarNotificationClaimV1(
                    claim_id=row["claim_id"],
                    dispatch_id=row["dispatch_id"],
                    notification_id=row["notification_id"],
                    claimed_by=row["claimed_by"],
                    claimed_at=row["claimed_at"],
                    lease_seconds=row["lease_seconds"],
                    expires_at=row["expires_at"],
                    status=row["status"],
                    settlement=json.loads(row["settlement"]) if row["settlement"] else None,
                )
                claims.append(claim)
                
                if claim.status == "active":
                    if datetime.fromisoformat(claim.expires_at) < now:
                        expired_count += 1
                        reassignable_count += 1
                    else:
                        active_count += 1
                elif claim.status == "released":
                    reassignable_count += 1
        
        return CalendarNotificationClaimSummaryV1(
            claims=claims,
            total_count=len(claims),
            active_count=active_count,
            expired_count=expired_count,
            reassignable_count=reassignable_count,
            revision=current_revision,
            latest_change_at=datetime.now().isoformat(),
        )
    
    def record_receipt(self, dispatch_id: str, notification_id: str, 
                       delivery_status: str, metadata: Optional[Dict] = None) -> CalendarNotificationReceiptV1:
        """Record a delivery receipt."""
        receipt_id = str(uuid.uuid4())
        now = datetime.now()
        revision = self._increment_revision()
        
        delivered_at = now.isoformat() if delivery_status == "delivered" else None
        next_retry_at = (now + timedelta(minutes=5)).isoformat() if delivery_status == "failed" else None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO delivery_receipts 
                (receipt_id, dispatch_id, notification_id, delivery_status, delivered_at, 
                 retry_count, next_retry_at, metadata)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """, (receipt_id, dispatch_id, notification_id, delivery_status, delivered_at, 
                  next_retry_at, json.dumps(metadata or {})))
            conn.execute("""
                UPDATE notification_revision SET revision = ?, updated_at = datetime('now') WHERE id = 1
            """, (revision,))
            conn.commit()
        
        return CalendarNotificationReceiptV1(
            receipt_id=receipt_id,
            dispatch_id=dispatch_id,
            notification_id=notification_id,
            delivery_status=delivery_status,
            delivered_at=delivered_at,
            read_at=None,
            acknowledged_at=None,
            failure_reason=None,
            retry_count=0,
            next_retry_at=next_retry_at,
            metadata=metadata or {},
        )
    
    def get_receipt_summary(self, since_revision: Optional[int] = None) -> CalendarNotificationReceiptSummaryV1:
        """Get summary of all receipts."""
        current_revision = self._get_revision()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM delivery_receipts ORDER BY created_at DESC LIMIT 100"
            cursor = conn.execute(query)
            
            receipts = []
            delivered_count = 0
            failed_count = 0
            pending_count = 0
            
            for row in cursor.fetchall():
                receipt = CalendarNotificationReceiptV1(
                    receipt_id=row["receipt_id"],
                    dispatch_id=row["dispatch_id"],
                    notification_id=row["notification_id"],
                    delivery_status=row["delivery_status"],
                    delivered_at=row["delivered_at"],
                    read_at=row["read_at"],
                    acknowledged_at=row["acknowledged_at"],
                    failure_reason=row["failure_reason"],
                    retry_count=row["retry_count"],
                    next_retry_at=row["next_retry_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
                receipts.append(receipt)
                
                if receipt.delivery_status == "delivered":
                    delivered_count += 1
                elif receipt.delivery_status == "failed":
                    failed_count += 1
                else:
                    pending_count += 1
        
        return CalendarNotificationReceiptSummaryV1(
            receipts=receipts,
            total_count=len(receipts),
            delivered_count=delivered_count,
            failed_count=failed_count,
            pending_count=pending_count,
            revision=current_revision,
            latest_change_at=datetime.now().isoformat(),
        )
