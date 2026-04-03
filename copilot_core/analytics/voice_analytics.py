"""Voice Analytics Surface — Voice-Command-Historie, Intent-spezifische Patterns und Voice-Effectiveness-Metriken."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class VoiceCommandStatus(str, Enum):
    """Voice-Command-Status."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class VoiceIntentType(str, Enum):
    """Voice-Intent-Typen."""

    LIGHT_CONTROL = "light_control"
    CLIMATE_CONTROL = "climate_control"
    SCENE_ACTIVATION = "scene_activation"
    PRESENCE_QUERY = "presence_query"
    STATUS_QUERY = "status_query"
    MEDIA_CONTROL = "media_control"
    SCHEDULE_QUERY = "schedule_query"
    PROPOSAL_ACCEPT = "proposal_accept"
    PROPOSAL_REJECT = "proposal_reject"
    GENERAL_COMMAND = "general_command"


@dataclass
class VoiceCommandEntryV1:
    """Einzelner Voice-Command-Eintrag."""

    command_id: str
    intent_type: str
    raw_command: str
    zone_id: str | None
    zone_name: str | None
    module_id: str | None
    module_name: str | None
    status: str
    confidence_score: float  # 0.0–1.0
    processing_time_ms: float
    execution_time: str
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 0


@dataclass
class VoiceCommandHistoryV1:
    """Historie der Voice-Commands."""

    entries: list[VoiceCommandEntryV1]
    total_count: int
    from_time: str | None = None
    to_time: str | None = None
    revision: int = 0


@dataclass
class VoiceIntentPatternEntryV1:
    """Pattern-Eintrag für einen Intent-Typ."""

    intent_type: str
    total_commands: int
    success_count: int
    partial_count: int
    failed_count: int
    rejected_count: int
    success_rate: float  # 0.0–1.0
    avg_confidence_score: float
    avg_processing_time_ms: float
    min_processing_time_ms: float
    max_processing_time_ms: float
    p95_processing_time_ms: float
    last_command_time: str
    last_status: str
    trend: str  # improving, stable, degrading
    zone_coverage: int  # Anzahl verschiedener Zonen


@dataclass
class VoiceIntentPatternsV1:
    """Aggregierte Patterns für alle Intent-Typen."""

    patterns: list[VoiceIntentPatternEntryV1]
    total_intents: int
    active_intents: int
    revision: int = 0


@dataclass
class VoiceEffectivenessMetricsV1:
    """Effectiveness-Metriken für Voice-System."""

    overall_success_rate: float  # 0.0–1.0
    total_commands_24h: int
    total_commands_7d: int
    avg_confidence_score: float
    avg_processing_time_ms: float
    intent_distribution: dict[str, int]
    zone_coverage_total: int
    rejection_rate: float
    timeout_rate: float
    revision: int = 0


@dataclass
class VoiceAnalyticsSummaryV1:
    """Zusammenfassung aller Voice-Analytics."""

    history_summary: dict[str, Any]
    patterns_summary: dict[str, Any]
    effectiveness_summary: dict[str, Any]
    revision: int = 0
    generated_at: str = ""


