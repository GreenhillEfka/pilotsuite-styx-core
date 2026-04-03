"""Brain/Neuron Analytics Contract Tests — Slice 61."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from copilot_core.analytics.brain_analytics import (
    BrainAnalyticsStore,
    BrainEffectivenessMetricsV1,
    NeuronEventV1,
    NeuronEventType,
    NeuronHistoryV1,
    NeuronLayer,
    NeuronPatternEntryV1,
    NeuronPatternsV1,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "brain_analytics.db"


@pytest.fixture
def store(temp_db: Path) -> BrainAnalyticsStore:
    """Create analytics store with temp database."""
    return BrainAnalyticsStore(temp_db)


class TestNeuronEventV1:
    """Test NeuronEventV1 dataclass."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event = NeuronEventV1(
            event_id="evt-001",
            neuron_id="neuron-001",
            zone_id="zone-living",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
            timestamp=time.time(),
            revision=1,
        )

        assert event.event_id == "evt-001"
        assert event.neuron_id == "neuron-001"
        assert event.zone_id == "zone-living"
        assert event.layer == NeuronLayer.CONTEXT
        assert event.event_type == NeuronEventType.ACTIVATED

    def test_event_to_dict(self) -> None:
        """Test event serialization."""
        event = NeuronEventV1(
            event_id="evt-002",
            neuron_id="neuron-002",
            zone_id="zone-bedroom",
            layer=NeuronLayer.STATE,
            event_type=NeuronEventType.EVALUATED,
            timestamp=1234567890.0,
            revision=1,
            metadata={"test": "value"},
        )

        d = event.to_dict()
        assert d["event_id"] == "evt-002"
        assert d["neuron_id"] == "neuron-002"
        assert d["zone_id"] == "zone-bedroom"
        assert d["layer"] == "state"
        assert d["event_type"] == "evaluated"
        assert d["metadata"] == {"test": "value"}


