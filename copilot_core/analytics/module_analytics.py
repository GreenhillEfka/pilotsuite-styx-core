"""Module Analytics Surface — Module-Execution-Historie, Module-spezifische Patterns und Module-Effectiveness-Metriken."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class ModuleExecutionStatus(str, Enum):
    """Module-Execution-Status."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class ModuleTriggerType(str, Enum):
    """Auslöser für Module-Execution."""

    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    MANUAL = "manual"
    PREDICTIVE = "predictive"
    HABITUS = "habitus"
    VOICE = "voice"
    API = "api"


@dataclass
class ModuleExecutionEntryV1:
    """Einzelner Module-Execution-Eintrag."""

    execution_id: str
    module_id: str
    module_name: str
    module_type: str
    zone_id: str | None
    zone_name: str | None
    status: str
    trigger_type: str
    execution_time: str
    duration_ms: float
    inputs_count: int
    outputs_count: int
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 0


@dataclass
class ModuleExecutionHistoryV1:
    """Historie der Module-Executions."""

    entries: list[ModuleExecutionEntryV1]
    total_count: int
    from_time: str | None = None
    to_time: str | None = None
    revision: int = 0


@dataclass
class ModulePatternEntryV1:
    """Pattern-Eintrag für ein Modul."""

    module_id: str
    module_name: str
    module_type: str
    total_executions: int
    success_count: int
    partial_count: int
    failed_count: int
    skipped_count: int
    success_rate: float  # 0.0–1.0
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    avg_inputs_count: float
    avg_outputs_count: float
    last_execution_time: str
    last_status: str
    trend: str  # improving, stable, degrading
    primary_trigger_type: str
    zone_coverage: int  # Anzahl verschiedener Zonen


@dataclass
class ModulePatternsV1:
    """Aggregierte Patterns für alle Module."""

    patterns: list[ModulePatternEntryV1]
    total_modules: int
    active_modules: int
    revision: int = 0


@dataclass
class ModuleEffectivenessMetricsV1:
    """Effectiveness-Metriken für Module-System."""

    overall_success_rate: float  # 0.0–1.0
    total_executions_24h: int
    total_executions_7d: int
    avg_duration_ms: float
    mtbf_hours: float  # Mean Time Between Failures
    mttr_minutes: float  # Mean Time To Recovery
    modules_by_status: dict[str, int]
    trigger_type_distribution: dict[str, int]
    zone_coverage_total: int
    revision: int = 0


@dataclass
class ModuleAnalyticsSummaryV1:
    """Zusammenfassung aller Module-Analytics."""

    history_summary: dict[str, Any]
    patterns_summary: dict[str, Any]
    effectiveness_summary: dict[str, Any]
    revision: int = 0
    generated_at: str = ""


