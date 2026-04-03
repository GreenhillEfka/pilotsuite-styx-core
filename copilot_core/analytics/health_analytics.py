"""System Health Analytics Surface — Health-Check-Historie, Component-Patterns, Effectiveness-Metriken."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def _get_data_dir() -> Path:
    """Data directory ermitteln."""
    try:
        from ..config import get_config
        return Path(get_config().data_dir)
    except (ImportError, AttributeError):
        # Fallback: Standard-Pfad
        return Path("/config/clawd/data")


class HealthCheckStatus(str, Enum):
    """Health-Check-Ergebnis-Status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthComponentType(str, Enum):
    """Typen von Health-Komponenten."""

    CORE = "core"
    DATABASE = "database"
    HA_CONNECTION = "ha_connection"
    OLLAMA = "ollama"
    SCHEDULER = "scheduler"
    NOTIFICATIONS = "notifications"
    INGEST = "ingest"
    MODULES = "modules"
    PRESENCE = "presence"
    ENERGY = "energy"
    WEATHER = "weather"
    CAMERA = "camera"
    MEDIA = "media"
    AUTOMATION = "automation"
    VOICE = "voice"
    CHAT = "chat"
    RAG = "rag"
    BRAIN = "brain"
    ZONES = "zones"
    PROPOSALS = "proposals"
    EXTERNAL = "external"


@dataclass
class HealthCheckEntryV1:
    """Einzelner Health-Check-Eintrag."""

    check_id: str
    component: str
    component_type: str
    status: str
    check_time: str
    response_time_ms: float
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    revision: int = 0


@dataclass
class HealthCheckHistoryV1:
    """Historie der Health-Checks."""

    entries: list[HealthCheckEntryV1]
    total_count: int
    from_time: str | None = None
    to_time: str | None = None
    revision: int = 0


@dataclass
class HealthComponentPatternEntryV1:
    """Pattern-Eintrag für eine Komponente."""

    component: str
    component_type: str
    total_checks: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    unknown_count: int
    health_rate: float  # 0.0–1.0
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    last_check_time: str
    last_status: str
    trend: str  # improving, stable, degrading
    flapping_score: float  # 0.0–1.0, wie stark der Status schwankt


@dataclass
class HealthComponentPatternsV1:
    """Aggregierte Patterns für alle Komponenten."""

    patterns: list[HealthComponentPatternEntryV1]
    total_components: int
    healthy_components: int
    degraded_components: int
    unhealthy_components: int
    revision: int = 0


@dataclass
class HealthEffectivenessMetricsV1:
    """Effectiveness-Metriken für System-Health."""

    overall_health_score: float  # 0.0–1.0
    system_uptime_rate: float  # 0.0–1.0
    avg_check_interval_seconds: float
    mtbf_hours: float  # Mean Time Between Failures
    mttr_minutes: float  # Mean Time To Recovery
    alert_accuracy_rate: float  # Wie viele Alerts waren berechtigt
    false_positive_rate: float
    components_by_health: dict[str, int]
    checks_last_24h: int
    checks_last_7d: int
    revision: int = 0


@dataclass
class HealthAnalyticsSummaryV1:
    """Zusammenfassung aller Health-Analytics."""

    history_summary: dict[str, Any]
    patterns_summary: dict[str, Any]
    effectiveness_summary: dict[str, Any]
    revision: int = 0
    generated_at: str = ""


