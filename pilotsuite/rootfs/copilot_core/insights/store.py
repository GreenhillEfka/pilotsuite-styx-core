"""
Insight Store for PilotSuite Core.

Persistent storage for insights derived from analytics data.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..insights.contracts import (
    InsightV1,
    InsightSummaryV1,
    InsightDeltaV1,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    InsightSource,
)


class InsightStore:
    """
    SQLite-backed store for insights.
    
    Provides persistent storage with revision tracking for delta polling.
    """
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._revision = 0
        self._init_db()
        self._load_revision()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                insight_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                zone_id TEXT,
                module_id TEXT,
                metric_name TEXT,
                metric_value REAL,
                baseline_value REAL,
                confidence REAL NOT NULL DEFAULT 0.0,
                evidence TEXT NOT NULL DEFAULT '{}',
                related_insight_ids TEXT NOT NULL DEFAULT '[]',
                revision INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insight_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_category 
            ON insights(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_severity 
            ON insights(severity)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_status 
            ON insights(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_source 
            ON insights(source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_zone 
            ON insights(zone_id)
        """)
        
        conn.commit()
        conn.close()
    
    def _load_revision(self):
        """Load current revision from metadata."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value FROM insight_metadata WHERE key = 'revision'"
        )
        row = cursor.fetchone()
        
        if row:
            self._revision = int(row[0])
        else:
            self._revision = 0
            cursor.execute(
                "INSERT INTO insight_metadata (key, value) VALUES (?, ?)",
                ("revision", "0")
            )
            conn.commit()
        
        conn.close()
    
    def _bump_revision(self) -> int:
        """Increment and return new revision."""
        self._revision += 1
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE insight_metadata SET value = ? WHERE key = 'revision'",
            (str(self._revision),)
        )
        conn.commit()
        conn.close()
        return self._revision
    
    def add_insight(self, insight: InsightV1) -> InsightV1:
        """Add a new insight to the store."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc)
        insight.created_at = now
        insight.updated_at = now
        insight.revision = self._bump_revision()
        
        cursor.execute("""
            INSERT INTO insights (
                insight_id, category, severity, status, source,
                title, description, recommendation,
                created_at, updated_at,
                zone_id, module_id, metric_name,
                metric_value, baseline_value, confidence,
                evidence, related_insight_ids, revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insight.insight_id,
            insight.category.value,
            insight.severity.value,
            insight.status.value,
            insight.source.value,
            insight.title,
            insight.description,
            insight.recommendation,
            insight.created_at.isoformat(),
            insight.updated_at.isoformat(),
            insight.zone_id,
            insight.module_id,
            insight.metric_name,
            insight.metric_value,
            insight.baseline_value,
            insight.confidence,
            json.dumps(insight.evidence),
            json.dumps(insight.related_insight_ids),
            insight.revision,
        ))
        
        conn.commit()
        conn.close()
        
        return insight
    
    def get_insight(self, insight_id: str) -> Optional[InsightV1]:
        """Get a single insight by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM insights WHERE insight_id = ?",
            (insight_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_insight(row)
    
    def get_insights(
        self,
        category: Optional[InsightCategory] = None,
        severity: Optional[InsightSeverity] = None,
        status: Optional[InsightStatus] = None,
        source: Optional[InsightSource] = None,
        zone_id: Optional[str] = None,
        since_revision: Optional[int] = None,
        limit: int = 100,
    ) -> list:
        """Get insights with optional filters."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        query = "SELECT * FROM insights WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category.value)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity.value)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        if source:
            query += " AND source = ?"
            params.append(source.value)
        
        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)
        
        if since_revision is not None:
            query += " AND revision > ?"
            params.append(since_revision)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_insight(row) for row in rows]
    
    def update_insight_status(
        self,
        insight_id: str,
        status: InsightStatus,
    ) -> Optional[InsightV1]:
        """Update the status of an insight."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        new_revision = self._bump_revision()
        
        cursor.execute("""
            UPDATE insights
            SET status = ?, updated_at = ?, revision = ?
            WHERE insight_id = ?
        """, (status.value, now, new_revision, insight_id))
        
        conn.commit()
        conn.close()
        
        return self.get_insight(insight_id)
    
    def get_summary(
        self,
        since_revision: Optional[int] = None,
    ) -> InsightSummaryV1:
        """Get summary of insights with counts."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        where_clause = f"WHERE revision > {since_revision}" if since_revision is not None else ""
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause}")
        total = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT category, COUNT(*) FROM insights {where_clause} GROUP BY category")
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(f"SELECT severity, COUNT(*) FROM insights {where_clause} GROUP BY severity")
        by_severity = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(f"SELECT status, COUNT(*) FROM insights {where_clause} GROUP BY status")
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(f"SELECT source, COUNT(*) FROM insights {where_clause} GROUP BY source")
        by_source = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}status = 'new'")
        new_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}status = 'acknowledged'")
        acknowledged_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}status = 'in_progress'")
        in_progress_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}status = 'resolved'")
        resolved_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}status = 'dismissed'")
        dismissed_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}severity = 'critical'")
        critical_count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM insights {where_clause} {'AND ' if where_clause else 'WHERE '}severity = 'high'")
        high_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT value FROM insight_metadata WHERE key = 'revision'")
        latest_revision = int(cursor.fetchone()[0])
        
        cursor.execute(
            f"SELECT MAX(updated_at) FROM insights {where_clause}"
        )
        latest_change_row = cursor.fetchone()[0]
        latest_change_at = (
            datetime.fromisoformat(latest_change_row)
            if latest_change_row
            else datetime.now(timezone.utc)
        )
        
        conn.close()
        
        return InsightSummaryV1(
            total_insights=total,
            by_category=by_category,
            by_severity=by_severity,
            by_status=by_status,
            by_source=by_source,
            new_count=new_count,
            acknowledged_count=acknowledged_count,
            in_progress_count=in_progress_count,
            resolved_count=resolved_count,
            dismissed_count=dismissed_count,
            critical_count=critical_count,
            high_count=high_count,
            latest_revision=latest_revision,
            latest_change_at=latest_change_at,
        )
    
    def get_delta(self, since_revision: int) -> InsightDeltaV1:
        """Get delta information for polling."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value FROM insight_metadata WHERE key = 'revision'"
        )
        current_revision = int(cursor.fetchone()[0])
        
        has_changes = current_revision > since_revision
        
        if has_changes:
            cursor.execute("""
                SELECT insight_id, category, severity, status, source,
                       title, updated_at
                FROM insights
                WHERE revision > ?
                ORDER BY updated_at DESC
                LIMIT 50
            """, (since_revision,))
            
            changes = []
            for row in cursor.fetchall():
                changes.append({
                    "insight_id": row[0],
                    "category": row[1],
                    "severity": row[2],
                    "status": row[3],
                    "source": row[4],
                    "title": row[5],
                    "updated_at": row[6],
                })
        else:
            changes = []
        
        conn.close()
        
        return InsightDeltaV1(
            has_changes=has_changes,
            revision=current_revision,
            changes_since_revision=changes,
        )
    
    def _row_to_insight(self, row: tuple) -> InsightV1:
        """Convert database row to InsightV1."""
        return InsightV1(
            insight_id=row[0],
            category=InsightCategory(row[1]),
            severity=InsightSeverity(row[2]),
            status=InsightStatus(row[3]),
            source=InsightSource(row[4]),
            title=row[5],
            description=row[6],
            recommendation=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
            zone_id=row[10],
            module_id=row[11],
            metric_name=row[12],
            metric_value=row[13],
            baseline_value=row[14],
            confidence=row[15],
            evidence=json.loads(row[16]),
            related_insight_ids=json.loads(row[17]),
            revision=row[18],
        )
