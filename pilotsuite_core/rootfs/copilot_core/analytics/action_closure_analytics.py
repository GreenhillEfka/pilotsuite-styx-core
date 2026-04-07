"""Action Closure Analytics Surface — Slice 60."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ClosureEventType(str, Enum):
    """Action closure event types."""
    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    FEEDBACK_PROVIDED = "feedback_provided"
    SETTLED = "settled"


class ClosureSource(str, Enum):
    """Action closure source types."""
    VOICE = "voice"
    PREDICTIVE = "predictive"
    HABITUS = "habitus"
    MULTI_ZONE = "multizone"
    MANUAL = "manual"


@dataclass
class ActionClosureEventV1:
    """Single action closure event."""
    event_id: str
    closure_id: str
    zone_id: str | None
    module_id: str | None
    event_type: ClosureEventType
    source: ClosureSource
    timestamp: float
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "closure_id": self.closure_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "revision": self.revision,
            "metadata": self.metadata,
        }


@dataclass
class ActionClosureHistoryV1:
    """Action closure event history."""
    events: list[ActionClosureEventV1]
    total_count: int
    from_timestamp: float | None
    to_timestamp: float | None
    revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_count": self.total_count,
            "from_timestamp": self.from_timestamp,
            "to_timestamp": self.to_timestamp,
            "revision": self.revision,
        }


@dataclass
class ClosurePatternEntryV1:
    """Closure pattern entry for a specific zone/source."""
    zone_id: str | None
    zone_name: str | None
    source: ClosureSource
    total_closures: int
    completed_count: int
    failed_count: int
    rejected_count: int
    completion_rate: float
    failure_rate: float
    avg_time_to_complete_seconds: float | None
    last_closure_at: float | None
    closures_per_day: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "source": self.source.value,
            "total_closures": self.total_closures,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "rejected_count": self.rejected_count,
            "completion_rate": self.completion_rate,
            "failure_rate": self.failure_rate,
            "avg_time_to_complete_seconds": self.avg_time_to_complete_seconds,
            "last_closure_at": self.last_closure_at,
            "closures_per_day": self.closures_per_day,
        }


@dataclass
class ClosurePatternsV1:
    """Closure-specific patterns."""
    patterns: list[ClosurePatternEntryV1]
    total_entries: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "total_entries": self.total_entries,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ClosureEffectivenessMetricsV1:
    """Action closure effectiveness metrics."""
    overall_completion_rate: float
    overall_failure_rate: float
    overall_rejection_rate: float
    avg_time_to_complete_seconds: float | None
    avg_time_to_feedback_seconds: float | None
    closures_by_source: dict[str, int]
    completions_by_source: dict[str, int]
    zones_with_closures: int
    zones_with_completions: int
    total_closures: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_completion_rate": self.overall_completion_rate,
            "overall_failure_rate": self.overall_failure_rate,
            "overall_rejection_rate": self.overall_rejection_rate,
            "avg_time_to_complete_seconds": self.avg_time_to_complete_seconds,
            "avg_time_to_feedback_seconds": self.avg_time_to_feedback_seconds,
            "closures_by_source": self.closures_by_source,
            "completions_by_source": self.completions_by_source,
            "zones_with_closures": self.zones_with_closures,
            "zones_with_completions": self.zones_with_completions,
            "total_closures": self.total_closures,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ClosureAnalyticsSummaryV1:
    """Closure analytics summary."""
    history: ActionClosureHistoryV1 | None
    patterns: ClosurePatternsV1 | None
    effectiveness: ClosureEffectivenessMetricsV1 | None
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "history": self.history.to_dict() if self.history else None,
            "patterns": self.patterns.to_dict() if self.patterns else None,
            "effectiveness": self.effectiveness.to_dict() if self.effectiveness else None,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


class ClosureAnalyticsStore:
    """SQLite-backed action closure analytics store."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._revision = 0

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS action_closure_events (
                    event_id TEXT PRIMARY KEY,
                    closure_id TEXT NOT NULL,
                    zone_id TEXT,
                    module_id TEXT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_closure_events_closure_id
                    ON action_closure_events(closure_id);
                CREATE INDEX IF NOT EXISTS idx_closure_events_timestamp
                    ON action_closure_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_closure_events_type
                    ON action_closure_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_closure_events_source
                    ON action_closure_events(source);
                CREATE INDEX IF NOT EXISTS idx_closure_events_zone
                    ON action_closure_events(zone_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self) -> int:
        """Get next revision number."""
        self._revision += 1
        return self._revision

    def add_closure_event(
        self,
        event_id: str,
        closure_id: str,
        zone_id: str | None,
        module_id: str | None,
        event_type: ClosureEventType,
        source: ClosureSource,
        metadata: dict[str, Any] | None = None,
    ) -> ActionClosureEventV1:
        """Record an action closure event."""
        timestamp = time.time()
        revision = self._get_next_revision()

        entry = ActionClosureEventV1(
            event_id=event_id,
            closure_id=closure_id,
            zone_id=zone_id,
            module_id=module_id,
            event_type=event_type,
            source=source,
            timestamp=timestamp,
            revision=revision,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO action_closure_events
                (event_id, closure_id, zone_id, module_id, event_type,
                 source, timestamp, revision, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.closure_id,
                    entry.zone_id,
                    entry.module_id,
                    entry.event_type.value,
                    entry.source.value,
                    entry.timestamp,
                    entry.revision,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    def build_closure_history(
        self,
        closure_id: str | None = None,
        zone_id: str | None = None,
        event_type: ClosureEventType | None = None,
        source: ClosureSource | None = None,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        limit: int = 100,
        since_revision: int | None = None,
    ) -> ActionClosureHistoryV1:
        """Build action closure history with filters."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM action_closure_events WHERE 1=1"
            params: list[Any] = []

            if closure_id:
                query += " AND closure_id = ?"
                params.append(closure_id)
            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            if source:
                query += " AND source = ?"
                params.append(source.value)
            if from_timestamp:
                query += " AND timestamp >= ?"
                params.append(from_timestamp)
            if to_timestamp:
                query += " AND timestamp <= ?"
                params.append(to_timestamp)
            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            count_query = query.replace("SELECT *", "SELECT COUNT(*)").replace(
                "ORDER BY timestamp DESC LIMIT ?", ""
            )
            count_params = params[:-1]
            total_count = conn.execute(count_query, count_params).fetchone()[0]

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM action_closure_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        events = []
        for row in rows:
            events.append(
                ActionClosureEventV1(
                    event_id=row[0],
                    closure_id=row[1],
                    zone_id=row[2],
                    module_id=row[3],
                    event_type=ClosureEventType(row[4]),
                    source=ClosureSource(row[5]),
                    timestamp=row[6],
                    revision=row[7],
                    metadata=json.loads(row[8]) if row[8] else {},
                )
            )

        return ActionClosureHistoryV1(
            events=list(reversed(events)),
            total_count=total_count,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            revision=max_revision,
        )

    def build_closure_patterns(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ClosurePatternsV1:
        """Build closure-specific patterns by zone and source."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    zone_id,
                    source,
                    COUNT(DISTINCT closure_id) as total_closures,
                    SUM(CASE WHEN event_type = 'execution_completed' THEN 1 ELSE 0 END) as completed_count,
                    SUM(CASE WHEN event_type = 'execution_failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN event_type = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    MAX(timestamp) as last_closure_at
                FROM action_closure_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " GROUP BY zone_id, source"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM action_closure_events"
            ).fetchone()[0] or 0

            patterns = []
            for row in rows:
                zone_id, source, total, completed, failed, rejected, last_ts = row

                total = total or 0
                completed = completed or 0
                failed = failed or 0
                rejected = rejected or 0

                completion_rate = (completed / total) if total > 0 else 0.0
                failure_rate = (failed / total) if total > 0 else 0.0

                if total > 1 and last_ts:
                    first_ts = conn.execute(
                        "SELECT MIN(timestamp) FROM action_closure_events WHERE zone_id = ? AND source = ? AND timestamp >= ?",
                        (zone_id, source, cutoff),
                    ).fetchone()[0]
                    if first_ts and last_ts > first_ts:
                        days_span = max(1, (last_ts - first_ts) / (24 * 60 * 60))
                        freq = total / days_span
                    else:
                        freq = 0.0
                else:
                    freq = 0.0

                patterns.append(
                    ClosurePatternEntryV1(
                        zone_id=zone_id,
                        zone_name=None,
                        source=ClosureSource(source),
                        total_closures=total,
                        completed_count=completed,
                        failed_count=failed,
                        rejected_count=rejected,
                        completion_rate=completion_rate,
                        failure_rate=failure_rate,
                        avg_time_to_complete_seconds=None,
                        last_closure_at=last_ts,
                        closures_per_day=freq,
                    )
                )

            return ClosurePatternsV1(
                patterns=patterns,
                total_entries=len(patterns),
                revision=max_revision,
                generated_at=time.time(),
            )
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ClosureEffectivenessMetricsV1:
        """Calculate action closure effectiveness metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    COUNT(DISTINCT closure_id) as total_closures,
                    COUNT(DISTINCT CASE WHEN event_type = 'execution_completed' THEN closure_id END) as completed,
                    COUNT(DISTINCT CASE WHEN event_type = 'execution_failed' THEN closure_id END) as failed,
                    COUNT(DISTINCT CASE WHEN event_type = 'rejected' THEN closure_id END) as rejected,
                    COUNT(DISTINCT zone_id) as zones_with_closures,
                    COUNT(DISTINCT CASE WHEN event_type = 'execution_completed' THEN zone_id END) as zones_with_completions
                FROM action_closure_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            row = conn.execute(query, params).fetchone()
            (
                total,
                completed,
                failed,
                rejected,
                zones_with_closures,
                zones_with_completions,
            ) = row

            total = total or 0
            completed = completed or 0
            failed = failed or 0
            rejected = rejected or 0

            completion_rate = (completed / total) if total > 0 else 0.0
            failure_rate = (failed / total) if total > 0 else 0.0
            rejection_rate = (rejected / total) if total > 0 else 0.0

            source_query = """
                SELECT source, COUNT(DISTINCT closure_id) as count
                FROM action_closure_events
                WHERE timestamp >= ?
            """
            source_params: list[Any] = [cutoff]
            if since_revision:
                source_query += " AND revision > ?"
                source_params.append(since_revision)
            source_query += " GROUP BY source"

            closures_by_source = {}
            for row in conn.execute(source_query, source_params):
                closures_by_source[row[0]] = row[1]

            completions_source_query = """
                SELECT source, COUNT(DISTINCT closure_id) as count
                FROM action_closure_events
                WHERE timestamp >= ? AND event_type = 'execution_completed'
            """
            completions_params: list[Any] = [cutoff]
            if since_revision:
                completions_source_query += " AND revision > ?"
                completions_params.append(since_revision)
            completions_source_query += " GROUP BY source"

            completions_by_source = {}
            for row in conn.execute(completions_source_query, completions_params):
                completions_by_source[row[0]] = row[1]

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM action_closure_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        return ClosureEffectivenessMetricsV1(
            overall_completion_rate=completion_rate,
            overall_failure_rate=failure_rate,
            overall_rejection_rate=rejection_rate,
            avg_time_to_complete_seconds=None,
            avg_time_to_feedback_seconds=None,
            closures_by_source=closures_by_source,
            completions_by_source=completions_by_source,
            zones_with_closures=zones_with_closures or 0,
            zones_with_completions=zones_with_completions or 0,
            total_closures=total,
            revision=max_revision,
            generated_at=time.time(),
        )

    def build_summary(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ClosureAnalyticsSummaryV1:
        """Build complete closure analytics summary."""
        history = self.build_closure_history(
            from_timestamp=time.time() - (days_lookback * 24 * 60 * 60),
            limit=50,
            since_revision=since_revision,
        )
        patterns = self.build_closure_patterns(
            days_lookback=days_lookback,
            since_revision=since_revision,
        )
        effectiveness = self.get_effectiveness_metrics(
            days_lookback=days_lookback,
            since_revision=since_revision,
        )

        max_revision = max(
            history.revision,
            patterns.revision,
            effectiveness.revision,
        )

        return ClosureAnalyticsSummaryV1(
            history=history,
            patterns=patterns,
            effectiveness=effectiveness,
            revision=max_revision,
            generated_at=time.time(),
        )
