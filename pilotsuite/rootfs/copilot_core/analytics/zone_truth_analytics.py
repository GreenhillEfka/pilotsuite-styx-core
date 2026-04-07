"""Zone Truth Analytics Surface — Slice 58."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ZoneSyncEventType(str, Enum):
    """Zone sync event types."""
    ZONE_CREATED = "zone_created"
    ZONE_UPDATED = "zone_updated"
    ZONE_DELETED = "zone_deleted"
    ENTITY_ADDED = "entity_added"
    ENTITY_REMOVED = "entity_removed"
    ENTITY_UPDATED = "entity_updated"
    TOPOLOGY_SYNC = "topology_sync"
    CONFLICT_RESOLVED = "conflict_resolved"


class ZoneSyncStatus(str, Enum):
    """Zone sync status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class ZoneSyncEventEntryV1:
    """Single zone sync event entry."""
    event_id: str
    zone_id: str | None
    event_type: ZoneSyncEventType
    status: ZoneSyncStatus
    entity_count_before: int
    entity_count_after: int
    entities_changed: int
    timestamp: float
    source: str
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "zone_id": self.zone_id,
            "event_type": self.event_type.value,
            "status": self.status.value,
            "entity_count_before": self.entity_count_before,
            "entity_count_after": self.entity_count_after,
            "entities_changed": self.entities_changed,
            "timestamp": self.timestamp,
            "source": self.source,
            "revision": self.revision,
            "metadata": self.metadata,
        }


@dataclass
class ZoneSyncHistoryV1:
    """Zone sync execution history."""
    events: list[ZoneSyncEventEntryV1]
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
class ZonePatternEntryV1:
    """Zone pattern entry for a specific zone."""
    zone_id: str
    zone_name: str | None
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    conflict_count: int
    avg_entities_per_sync: float
    avg_entities_changed_per_sync: float
    last_sync_at: float | None
    sync_frequency_per_day: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "conflict_count": self.conflict_count,
            "avg_entities_per_sync": self.avg_entities_per_sync,
            "avg_entities_changed_per_sync": self.avg_entities_changed_per_sync,
            "last_sync_at": self.last_sync_at,
            "sync_frequency_per_day": self.sync_frequency_per_day,
        }


@dataclass
class ZonePatternsV1:
    """Zone-specific sync patterns."""
    patterns: list[ZonePatternEntryV1]
    total_zones: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "total_zones": self.total_zones,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ZoneEffectivenessMetricsV1:
    """Zone truth effectiveness metrics."""
    overall_sync_success_rate: float
    overall_conflict_rate: float
    avg_sync_duration_ms: float | None
    topology_stability_score: float
    entity_churn_rate: float
    zones_with_conflicts: int
    zones_healthy: int
    total_zones: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_sync_success_rate": self.overall_sync_success_rate,
            "overall_conflict_rate": self.overall_conflict_rate,
            "avg_sync_duration_ms": self.avg_sync_duration_ms,
            "topology_stability_score": self.topology_stability_score,
            "entity_churn_rate": self.entity_churn_rate,
            "zones_with_conflicts": self.zones_with_conflicts,
            "zones_healthy": self.zones_healthy,
            "total_zones": self.total_zones,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ZoneAnalyticsSummaryV1:
    """Zone analytics summary."""
    history: ZoneSyncHistoryV1 | None
    patterns: ZonePatternsV1 | None
    effectiveness: ZoneEffectivenessMetricsV1 | None
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