class ModuleAnalyticsStore:
    """SQLite-Speicher für Module-Analytics-Daten."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            try:
                from ..config import get_config
                db_path = Path(get_config().data_dir) / "analytics" / "module_analytics.db"
            except (ImportError, AttributeError):
                db_path = Path("/config/clawd/data") / "analytics" / "module_analytics.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Datenbank-Tabellen initialisieren."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS module_executions (
                    execution_id TEXT PRIMARY KEY,
                    module_id TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    module_type TEXT NOT NULL,
                    zone_id TEXT,
                    zone_name TEXT,
                    status TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    execution_time TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    inputs_count INTEGER NOT NULL DEFAULT 0,
                    outputs_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    metadata TEXT,
                    revision INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_module_executions_module
                    ON module_executions(module_id);

                CREATE INDEX IF NOT EXISTS idx_module_executions_time
                    ON module_executions(execution_time);

                CREATE INDEX IF NOT EXISTS idx_module_executions_status
                    ON module_executions(status);

                CREATE INDEX IF NOT EXISTS idx_module_executions_zone
                    ON module_executions(zone_id);

                CREATE TABLE IF NOT EXISTS module_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    revision_type TEXT NOT NULL,
                    revision INTEGER NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self, revision_type: str) -> int:
        """Nächste Revisionsnummer ermitteln."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT MAX(revision) FROM module_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            current = row[0] if row and row[0] else 0
            next_rev = current + 1

            conn.execute(
                "INSERT INTO module_revisions (revision_type, revision, created_at) VALUES (?, ?, ?)",
                (revision_type, next_rev, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            return next_rev
        finally:
            conn.close()

    def _get_latest_revision(self, revision_type: str) -> int:
        """Letzte Revisionsnummer für einen Typ holen."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT MAX(revision) FROM module_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
        finally:
            conn.close()

    def add_execution_entry(self, entry: ModuleExecutionEntryV1) -> int:
        """Module-Execution-Eintrag hinzufügen."""
        conn = self._get_connection()
        try:
            import json

            revision = self._get_next_revision("execution")
            entry.revision = revision

            conn.execute(
                """
                INSERT OR REPLACE INTO module_executions
                (execution_id, module_id, module_name, module_type, zone_id, zone_name,
                 status, trigger_type, execution_time, duration_ms, inputs_count, outputs_count,
                 error_message, metadata, revision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.execution_id,
                    entry.module_id,
                    entry.module_name,
                    entry.module_type,
                    entry.zone_id,
                    entry.zone_name,
                    entry.status,
                    entry.trigger_type,
                    entry.execution_time,
                    entry.duration_ms,
                    entry.inputs_count,
                    entry.outputs_count,
                    entry.error_message,
                    json.dumps(entry.metadata),
                    revision,
                )
            )
            conn.commit()
            return revision
        finally:
            conn.close()

    def build_history(
        self,
        module_id: str | None = None,
        zone_id: str | None = None,
        status: str | None = None,
        trigger_type: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ModuleExecutionHistoryV1:
        """Historie der Module-Executions aufbauen."""
        conn = self._get_connection()
        try:
            import json

            query = "SELECT * FROM module_executions WHERE 1=1"
            params: list[Any] = []

            if module_id:
                query += " AND module_id = ?"
                params.append(module_id)
            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            if trigger_type:
                query += " AND trigger_type = ?"
                params.append(trigger_type)
            if from_time:
                query += " AND execution_time >= ?"
                params.append(from_time)
            if to_time:
                query += " AND execution_time <= ?"
                params.append(to_time)

            query += " ORDER BY execution_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            entries = [
                ModuleExecutionEntryV1(
                    execution_id=row["execution_id"],
                    module_id=row["module_id"],
                    module_name=row["module_name"],
                    module_type=row["module_type"],
                    zone_id=row["zone_id"],
                    zone_name=row["zone_name"],
                    status=row["status"],
                    trigger_type=row["trigger_type"],
                    execution_time=row["execution_time"],
                    duration_ms=row["duration_ms"],
                    inputs_count=row["inputs_count"],
                    outputs_count=row["outputs_count"],
                    error_message=row["error_message"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    revision=row["revision"],
                )
                for row in rows
            ]

            # Total count berechnen
            count_query = "SELECT COUNT(*) FROM module_executions WHERE 1=1"
            count_params = params[:len(params) - 2]  # Remove limit and offset
            if module_id:
                count_query += " AND module_id = ?"
            if zone_id:
                count_query += " AND zone_id = ?"
            if status:
                count_query += " AND status = ?"
            if trigger_type:
                count_query += " AND trigger_type = ?"
            if from_time:
                count_query += " AND execution_time >= ?"
            if to_time:
                count_query += " AND execution_time <= ?"

            cursor = conn.execute(count_query, count_params)
            total = cursor.fetchone()[0]

            return ModuleExecutionHistoryV1(
                entries=entries,
                total_count=total,
                from_time=from_time,
                to_time=to_time,
                revision=entries[0].revision if entries else 0,
            )
        finally:
            conn.close()

    def build_module_patterns(
        self,
        time_range_days: int = 7,
    ) -> ModulePatternsV1:
        """Patterns für alle Module aufbauen."""
        conn = self._get_connection()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            cursor = conn.execute(
                """
                SELECT
                    module_id,
                    module_name,
                    module_type,
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_count,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration,
                    AVG(inputs_count) as avg_inputs,
                    AVG(outputs_count) as avg_outputs,
                    MAX(execution_time) as last_execution_time,
                    (SELECT status FROM module_executions h2
                     WHERE h2.module_id = module_executions.module_id
                     ORDER BY execution_time DESC LIMIT 1) as last_status,
                    (SELECT trigger_type FROM module_executions h3
                     WHERE h3.module_id = module_executions.module_id
                     GROUP BY trigger_type
                     ORDER BY COUNT(*) DESC LIMIT 1) as primary_trigger_type,
                    COUNT(DISTINCT zone_id) as zone_coverage
                FROM module_executions
                WHERE execution_time >= ?
                GROUP BY module_id, module_name, module_type
                ORDER BY module_name
                """,
                (cutoff,)
            )
            rows = cursor.fetchall()

            patterns = []
            active_modules = 0

            for row in rows:
                total = row["total_executions"]
                success = row["success_count"] or 0
                partial = row["partial_count"] or 0
                failed = row["failed_count"] or 0

                success_rate = (success + partial * 0.5) / total if total > 0 else 0.0

                # P95 berechnen
                p95_cursor = conn.execute(
                    """
                    SELECT duration_ms FROM module_executions
                    WHERE module_id = ? AND execution_time >= ?
                    ORDER BY duration_ms DESC
                    LIMIT 1 OFFSET (SELECT COUNT(*) * 95 / 100 FROM module_executions
                                    WHERE module_id = ? AND execution_time >= ?)
                    """,
                    (row["module_id"], cutoff, row["module_id"], cutoff)
                )
                p95_row = p95_cursor.fetchone()
                p95 = p95_row[0] if p95_row else row["avg_duration"]

                # Trend bestimmen
                trend_cursor = conn.execute(
                    """
                    SELECT status FROM module_executions
                    WHERE module_id = ? AND execution_time >= ?
                    ORDER BY execution_time DESC
                    """,
                    (row["module_id"], cutoff)
                )
                statuses = [r[0] for r in trend_cursor.fetchall()]
                if len(statuses) >= 10:
                    recent_success = statuses[:5].count("success") + statuses[:5].count("partial") * 0.5
                    older_success = statuses[5:10].count("success") + statuses[5:10].count("partial") * 0.5
                    if recent_success > older_success:
                        trend = "improving"
                    elif recent_success < older_success:
                        trend = "degrading"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"

                if row["last_status"] in ["success", "partial"]:
                    active_modules += 1

                pattern = ModulePatternEntryV1(
                    module_id=row["module_id"],
                    module_name=row["module_name"],
                    module_type=row["module_type"],
                    total_executions=total,
                    success_count=success,
                    partial_count=partial,
                    failed_count=failed,
                    skipped_count=row["skipped_count"] or 0,
                    success_rate=round(success_rate, 4),
                    avg_duration_ms=round(row["avg_duration"] or 0, 2),
                    min_duration_ms=round(row["min_duration"] or 0, 2),
                    max_duration_ms=round(row["max_duration"] or 0, 2),
                    p95_duration_ms=round(p95, 2),
                    avg_inputs_count=round(row["avg_inputs"] or 0, 2),
                    avg_outputs_count=round(row["avg_outputs"] or 0, 2),
                    last_execution_time=row["last_execution_time"],
                    last_status=row["last_status"],
                    trend=trend,
                    primary_trigger_type=row["primary_trigger_type"] or "unknown",
                    zone_coverage=row["zone_coverage"] or 0,
                )
                patterns.append(pattern)

            return ModulePatternsV1(
                patterns=patterns,
                total_modules=len(patterns),
                active_modules=active_modules,
                revision=self._get_latest_revision("execution"),
            )
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        time_range_days: int = 7,
    ) -> ModuleEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = self._get_connection()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            # Gesamte Executions und Status-Verteilung
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count
                FROM module_executions
                WHERE execution_time >= ?
                """,
                (cutoff,)
            )
            row = cursor.fetchone()

            total = row["total_executions"] or 0
            success = row["success_count"] or 0
            partial = row["partial_count"] or 0
            failed = row["failed_count"] or 0

            overall_success_rate = (success + partial * 0.5) / total if total > 0 else 0.0

            # Modules by Status (letzter Status pro Modul)
            mod_cursor = conn.execute(
                """
                SELECT module_id, status FROM module_executions h1
                WHERE execution_time = (
                    SELECT MAX(execution_time) FROM module_executions h2
                    WHERE h2.module_id = h1.module_id
                )
                """
            )
            modules_by_status: dict[str, int] = {"success": 0, "partial": 0, "failed": 0, "skipped": 0}
            for mod_row in mod_cursor.fetchall():
                status = mod_row[1]
                if status in modules_by_status:
                    modules_by_status[status] += 1

            # Executions last 24h / 7d
            cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            exec_24h_cursor = conn.execute(
                "SELECT COUNT(*) FROM module_executions WHERE execution_time >= ?",
                (cutoff_24h,)
            )
            exec_24h = exec_24h_cursor.fetchone()[0]

            exec_7d_cursor = conn.execute(
                "SELECT COUNT(*) FROM module_executions WHERE execution_time >= ?",
                (cutoff,)
            )
            exec_7d = exec_7d_cursor.fetchone()[0]

            # Trigger-Type-Verteilung
            trigger_cursor = conn.execute(
                """
                SELECT trigger_type, COUNT(*) as cnt FROM module_executions
                WHERE execution_time >= ?
                GROUP BY trigger_type
                """,
                (cutoff,)
            )
            trigger_distribution: dict[str, int] = {}
            for trigger_row in trigger_cursor.fetchall():
                trigger_distribution[trigger_row[0]] = trigger_row[1]

            # Zone Coverage
            zone_cursor = conn.execute(
                "SELECT COUNT(DISTINCT zone_id) FROM module_executions WHERE execution_time >= ? AND zone_id IS NOT NULL",
                (cutoff,)
            )
            zone_coverage = zone_cursor.fetchone()[0] or 0

            # Durchschnittliche Dauer
            duration_cursor = conn.execute(
                "SELECT AVG(duration_ms) FROM module_executions WHERE execution_time >= ?",
                (cutoff,)
            )
            avg_duration = duration_cursor.fetchone()[0] or 0.0

            # MTBF (Mean Time Between Failures)
            failures_cursor = conn.execute(
                """
                SELECT module_id, status, execution_time FROM module_executions
                WHERE execution_time >= ?
                ORDER BY module_id, execution_time
                """,
                (cutoff,)
            )
            failures = 0
            prev: dict[str, str] = {}
            for mod, status, _ in failures_cursor.fetchall():
                if prev.get(mod) == "failed" and status == "success":
                    failures += 1
                prev[mod] = status

            days = time_range_days
            mtbf_hours = (days * 24) / failures if failures > 0 else float(days * 24)

            # MTTR (vereinfacht)
            mttr_minutes = 5.0  # Default-Annahme

            return ModuleEffectivenessMetricsV1(
                overall_success_rate=round(overall_success_rate, 4),
                total_executions_24h=exec_24h,
                total_executions_7d=exec_7d,
                avg_duration_ms=round(avg_duration, 2),
                mtbf_hours=round(mtbf_hours, 2),
                mttr_minutes=round(mttr_minutes, 2),
                modules_by_status=modules_by_status,
                trigger_type_distribution=trigger_distribution,
                zone_coverage_total=zone_coverage,
                revision=self._get_latest_revision("execution"),
            )
        finally:
            conn.close()

    def build_summary(
        self,
        time_range_days: int = 7,
    ) -> ModuleAnalyticsSummaryV1:
        """Zusammenfassung aller Module-Analytics aufbauen."""
        patterns = self.build_module_patterns(time_range_days=time_range_days)
        effectiveness = self.get_effectiveness_metrics(time_range_days=time_range_days)

        return ModuleAnalyticsSummaryV1(
            history_summary={
                "total_executions": effectiveness.total_executions_7d,
                "time_range_days": time_range_days,
            },
            patterns_summary={
                "total_modules": patterns.total_modules,
                "active_modules": patterns.active_modules,
            },
            effectiveness_summary={
                "overall_success_rate": effectiveness.overall_success_rate,
                "mtbf_hours": effectiveness.mtbf_hours,
                "zone_coverage": effectiveness.zone_coverage_total,
            },
            revision=patterns.revision,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