class TestBrainAnalyticsStore:
    """Test BrainAnalyticsStore operations."""

    def test_add_neuron_event(self, store: BrainAnalyticsStore) -> None:
        """Test adding a neuron event."""
        entry = store.add_neuron_event(
            event_id="evt-001",
            neuron_id="neuron-001",
            zone_id="zone-living",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
        )

        assert entry.event_id == "evt-001"
        assert entry.neuron_id == "neuron-001"
        assert entry.revision == 1

    def test_add_neuron_event_no_neuron(self, store: BrainAnalyticsStore) -> None:
        """Test adding event without neuron_id (graph-level event)."""
        entry = store.add_neuron_event(
            event_id="evt-002",
            neuron_id=None,
            zone_id=None,
            layer=None,
            event_type=NeuronEventType.GRAPH_GROWN,
        )

        assert entry.event_id == "evt-002"
        assert entry.neuron_id is None
        assert entry.revision == 1

    def test_revision_increments(self, store: BrainAnalyticsStore) -> None:
        """Test revision increments with each event."""
        store.add_neuron_event(
            event_id=str(uuid.uuid4()),
            neuron_id="neuron-001",
            zone_id="zone-1",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
        )

        entry2 = store.add_neuron_event(
            event_id=str(uuid.uuid4()),
            neuron_id="neuron-002",
            zone_id="zone-2",
            layer=NeuronLayer.STATE,
            event_type=NeuronEventType.EVALUATED,
        )

        assert entry2.revision == 2

    def test_build_neuron_history(self, store: BrainAnalyticsStore) -> None:
        """Test building neuron history."""
        for i in range(5):
            store.add_neuron_event(
                event_id=f"evt-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-living",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        history = store.build_neuron_history(limit=10)

        assert isinstance(history, NeuronHistoryV1)
        assert history.total_count == 5
        assert len(history.events) == 5
        assert history.revision == 5

    def test_build_neuron_history_filtered_by_neuron(self, store: BrainAnalyticsStore) -> None:
        """Test filtering history by neuron."""
        store.add_neuron_event(
            event_id="evt-001",
            neuron_id="neuron-001",
            zone_id="zone-living",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
        )
        store.add_neuron_event(
            event_id="evt-002",
            neuron_id="neuron-001",
            zone_id="zone-living",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.EVALUATED,
        )
        store.add_neuron_event(
            event_id="evt-003",
            neuron_id="neuron-002",
            zone_id="zone-bedroom",
            layer=NeuronLayer.STATE,
            event_type=NeuronEventType.ACTIVATED,
        )

        history = store.build_neuron_history(neuron_id="neuron-001")

        assert history.total_count == 2
        assert all(e.neuron_id == "neuron-001" for e in history.events)

    def test_build_neuron_history_with_revision_filter(self, store: BrainAnalyticsStore) -> None:
        """Test filtering history by revision."""
        for i in range(5):
            store.add_neuron_event(
                event_id=f"evt-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-living",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        history = store.build_neuron_history(since_revision=3)

        assert history.total_count == 2
        assert all(e.revision > 3 for e in history.events)

    def test_build_neuron_patterns(self, store: BrainAnalyticsStore) -> None:
        """Test building neuron patterns."""
        for i in range(10):
            store.add_neuron_event(
                event_id=f"evt-living-{i:03d}",
                neuron_id=f"neuron-living-{i:03d}",
                zone_id="zone-living",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        for i in range(5):
            store.add_neuron_event(
                event_id=f"evt-bedroom-{i:03d}",
                neuron_id=f"neuron-bedroom-{i:03d}",
                zone_id="zone-bedroom",
                layer=NeuronLayer.STATE,
                event_type=NeuronEventType.EVALUATED,
            )

        patterns = store.build_neuron_patterns()

        assert isinstance(patterns, NeuronPatternsV1)
        assert patterns.total_entries == 2
        assert len(patterns.patterns) == 2

    def test_build_neuron_patterns_with_mixed_events(self, store: BrainAnalyticsStore) -> None:
        """Test patterns with mixed event types."""
        for i in range(8):
            store.add_neuron_event(
                event_id=f"evt-activated-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-kitchen",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        for i in range(6):
            store.add_neuron_event(
                event_id=f"evt-evaluated-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-kitchen",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.EVALUATED,
            )

        for i in range(2):
            store.add_neuron_event(
                event_id=f"evt-pruned-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-kitchen",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.PRUNED,
            )

        patterns = store.build_neuron_patterns()

        kitchen = next(p for p in patterns.patterns if p.zone_id == "zone-kitchen")
        assert kitchen.total_events == 16
        assert kitchen.activation_count == 8
        assert kitchen.evaluation_count == 6
        assert kitchen.prune_count == 2

    def test_get_effectiveness_metrics(self, store: BrainAnalyticsStore) -> None:
        """Test effectiveness metrics calculation."""
        for i in range(70):
            store.add_neuron_event(
                event_id=f"evt-activated-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id=f"zone-{i % 5}",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        for i in range(50):
            store.add_neuron_event(
                event_id=f"evt-evaluated-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id=f"zone-{i % 5}",
                layer=NeuronLayer.STATE,
                event_type=NeuronEventType.EVALUATED,
            )

        for i in range(10):
            store.add_neuron_event(
                event_id=f"evt-grown-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id=f"zone-{i % 3}",
                layer=NeuronLayer.PERCEPTION,
                event_type=NeuronEventType.GRAPH_GROWN,
            )

        metrics = store.get_effectiveness_metrics()

        assert isinstance(metrics, BrainEffectivenessMetricsV1)
        assert metrics.total_neurons == 70
        assert metrics.total_events == 130
        assert metrics.zones_with_activity == 5
        assert abs(metrics.activation_rate - (70 / 130)) < 0.01
        assert "context" in metrics.layers_active or "state" in metrics.layers_active

    def test_build_summary(self, store: BrainAnalyticsStore) -> None:
        """Test building complete summary."""
        for i in range(5):
            store.add_neuron_event(
                event_id=f"evt-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-living",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        summary = store.build_summary()

        assert summary.history is not None
        assert summary.patterns is not None
        assert summary.effectiveness is not None
        assert summary.revision == 5

    def test_build_summary_with_revision_filter(self, store: BrainAnalyticsStore) -> None:
        """Test summary with revision filter."""
        for i in range(10):
            store.add_neuron_event(
                event_id=f"evt-{i:03d}",
                neuron_id=f"neuron-{i:03d}",
                zone_id="zone-living",
                layer=NeuronLayer.CONTEXT,
                event_type=NeuronEventType.ACTIVATED,
            )

        summary = store.build_summary(since_revision=7)

        assert summary.history.total_count == 3
        assert summary.revision >= 10


class TestNeuronEventType:
    """Test NeuronEventType enum."""

    def test_all_event_types(self) -> None:
        """Test all event type values."""
        assert NeuronEventType.ACTIVATED.value == "activated"
        assert NeuronEventType.EVALUATED.value == "evaluated"
        assert NeuronEventType.CONTEXT_UPDATED.value == "context_updated"
        assert NeuronEventType.STATE_CHANGED.value == "state_changed"
        assert NeuronEventType.MOOD_UPDATED.value == "mood_updated"
        assert NeuronEventType.GRAPH_GROWN.value == "graph_grown"
        assert NeuronEventType.NODE_ADDED.value == "node_added"
        assert NeuronEventType.EDGE_ADDED.value == "edge_added"
        assert NeuronEventType.PRUNED.value == "pruned"


class TestNeuronLayer:
    """Test NeuronLayer enum."""

    def test_all_layers(self) -> None:
        """Test all layer values."""
        assert NeuronLayer.PERCEPTION.value == "perception"
        assert NeuronLayer.CONTEXT.value == "context"
        assert NeuronLayer.STATE.value == "state"
        assert NeuronLayer.MOOD.value == "mood"
        assert NeuronLayer.DECISION.value == "decision"


class TestNeuronPatternsV1:
    """Test NeuronPatternsV1 serialization."""

    def test_patterns_to_dict(self, store: BrainAnalyticsStore) -> None:
        """Test patterns serialization."""
        store.add_neuron_event(
            event_id="evt-001",
            neuron_id="neuron-001",
            zone_id="zone-test",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
        )

        patterns = store.build_neuron_patterns()
        d = patterns.to_dict()

        assert "patterns" in d
        assert "total_entries" in d
        assert "revision" in d
        assert "generated_at" in d
        assert len(d["patterns"]) == 1


class TestBrainEffectivenessMetricsV1:
    """Test BrainEffectivenessMetricsV1."""

    def test_metrics_to_dict(self, store: BrainAnalyticsStore) -> None:
        """Test metrics serialization."""
        store.add_neuron_event(
            event_id="evt-001",
            neuron_id="neuron-001",
            zone_id="zone-test",
            layer=NeuronLayer.CONTEXT,
            event_type=NeuronEventType.ACTIVATED,
        )

        metrics = store.get_effectiveness_metrics()
        d = metrics.to_dict()

        assert "total_neurons" in d
        assert "total_events" in d
        assert "activation_rate" in d
        assert "evaluation_rate" in d
        assert "growth_rate" in d
        assert "prune_rate" in d
        assert "zones_with_activity" in d
        assert "layers_active" in d
