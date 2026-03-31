"""Tests for Brain Read Model v2 — Unified brain growth and neuron activity."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.core.brain_read_model import (
    BrainActivitySnapshot,
    BrainGraphGrowth,
    NeuronSnapshot,
    build_brain_activity_snapshot,
    get_brain_summary,
    feed_brain,
    update_graph_growth_snapshot,
    reset_brain_state,
)


class TestNeuronSnapshot:
    """Tests for NeuronSnapshot dataclass."""

    def test_create_neuron_snapshot(self) -> None:
        """Test creating a neuron snapshot."""
        snap = NeuronSnapshot(
            name="context.presence",
            neuron_type="context",
            value=0.85,
            active=True,
            confidence=0.92,
        )
        
        assert snap.name == "context.presence"
        assert snap.neuron_type == "context"
        assert snap.value == 0.85
        assert snap.active is True
        assert snap.confidence == 0.92

    def test_neuron_snapshot_to_dict(self) -> None:
        """Test neuron snapshot serialization."""
        snap = NeuronSnapshot(
            name="mood.stress",
            neuron_type="mood",
            value=0.3,
            active=False,
            confidence=0.75,
            last_update="2026-03-31T10:00:00Z",
            trigger_count=5,
        )
        
        data = snap.to_dict()
        
        assert data["name"] == "mood.stress"
        assert data["type"] == "mood"
        assert data["value"] == 0.3
        assert data["active"] is False
        assert data["confidence"] == 0.75
        assert data["trigger_count"] == 5


class TestBrainGraphGrowth:
    """Tests for BrainGraphGrowth dataclass."""

    def test_create_graph_growth(self) -> None:
        """Test creating brain graph growth snapshot."""
        growth = BrainGraphGrowth(
            total_nodes=150,
            total_edges=320,
            new_nodes_since_last=5,
            new_edges_since_last=12,
            nodes_by_kind={"entity": 80, "zone": 10, "concept": 60},
            edges_by_type={"relates_to": 200, "contains": 120},
        )
        
        assert growth.total_nodes == 150
        assert growth.total_edges == 320
        assert growth.new_nodes_since_last == 5
        assert growth.nodes_by_kind["entity"] == 80

    def test_graph_growth_to_dict(self) -> None:
        """Test graph growth serialization."""
        growth = BrainGraphGrowth(
            total_nodes=100,
            total_edges=200,
            top_active_nodes=[
                {"id": "entity.light.wohnzimmer", "score": 0.95},
                {"id": "zone.wohnzimmer", "score": 0.88},
            ],
            graph_version=5,
        )
        
        data = growth.to_dict()
        
        assert data["total_nodes"] == 100
        assert data["top_active_nodes"][0]["id"] == "entity.light.wohnzimmer"
        assert data["graph_version"] == 5


class TestBrainActivitySnapshot:
    """Tests for BrainActivitySnapshot dataclass."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_brain_state()

    def test_create_brain_snapshot(self) -> None:
        """Test creating brain activity snapshot."""
        snapshot = BrainActivitySnapshot(
            graph=BrainGraphGrowth(total_nodes=50, total_edges=100),
            context_neurons=[
                NeuronSnapshot("context.presence", "context", 0.8, True, 0.9),
            ],
            state_neurons=[
                NeuronSnapshot("state.energy", "state", 0.6, True, 0.75),
            ],
            mood_neurons=[
                NeuronSnapshot("mood.relaxed", "mood", 0.7, True, 0.85),
            ],
            dominant_mood="relaxed",
            mood_confidence=0.85,
        )
        
        assert snapshot.graph.total_nodes == 50
        assert len(snapshot.context_neurons) == 1
        assert len(snapshot.state_neurons) == 1
        assert len(snapshot.mood_neurons) == 1
        assert snapshot.dominant_mood == "relaxed"

    def test_brain_snapshot_to_dict(self) -> None:
        """Test full brain snapshot serialization."""
        snapshot = BrainActivitySnapshot(
            graph=BrainGraphGrowth(
                total_nodes=75,
                total_edges=150,
                nodes_by_kind={"entity": 50, "zone": 5},
            ),
            context_neurons=[
                NeuronSnapshot("context.time", "context", 0.5, False, 0.6),
            ],
            dominant_mood="focused",
            mood_confidence=0.7,
        )
        
        data = snapshot.to_dict()
        
        assert "generated_at" in data
        assert data["graph"]["total_nodes"] == 75
        assert len(data["neurons"]["context"]) == 1
        assert data["dominant_mood"] == "focused"
        assert data["mood_confidence"] == 0.7


