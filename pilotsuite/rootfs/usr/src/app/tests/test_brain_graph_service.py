#!/usr/bin/env python3
"""
Tests for brain graph service layer.
"""

import time
import tempfile
import os
import pytest
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.store import BrainGraphStore as GraphStore


def test_service_initialization():
    """Test service initialization with custom store."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        assert service.store == store
        assert service.node_half_life_hours == 24.0
        assert service.edge_half_life_hours == 12.0


def test_touch_node_new():
    """Test creating a new node via touch_node."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Touch new node
        node = service.touch_node(
            node_id="test:new",
            label="New Node",
            kind="entity",
            domain="light",
            delta=2.0,
            meta_patch={"brightness": 80}
        )
        
        assert node.id == "test:new"
        assert node.label == "New Node"
        assert node.kind == "entity"
        assert node.domain == "light"
        assert node.score == 2.0
        assert node.meta["brightness"] == 80
        
        # Verify it's stored
        stored_node = store.get_node("test:new")
        assert stored_node is not None
        assert stored_node.label == "New Node"


def test_touch_node_update():
    """Test updating an existing node."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Create initial node
        node1 = service.touch_node(
            node_id="test:update",
            label="Original",
            kind="entity",
            domain="sensor",
            delta=1.0
        )
        
        # Update with new score and metadata
        node2 = service.touch_node(
            node_id="test:update",
            delta=2.0,
            meta_patch={"new_field": "value"}
        )
        
        assert node2.score == pytest.approx(3.0, abs=1e-6)  # 1.0 + 2.0
        assert node2.label == "Original"  # Unchanged
        assert node2.meta["new_field"] == "value"
        
        # Verify persisted
        stored = store.get_node("test:update")
        assert stored is not None
        assert stored.meta["new_field"] == "value"


def test_touch_edge_new():
    """Test creating a new edge via touch_edge."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Touch edge
        edge = service.touch_edge(
            from_node="node_a",
            to_node="node_b",
            edge_type="relates_to",
            delta=0.5
        )
        
        assert edge.from_node == "node_a"
        assert edge.to_node == "node_b"
        assert edge.edge_type == "relates_to"
        assert edge.weight == 0.5
        
        # Verify stored
        edges = store.get_edges(from_node="node_a")
        assert len(edges) == 1
        assert edges[0].to_node == "node_b"


def test_link_shortcut():
    """Test the link() convenience method."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Use link() shortcut
        edge = service.link(
            from_node="node_1",
            to_node="node_2",
            edge_type="connects",
            initial_weight=0.8
        )
        
        assert edge.from_node == "node_1"
        assert edge.to_node == "node_2"
        
        # Verify it was actually created
        stored_edges = store.get_edges(from_node="node_1")
        assert len(stored_edges) == 1
        assert stored_edges[0].weight == 0.8


def test_get_graph_state_basic():
    """Test basic graph state retrieval."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Add a few nodes
        service.touch_node("node_1", label="Node 1", kind="entity", domain="light", delta=1.0)
        service.touch_node("node_2", label="Node 2", kind="entity", domain="sensor", delta=1.0)
        service.link("node_1", "relates_to", "node_2", 0.5)
        
        # Get state
        state = service.get_graph_state()
        
        assert "nodes" in state
        assert "edges" in state
        assert len(state["nodes"]) >= 2
        assert len(state["edges"]) >= 1


def test_get_graph_state_filtered():
    """Test graph state with filters."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Add nodes of different kinds
        service.touch_node("entity_1", label="Entity 1", kind="entity", domain="light", delta=1.0)
        service.touch_node("entity_2", label="Entity 2", kind="entity", domain="sensor", delta=1.0)
        service.touch_node("concept_1", label="Concept", kind="concept", delta=1.0)
        
        # Filter by kind
        state = service.get_graph_state(kinds=["entity"])
        
        assert len(state["nodes"]) == 2
        assert all(n["kind"] == "entity" for n in state["nodes"])

        # Filter by domain
        state = service.get_graph_state(domains=["light"])
        assert len(state["nodes"]) == 1
        assert state["nodes"][0]["domain"] == "light"


def test_get_graph_state_neighborhood():
    """Test neighborhood graph state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Create connected nodes
        service.touch_node("center", label="Center", kind="entity", domain="light", delta=1.0)
        service.touch_node("neighbor_1", label="Neighbor 1", kind="entity", domain="sensor", delta=1.0)
        service.touch_node("neighbor_2", label="Neighbor 2", kind="entity", domain="sensor", delta=1.0)
        service.link("center", "relates_to", "neighbor_1", 0.5)
        service.link("center", "relates_to", "neighbor_2", 0.5)
        
        # Get neighborhood
        state = service.get_graph_state(center_node="center", hops=1)
        
        assert len(state["nodes"]) >= 3  # center + 2 neighbors
        assert len(state["edges"]) >= 2  # 2 edges from center


def test_get_stats():
    """Test graph statistics."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Add some nodes
        for i in range(5):
            service.touch_node(f"node_{i}", label=f"Node {i}", kind="entity", domain="light", delta=1.0)
        
        # Get stats
        stats = service.get_stats()
        
        assert "nodes" in stats
        assert "edges" in stats
        assert stats["nodes"] == 5


def test_ha_state_change_processing():
    """Test processing Home Assistant state change events."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Mock state change event
        event_data = {
            "event_type": "state_changed",
            "data": {
                "entity_id": "light.kitchen",
                "old_state": {"state": "off"},
                "new_state": {"state": "on", "attributes": {"brightness": 100}}
            }
        }
        
        # Process event
        service.process_ha_event(event_data)
        
        # Check that entity node was created/updated
        node = store.get_node("ha.entity:light.kitchen")
        assert node is not None
        assert "light" in node.label.lower() or "kitchen" in node.label.lower()
        
        # Check score boost
        assert node.score > 0


def test_ha_service_call_processing():
    """Test processing Home Assistant service call events."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        service = BrainGraphService(store=store)
        
        # Mock service call event
        event_data = {
            "event_type": "call_service",
            "data": {
                "domain": "light",
                "service": "turn_on",
                "service_data": {
                    "entity_id": ["light.kitchen", "light.living_room"]
                },
                "origin": "user"
            }
        }
        
        # Process event
        service.process_ha_event(event_data)
        
        # Check that service node was created
        service_node = store.get_node("ha.service:light.turn_on")
        assert service_node is not None
        assert service_node.kind in ("concept", "service")
        
        # Check that entity nodes were created
        kitchen_node = store.get_node("ha.entity:light.kitchen")
        living_node = store.get_node("ha.entity:light.living_room")
        assert kitchen_node is not None
        assert living_node is not None
        assert kitchen_node.kind in ("entity", "light")
        assert living_node.kind in ("entity", "light")
        
        # Check that affects edges were created
        edges = store.get_edges(from_node="ha.service:light.turn_on")
        assert len(edges) >= 2
