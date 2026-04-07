"""Brain/Neuron Analytics Surface — Slice 61."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NeuronEventType(str, Enum):
    """Neuron event types."""
    ACTIVATED = "activated"
    EVALUATED = "evaluated"
    CONTEXT_UPDATED = "context_updated"
    STATE_CHANGED = "state_changed"
    MOOD_UPDATED = "mood_updated"
    GRAPH_GROWN = "graph_grown"
    NODE_ADDED = "node_added"
    EDGE_ADDED = "edge_added"
    PRUNED = "pruned"


class NeuronLayer(str, Enum):
    """Neuron layer types."""
    PERCEPTION = "perception"
    CONTEXT = "context"
    STATE = "state"
    MOOD = "mood"
    DECISION = "decision"


@dataclass
class NeuronEventV1:
    """Single neuron/brain event."""
    event_id: str
    neuron_id: str | None
    zone_id: str | None
    layer: NeuronLayer | None
    event_type: NeuronEventType
    timestamp: float
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "neuron_id": self.neuron_id,
            "zone_id": self.zone_id,
            "layer": self.layer.value if self.layer else None,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "revision": self.revision,
            "metadata": self.metadata,
        }


@dataclass
class NeuronHistoryV1:
    """Neuron event history."""
    events: list[NeuronEventV1]
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
class NeuronPatternEntryV1:
    """Neuron pattern entry for a specific zone/layer."""
    zone_id: str | None
    zone_name: str | None
    layer: NeuronLayer | None
    total_events: int
    activation_count: int
    evaluation_count: int
    context_update_count: int
    state_change_count: int
    growth_count: int
    prune_count: int
    events_per_day: float
    last_event_at: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "layer": self.layer.value if self.layer else None,
            "total_events": self.total_events,
            "activation_count": self.activation_count,
            "evaluation_count": self.evaluation_count,
            "context_update_count": self.context_update_count,
            "state_change_count": self.state_change_count,
            "growth_count": self.growth_count,
            "prune_count": self.prune_count,
            "events_per_day": self.events_per_day,
            "last_event_at": self.last_event_at,
        }


@dataclass
class NeuronPatternsV1:
    """Neuron-specific patterns."""
    patterns: list[NeuronPatternEntryV1]
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
class BrainEffectivenessMetricsV1:
    """Brain effectiveness metrics."""
    total_neurons: int
    total_events: int
    activation_rate: float
    evaluation_rate: float
    growth_rate: float
    prune_rate: float
    avg_events_per_neuron: float
    zones_with_activity: int
    layers_active: list[str]
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_neurons": self.total_neurons,
            "total_events": self.total_events,
            "activation_rate": self.activation_rate,
            "evaluation_rate": self.evaluation_rate,
            "growth_rate": self.growth_rate,
            "prune_rate": self.prune_rate,
            "avg_events_per_neuron": self.avg_events_per_neuron,
            "zones_with_activity": self.zones_with_activity,
            "layers_active": self.layers_active,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class BrainAnalyticsSummaryV1:
    """Brain analytics summary."""
    history: NeuronHistoryV1 | None
    patterns: NeuronPatternsV1 | None
    effectiveness: BrainEffectivenessMetricsV1 | None
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


class BrainAnalyticsStore:
    """SQLite-backed brain/neuron analytics store."""

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
                CREATE TABLE IF NOT EXISTS neuron_events (
                    event_id TEXT PRIMARY KEY,
                    neuron_id TEXT,
                    zone_id TEXT,
                    layer TEXT,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_neuron_events_neuron_id
                    ON neuron_events(neuron_id);
                CREATE INDEX IF NOT EXISTS idx_neuron_events_timestamp
                    ON neuron_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_neuron_events_type
                    ON neuron_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_neuron_events_layer
                    ON neuron_events(layer);
                CREATE INDEX IF NOT EXISTS idx_neuron_events_zone
                    ON neuron_events(zone_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self) -> int:
        """Get next revision number."""
        self._revision += 1
        return self._revision

    def add_neuron_event(
        self,
        event_id: str,
        neuron_id: str | None,
        zone_id: str | None,
        layer: NeuronLayer | None,
        event_type: NeuronEventType,
        metadata: dict[str, Any] | None = None,
    ) -> NeuronEventV1:
        """Record a neuron event."""
        timestamp = time.time()
        revision = self._get_next_revision()

        entry = NeuronEventV1(
            event_id=event_id,
            neuron_id=neuron_id,
            zone_id=zone_id,
            layer=layer,
            event_type=event_type,
            timestamp=timestamp,
            revision=revision,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO neuron_events
                (event_id, neuron_id, zone_id, layer, event_type,
                 timestamp, revision, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.neuron_id,
                    entry.zone_id,
                    entry.layer.value if entry.layer else None,
                    entry.event_type.value,
                    entry.timestamp,
                    entry.revision,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    def build_neuron_history(
        self,
        neuron_id: str | None = None,
        zone_id: str | None = None,
        layer: NeuronLayer | None = None,
        event_type: NeuronEventType | None = None,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        limit: int = 100,
        since_revision: int | None = None,
    ) -> NeuronHistoryV1:
        """Build neuron history with filters."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM neuron_events WHERE 1=1"
            params: list[Any] = []

            if neuron_id:
                query += " AND neuron_id = ?"
                params.append(neuron_id)
            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if layer:
                query += " AND layer = ?"
                params.append(layer.value)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
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
                "SELECT MAX(revision) FROM neuron_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        events = []
        for row in rows:
            events.append(
                NeuronEventV1(
                    event_id=row[0],
                    neuron_id=row[1],
                    zone_id=row[2],
                    layer=NeuronLayer(row[3]) if row[3] else None,
                    event_type=NeuronEventType(row[4]),
                    timestamp=row[5],
                    revision=row[6],
                    metadata=json.loads(row[7]) if row[7] else {},
                )
            )

        return NeuronHistoryV1(
            events=list(reversed(events)),
            total_count=total_count,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            revision=max_revision,
        )

    def build_neuron_patterns(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> NeuronPatternsV1:
        """Build neuron-specific patterns by zone and layer."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    zone_id,
                    layer,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event_type = 'activated' THEN 1 ELSE 0 END) as activation_count,
                    SUM(CASE WHEN event_type = 'evaluated' THEN 1 ELSE 0 END) as evaluation_count,
                    SUM(CASE WHEN event_type = 'context_updated' THEN 1 ELSE 0 END) as context_update_count,
                    SUM(CASE WHEN event_type = 'state_changed' THEN 1 ELSE 0 END) as state_change_count,
                    SUM(CASE WHEN event_type IN ('graph_grown', 'node_added', 'edge_added') THEN 1 ELSE 0 END) as growth_count,
                    SUM(CASE WHEN event_type = 'pruned' THEN 1 ELSE 0 END) as prune_count,
                    MAX(timestamp) as last_event_at
                FROM neuron_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " GROUP BY zone_id, layer"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM neuron_events"
            ).fetchone()[0] or 0

            patterns = []
            for row in rows:
                zone_id, layer, total, activations, evaluations, context_updates, state_changes, growth, prunes, last_ts = row

                total = total or 0
                activations = activations or 0
                evaluations = evaluations or 0
                context_updates = context_updates or 0
                state_changes = state_changes or 0
                growth = growth or 0
                prunes = prunes or 0

                if total > 1 and last_ts:
                    first_ts = conn.execute(
                        "SELECT MIN(timestamp) FROM neuron_events WHERE zone_id = ? AND layer = ? AND timestamp >= ?",
                        (zone_id, layer, cutoff),
                    ).fetchone()[0]
                    if first_ts and last_ts > first_ts:
                        days_span = max(1, (last_ts - first_ts) / (24 * 60 * 60))
                        freq = total / days_span
                    else:
                        freq = 0.0
                else:
                    freq = 0.0

                patterns.append(
                    NeuronPatternEntryV1(
                        zone_id=zone_id,
                        zone_name=None,
                        layer=NeuronLayer(layer) if layer else None,
                        total_events=total,
                        activation_count=activations,
                        evaluation_count=evaluations,
                        context_update_count=context_updates,
                        state_change_count=state_changes,
                        growth_count=growth,
                        prune_count=prunes,
                        events_per_day=freq,
                        last_event_at=last_ts,
                    )
                )

            return NeuronPatternsV1(
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
    ) -> BrainEffectivenessMetricsV1:
        """Calculate brain effectiveness metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    COUNT(DISTINCT neuron_id) as total_neurons,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event_type = 'activated' THEN 1 ELSE 0 END) as activations,
                    SUM(CASE WHEN event_type = 'evaluated' THEN 1 ELSE 0 END) as evaluations,
                    SUM(CASE WHEN event_type IN ('graph_grown', 'node_added', 'edge_added') THEN 1 ELSE 0 END) as growth,
                    SUM(CASE WHEN event_type = 'pruned' THEN 1 ELSE 0 END) as prunes,
                    COUNT(DISTINCT zone_id) as zones_with_activity
                FROM neuron_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            row = conn.execute(query, params).fetchone()
            (
                total_neurons,
                total_events,
                activations,
                evaluations,
                growth,
                prunes,
                zones_with_activity,
            ) = row

            total_neurons = total_neurons or 0
            total_events = total_events or 0
            activations = activations or 0
            evaluations = evaluations or 0
            growth = growth or 0
            prunes = prunes or 0
            zones_with_activity = zones_with_activity or 0

            activation_rate = (activations / total_events) if total_events > 0 else 0.0
            evaluation_rate = (evaluations / total_events) if total_events > 0 else 0.0
            growth_rate = (growth / total_events) if total_events > 0 else 0.0
            prune_rate = (prunes / total_events) if total_events > 0 else 0.0
            avg_events_per_neuron = (total_events / total_neurons) if total_neurons > 0 else 0.0

            # Get active layers
            layer_query = """
                SELECT DISTINCT layer FROM neuron_events
                WHERE timestamp >= ?
            """
            layer_params: list[Any] = [cutoff]
            if since_revision:
                layer_query += " AND revision > ?"
                layer_params.append(since_revision)

            layers_active = [row[0] for row in conn.execute(layer_query, layer_params) if row[0]]

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM neuron_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        return BrainEffectivenessMetricsV1(
            total_neurons=total_neurons,
            total_events=total_events,
            activation_rate=activation_rate,
            evaluation_rate=evaluation_rate,
            growth_rate=growth_rate,
            prune_rate=prune_rate,
            avg_events_per_neuron=avg_events_per_neuron,
            zones_with_activity=zones_with_activity,
            layers_active=layers_active,
            revision=max_revision,
            generated_at=time.time(),
        )

    def build_summary(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> BrainAnalyticsSummaryV1:
        """Build complete brain analytics summary."""
        history = self.build_neuron_history(
            from_timestamp=time.time() - (days_lookback * 24 * 60 * 60),
            limit=50,
            since_revision=since_revision,
        )
        patterns = self.build_neuron_patterns(
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

        return BrainAnalyticsSummaryV1(
            history=history,
            patterns=patterns,
            effectiveness=effectiveness,
            revision=max_revision,
            generated_at=time.time(),
        )