class HealthAnalyticsStore:
    """SQLite-Speicher für Health-Analytics-Daten."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = _get_data_dir() / "analytics" / "health_analytics.db"

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
                CREATE TABLE IF NOT EXISTS health_checks (
                    check_id TEXT PRIMARY KEY,
                    component TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    check_time TEXT NOT NULL,
                    response_time_ms REAL NOT NULL,
                    message TEXT,
                    details TEXT,
                    revision INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_health_checks_component
                    ON health_checks(component);

                CREATE INDEX IF NOT EXISTS idx_health_checks_check_time
                    ON health_checks(check_time);

                CREATE INDEX IF NOT EXISTS idx_health_checks_status
                    ON health_checks(status);

                CREATE TABLE IF NOT EXISTS health_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    revision_type TEXT NOT NULL,
                    revision INTEGER NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS health_effectiveness (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL UNIQUE,
                    metric_value REAL NOT NULL,
                    details TEXT,
                    updated_at TEXT NOT NULL
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
                "SELECT MAX(revision) FROM health_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            current = row[0] if row and row[0] else 0
            next_rev = current + 1

            conn.execute(
                "INSERT INTO health_revisions (revision_type, revision, created_at) VALUES (?, ?, ?)",
                (revision_type, next_rev, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            return next_rev
        finally:
            conn.close()

    def add_check_entry(self, entry: HealthCheckEntryV1) -> int:
        """Health-Check-Eintrag hinzufügen."""
        conn = self._get_connection()
        try:
            import json

            revision = self._get_next_revision("check")
            entry.revision = revision

            conn.execute(
                """
                INSERT OR REPLACE INTO health_checks
                (check_id, component, component_type, status, check_time, response_time_ms, message, details, revision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.check_id,
                    entry.component,
                    entry.component_type,
                    entry.status,
                    entry.check_time,
                    entry.response_time_ms,
                    entry.message,
                    json.dumps(entry.details),
                    revision,
                )
            )
            conn.commit()
            return revision
        finally:
            conn.close()

    def build_history(
        self,
        component: str | None = None,
        status: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> HealthCheckHistoryV1:
        """Historie der Health-Checks aufbauen."""
        conn = self._get_connection()
        try:
            import json

            query = "SELECT * FROM health_checks WHERE 1=1"
            params: list[Any] = []

            if component:
                query += " AND component = ?"
                params.append(component)
            if status:
                query += " AND status = ?"
                params.append(status)
            if from_time:
                query += " AND check_time >= ?"
                params.append(from_time)
            if to_time:
                query += " AND check_time <= ?"
                params.append(to_time)

            query += " ORDER BY check_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            entries = [
                HealthCheckEntryV1(
                    check_id=row["check_id"],
                    component=row["component"],
                    component_type=row["component_type"],
                    status=row["status"],
                    check_time=row["check_time"],
                    response_time_ms=row["response_time_ms"],
                    message=row["message"],
                    details=json.loads(row["details"]) if row["details"] else {},
                    revision=row["revision"],
                )
                for row in rows
            ]

            count_cursor = conn.execute(
                "SELECT COUNT(*) FROM health_checks WHERE 1=1"
                + (" AND component = ?" if component else "")
                + (" AND status = ?" if status else "")
                + (" AND check_time >= ?" if from_time else "")
                + (" AND check_time <= ?" if to_time else ""),
                [p for p in params if p not in [limit, offset]][:4]
            )
            total = count_cursor.fetchone()[0]

            return HealthCheckHistoryV1(
                entries=entries,
                total_count=total,
                from_time=from_time,
                to_time=to_time,
                revision=entries[0].revision if entries else 0,
            )
        finally:
            conn.close()

    def build_component_patterns(
        self,
        time_range_days: int = 7,
    ) -> HealthComponentPatternsV1:
        """Patterns für alle Komponenten aufbauen."""
        conn = self._get_connection()
        try:
            import json
            from datetime import timedelta

            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            cursor = conn.execute(
                """
                SELECT
                    component,
                    component_type,
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                    SUM(CASE WHEN status = 'degraded' THEN 1 ELSE 0 END) as degraded_count,
                    SUM(CASE WHEN status = 'unhealthy' THEN 1 ELSE 0 END) as unhealthy_count,
                    SUM(CASE WHEN status = 'unknown' THEN 1 ELSE 0 END) as unknown_count,
                    AVG(response_time_ms) as avg_response_time,
                    MIN(response_time_ms) as min_response_time,
                    MAX(response_time_ms) as max_response_time,
                    MAX(check_time) as last_check_time,
                    (SELECT status FROM health_checks h2
                     WHERE h2.component = health_checks.component
                     ORDER BY check_time DESC LIMIT 1) as last_status
                FROM health_checks
                WHERE check_time >= ?
                GROUP BY component, component_type
                ORDER BY component
                """,
                (cutoff,)
            )
            rows = cursor.fetchall()

            patterns = []
            healthy_components = 0
            degraded_components = 0
            unhealthy_components = 0

            for row in rows:
                total = row["total_checks"]
                healthy = row["healthy_count"] or 0
                degraded = row["degraded_count"] or 0
                unhealthy = row["unhealthy_count"] or 0

                health_rate = healthy / total if total > 0 else 0.0

                # P95 berechnen
                p95_cursor = conn.execute(
                    """
                    SELECT response_time_ms FROM health_checks
                    WHERE component = ? AND check_time >= ?
                    ORDER BY response_time_ms DESC
                    LIMIT 1 OFFSET (SELECT COUNT(*) * 95 / 100 FROM health_checks
                                    WHERE component = ? AND check_time >= ?)
                    """,
                    (row["component"], cutoff, row["component"], cutoff)
                )
                p95_row = p95_cursor.fetchone()
                p95 = p95_row[0] if p95_row else row["avg_response_time"]

                # Flapping-Score berechnen (wie oft Status wechselt)
                flap_cursor = conn.execute(
                    """
                    SELECT status FROM health_checks
                    WHERE component = ? AND check_time >= ?
                    ORDER BY check_time DESC
                    """,
                    (row["component"], cutoff)
                )
                statuses = [r[0] for r in flap_cursor.fetchall()]
                flaps = sum(1 for i in range(1, len(statuses)) if statuses[i] != statuses[i-1])
                flapping_score = flaps / len(statuses) if len(statuses) > 1 else 0.0

                # Trend bestimmen
                if len(statuses) >= 10:
                    recent_healthy = statuses[:5].count("healthy")
                    older_healthy = statuses[5:10].count("healthy")
                    if recent_healthy > older_healthy:
                        trend = "improving"
                    elif recent_healthy < older_healthy:
                        trend = "degrading"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"

                pattern = HealthComponentPatternEntryV1(
                    component=row["component"],
                    component_type=row["component_type"],
                    total_checks=total,
                    healthy_count=healthy,
                    degraded_count=degraded,
                    unhealthy_count=unhealthy,
                    unknown_count=row["unknown_count"] or 0,
                    health_rate=round(health_rate, 4),
                    avg_response_time_ms=round(row["avg_response_time"] or 0, 2),
                    min_response_time_ms=round(row["min_response_time"] or 0, 2),
                    max_response_time_ms=round(row["max_response_time"] or 0, 2),
                    p95_response_time_ms=round(p95, 2),
                    last_check_time=row["last_check_time"],
                    last_status=row["last_status"],
                    trend=trend,
                    flapping_score=round(flapping_score, 4),
                )
                patterns.append(pattern)

                if row["last_status"] == "healthy":
                    healthy_components += 1
                elif row["last_status"] == "degraded":
                    degraded_components += 1
                elif row["last_status"] == "unhealthy":
                    unhealthy_components += 1

            return HealthComponentPatternsV1(
                patterns=patterns,
                total_components=len(patterns),
                healthy_components=healthy_components,
                degraded_components=degraded_components,
                unhealthy_components=unhealthy_components,
                revision=self._get_latest_revision("check"),
            )
        finally:
            conn.close()

    def _get_latest_revision(self, revision_type: str) -> int:
        """Letzte Revisionsnummer für einen Typ holen."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT MAX(revision) FROM health_revisions WHERE revision_type = ?",
                (revision_type,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        time_range_days: int = 7,
    ) -> HealthEffectivenessMetricsV1:
        """Effectiveness-Metriken berechnen."""
        conn = self._get_connection()
        try:
            from datetime import timedelta

            cutoff = (datetime.now(timezone.utc) - timedelta(days=time_range_days)).isoformat()

            # Gesamte Checks und Status-Verteilung
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                    SUM(CASE WHEN status = 'degraded' THEN 1 ELSE 0 END) as degraded_count,
                    SUM(CASE WHEN status = 'unhealthy' THEN 1 ELSE 0 END) as unhealthy_count
                FROM health_checks
                WHERE check_time >= ?
                """,
                (cutoff,)
            )
            row = cursor.fetchone()

            total = row["total_checks"] or 0
            healthy = row["healthy_count"] or 0
            degraded = row["degraded_count"] or 0
            unhealthy = row["unhealthy_count"] or 0

            overall_health_score = healthy / total if total > 0 else 0.0

            # Components by Health
            comp_cursor = conn.execute(
                """
                SELECT component, status FROM health_checks h1
                WHERE check_time = (
                    SELECT MAX(check_time) FROM health_checks h2
                    WHERE h2.component = h1.component
                )
                """
            )
            components_by_health: dict[str, int] = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}
            for comp_row in comp_cursor.fetchall():
                status = comp_row[1]
                if status in components_by_health:
                    components_by_health[status] += 1

            # Checks last 24h / 7d
            from datetime import timedelta

            cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            checks_24h_cursor = conn.execute(
                "SELECT COUNT(*) FROM health_checks WHERE check_time >= ?",
                (cutoff_24h,)
            )
            checks_24h = checks_24h_cursor.fetchone()[0]

            checks_7d_cursor = conn.execute(
                "SELECT COUNT(*) FROM health_checks WHERE check_time >= ?",
                (cutoff,)
            )
            checks_7d = checks_7d_cursor.fetchone()[0]

            # Durchschnittliches Check-Intervall (vereinfacht: Gesamtzeitraum / Anzahl)
            if checks_7d > 1:
                time_cursor = conn.execute(
                    """
                    SELECT 
                        (julianday(MAX(check_time)) - julianday(MIN(check_time))) * 86400 as total_seconds,
                        COUNT(*) as cnt
                    FROM health_checks
                    WHERE check_time >= ?
                    """,
                    (cutoff,)
                )
                time_row = time_cursor.fetchone()
                total_seconds = time_row[0] if time_row and time_row[0] else 0
                cnt = time_row[1] if time_row else 0
                avg_interval = total_seconds / (cnt - 1) if cnt > 1 else 0
            else:
                avg_interval = 0.0

            # MTBF (Mean Time Between Failures) in Stunden
            # Zählen, wie oft unhealthy→healthy Übergänge passiert sind
            mtbf_cursor = conn.execute(
                """
                SELECT component, status, check_time FROM health_checks
                WHERE check_time >= ?
                ORDER BY component, check_time
                """,
                (cutoff,)
            )
            failures = 0
            prev: dict[str, str] = {}
            for comp, status, _ in mtbf_cursor.fetchall():
                if prev.get(comp) == "unhealthy" and status == "healthy":
                    failures += 1
                prev[comp] = status

            days = time_range_days
            mtbf_hours = (days * 24) / failures if failures > 0 else float(days * 24)

            # MTTR (Mean Time To Recovery) in Minuten
            # Durchschnittliche Dauer von unhealthy-Phasen
            mttr_cursor = conn.execute(
                """
                SELECT component, status, check_time FROM health_checks
                WHERE check_time >= ? AND status IN ('unhealthy', 'degraded')
                ORDER BY component, check_time
                """,
                (cutoff,)
            )
            recovery_times: list[float] = []
            # Vereinfacht: Annahme, dass Recovery im nächsten Check passiert
            avg_recovery_minutes = 5.0  # Default-Annahme

            return HealthEffectivenessMetricsV1(
                overall_health_score=round(overall_health_score, 4),
                system_uptime_rate=round(overall_health_score, 4),
                avg_check_interval_seconds=round(avg_interval, 2),
                mtbf_hours=round(mtbf_hours, 2),
                mttr_minutes=round(avg_recovery_minutes, 2),
                alert_accuracy_rate=0.95,  # Placeholder
                false_positive_rate=0.05,  # Placeholder
                components_by_health=components_by_health,
                checks_last_24h=checks_24h,
                checks_last_7d=checks_7d,
                revision=self._get_latest_revision("check"),
            )
        finally:
            conn.close()

    def build_summary(
        self,
        time_range_days: int = 7,
    ) -> HealthAnalyticsSummaryV1:
        """Zusammenfassung aller Health-Analytics aufbauen."""
        patterns = self.build_component_patterns(time_range_days)
        effectiveness = self.get_effectiveness_metrics(time_range_days)

        return HealthAnalyticsSummaryV1(
            history_summary={
                "total_checks": effectiveness.checks_last_7d,
                "time_range_days": time_range_days,
            },
            patterns_summary={
                "total_components": patterns.total_components,
                "healthy_components": patterns.healthy_components,
                "degraded_components": patterns.degraded_components,
                "unhealthy_components": patterns.unhealthy_components,
            },
            effectiveness_summary={
                "overall_health_score": effectiveness.overall_health_score,
                "mtbf_hours": effectiveness.mtbf_hours,
                "mttr_minutes": effectiveness.mttr_minutes,
            },
            revision=patterns.revision,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
