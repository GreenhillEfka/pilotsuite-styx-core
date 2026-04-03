"""Audit Log Store — SQLite-backed persistent audit trail — Slice 69"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AuditLogDeltaV1,
    AuditLogEntryV1,
    AuditLogSummaryV1,
    AuditOutcome,
    AuditSeverity,
)


class AuditLogStore:
    """SQLite-backed audit log store with revision tracking."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._revision = 0
        self._init_db()
        self._load_revision()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        entry_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        event_at TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        zone_id TEXT,
                        module_id TEXT,
                        proposal_id TEXT,
                        action_closure_id TEXT,
                        notification_id TEXT,
                        user_id TEXT,
                        session_id TEXT,
                        subject TEXT NOT NULL,
                        details TEXT,
                        metadata TEXT,
                        revision INTEGER NOT NULL,
                        parent_entry_id TEXT,
                        correlation_id TEXT,
                        duration_ms REAL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
                    CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_log(outcome);
                    CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
                    CREATE INDEX IF NOT EXISTS idx_audit_zone ON audit_log(zone_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_module ON audit_log(module_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_proposal ON audit_log(proposal_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_closure ON audit_log(action_closure_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_log(correlation_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_event_at ON audit_log(event_at);
                    CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);

                    CREATE TABLE IF NOT EXISTS audit_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    def _load_revision(self) -> None:
        """Load current revision from metadata table."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT value FROM audit_metadata WHERE key = 'revision'"
                )
                row = cursor.fetchone()
                self._revision = int(row[0]) if row else 0
            finally:
                conn.close()

    def _increment_revision(self) -> int:
        """Increment and return new revision."""
        self._revision += 1
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO audit_metadata (key, value)
                    VALUES ('revision', ?)
                    """,
                    (str(self._revision),),
                )
                conn.commit()
            finally:
                conn.close()
        return self._revision

    def add_entry(self, entry: AuditLogEntryV1) -> AuditLogEntryV1:
        """Add an audit log entry."""
        entry.revision = self._increment_revision()
        entry.created_at = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        entry_id, event_type, event_at, outcome, severity,
                        zone_id, module_id, proposal_id, action_closure_id,
                        notification_id, user_id, session_id,
                        subject, details, metadata,
                        revision, parent_entry_id, correlation_id,
                        duration_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.event_type,
                        entry.event_at,
                        entry.outcome,
                        entry.severity,
                        entry.zone_id,
                        entry.module_id,
                        entry.proposal_id,
                        entry.action_closure_id,
                        entry.notification_id,
                        entry.user_id,
                        entry.session_id,
                        entry.subject,
                        json.dumps(entry.details),
                        json.dumps(entry.metadata),
                        entry.revision,
                        entry.parent_entry_id,
                        entry.correlation_id,
                        entry.duration_ms,
                        entry.created_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        return entry

    def get_entry(self, entry_id: str) -> Optional[AuditLogEntryV1]:
        """Get a single audit log entry by ID."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT * FROM audit_log WHERE entry_id = ?", (entry_id,)
                )
                row = cursor.fetchone()
                return self._row_to_entry(row) if row else None
            finally:
                conn.close()

    def get_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        zone_id: Optional[str] = None,
        module_id: Optional[str] = None,
        event_type: Optional[str] = None,
        outcome: Optional[str] = None,
        severity: Optional[str] = None,
        user_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        action_closure_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        order_by: str = "created_at",
        order: str = "DESC",
    ) -> List[AuditLogEntryV1]:
        """Query audit log entries with filters."""
        where_clauses = []
        params: List[Any] = []

        if zone_id:
            where_clauses.append("zone_id = ?")
            params.append(zone_id)
        if module_id:
            where_clauses.append("module_id = ?")
            params.append(module_id)
        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)
        if outcome:
            where_clauses.append("outcome = ?")
            params.append(outcome)
        if severity:
            where_clauses.append("severity = ?")
            params.append(severity)
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if proposal_id:
            where_clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if action_closure_id:
            where_clauses.append("action_closure_id = ?")
            params.append(action_closure_id)
        if correlation_id:
            where_clauses.append("correlation_id = ?")
            params.append(correlation_id)
        if since:
            where_clauses.append("event_at >= ?")
            params.append(since)
        if until:
            where_clauses.append("event_at <= ?")
            params.append(until)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        order_sql = f"{order_by} {order}"

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                query = f"""
                    SELECT * FROM audit_log
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """
                cursor = conn.execute(query, params + [limit, offset])
                return [self._row_to_entry(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_delta(
        self, since_revision: int, limit: int = 100
    ) -> AuditLogDeltaV1:
        """Get entries changed since a revision (for delta polling)."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    """
                    SELECT * FROM audit_log
                    WHERE revision > ?
                    ORDER BY revision ASC
                    LIMIT ?
                    """,
                    (since_revision, limit),
                )
                entries = [self._row_to_entry(row) for row in cursor.fetchall()]

                latest = None
                if entries:
                    latest = entries[-1].event_at

                return AuditLogDeltaV1(
                    revision=self._revision,
                    has_changes=len(entries) > 0,
                    new_entries=entries,
                    latest_entry_at=latest,
                )
            finally:
                conn.close()

    def get_summary(
        self,
        zone_id: Optional[str] = None,
        module_id: Optional[str] = None,
        event_type: Optional[str] = None,
        outcome: Optional[str] = None,
        severity: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        recent_limit: int = 10,
    ) -> AuditLogSummaryV1:
        """Get aggregated audit log summary."""
        where_clauses = []
        params: List[Any] = []

        if zone_id:
            where_clauses.append("zone_id = ?")
            params.append(zone_id)
        if module_id:
            where_clauses.append("module_id = ?")
            params.append(module_id)
        if event_type:
            where_clauses.append("event_type = ?")
            params.append(event_type)
        if outcome:
            where_clauses.append("outcome = ?")
            params.append(outcome)
        if severity:
            where_clauses.append("severity = ?")
            params.append(severity)
        if since:
            where_clauses.append("event_at >= ?")
            params.append(since)
        if until:
            where_clauses.append("event_at <= ?")
            params.append(until)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                # Total count
                cursor = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM audit_log WHERE {where_sql}", params
                )
                total = cursor.fetchone()["cnt"]

                # Counts by outcome
                outcome_counts: Dict[str, int] = {}
                cursor = conn.execute(
                    f"""
                    SELECT outcome, COUNT(*) as cnt FROM audit_log
                    WHERE {where_sql}
                    GROUP BY outcome
                    """,
                    params,
                )
                for row in cursor.fetchall():
                    outcome_counts[row["outcome"]] = row["cnt"]

                # Counts by severity
                severity_counts: Dict[str, int] = {}
                cursor = conn.execute(
                    f"""
                    SELECT severity, COUNT(*) as cnt FROM audit_log
                    WHERE {where_sql}
                    GROUP BY severity
                    """,
                    params,
                )
                for row in cursor.fetchall():
                    severity_counts[row["severity"]] = row["cnt"]

                # Counts by event type
                event_type_counts: Dict[str, int] = {}
                cursor = conn.execute(
                    f"""
                    SELECT event_type, COUNT(*) as cnt FROM audit_log
                    WHERE {where_sql}
                    GROUP BY event_type
                    ORDER BY cnt DESC
                    LIMIT 20
                    """,
                    params,
                )
                for row in cursor.fetchall():
                    event_type_counts[row["event_type"]] = row["cnt"]

                # Time range
                cursor = conn.execute(
                    f"""
                    SELECT MIN(event_at) as earliest, MAX(event_at) as latest
                    FROM audit_log WHERE {where_sql}
                    """,
                    params,
                )
                time_row = cursor.fetchone()
                earliest = time_row["earliest"] if time_row else None
                latest = time_row["latest"] if time_row else None

                # Recent entries
                recent_cursor = conn.execute(
                    f"""
                    SELECT * FROM audit_log
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    params + [recent_limit],
                )
                recent = [self._row_to_entry(row) for row in recent_cursor.fetchall()]

                return AuditLogSummaryV1(
                    total_entries=total,
                    revision=self._revision,
                    latest_entry_at=latest,
                    success_count=outcome_counts.get(AuditOutcome.SUCCESS.value, 0),
                    failure_count=outcome_counts.get(AuditOutcome.FAILURE.value, 0),
                    pending_count=outcome_counts.get(AuditOutcome.PENDING.value, 0),
                    cancelled_count=outcome_counts.get(
                        AuditOutcome.CANCELLED.value, 0
                    ),
                    skipped_count=outcome_counts.get(AuditOutcome.SKIPPED.value, 0),
                    debug_count=severity_counts.get(AuditSeverity.DEBUG.value, 0),
                    info_count=severity_counts.get(AuditSeverity.INFO.value, 0),
                    warning_count=severity_counts.get(AuditSeverity.WARNING.value, 0),
                    error_count=severity_counts.get(AuditSeverity.ERROR.value, 0),
                    critical_count=severity_counts.get(
                        AuditSeverity.CRITICAL.value, 0
                    ),
                    event_type_counts=event_type_counts,
                    recent_entries=recent,
                    earliest_entry_at=earliest,
                    zone_id=zone_id,
                    module_id=module_id,
                    event_type=event_type,
                    outcome=outcome,
                    severity=severity,
                    since=since,
                    until=until,
                )
            finally:
                conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> AuditLogEntryV1:
        """Convert database row to AuditLogEntryV1."""
        return AuditLogEntryV1(
            entry_id=row["entry_id"],
            event_type=row["event_type"],
            event_at=row["event_at"],
            outcome=row["outcome"],
            severity=row["severity"],
            zone_id=row["zone_id"],
            module_id=row["module_id"],
            proposal_id=row["proposal_id"],
            action_closure_id=row["action_closure_id"],
            notification_id=row["notification_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            subject=row["subject"],
            details=json.loads(row["details"]) if row["details"] else {},
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            revision=row["revision"],
            parent_entry_id=row["parent_entry_id"],
            correlation_id=row["correlation_id"],
            duration_ms=row["duration_ms"],
            created_at=row["created_at"],
        )

    def get_revision(self) -> int:
        """Get current store revision."""
        return self._revision

    def export_entries(
        self,
        export_id: str,
        format: str = "json",
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int]:
        """Export entries to file, return (path, count)."""
        filters = filters or {}
        entries = self.get_entries(
            limit=filters.get("limit", 10000),
            zone_id=filters.get("zone_id"),
            module_id=filters.get("module_id"),
            event_type=filters.get("event_type"),
            outcome=filters.get("outcome"),
            severity=filters.get("severity"),
            since=filters.get("since"),
            until=filters.get("until"),
        )

        export_dir = self.db_path.parent / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"{export_id}.{format}"

        if format == "json":
            with open(export_path, "w") as f:
                json.dump(
                    {
                        "export_id": export_id,
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                        "filters": filters,
                        "count": len(entries),
                        "entries": [
                            {
                                k: v
                                for k, v in entry.__dict__.items()
                                if not k.startswith("_")
                            }
                            for entry in entries
                        ],
                    },
                    f,
                    indent=2,
                )
        elif format == "ndjson":
            with open(export_path, "w") as f:
                for entry in entries:
                    f.write(
                        json.dumps(
                            {
                                k: v
                                for k, v in entry.__dict__.items()
                                if not k.startswith("_")
                            }
                        )
                        + "\n"
                    )
        elif format == "csv":
            import csv

            with open(export_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "entry_id",
                        "event_type",
                        "event_at",
                        "outcome",
                        "severity",
                        "zone_id",
                        "module_id",
                        "subject",
                        "duration_ms",
                        "created_at",
                    ]
                )
                for entry in entries:
                    writer.writerow(
                        [
                            entry.entry_id,
                            entry.event_type,
                            entry.event_at,
                            entry.outcome,
                            entry.severity,
                            entry.zone_id or "",
                            entry.module_id or "",
                            entry.subject,
                            entry.duration_ms or "",
                            entry.created_at,
                        ]
                    )

        return str(export_path), len(entries)