class ZoneAnalyticsStore:
    """SQLite-backed zone analytics store."""

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
                CREATE TABLE IF NOT EXISTS zone_sync_events (
                    event_id TEXT PRIMARY KEY,
                    zone_id TEXT,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    entity_count_before INTEGER NOT NULL,
                    entity_count_after INTEGER NOT NULL,
                    entities_changed INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    source TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_zone_events_zone_id
                    ON zone_sync_events(zone_id);
                CREATE INDEX IF NOT EXISTS idx_zone_events_timestamp
                    ON zone_sync_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_zone_events_type
                    ON zone_sync_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_zone_events_status
                    ON zone_sync_events(status);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self) -> int:
        """Get next revision number."""
        self._revision += 1
        return self._revision

    def add_sync_event(
        self,
        event_id: str,
        zone_id: str | None,
        event_type: ZoneSyncEventType,
        status: ZoneSyncStatus,
        entity_count_before: int,
        entity_count_after: int,
        entities_changed: int,
        source: str = "ha_topology_sync",
        metadata: dict[str, Any] | None = None,
    ) -> ZoneSyncEventEntryV1:
        """Record a zone sync event."""
        timestamp = time.time()
        revision = self._get_next_revision()

        entry = ZoneSyncEventEntryV1(
            event_id=event_id,
            zone_id=zone_id,
            event_type=event_type,
            status=status,
            entity_count_before=entity_count_before,
            entity_count_after=entity_count_after,
            entities_changed=entities_changed,
            timestamp=timestamp,
            source=source,
            revision=revision,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO zone_sync_events
                (event_id, zone_id, event_type, status, entity_count_before,
                 entity_count_after, entities_changed, timestamp, source,
                 revision, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.zone_id,
                    entry.event_type.value,
                    entry.status.value,
                    entry.entity_count_before,
                    entry.entity_count_after,
                    entry.entities_changed,
                    entry.timestamp,
                    entry.source,
                    entry.revision,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    def build_sync_history(
        self,
        zone_id: str | None = None,
        event_type: ZoneSyncEventType | None = None,
        status: ZoneSyncStatus | None = None,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        limit: int = 100,
        since_revision: int | None = None,
    ) -> ZoneSyncHistoryV1:
        """Build zone sync history with filters."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM zone_sync_events WHERE 1=1"
            params: list[Any] = []

            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            if status:
                query += " AND status = ?"
                params.append(status.value)
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
                "SELECT MAX(revision) FROM zone_sync_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        events = []
        for row in rows:
            events.append(
                ZoneSyncEventEntryV1(
                    event_id=row[0],
                    zone_id=row[1],
                    event_type=ZoneSyncEventType(row[2]),
                    status=ZoneSyncStatus(row[3]),
                    entity_count_before=row[4],
                    entity_count_after=row[5],
                    entities_changed=row[6],
                    timestamp=row[7],
                    source=row[8],
                    revision=row[9],
                    metadata=json.loads(row[10]) if row[10] else {},
                )
            )

        return ZoneSyncHistoryV1(
            events=list(reversed(events)),
            total_count=total_count,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            revision=max_revision,
        )

    def build_zone_patterns(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ZonePatternsV1:
        """Build zone-specific sync patterns."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            # Get zone-level aggregations
            query = """
                SELECT
                    zone_id,
                    COUNT(*) as total_syncs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_syncs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_syncs,
                    SUM(CASE WHEN status = 'conflict' THEN 1 ELSE 0 END) as conflict_count,
                    AVG(entity_count_after) as avg_entities,
                    AVG(entities_changed) as avg_changed,
                    MAX(timestamp) as last_sync_at
                FROM zone_sync_events
                WHERE timestamp >= ?
                AND zone_id IS NOT NULL
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " GROUP BY zone_id"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Get max revision
            max_revision = conn.execute(
                "SELECT MAX(revision) FROM zone_sync_events"
            ).fetchone()[0] or 0

            patterns = []
            for row in rows:
                zone_id, total, successful, failed, conflicts, avg_ent, avg_chg, last_sync = row

                # Calculate sync frequency per day
                if total > 1 and last_sync:
                    # Get first sync timestamp for this zone
                    first_sync = conn.execute(
                        "SELECT MIN(timestamp) FROM zone_sync_events WHERE zone_id = ? AND timestamp >= ?",
                        (zone_id, cutoff),
                    ).fetchone()[0]
                    if first_sync and last_sync > first_sync:
                        days_span = max(1, (last_sync - first_sync) / (24 * 60 * 60))
                        freq = total / days_span
                    else:
                        freq = 0.0
                else:
                    freq = 0.0

                patterns.append(
                    ZonePatternEntryV1(
                        zone_id=zone_id,
                        zone_name=None,  # To be resolved by API layer
                        total_syncs=total or 0,
                        successful_syncs=successful or 0,
                        failed_syncs=failed or 0,
                        conflict_count=conflicts or 0,
                        avg_entities_per_sync=avg_ent or 0.0,
                        avg_entities_changed_per_sync=avg_chg or 0.0,
                        last_sync_at=last_sync,
                        sync_frequency_per_day=freq,
                    )
                )

            return ZonePatternsV1(
                patterns=patterns,
                total_zones=len(patterns),
                revision=max_revision,
                generated_at=time.time(),
            )
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ZoneEffectivenessMetricsV1:
        """Calculate zone truth effectiveness metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    COUNT(*) as total_syncs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'conflict' THEN 1 ELSE 0 END) as conflicts,
                    COUNT(DISTINCT zone_id) as total_zones,
                    COUNT(DISTINCT CASE WHEN status = 'success' THEN zone_id END) as healthy_zones,
                    COUNT(DISTINCT CASE WHEN status = 'conflict' THEN zone_id END) as conflict_zones,
                    AVG(entities_changed) as avg_changed
                FROM zone_sync_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            row = conn.execute(query, params).fetchone()
            (
                total,
                successful,
                failed,
                conflicts,
                total_zones,
                healthy_zones,
                conflict_zones,
                avg_changed,
            ) = row

            # Calculate metrics
            success_rate = (successful / total) if total > 0 else 0.0
            conflict_rate = (conflicts / total) if total > 0 else 0.0

            # Topology stability: inverse of conflict rate and entity churn
            churn_rate = avg_changed or 0.0
            stability = max(0.0, 1.0 - conflict_rate - (churn_rate / 100.0))

            # Get max revision
            max_revision = conn.execute(
                "SELECT MAX(revision) FROM zone_sync_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        return ZoneEffectivenessMetricsV1(
            overall_sync_success_rate=success_rate,
            overall_conflict_rate=conflict_rate,
            avg_sync_duration_ms=None,  # Not tracked yet
            topology_stability_score=stability,
            entity_churn_rate=churn_rate,
            zones_with_conflicts=conflict_zones or 0,
            zones_healthy=healthy_zones or 0,
            total_zones=total_zones or 0,
            revision=max_revision,
            generated_at=time.time(),
        )

    def build_summary(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ZoneAnalyticsSummaryV1:
        """Build complete zone analytics summary."""
        history = self.build_sync_history(
            from_timestamp=time.time() - (days_lookback * 24 * 60 * 60),
            limit=50,
            since_revision=since_revision,
        )
        patterns = self.build_zone_patterns(
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

        return ZoneAnalyticsSummaryV1(
            history=history,
            patterns=patterns,
            effectiveness=effectiveness,
            revision=max_revision,
            generated_at=time.time(),
        )
