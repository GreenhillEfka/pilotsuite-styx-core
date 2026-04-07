"""Scheduler Analytics Store — Slice 53."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    SchedulerAnalyticsSummaryV1,
    SchedulerEffectivenessMetricsV1,
    SchedulerJobExecutionEntryV1,
    SchedulerJobExecutionHistoryV1,
    SchedulerJobPatternEntryV1,
    SchedulerJobPatternsV1,
)


class SchedulerAnalyticsStore:
    """Store für Scheduler-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/scheduler_analytics.db"):
        self.db_path = db_path
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        self._init_db()

    def _init_db(self) -> None:
        """Datenbank-Schema initialisieren."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Job execution history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_job_execution_history (
                entry_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                job_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                triggered_by TEXT,
                zone_id TEXT,
                zone_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Job patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_job_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                job_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                total_executions INTEGER NOT NULL DEFAULT 0,
                completed_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0.0,
                avg_duration_seconds REAL,
                min_duration_seconds REAL,
                max_duration_seconds REAL,
                failure_rate REAL NOT NULL DEFAULT 0.0,
                last_execution_at TEXT,
                next_scheduled_at TEXT,
                executions_last_24_hours INTEGER NOT NULL DEFAULT 0,
                executions_last_7_days INTEGER NOT NULL DEFAULT 0,
                most_common_status TEXT,
                peak_execution_hour INTEGER,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_executions_analyzed INTEGER DEFAULT 0,
                executions_by_status TEXT,
                executions_by_type TEXT,
                overall_success_rate REAL DEFAULT 0.0,
                overall_failure_rate REAL DEFAULT 0.0,
                avg_duration_by_job_type TEXT,
                failure_rate_by_job_type TEXT,
                jobs_with_regular_executions INTEGER DEFAULT 0,
                jobs_with_rare_executions INTEGER DEFAULT 0,
                peak_execution_time TEXT,
                reliability_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO scheduler_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def add_execution_entry(self, entry: SchedulerJobExecutionEntryV1) -> None:
        """Scheduler-Job-Execution-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO scheduler_job_execution_history 
            (entry_id, job_id, job_name, job_type, status, scheduled_at,
             started_at, completed_at, duration_seconds, error_message,
             retry_count, triggered_by, zone_id, zone_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.job_id, entry.job_name, entry.job_type,
            entry.status, entry.scheduled_at, entry.started_at, entry.completed_at,
            entry.duration_seconds, entry.error_message, entry.retry_count,
            entry.triggered_by, entry.zone_id, entry.zone_name
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_execution_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> SchedulerJobExecutionHistoryV1:
        """Scheduler-Job-Execution-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, job_id, job_name, job_type, status, scheduled_at,
                   started_at, completed_at, duration_seconds, error_message,
                   retry_count, triggered_by, zone_id, zone_name
            FROM scheduler_job_execution_history
            WHERE created_at >= ? AND created_at <= ?
        """
        params = [query_start, query_end]

        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[SchedulerJobExecutionEntryV1] = []
        total_completed = 0
        total_failed = 0
        total_skipped = 0
        total_cancelled = 0
        durations: List[float] = []

        for row in rows:
            status = row[4]
            duration = row[8]

            if status == "completed":
                total_completed += 1
            elif status == "failed":
                total_failed += 1
            elif status == "skipped":
                total_skipped += 1
            elif status == "cancelled":
                total_cancelled += 1

            if duration is not None:
                durations.append(duration)

            entries.append(
                SchedulerJobExecutionEntryV1(
                    entry_id=row[0],
                    job_id=row[1],
                    job_name=row[2],
                    job_type=row[3],
                    status=status,
                    scheduled_at=row[5],
                    started_at=row[6],
                    completed_at=row[7],
                    duration_seconds=duration,
                    error_message=row[9],
                    retry_count=row[10],
                    triggered_by=row[11],
                    zone_id=row[12],
                    zone_name=row[13],
                )
            )

        avg_duration = sum(durations) / len(durations) if durations else None

        return SchedulerJobExecutionHistoryV1(
            entries=entries,
            total_executions=len(entries),
            total_completed=total_completed,
            total_failed=total_failed,
            total_skipped=total_skipped,
            total_cancelled=total_cancelled,
            avg_duration_seconds=avg_duration,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_job_patterns(
        self,
        job_ids: Optional[List[str]] = None,
    ) -> SchedulerJobPatternsV1:
        """Job-spezifische Scheduler-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        twentyfour_hours_ago = (now - timedelta(hours=24)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # Alle Jobs laden
        query = """
            SELECT DISTINCT job_id, job_name, job_type FROM scheduler_job_execution_history
        """
        if job_ids:
            placeholders = ",".join("?" * len(job_ids))
            query += f" WHERE job_id IN ({placeholders})"
            cursor.execute(query, job_ids)
        else:
            cursor.execute(query)

        job_rows = cursor.fetchall()

        patterns: List[SchedulerJobPatternEntryV1] = []
        jobs_with_executions = 0

        for job_id, job_name, job_type in job_rows:
            # Total executions
            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ?",
                (job_id,)
            )
            total_executions = cursor.fetchone()[0]

            if total_executions == 0:
                continue

            jobs_with_executions += 1

            # Completed count
            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ? AND status = 'completed'",
                (job_id,)
            )
            completed_count = cursor.fetchone()[0]

            # Failed count
            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ? AND status = 'failed'",
                (job_id,)
            )
            failed_count = cursor.fetchone()[0]

            # Skipped count
            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ? AND status = 'skipped'",
                (job_id,)
            )
            skipped_count = cursor.fetchone()[0]

            # Success rate
            success_rate = completed_count / total_executions if total_executions > 0 else 0.0

            # Duration stats
            cursor.execute(
                "SELECT AVG(duration_seconds), MIN(duration_seconds), MAX(duration_seconds) FROM scheduler_job_execution_history WHERE job_id = ? AND duration_seconds IS NOT NULL",
                (job_id,)
            )
            duration_row = cursor.fetchone()
            avg_duration = duration_row[0]
            min_duration = duration_row[1]
            max_duration = duration_row[2]

            # Failure rate
            failure_rate = failed_count / total_executions if total_executions > 0 else 0.0

            # Last execution
            cursor.execute(
                "SELECT MAX(completed_at) FROM scheduler_job_execution_history WHERE job_id = ?",
                (job_id,)
            )
            last_execution = cursor.fetchone()[0]

            # Most common status
            cursor.execute(
                """
                SELECT status, COUNT(*) as cnt 
                FROM scheduler_job_execution_history 
                WHERE job_id = ? 
                GROUP BY status 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (job_id,)
            )
            most_common_status_row = cursor.fetchone()
            most_common_status = most_common_status_row[0] if most_common_status_row else None

            # Peak execution hour
            cursor.execute(
                """
                SELECT strftime('%H', started_at) as hour, COUNT(*) as cnt
                FROM scheduler_job_execution_history
                WHERE job_id = ? AND started_at IS NOT NULL
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (job_id,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            # Executions last 24 hours / 7 days
            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ? AND created_at >= ?",
                (job_id, twentyfour_hours_ago)
            )
            executions_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM scheduler_job_execution_history WHERE job_id = ? AND created_at >= ?",
                (job_id, seven_days_ago)
            )
            executions_7d = cursor.fetchone()[0]

            patterns.append(
                SchedulerJobPatternEntryV1(
                    job_id=job_id,
                    job_name=job_name,
                    job_type=job_type,
                    total_executions=total_executions,
                    completed_count=completed_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    success_rate=success_rate,
                    avg_duration_seconds=avg_duration,
                    min_duration_seconds=min_duration,
                    max_duration_seconds=max_duration,
                    failure_rate=failure_rate,
                    last_execution_at=last_execution,
                    next_scheduled_at=None,  # Would need scheduler state
                    executions_last_24_hours=executions_24h,
                    executions_last_7_days=executions_7d,
                    most_common_status=most_common_status,
                    peak_execution_hour=peak_hour,
                )
            )

        conn.close()

        total_jobs = len(job_rows)

        return SchedulerJobPatternsV1(
            patterns=patterns,
            total_jobs=total_jobs,
            jobs_with_executions=jobs_with_executions,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> SchedulerEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total executions analyzed
        cursor.execute("SELECT COUNT(*) FROM scheduler_job_execution_history")
        total_executions = cursor.fetchone()[0]

        # Executions by status
        cursor.execute(
            """
            SELECT status, COUNT(*) as cnt 
            FROM scheduler_job_execution_history 
            GROUP BY status
            """
        )
        executions_by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Executions by type
        cursor.execute(
            """
            SELECT job_type, COUNT(*) as cnt 
            FROM scheduler_job_execution_history 
            GROUP BY job_type
            """
        )
        executions_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Overall success/failure rates
        completed_count = executions_by_status.get("completed", 0)
        failed_count = executions_by_status.get("failed", 0)
        overall_success_rate = completed_count / total_executions if total_executions > 0 else 0.0
        overall_failure_rate = failed_count / total_executions if total_executions > 0 else 0.0

        # Avg duration by job type
        cursor.execute(
            """
            SELECT job_type, AVG(duration_seconds)
            FROM scheduler_job_execution_history
            WHERE duration_seconds IS NOT NULL
            GROUP BY job_type
            """
        )
        avg_duration_by_job_type = {
            row[0]: row[1] for row in cursor.fetchall() if row[1] is not None
        }

        # Failure rate by job type
        cursor.execute(
            """
            SELECT job_type, 
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as failure_rate
            FROM scheduler_job_execution_history
            GROUP BY job_type
            """
        )
        failure_rate_by_job_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Jobs with regular vs rare executions
        cursor.execute(
            """
            SELECT job_id, COUNT(*) as cnt 
            FROM scheduler_job_execution_history 
            GROUP BY job_id
            """
        )
        job_counts = cursor.fetchall()
        jobs_regular = sum(1 for _, cnt in job_counts if cnt > 10)
        jobs_rare = sum(1 for _, cnt in job_counts if cnt <= 10)

        # Peak execution time
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', started_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', started_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', started_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                COUNT(*) as cnt
            FROM scheduler_job_execution_history
            WHERE started_at IS NOT NULL
            GROUP BY time_of_day
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        peak_time_row = cursor.fetchone()
        peak_execution_time = peak_time_row[0] if peak_time_row else None

        # Reliability score (composite)
        reliability_score = min(
            1.0,
            overall_success_rate * 0.5
            + (1.0 - overall_failure_rate) * 0.3
            + (jobs_regular / max(1, jobs_regular + jobs_rare)) * 0.2,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE scheduler_effectiveness_metrics 
            SET total_executions_analyzed = ?,
                executions_by_status = ?,
                executions_by_type = ?,
                overall_success_rate = ?,
                overall_failure_rate = ?,
                avg_duration_by_job_type = ?,
                failure_rate_by_job_type = ?,
                jobs_with_regular_executions = ?,
                jobs_with_rare_executions = ?,
                peak_execution_time = ?,
                reliability_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_executions,
                str(executions_by_status),
                str(executions_by_type),
                overall_success_rate,
                overall_failure_rate,
                str(avg_duration_by_job_type),
                str(failure_rate_by_job_type),
                jobs_regular,
                jobs_rare,
                peak_execution_time,
                reliability_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return SchedulerEffectivenessMetricsV1(
            total_executions_analyzed=total_executions,
            executions_by_status=executions_by_status,
            executions_by_type=executions_by_type,
            overall_success_rate=overall_success_rate,
            overall_failure_rate=overall_failure_rate,
            avg_duration_by_job_type=avg_duration_by_job_type,
            failure_rate_by_job_type=failure_rate_by_job_type,
            jobs_with_regular_executions=jobs_regular,
            jobs_with_rare_executions=jobs_rare,
            peak_execution_time=peak_execution_time,
            reliability_score=reliability_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> SchedulerAnalyticsSummaryV1:
        """Zusammenfassung aller Scheduler-Analytics."""
        usage = self.build_execution_history()
        patterns = self.build_job_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return SchedulerAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_scheduler_analytics_store: Optional[SchedulerAnalyticsStore] = None


def get_scheduler_analytics_store() -> SchedulerAnalyticsStore:
    """SchedulerAnalyticsStore-Singleton holen."""
    global _scheduler_analytics_store
    if _scheduler_analytics_store is None:
        _scheduler_analytics_store = SchedulerAnalyticsStore()
    return _scheduler_analytics_store