class VoiceAnalyticsStore:
    """SQLite-Speicher für Voice-Analytics-Daten."""

    _instance: "VoiceAnalyticsStore | None" = None

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            try:
                from ..config import get_config
                db_path = Path(get_config().data_dir) / "analytics" / "voice_analytics.db"
            except (ImportError, AttributeError):
                db_path = Path("/config/clawd/data") / "analytics" / "voice_analytics.db"

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
                CREATE TABLE IF NOT EXISTS voice_commands (
                    command_id TEXT PRIMARY KEY,
                    intent_type TEXT NOT NULL,
                    raw_command TEXT NOT NULL,
                    zone_id TEXT,
                    zone_name TEXT,
                    module_id TEXT,
                    module_name TEXT,
                    status TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    processing_time_ms REAL NOT NULL,
                    execution_time TEXT NOT NULL,
                    error_message TEXT,
                    metadata TEXT,
                    revision INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_voice_commands_intent
                    ON voice_commands(intent_type);

                CREATE INDEX IF NOT EXISTS idx_voice_commands_time
                    ON voice_commands(execution_time);

                CREATE INDEX IF NOT EXISTS idx_voice_commands_status
                    ON voice_commands(status);

                CREATE INDEX IF NOT EXISTS idx_voice_commands_zone
                    ON voice_commands(zone_id);

                CREATE TABLE IF NOT EXISTS voice_revisions (
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
                "SELECT MAX(revision) FROM voice_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            current = row[0] if row and row[0] else 0
            next_rev = current + 1

            conn.execute(
                "INSERT INTO voice_revisions (revision_type, revision, created_at) VALUES (?, ?, ?)",
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
                "SELECT MAX(revision) FROM voice_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
        finally:
            conn.close()

    def add_command_entry(self, entry: VoiceCommandEntryV1) -> int:
        """Voice-Command-Eintrag hinzufügen."""
        conn = self._get_connection()
        try:
            import json

            revision = self._get_next_revision("command")
            entry.revision = revision

            conn.execute(
                """
                INSERT OR REPLACE INTO voice_commands
                (command_id, intent_type, raw_command, zone_id, zone_name,
                 module_id, module_name, status, confidence_score, processing_time_ms,
                 execution_time, error_message, metadata, revision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.command_id,
                    entry.intent_type,
                    entry.raw_command,
                    entry.zone_id,
                    entry.zone_name,
                    entry.module_id,
                    entry.module_name,
                    entry.status,
                    entry.confidence_score,
                    entry.processing_time_ms,
                    entry.execution_time,
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
        intent_type: str | None = None,
        zone_id: str | None = None,
        status: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> VoiceCommandHistoryV1:
        """Historie der Voice-Commands aufbauen."""
        conn = self._get_connection()
        try:
            import json

            query = "SELECT * FROM voice_commands WHERE 1=1"
            params: list[Any] = []

            if intent_type:
                query += " AND intent_type = ?"
                params.append(intent_type)
            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if status:
                query += " AND status = ?"
                params.append(status)
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
                VoiceCommandEntryV1(
                    command_id=row["command_id"],
                    intent_type=row["intent_type"],
                    raw_command=row["raw_command"],
                    zone_id=row["zone_id"],
                    zone_name=row["zone_name"],
                    module_id=row["module_id"],
                    module_name=row["module_name"],
                    status=row["status"],
                    confidence_score=row["confidence_score"],
                    processing_time_ms=row["processing_time_ms"],
                    execution_time=row["execution_time"],
                    error_message=row["error_message"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    revision=row["revision"],
                )
                for row in rows
            ]

            # Total count berechnen
            count_params = params[:len(params) - 2]
            count_query = "SELECT COUNT(*) FROM voice_commands WHERE 1=1"
            if intent_type:
                count_query += " AND intent_type = ?"
            if zone_id:
                count_query += " AND zone_id = ?"
            if status:
                count_query += " AND status = ?"
            if from_time:
                count_query += " AND execution_time >= ?"
            if to_time:
                count_query += " AND execution_time <= ?"

            cursor = conn.execute(count_query, count_params)
            total = cursor.fetchone()[0]

            return VoiceCommandHistoryV1(
                entries=entries,
                total_count=total,
                from_time=from_time,
                to_time=to_time,
                revision=entries[0].revision if entries else 0,
            )
        finally:
            conn.close()

    def build_intent_patterns(
        self,
        time_range_days: int = 7,
    ) -> VoiceIntentPatternsV1:
        """Patterns für alle Intent-Typen aufbauen."""
        conn = self._get_connection()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            cursor = conn.execute(
                """
                SELECT
                    intent_type,
                    COUNT(*) as total_commands,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    AVG(confidence_score) as avg_confidence,
                    AVG(processing_time_ms) as avg_processing_time,
                    MIN(processing_time_ms) as min_processing_time,
                    MAX(processing_time_ms) as max_processing_time,
                    MAX(execution_time) as last_command_time,
                    (SELECT status FROM voice_commands h2
                     WHERE h2.intent_type = voice_commands.intent_type
                     ORDER BY execution_time DESC LIMIT 1) as last_status,
                    COUNT(DISTINCT zone_id) as zone_coverage
                FROM voice_commands
                WHERE execution_time >= ?
                GROUP BY intent_type
                ORDER BY intent_type
                """,
                (cutoff,)
            )
            rows = cursor.fetchall()

            patterns = []
            active_intents = 0

            for row in rows:
                total = row["total_commands"]
                success = row["success_count"] or 0
                partial = row["partial_count"] or 0
                failed = row["failed_count"] or 0

                success_rate = (success + partial * 0.5) / total if total > 0 else 0.0

                # P95 berechnen
                p95_cursor = conn.execute(
                    """
                    SELECT processing_time_ms FROM voice_commands
                    WHERE intent_type = ? AND execution_time >= ?
                    ORDER BY processing_time_ms DESC
                    LIMIT 1 OFFSET (SELECT COUNT(*) * 95 / 100 FROM voice_commands
                                    WHERE intent_type = ? AND execution_time >= ?)
                    """,
                    (row["intent_type"], cutoff, row["intent_type"], cutoff)
                )
                p95_row = p95_cursor.fetchone()
                p95 = p95_row[0] if p95_row else row["avg_processing_time"]

                # Trend bestimmen
                trend_cursor = conn.execute(
                    """
                    SELECT status FROM voice_commands
                    WHERE intent_type = ? AND execution_time >= ?
                    ORDER BY execution_time DESC
                    """,
                    (row["intent_type"], cutoff)
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
                    active_intents += 1

                pattern = VoiceIntentPatternEntryV1(
                    intent_type=row["intent_type"],
                    total_commands=total,
                    success_count=success,
                    partial_count=partial,
                    failed_count=failed,
                    rejected_count=row["rejected_count"] or 0,
                    success_rate=round(success_rate, 4),
                    avg_confidence_score=round(row["avg_confidence"] or 0, 4),
                    avg_processing_time_ms=round(row["avg_processing_time"] or 0, 2),
                    min_processing_time_ms=round(row["min_processing_time"] or 0, 2),
                    max_processing_time_ms=round(row["max_processing_time"] or 0, 2),
                    p95_processing_time_ms=round(p95, 2),
                    last_command_time=row["last_command_time"],
                    last_status=row["last_status"],
                    trend=trend,
                    zone_coverage=row["zone_coverage"] or 0,
                )
                patterns.append(pattern)

            return VoiceIntentPatternsV1(
                patterns=patterns,
                total_intents=len(patterns),
                active_intents=active_intents,
                revision=self._get_latest_revision("command"),
            )
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        time_range_days: int = 7,
    ) -> VoiceEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = self._get_connection()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            # Gesamte Commands und Status-Verteilung
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_commands,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeout_count,
                    AVG(confidence_score) as avg_confidence,
                    AVG(processing_time_ms) as avg_processing_time
                FROM voice_commands
                WHERE execution_time >= ?
                """,
                (cutoff,)
            )
            row = cursor.fetchone()

            total = row["total_commands"] or 0
            success = row["success_count"] or 0
            partial = row["partial_count"] or 0
            failed = row["failed_count"] or 0
            rejected = row["rejected_count"] or 0
            timeout = row["timeout_count"] or 0

            overall_success_rate = (success + partial * 0.5) / total if total > 0 else 0.0
            rejection_rate = rejected / total if total > 0 else 0.0
            timeout_rate = timeout / total if total > 0 else 0.0

            # Executions last 24h / 7d
            cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            exec_24h_cursor = conn.execute(
                "SELECT COUNT(*) FROM voice_commands WHERE execution_time >= ?",
                (cutoff_24h,)
            )
            exec_24h = exec_24h_cursor.fetchone()[0]

            exec_7d_cursor = conn.execute(
                "SELECT COUNT(*) FROM voice_commands WHERE execution_time >= ?",
                (cutoff,)
            )
            exec_7d = exec_7d_cursor.fetchone()[0]

            # Intent-Type-Verteilung
            intent_cursor = conn.execute(
                """
                SELECT intent_type, COUNT(*) as cnt FROM voice_commands
                WHERE execution_time >= ?
                GROUP BY intent_type
                """,
                (cutoff,)
            )
            intent_distribution: dict[str, int] = {}
            for intent_row in intent_cursor.fetchall():
                intent_distribution[intent_row[0]] = intent_row[1]

            # Zone Coverage
            zone_cursor = conn.execute(
                "SELECT COUNT(DISTINCT zone_id) FROM voice_commands WHERE execution_time >= ? AND zone_id IS NOT NULL",
                (cutoff,)
            )
            zone_coverage = zone_cursor.fetchone()[0] or 0

            return VoiceEffectivenessMetricsV1(
                overall_success_rate=round(overall_success_rate, 4),
                total_commands_24h=exec_24h,
                total_commands_7d=exec_7d,
                avg_confidence_score=round(row["avg_confidence"] or 0, 4),
                avg_processing_time_ms=round(row["avg_processing_time"] or 0, 2),
                intent_distribution=intent_distribution,
                zone_coverage_total=zone_coverage,
                rejection_rate=round(rejection_rate, 4),
                timeout_rate=round(timeout_rate, 4),
                revision=self._get_latest_revision("command"),
            )
        finally:
            conn.close()

    def build_summary(
        self,
        time_range_days: int = 7,
    ) -> VoiceAnalyticsSummaryV1:
        """Zusammenfassung aller Voice-Analytics aufbauen."""
        patterns = self.build_intent_patterns(time_range_days=time_range_days)
        effectiveness = self.get_effectiveness_metrics(time_range_days=time_range_days)

        return VoiceAnalyticsSummaryV1(
            history_summary={
                "total_commands": effectiveness.total_commands_7d,
                "time_range_days": time_range_days,
            },
            patterns_summary={
                "total_intents": patterns.total_intents,
                "active_intents": patterns.active_intents,
            },
            effectiveness_summary={
                "overall_success_rate": effectiveness.overall_success_rate,
                "avg_confidence_score": effectiveness.avg_confidence_score,
                "rejection_rate": effectiveness.rejection_rate,
                "zone_coverage": effectiveness.zone_coverage_total,
            },
            revision=patterns.revision,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# =============================================================================
# Global Store Instance
# =============================================================================

_store: VoiceAnalyticsStore | None = None


def get_voice_analytics_store(db_path: Path | None = None) -> VoiceAnalyticsStore:
    """Globalen VoiceAnalyticsStore holen oder erstellen."""
    global _store
    if _store is None:
        _store = VoiceAnalyticsStore(db_path=db_path)
    return _store
