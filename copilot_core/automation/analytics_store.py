"""Automation Analytics Store — Slice 54."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .analytics import (
    AutomationAnalyticsSummaryV1,
    AutomationEffectivenessMetricsV1,
    AutomationExecutionEntryV1,
    AutomationExecutionHistoryV1,
    AutomationRulePatternEntryV1,
    AutomationRulePatternsV1,
)


class AutomationAnalyticsStore:
    """Store für Automation-Analytics-Read-Models."""

    def __init__(self, db_path: str = "/data/automation_analytics.db"):
        self.db_path = db_path
        self._revision = 0
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        self._init_db()

    def _init_db(self) -> None:
        """Datenbank-Schema initialisieren."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Execution history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_execution_history (
                entry_id TEXT PRIMARY KEY,
                automation_id TEXT NOT NULL,
                automation_name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                status TEXT NOT NULL,
                zone_id TEXT,
                zone_name TEXT,
                module_id TEXT,
                module_name TEXT,
                triggered_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                error_message TEXT,
                actions_executed INTEGER NOT NULL DEFAULT 0,
                actions_failed INTEGER NOT NULL DEFAULT 0,
                entities_affected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Rule patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_rule_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                automation_id TEXT UNIQUE NOT NULL,
                automation_name TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                total_executions INTEGER NOT NULL DEFAULT 0,
                completed_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0.0,
                avg_duration_seconds REAL,
                avg_actions_executed REAL,
                avg_entities_affected REAL,
                failure_rate REAL NOT NULL DEFAULT 0.0,
                last_execution_at TEXT,
                executions_last_24_hours INTEGER NOT NULL DEFAULT 0,
                executions_last_7_days INTEGER NOT NULL DEFAULT 0,
                most_common_trigger TEXT,
                peak_execution_hour INTEGER,
                zones_affected TEXT,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automation_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_executions_analyzed INTEGER DEFAULT 0,
                executions_by_status TEXT,
                executions_by_trigger TEXT,
                overall_success_rate REAL DEFAULT 0.0,
                overall_failure_rate REAL DEFAULT 0.0,
                avg_duration_by_trigger TEXT,
                failure_rate_by_trigger TEXT,
                automations_with_regular_executions INTEGER DEFAULT 0,
                automations_with_rare_executions INTEGER DEFAULT 0,
                peak_automation_time TEXT,
                reliability_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO automation_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def _bump_revision(self) -> int:
        self._revision += 1
        self._latest_change_at = datetime.now(timezone.utc).isoformat()
        return self._revision

    def add_execution_entry(self, entry: AutomationExecutionEntryV1) -> None:
        """Automation-Execution-Eintrag hinzufügen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO automation_execution_history 
            (entry_id, automation_id, automation_name, trigger_type, status,
             zone_id, zone_name, module_id, module_name, triggered_at,
             started_at, completed_at, duration_seconds, error_message,
             actions_executed, actions_failed, entities_affected)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.automation_id, entry.automation_name,
            entry.trigger_type, entry.status, entry.zone_id, entry.zone_name,
            entry.module_id, entry.module_name, entry.triggered_at,
            entry.started_at, entry.completed_at, entry.duration_seconds,
            entry.error_message, entry.actions_executed, entry.actions_failed,
            entry.entities_affected
        ))

        conn.commit()
        conn.close()
        self._bump_revision()

    def build_execution_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        automation_id: Optional[str] = None,
        status: Optional[str] = None,
        trigger_type: Optional[str] = None,
        zone_id: Optional[str] = None,
        limit: int = 100,
    ) -> AutomationExecutionHistoryV1:
        """Automation-Execution-Historie mit optionalen Filtern aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        default_start = (now - timedelta(days=7)).isoformat()

        query_start = time_range_start or default_start
        query_end = time_range_end or now.isoformat()

        query = """
            SELECT entry_id, automation_id, automation_name, trigger_type, status,
                   zone_id, zone_name, module_id, module_name, triggered_at,
                   started_at, completed_at, duration_seconds, error_message,
                   actions_executed, actions_failed, entities_affected
            FROM automation_execution_history
            WHERE created_at >= ? AND created_at <= ?
        """
        params = [query_start, query_end]

        if automation_id:
            query += " AND automation_id = ?"
            params.append(automation_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if trigger_type:
            query += " AND trigger_type = ?"
            params.append(trigger_type)

        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        entries: List[AutomationExecutionEntryV1] = []
        total_completed = 0
        total_failed = 0
        total_skipped = 0
        total_blocked = 0
        durations: List[float] = []

        for row in rows:
            status = row[4]
            duration = row[12]

            if status == "completed":
                total_completed += 1
            elif status == "failed":
                total_failed += 1
            elif status == "skipped":
                total_skipped += 1
            elif status == "blocked":
                total_blocked += 1

            if duration is not None:
                durations.append(duration)

            entries.append(
                AutomationExecutionEntryV1(
                    entry_id=row[0],
                    automation_id=row[1],
                    automation_name=row[2],
                    trigger_type=row[3],
                    status=status,
                    zone_id=row[5],
                    zone_name=row[6],
                    module_id=row[7],
                    module_name=row[8],
                    triggered_at=row[9],
                    started_at=row[10],
                    completed_at=row[11],
                    duration_seconds=duration,
                    error_message=row[13],
                    actions_executed=row[14],
                    actions_failed=row[15],
                    entities_affected=row[16],
                )
            )

        avg_duration = sum(durations) / len(durations) if durations else None

        return AutomationExecutionHistoryV1(
            entries=entries,
            total_executions=len(entries),
            total_completed=total_completed,
            total_failed=total_failed,
            total_skipped=total_skipped,
            total_blocked=total_blocked,
            avg_duration_seconds=avg_duration,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
            time_range_start=query_start,
            time_range_end=query_end,
        )

    def build_rule_patterns(
        self,
        automation_ids: Optional[List[str]] = None,
    ) -> AutomationRulePatternsV1:
        """Rule-spezifische Automation-Patterns aufbauen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        twentyfour_hours_ago = (now - timedelta(hours=24)).isoformat()
        seven_days_ago = (now - timedelta(days=7)).isoformat()

        # Alle Automations laden
        query = """
            SELECT DISTINCT automation_id, automation_name, trigger_type 
            FROM automation_execution_history
        """
        if automation_ids:
            placeholders = ",".join("?" * len(automation_ids))
            query += f" WHERE automation_id IN ({placeholders})"
            cursor.execute(query, automation_ids)
        else:
            cursor.execute(query)

        automation_rows = cursor.fetchall()

        patterns: List[AutomationRulePatternEntryV1] = []
        automations_with_executions = 0

        for automation_id, automation_name, trigger_type in automation_rows:
            # Total executions
            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ?",
                (automation_id,)
            )
            total_executions = cursor.fetchone()[0]

            if total_executions == 0:
                continue

            automations_with_executions += 1

            # Completed count
            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ? AND status = 'completed'",
                (automation_id,)
            )
            completed_count = cursor.fetchone()[0]

            # Failed count
            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ? AND status = 'failed'",
                (automation_id,)
            )
            failed_count = cursor.fetchone()[0]

            # Skipped count
            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ? AND status = 'skipped'",
                (automation_id,)
            )
            skipped_count = cursor.fetchone()[0]

            # Success rate
            success_rate = completed_count / total_executions if total_executions > 0 else 0.0

            # Duration stats
            cursor.execute(
                "SELECT AVG(duration_seconds) FROM automation_execution_history WHERE automation_id = ? AND duration_seconds IS NOT NULL",
                (automation_id,)
            )
            avg_duration = cursor.fetchone()[0]

            # Actions executed avg
            cursor.execute(
                "SELECT AVG(actions_executed) FROM automation_execution_history WHERE automation_id = ?",
                (automation_id,)
            )
            avg_actions = cursor.fetchone()[0]

            # Entities affected avg
            cursor.execute(
                "SELECT AVG(entities_affected) FROM automation_execution_history WHERE automation_id = ?",
                (automation_id,)
            )
            avg_entities = cursor.fetchone()[0]

            # Failure rate
            failure_rate = failed_count / total_executions if total_executions > 0 else 0.0

            # Last execution
            cursor.execute(
                "SELECT MAX(triggered_at) FROM automation_execution_history WHERE automation_id = ?",
                (automation_id,)
            )
            last_execution = cursor.fetchone()[0]

            # Most common trigger
            cursor.execute(
                """
                SELECT trigger_type, COUNT(*) as cnt 
                FROM automation_execution_history 
                WHERE automation_id = ? 
                GROUP BY trigger_type 
                ORDER BY cnt DESC 
                LIMIT 1
                """,
                (automation_id,)
            )
            most_common_trigger_row = cursor.fetchone()
            most_common_trigger = most_common_trigger_row[0] if most_common_trigger_row else None

            # Peak execution hour
            cursor.execute(
                """
                SELECT strftime('%H', triggered_at) as hour, COUNT(*) as cnt
                FROM automation_execution_history
                WHERE automation_id = ? AND triggered_at IS NOT NULL
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 1
                """,
                (automation_id,)
            )
            peak_hour_row = cursor.fetchone()
            peak_hour = int(peak_hour_row[0]) if peak_hour_row and peak_hour_row[0] else None

            # Executions last 24 hours / 7 days
            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ? AND created_at >= ?",
                (automation_id, twentyfour_hours_ago)
            )
            executions_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM automation_execution_history WHERE automation_id = ? AND created_at >= ?",
                (automation_id, seven_days_ago)
            )
            executions_7d = cursor.fetchone()[0]

            # Zones affected
            cursor.execute(
                "SELECT DISTINCT zone_id FROM automation_execution_history WHERE automation_id = ? AND zone_id IS NOT NULL",
                (automation_id,)
            )
            zones_affected = [row[0] for row in cursor.fetchall()]

            patterns.append(
                AutomationRulePatternEntryV1(
                    automation_id=automation_id,
                    automation_name=automation_name,
                    trigger_type=trigger_type,
                    total_executions=total_executions,
                    completed_count=completed_count,
                    failed_count=failed_count,
                    skipped_count=skipped_count,
                    success_rate=success_rate,
                    avg_duration_seconds=avg_duration,
                    avg_actions_executed=avg_actions,
                    avg_entities_affected=avg_entities,
                    failure_rate=failure_rate,
                    last_execution_at=last_execution,
                    executions_last_24_hours=executions_24h,
                    executions_last_7_days=executions_7d,
                    most_common_trigger=most_common_trigger,
                    peak_execution_hour=peak_hour,
                    zones_affected=zones_affected,
                )
            )

        conn.close()

        total_automations = len(automation_rows)

        return AutomationRulePatternsV1(
            patterns=patterns,
            total_automations=total_automations,
            automations_with_executions=automations_with_executions,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def get_effectiveness_metrics(self) -> AutomationEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total executions analyzed
        cursor.execute("SELECT COUNT(*) FROM automation_execution_history")
        total_executions = cursor.fetchone()[0]

        # Executions by status
        cursor.execute(
            """
            SELECT status, COUNT(*) as cnt 
            FROM automation_execution_history 
            GROUP BY status
            """
        )
        executions_by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Executions by trigger type
        cursor.execute(
            """
            SELECT trigger_type, COUNT(*) as cnt 
            FROM automation_execution_history 
            GROUP BY trigger_type
            """
        )
        executions_by_trigger = {row[0]: row[1] for row in cursor.fetchall()}

        # Overall success/failure rates
        completed_count = executions_by_status.get("completed", 0)
        failed_count = executions_by_status.get("failed", 0)
        overall_success_rate = completed_count / total_executions if total_executions > 0 else 0.0
        overall_failure_rate = failed_count / total_executions if total_executions > 0 else 0.0

        # Avg duration by trigger type
        cursor.execute(
            """
            SELECT trigger_type, AVG(duration_seconds)
            FROM automation_execution_history
            WHERE duration_seconds IS NOT NULL
            GROUP BY trigger_type
            """
        )
        avg_duration_by_trigger = {
            row[0]: row[1] for row in cursor.fetchall() if row[1] is not None
        }

        # Failure rate by trigger type
        cursor.execute(
            """
            SELECT trigger_type, 
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as failure_rate
            FROM automation_execution_history
            GROUP BY trigger_type
            """
        )
        failure_rate_by_trigger = {row[0]: row[1] for row in cursor.fetchall()}

        # Automations with regular vs rare executions
        cursor.execute(
            """
            SELECT automation_id, COUNT(*) as cnt 
            FROM automation_execution_history 
            GROUP BY automation_id
            """
        )
        automation_counts = cursor.fetchall()
        automations_regular = sum(1 for _, cnt in automation_counts if cnt > 10)
        automations_rare = sum(1 for _, cnt in automation_counts if cnt <= 10)

        # Peak automation time
        cursor.execute(
            """
            SELECT 
                CASE 
                    WHEN strftime('%H', triggered_at) BETWEEN '06' AND '11' THEN 'morning'
                    WHEN strftime('%H', triggered_at) BETWEEN '12' AND '17' THEN 'day'
                    WHEN strftime('%H', triggered_at) BETWEEN '18' AND '22' THEN 'evening'
                    ELSE 'night'
                END as time_of_day,
                COUNT(*) as cnt
            FROM automation_execution_history
            WHERE triggered_at IS NOT NULL
            GROUP BY time_of_day
            ORDER BY cnt DESC
            LIMIT 1
            """
        )
        peak_time_row = cursor.fetchone()
        peak_automation_time = peak_time_row[0] if peak_time_row else None

        # Reliability score (composite)
        reliability_score = min(
            1.0,
            overall_success_rate * 0.5
            + (1.0 - overall_failure_rate) * 0.3
            + (automations_regular / max(1, automations_regular + automations_rare)) * 0.2,
        )

        # Update DB
        cursor.execute(
            """
            UPDATE automation_effectiveness_metrics 
            SET total_executions_analyzed = ?,
                executions_by_status = ?,
                executions_by_trigger = ?,
                overall_success_rate = ?,
                overall_failure_rate = ?,
                avg_duration_by_trigger = ?,
                failure_rate_by_trigger = ?,
                automations_with_regular_executions = ?,
                automations_with_rare_executions = ?,
                peak_automation_time = ?,
                reliability_score = ?,
                revision = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                total_executions,
                str(executions_by_status),
                str(executions_by_trigger),
                overall_success_rate,
                overall_failure_rate,
                str(avg_duration_by_trigger),
                str(failure_rate_by_trigger),
                automations_regular,
                automations_rare,
                peak_automation_time,
                reliability_score,
                self._revision,
                datetime.now(timezone.utc).isoformat(),
            )
        )
        conn.commit()
        conn.close()

        return AutomationEffectivenessMetricsV1(
            total_executions_analyzed=total_executions,
            executions_by_status=executions_by_status,
            executions_by_trigger=executions_by_trigger,
            overall_success_rate=overall_success_rate,
            overall_failure_rate=overall_failure_rate,
            avg_duration_by_trigger=avg_duration_by_trigger,
            failure_rate_by_trigger=failure_rate_by_trigger,
            automations_with_regular_executions=automations_regular,
            automations_with_rare_executions=automations_rare,
            peak_automation_time=peak_automation_time,
            reliability_score=reliability_score,
            revision=self._revision,
            latest_change_at=self._latest_change_at,
        )

    def build_summary(self) -> AutomationAnalyticsSummaryV1:
        """Zusammenfassung aller Automation-Analytics."""
        usage = self.build_execution_history()
        patterns = self.build_rule_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return AutomationAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=self._revision,
            latest_change_at=self._latest_change_at,
        )


# Singleton-Getter
_automation_analytics_store: Optional[AutomationAnalyticsStore] = None


def get_automation_analytics_store() -> AutomationAnalyticsStore:
    """AutomationAnalyticsStore-Singleton holen."""
    global _automation_analytics_store
    if _automation_analytics_store is None:
        _automation_analytics_store = AutomationAnalyticsStore()
    return _automation_analytics_store
