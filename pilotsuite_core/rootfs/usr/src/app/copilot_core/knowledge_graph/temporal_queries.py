"""Temporal Query Patterns for Knowledge Graph.

Provides time-based querying capabilities for the knowledge graph:
- Time-windowed queries
- Temporal pattern matching
- Sequence detection
- Time-aware entity state queries
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from .models import EdgeType, GraphResult, Node, NodeType

_LOGGER = logging.getLogger(__name__)


# ==================== Temporal Query Types ====================

@dataclass
class TimeWindow:
    """Represents a time window for temporal queries."""
    start: datetime
    end: datetime

    @classmethod
    def from_hours_ago(cls, hours: int) -> "TimeWindow":
        """Create a window from N hours ago until now."""
        now = datetime.now()
        return cls(start=now - timedelta(hours=hours), end=now)

    @classmethod
    def from_minutes_ago(cls, minutes: int) -> "TimeWindow":
        """Create a window from N minutes ago until now."""
        now = datetime.now()
        return cls(start=now - timedelta(minutes=minutes), end=now)

    @classmethod
    def from_days_ago(cls, days: int) -> "TimeWindow":
        """Create a window from N days ago until now."""
        now = datetime.now()
        return cls(start=now - timedelta(days=days), end=now)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass
class TemporalPattern:
    """A pattern that occurs over time."""
    name: str
    entity_ids: list[str]
    sequence: list[str]  # Ordered sequence of states/events
    time_window: TimeWindow
    min_occurrences: int = 1


@dataclass
class TemporalQuery:
    """Base class for temporal queries."""
    query_type: str  # "window", "sequence", "frequency", "trend"
    entity_ids: list[str] = field(default_factory=list)
    time_window: Optional[TimeWindow] = None
    zone_id: Optional[str] = None
    domain: Optional[str] = None


@dataclass
class WindowedQuery(TemporalQuery):
    """Query entity states within a time window."""
    aggregation: str = "raw"  # "raw", "avg", "min", "max", "count"
    granularity_seconds: int = 60


@dataclass
class SequenceQuery(TemporalQuery):
    """Query for detecting event sequences."""
    expected_sequence: list[str]
    max_gap_seconds: int = 300
    allow_partial: bool = False


@dataclass
class FrequencyQuery(TemporalQuery):
    """Query event frequency patterns."""
    min_frequency: int = 1
    max_frequency: Optional[int] = None
    period_seconds: int = 3600


@dataclass
class TrendQuery(TemporalQuery):
    """Query for detecting trends over time."""
    metric: str = "value"
    direction: Optional[str] = None  # "increasing", "decreasing", "stable"
    min_slope: float = 0.0


# ==================== Temporal Query Executor ====================

class TemporalQueryExecutor:
    """
    Executes temporal queries against the knowledge graph.

    Example:
        executor = TemporalQueryExecutor(graph_store, event_store)
        result = executor.query_window(
            entity_ids=["sensor.temperature_living"],
            window=TimeWindow.from_hours_ago(24),
            aggregation="avg",
        )
    """

    def __init__(self, graph_store: Any, event_store: Optional[Any] = None) -> None:
        self._store = graph_store
        self._event_store = event_store

    def query_window(
        self,
        entity_ids: list[str],
        window: TimeWindow,
        aggregation: str = "raw",
        granularity_seconds: int = 60,
    ) -> GraphResult:
        """
        Query entity states within a time window.

        Args:
            entity_ids: List of entity IDs to query
            window: Time window for the query
            aggregation: Aggregation type ("raw", "avg", "min", "max", "count")
            granularity_seconds: Data granularity in seconds

        Returns:
            GraphResult with temporal data in properties
        """
        if not self._event_store:
            _LOGGER.warning("No event store available for temporal queries")
            return GraphResult(nodes=[], edges=[])

        nodes = []
        edges = []

        for entity_id in entity_ids:
            # Get the entity node
            entity_node = self._store.get_node(entity_id)
            if not entity_node:
                continue

            # Query events from event store
            try:
                events = self._event_store.get_events(
                    entity_id=entity_id,
                    start_time=window.start,
                    end_time=window.end,
                )

                # Apply aggregation
                if aggregation == "raw":
                    values = [e.get("value") for e in events if "value" in e]
                elif aggregation == "avg":
                    values = [self._aggregate_events(events, "avg", granularity_seconds)]
                elif aggregation == "min":
                    values = [self._aggregate_events(events, "min", granularity_seconds)]
                elif aggregation == "max":
                    values = [self._aggregate_events(events, "max", granularity_seconds)]
                elif aggregation == "count":
                    values = [len(events)]
                else:
                    values = []

                # Store aggregated data in node properties
                entity_node.properties["temporal_data"] = {
                    "window": {
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                    "aggregation": aggregation,
                    "values": values,
                    "event_count": len(events),
                }
                nodes.append(entity_node)

            except Exception as e:
                _LOGGER.warning("Failed to query events for %s: %s", entity_id, e)

        return GraphResult(
            nodes=nodes,
            edges=edges,
            confidence=1.0 if nodes else 0.0,
            sources=["temporal_window_query"],
        )

    def detect_sequence(
        self,
        entity_ids: list[str],
        expected_sequence: list[str],
        window: TimeWindow,
        max_gap_seconds: int = 300,
    ) -> GraphResult:
        """
        Detect if an expected sequence of states occurred.

        Args:
            entity_ids: Entities to monitor
            expected_sequence: Expected sequence of states
            window: Time window to search
            max_gap_seconds: Maximum gap between sequence steps

        Returns:
            GraphResult with sequence detection results
        """
        if not self._event_store:
            return GraphResult(nodes=[], edges=[])

        detected_sequences = []

        for entity_id in entity_ids:
            events = self._event_store.get_events(
                entity_id=entity_id,
                start_time=window.start,
                end_time=window.end,
            )

            # Extract state sequence
            states = [(e.get("timestamp"), e.get("value")) for e in events if "value" in e]
            states.sort(key=lambda x: x[0] if x[0] else 0)

            # Try to match expected sequence
            matches = self._match_sequence(states, expected_sequence, max_gap_seconds)
            if matches:
                detected_sequences.append({
                    "entity_id": entity_id,
                    "matches": matches,
                })

        # Create result nodes
        nodes = []
        edges = []

        for seq_result in detected_sequences:
            entity_node = self._store.get_node(seq_result["entity_id"])
            if entity_node:
                entity_node.properties["sequence_detected"] = True
                entity_node.properties["sequence_matches"] = seq_result["matches"]
                nodes.append(entity_node)

        return GraphResult(
            nodes=nodes,
            edges=edges,
            confidence=1.0 if nodes else 0.0,
            sources=["temporal_sequence_query"],
        )

    def query_frequency(
        self,
        entity_ids: list[str],
        window: TimeWindow,
        period_seconds: int = 3600,
        min_frequency: int = 1,
    ) -> GraphResult:
        """
        Query event frequency patterns.

        Args:
            entity_ids: Entities to analyze
            window: Time window for analysis
            period_seconds: Period for frequency calculation
            min_frequency: Minimum frequency threshold

        Returns:
            GraphResult with frequency data
        """
        if not self._event_store:
            return GraphResult(nodes=[], edges=[])

        nodes = []

        for entity_id in entity_ids:
            events = self._event_store.get_events(
                entity_id=entity_id,
                start_time=window.start,
                end_time=window.end,
            )

            # Calculate frequency per period
            if events:
                total_duration = window.duration_seconds
                event_count = len(events)
                frequency = (event_count / total_duration) * period_seconds if total_duration > 0 else 0

                if frequency >= min_frequency:
                    entity_node = self._store.get_node(entity_id)
                    if entity_node:
                        entity_node.properties["frequency_analysis"] = {
                            "events_per_period": frequency,
                            "period_seconds": period_seconds,
                            "total_events": event_count,
                            "window_hours": total_duration / 3600,
                        }
                        nodes.append(entity_node)

        return GraphResult(
            nodes=nodes,
            edges=[],
            confidence=1.0 if nodes else 0.0,
            sources=["temporal_frequency_query"],
        )

    def detect_trend(
        self,
        entity_ids: list[str],
        window: TimeWindow,
        metric: str = "value",
        direction: Optional[str] = None,
        min_slope: float = 0.0,
    ) -> GraphResult:
        """
        Detect trends in entity values over time.

        Args:
            entity_ids: Entities to analyze
            window: Time window for trend analysis
            metric: Metric to analyze
            direction: Filter by trend direction ("increasing", "decreasing", "stable")
            min_slope: Minimum slope threshold

        Returns:
            GraphResult with trend analysis
        """
        if not self._event_store:
            return GraphResult(nodes=[], edges=[])

        nodes = []

        for entity_id in entity_ids:
            events = self._event_store.get_events(
                entity_id=entity_id,
                start_time=window.start,
                end_time=window.end,
            )

            if len(events) < 2:
                continue

            # Extract time series
            values = []
            timestamps = []
            for e in events:
                if metric in e and e.get("timestamp"):
                    values.append(e[metric])
                    timestamps.append(e["timestamp"])

            if len(values) < 2:
                continue

            # Calculate linear regression slope
            slope = self._calculate_slope(timestamps, values)

            # Determine trend direction
            if abs(slope) < min_slope:
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"

            # Apply direction filter
            if direction and trend_direction != direction:
                continue

            entity_node = self._store.get_node(entity_id)
            if entity_node:
                entity_node.properties["trend_analysis"] = {
                    "slope": slope,
                    "direction": trend_direction,
                    "data_points": len(values),
                    "window": {
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                }
                nodes.append(entity_node)

        return GraphResult(
            nodes=nodes,
            edges=[],
            confidence=1.0 if nodes else 0.0,
            sources=["temporal_trend_query"],
        )

    def _aggregate_events(
        self,
        events: list[dict],
        agg_type: str,
        granularity_seconds: int,
    ) -> list[dict]:
        """Aggregate events by time buckets."""
        if not events:
            return []

        # Group by time bucket
        buckets: dict[int, list[float]] = {}
        for e in events:
            if "timestamp" in e and "value" in e:
                ts = e["timestamp"]
                bucket = int(ts // granularity_seconds)
                if bucket not in buckets:
                    buckets[bucket] = []
                try:
                    buckets[bucket].append(float(e["value"]))
                except (ValueError, TypeError):
                    pass

        # Calculate aggregations
        result = []
        for bucket, values in sorted(buckets.items()):
            if not values:
                continue

            if agg_type == "avg":
                val = sum(values) / len(values)
            elif agg_type == "min":
                val = min(values)
            elif agg_type == "max":
                val = max(values)
            else:
                val = values[0]

            result.append({
                "bucket": bucket * granularity_seconds,
                "value": val,
                "count": len(values),
            })

        return result

    def _match_sequence(
        self,
        states: list[tuple],
        expected: list[str],
        max_gap_seconds: int,
    ) -> list[dict]:
        """Match expected sequence against actual states."""
        matches = []
        state_idx = 0

        for i, (ts, state) in enumerate(states):
            if state_idx >= len(expected):
                break

            if state == expected[state_idx]:
                match_start = i
                match_states = [(ts, state)]

                # Look for next state in sequence
                for j in range(i + 1, len(states)):
                    ts_next, state_next = states[j]
                    gap = (ts_next - ts) if ts and ts_next else float("inf")

                    if gap > max_gap_seconds:
                        break

                    if state_next == expected[state_idx + 1] if state_idx + 1 < len(expected) else True:
                        match_states.append((ts_next, state_next))
                        state_idx += 1
                        if state_idx >= len(expected):
                            matches.append({
                                "start_time": match_states[0][0],
                                "end_time": match_states[-1][0],
                                "states": [s[1] for s in match_states],
                            })
                            break

            state_idx += 1

        return matches

    def _calculate_slope(self, timestamps: list, values: list) -> float:
        """Calculate linear regression slope."""
        if len(timestamps) < 2 or len(values) < 2:
            return 0.0

        n = min(len(timestamps), len(values))
        x = [float(t) for t in timestamps[:n]]
        y = [float(v) for v in values[:n]]

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator
