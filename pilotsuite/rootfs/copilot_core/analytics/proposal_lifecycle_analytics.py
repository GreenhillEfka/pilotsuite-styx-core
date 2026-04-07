"""Proposal Lifecycle Analytics Surface — Slice 59."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ProposalEventType(str, Enum):
    """Proposal lifecycle event types."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SNOOZED = "snoozed"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class ProposalSource(str, Enum):
    """Proposal source types."""
    PREDICTIVE = "predictive"
    HABITUS = "habitus"
    VOICE = "voice"
    MULTI_ZONE = "multizone"
    MANUAL = "manual"
    SYSTEM = "system"


@dataclass
class ProposalLifecycleEventV1:
    """Single proposal lifecycle event."""
    event_id: str
    proposal_id: str
    zone_id: str | None
    module_id: str | None
    event_type: ProposalEventType
    source: ProposalSource
    timestamp: float
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "proposal_id": self.proposal_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "revision": self.revision,
            "metadata": self.metadata,
        }


@dataclass
class ProposalLifecycleHistoryV1:
    """Proposal lifecycle event history."""
    events: list[ProposalLifecycleEventV1]
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
class ProposalPatternEntryV1:
    """Proposal pattern entry for a specific zone/source."""
    zone_id: str | None
    zone_name: str | None
    source: ProposalSource
    total_proposals: int
    accepted_count: int
    rejected_count: int
    executed_count: int
    failed_count: int
    acceptance_rate: float
    execution_rate: float
    avg_time_to_accept_seconds: float | None
    last_proposal_at: float | None
    proposals_per_day: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "source": self.source.value,
            "total_proposals": self.total_proposals,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "executed_count": self.executed_count,
            "failed_count": self.failed_count,
            "acceptance_rate": self.acceptance_rate,
            "execution_rate": self.execution_rate,
            "avg_time_to_accept_seconds": self.avg_time_to_accept_seconds,
            "last_proposal_at": self.last_proposal_at,
            "proposals_per_day": self.proposals_per_day,
        }


@dataclass
class ProposalPatternsV1:
    """Proposal-specific patterns."""
    patterns: list[ProposalPatternEntryV1]
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
class ProposalEffectivenessMetricsV1:
    """Proposal lifecycle effectiveness metrics."""
    overall_acceptance_rate: float
    overall_execution_rate: float
    overall_failure_rate: float
    avg_time_to_accept_seconds: float | None
    avg_time_to_execute_seconds: float | None
    proposals_by_source: dict[str, int]
    acceptances_by_source: dict[str, int]
    zones_with_proposals: int
    zones_with_acceptances: int
    total_proposals: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_acceptance_rate": self.overall_acceptance_rate,
            "overall_execution_rate": self.overall_execution_rate,
            "overall_failure_rate": self.overall_failure_rate,
            "avg_time_to_accept_seconds": self.avg_time_to_accept_seconds,
            "avg_time_to_execute_seconds": self.avg_time_to_execute_seconds,
            "proposals_by_source": self.proposals_by_source,
            "acceptances_by_source": self.acceptances_by_source,
            "zones_with_proposals": self.zones_with_proposals,
            "zones_with_acceptances": self.zones_with_acceptances,
            "total_proposals": self.total_proposals,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ProposalAnalyticsSummaryV1:
    """Proposal analytics summary."""
    history: ProposalLifecycleHistoryV1 | None
    patterns: ProposalPatternsV1 | None
    effectiveness: ProposalEffectivenessMetricsV1 | None
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