class TestBrainReadModelAPI:
    """Tests for brain read model public API."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_brain_state()

    def test_feed_brain_event(self) -> None:
        """Test feeding events into brain read model."""
        event = {
            "entity_id": "light.wohnzimmer",
            "domain": "light",
            "kind": "state_changed",
            "ts": 1711882800000,
            "new_state": "on",
        }
        
        feed_brain(event)
        
        # Verify event was recorded
        from copilot_core.core.brain_read_model import _brain_state
        assert len(_brain_state["recent_events"]) >= 1
        last_event = _brain_state["recent_events"][-1]
        assert last_event["entity_id"] == "light.wohnzimmer"
        assert last_event["state"] == "on"

    def test_feed_brain_event_minimal(self) -> None:
        """Test feeding minimal event."""
        event = {
            "entity_id": "sensor.kitchen_temp",
            "domain": "sensor",
            "kind": "state_changed",
        }
        
        feed_brain(event)
        
        from copilot_core.core.brain_read_model import _brain_state
        assert len(_brain_state["recent_events"]) >= 1

    def test_update_graph_growth_snapshot(self) -> None:
        """Test updating graph growth snapshot."""
        update_graph_growth_snapshot(
            total_nodes=100,
            total_edges=250,
            nodes_by_kind={"entity": 60, "zone": 8, "concept": 32},
            edges_by_type={"relates_to": 150, "contains": 100},
            top_active_nodes=[
                {"id": "entity.light.main", "score": 0.9},
            ],
        )
        
        from copilot_core.core.brain_read_model import _brain_state
        assert _brain_state["last_graph_nodes"] == 100
        assert _brain_state["last_graph_edges"] == 250
        assert _brain_state["_growth_new_nodes"] == 100  # First update, so all are new

    def test_build_snapshot_with_mock_services(self) -> None:
        """Test building brain snapshot with mock services."""
        class MockGraphService:
            def get_stats(self):
                return {"nodes_count": 80, "edges_count": 160}
            
            def get_graph_state(self, limit_nodes=1000, limit_edges=2000):
                return {
                    "nodes": [
                        {"id": "entity.1", "kind": "entity", "score": 0.8},
                        {"id": "zone.1", "kind": "zone", "score": 0.9},
                    ],
                    "edges": [
                        {"type": "relates_to"},
                        {"type": "contains"},
                    ],
                }
        
        class MockNeuronManager:
            def get_all_neurons(self):
                return {
                    "context.presence": type('obj', (object,), {
                        "state": type('obj', (object,), {
                            "value": 0.75, "active": True, "confidence": 0.85,
                            "last_update": "2026-03-31T10:00:00Z",
                            "last_trigger": "2026-03-31T09:55:00Z",
                            "trigger_count": 10,
                        })(),
                    })(),
                    "mood.relaxed": type('obj', (object,), {
                        "state": type('obj', (object,), {
                            "value": 0.6, "active": True, "confidence": 0.7,
                            "last_update": "2026-03-31T10:00:00Z",
                            "last_trigger": None,
                            "trigger_count": 3,
                        })(),
                    })(),
                }
            
            def get_mood_summary(self):
                return {"mood": "relaxed", "confidence": 0.7}
        
        snapshot = build_brain_activity_snapshot(
            brain_graph_service=MockGraphService(),
            neuron_manager=MockNeuronManager(),
        )
        
        assert snapshot.graph.total_nodes == 80
        assert snapshot.graph.total_edges == 160
        assert len(snapshot.context_neurons) == 1
        assert len(snapshot.mood_neurons) == 1
        assert snapshot.dominant_mood == "relaxed"

    def test_get_brain_summary_alias(self) -> None:
        """Test get_brain_summary() as alias for snapshot builder."""
        reset_brain_state()
        
        summary = get_brain_summary()
        
        assert "generated_at" in summary
        assert "graph" in summary
        assert "neurons" in summary


class TestBrainReadModelIntegration:
    """Integration tests for brain read model."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        reset_brain_state()

    def test_full_pipeline_feed_and_snapshot(self) -> None:
        """Test full pipeline: feed events, update graph, build snapshot."""
        # Feed some events
        for i in range(5):
            feed_brain({
                "entity_id": f"sensor.sensor_{i}",
                "domain": "sensor",
                "kind": "state_changed",
                "ts": 1711882800000 + i * 1000,
                "new_state": str(i * 10),
            })
        
        # Update graph growth
        update_graph_growth_snapshot(
            total_nodes=50,
            total_edges=100,
            nodes_by_kind={"entity": 30, "zone": 5, "concept": 15},
        )
        
        # Build snapshot
        snapshot = build_brain_activity_snapshot()
        
        assert len(snapshot.recent_events) == 5
        assert snapshot.graph.total_nodes == 50
        assert snapshot.graph.total_edges == 100
        assert snapshot.graph.nodes_by_kind["entity"] == 30

    def test_event_bounding(self) -> None:
        """Test that recent events are bounded to max_recent_events."""
        from copilot_core.core.brain_read_model import _brain_state
        
        # Feed more than max_recent_events (default 50)
        for i in range(60):
            feed_brain({
                "entity_id": f"sensor.sensor_{i}",
                "domain": "sensor",
                "kind": "state_changed",
            })
        
        # Should be bounded to max_recent_events
        assert len(_brain_state["recent_events"]) <= _brain_state["max_recent_events"]