class ProposalAnalyticsStore:
    """SQLite-backed proposal lifecycle analytics store."""

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
                CREATE TABLE IF NOT EXISTS proposal_lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    zone_id TEXT,
                    module_id TEXT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal_id
                    ON proposal_lifecycle_events(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_proposal_events_timestamp
                    ON proposal_lifecycle_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_proposal_events_type
                    ON proposal_lifecycle_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_proposal_events_source
                    ON proposal_lifecycle_events(source);
                CREATE INDEX IF NOT EXISTS idx_proposal_events_zone
                    ON proposal_lifecycle_events(zone_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self) -> int:
        """Get next revision number."""
        self._revision += 1
        return self._revision

    def add_lifecycle_event(
        self,
        event_id: str,
        proposal_id: str,
        zone_id: str | None,
        module_id: str | None,
        event_type: ProposalEventType,
        source: ProposalSource,
        metadata: dict[str, Any] | None = None,
    ) -> ProposalLifecycleEventV1:
        """Record a proposal lifecycle event."""
        timestamp = time.time()
        revision = self._get_next_revision()

        entry = ProposalLifecycleEventV1(
            event_id=event_id,
            proposal_id=proposal_id,
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
                INSERT INTO proposal_lifecycle_events
                (event_id, proposal_id, zone_id, module_id, event_type,
                 source, timestamp, revision, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.proposal_id,
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

    def build_lifecycle_history(
        self,
        proposal_id: str | None = None,
        zone_id: str | None = None,
        event_type: ProposalEventType | None = None,
        source: ProposalSource | None = None,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        limit: int = 100,
        since_revision: int | None = None,
    ) -> ProposalLifecycleHistoryV1:
        """Build proposal lifecycle history with filters."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM proposal_lifecycle_events WHERE 1=1"
            params: list[Any] = []

            if proposal_id:
                query += " AND proposal_id = ?"
                params.append(proposal_id)
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

            # Get total count
            count_query = query.replace("SELECT *", "SELECT COUNT(*)").replace(
                "ORDER BY timestamp DESC LIMIT ?", ""
            )
            count_params = params[:-1]
            total_count = conn.execute(count_query, count_params).fetchone()[0]

            # Get current max revision
            max_revision = conn.execute(
                "SELECT MAX(revision) FROM proposal_lifecycle_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        events = []
        for row in rows:
            events.append(
                ProposalLifecycleEventV1(
                    event_id=row[0],
                    proposal_id=row[1],
                    zone_id=row[2],
                    module_id=row[3],
                    event_type=ProposalEventType(row[4]),
                    source=ProposalSource(row[5]),
                    timestamp=row[6],
                    revision=row[7],
                    metadata=json.loads(row[8]) if row[8] else {},
                )
            )

        return ProposalLifecycleHistoryV1(
            events=list(reversed(events)),
            total_count=total_count,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            revision=max_revision,
        )

    def build_proposal_patterns(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ProposalPatternsV1:
        """Build proposal-specific patterns by zone and source."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            # Get zone/source-level aggregations
            query = """
                SELECT
                    zone_id,
                    source,
                    COUNT(*) as total_proposals,
                    SUM(CASE WHEN event_type = 'accepted' THEN 1 ELSE 0 END) as accepted_count,
                    SUM(CASE WHEN event_type = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    SUM(CASE WHEN event_type = 'executed' THEN 1 ELSE 0 END) as executed_count,
                    SUM(CASE WHEN event_type = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    MAX(timestamp) as last_proposal_at
                FROM proposal_lifecycle_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " GROUP BY zone_id, source"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Get max revision
            max_revision = conn.execute(
                "SELECT MAX(revision) FROM proposal_lifecycle_events"
            ).fetchone()[0] or 0

            patterns = []
            for row in rows:
                zone_id, source, total, accepted, rejected, executed, failed, last_ts = row

                total = total or 0
                accepted = accepted or 0
                rejected = rejected or 0
                executed = executed or 0
                failed = failed or 0

                acceptance_rate = (accepted / total) if total > 0 else 0.0
                execution_rate = (executed / total) if total > 0 else 0.0

                # Calculate proposals per day
                if total > 1 and last_ts:
                    first_ts = conn.execute(
                        "SELECT MIN(timestamp) FROM proposal_lifecycle_events WHERE zone_id = ? AND source = ? AND timestamp >= ?",
                        (zone_id, source, cutoff),
                    ).fetchone()[0]
                    if first_ts and last_ts > first_ts:
                        days_span = max(1, (last_ts - first_ts) / (24 * 60 * 60))
                        freq = total / days_span
                    else:
                        freq = 0.0
                else:
                    freq = 0.0

                # Calculate avg time to accept (would need proposal creation timestamp)
                avg_time_to_accept = None  # Would need proposal creation events

                patterns.append(
                    ProposalPatternEntryV1(
                        zone_id=zone_id,
                        zone_name=None,
                        source=ProposalSource(source),
                        total_proposals=total,
                        accepted_count=accepted,
                        rejected_count=rejected,
                        executed_count=executed,
                        failed_count=failed,
                        acceptance_rate=acceptance_rate,
                        execution_rate=execution_rate,
                        avg_time_to_accept_seconds=avg_time_to_accept,
                        last_proposal_at=last_ts,
                        proposals_per_day=freq,
                    )
                )

            return ProposalPatternsV1(
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
    ) -> ProposalEffectivenessMetricsV1:
        """Calculate proposal lifecycle effectiveness metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    COUNT(*) as total_proposals,
                    SUM(CASE WHEN event_type = 'accepted' THEN 1 ELSE 0 END) as accepted,
                    SUM(CASE WHEN event_type = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN event_type = 'executed' THEN 1 ELSE 0 END) as executed,
                    SUM(CASE WHEN event_type = 'failed' THEN 1 ELSE 0 END) as failed,
                    COUNT(DISTINCT zone_id) as zones_with_proposals,
                    COUNT(DISTINCT CASE WHEN event_type = 'accepted' THEN zone_id END) as zones_with_acceptances
                FROM proposal_lifecycle_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            row = conn.execute(query, params).fetchone()
            (
                total,
                accepted,
                rejected,
                executed,
                failed,
                zones_with_proposals,
                zones_with_acceptances,
            ) = row

            total = total or 0
            accepted = accepted or 0
            executed = executed or 0
            failed = failed or 0

            # Calculate rates
            acceptance_rate = (accepted / total) if total > 0 else 0.0
            execution_rate = (executed / total) if total > 0 else 0.0
            failure_rate = (failed / total) if total > 0 else 0.0

            # Get proposals by source
            source_query = """
                SELECT source, COUNT(*) as count
                FROM proposal_lifecycle_events
                WHERE timestamp >= ?
            """
            source_params: list[Any] = [cutoff]
            if since_revision:
                source_query += " AND revision > ?"
                source_params.append(since_revision)
            source_query += " GROUP BY source"

            proposals_by_source = {}
            for row in conn.execute(source_query, source_params):
                proposals_by_source[row[0]] = row[1]

            # Get acceptances by source
            accept_source_query = """
                SELECT source, COUNT(*) as count
                FROM proposal_lifecycle_events
                WHERE timestamp >= ? AND event_type = 'accepted'
            """
            accept_params: list[Any] = [cutoff]
            if since_revision:
                accept_source_query += " AND revision > ?"
                accept_params.append(since_revision)
            accept_source_query += " GROUP BY source"

            acceptances_by_source = {}
            for row in conn.execute(accept_source_query, accept_params):
                acceptances_by_source[row[0]] = row[1]

            # Get max revision
            max_revision = conn.execute(
                "SELECT MAX(revision) FROM proposal_lifecycle_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        return ProposalEffectivenessMetricsV1(
            overall_acceptance_rate=acceptance_rate,
            overall_execution_rate=execution_rate,
            overall_failure_rate=failure_rate,
            avg_time_to_accept_seconds=None,
            avg_time_to_execute_seconds=None,
            proposals_by_source=proposals_by_source,
            acceptances_by_source=acceptances_by_source,
            zones_with_proposals=zones_with_proposals or 0,
            zones_with_acceptances=zones_with_acceptances or 0,
            total_proposals=total,
            revision=max_revision,
            generated_at=time.time(),
        )

    def build_summary(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ProposalAnalyticsSummaryV1:
        """Build complete proposal analytics summary."""
        history = self.build_lifecycle_history(
            from_timestamp=time.time() - (days_lookback * 24 * 60 * 60),
            limit=50,
            since_revision=since_revision,
        )
        patterns = self.build_proposal_patterns(
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

        return ProposalAnalyticsSummaryV1(
            history=history,
            patterns=patterns,
            effectiveness=effectiveness,
            revision=max_revision,
            generated_at=time.time(),
        )
