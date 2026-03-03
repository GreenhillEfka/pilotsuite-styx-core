"""Tests for Neuron Graph API and Data Structures."""

import pytest
from datetime import datetime, timezone
import time

from copilot_core.api.v1.neuron_graph import (
    NeuronGraph,
    GraphNode,
    GraphEdge,
    NodeMetrics,
    get_neuron_graph,
    reset_neuron_graph,
    get_neuron_connections,
    find_paths
)


class TestNodeMetrics:
    """Tests for NodeMetrics dataclass."""
    
    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = NodeMetrics()
        assert metrics.fire_rate == 0.0
        assert metrics.confidence == 0.0
        assert metrics.avg_value == 0.0
        assert metrics.trend == "stable"
        assert metrics.last_fire_time is None
    
    def test_record_fire(self):
        """Test recording a fire event."""
        metrics = NodeMetrics()
        metrics.record_fire(0.8)
        
        assert metrics.last_fire_time is not None
        assert len(metrics.fire_history) == 1
        assert metrics.fire_rate >= 0.0
    
    def test_update_confidence(self):
        """Test updating confidence score."""
        metrics = NodeMetrics()
        metrics.update_confidence(0.95)
        assert metrics.confidence == 0.95
    
    def test_update_trend_increasing(self):
        """Test trend update for increasing values."""
        metrics = NodeMetrics()
        metrics.update_trend(0.85)
        assert metrics.trend == "increasing"
    
    def test_update_trend_decreasing(self):
        """Test trend update for decreasing values."""
        metrics = NodeMetrics()
        metrics.update_trend(0.15)
        assert metrics.trend == "decreasing"
    
    def test_update_trend_stable(self):
        """Test trend update for stable values."""
        metrics = NodeMetrics()
        metrics.update_trend(0.5)
        assert metrics.trend == "stable"
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = NodeMetrics(
            fire_rate=2.5,
            confidence=0.87,
            avg_value=0.65,
            trend="increasing"
        )
        data = metrics.to_dict()
        
        assert data["fire_rate"] == 2.5
        assert data["confidence"] == 0.87
        assert data["avg_value"] == 0.65
        assert data["trend"] == "increasing"


class TestGraphNode:
    """Tests for GraphNode dataclass."""
    
    def test_create_node(self):
        """Test creating a graph node."""
        node = GraphNode(
            id="context.presence",
            name="Presence",
            neuron_type="context",
            layer=0
        )
        
        assert node.id == "context.presence"
        assert node.name == "Presence"
        assert node.neuron_type == "context"
        assert node.layer == 0
        assert node.active is False
        assert node.value == 0.0
    
    def test_node_to_dict(self):
        """Test node serialization."""
        node = GraphNode(
            id="state.energy_level",
            name="Energy Level",
            neuron_type="state",
            layer=1,
            active=True,
            value=0.75
        )
        
        data = node.to_dict()
        
        assert data["id"] == "state.energy_level"
        assert data["name"] == "Energy Level"
        assert data["active"] is True
        assert data["value"] == 0.75
        assert "metrics" in data


class TestGraphEdge:
    """Tests for GraphEdge dataclass."""
    
    def test_create_edge(self):
        """Test creating a graph edge."""
        edge = GraphEdge(
            source="context.presence",
            target="state.energy_level",
            weight=0.8
        )
        
        assert edge.source == "context.presence"
        assert edge.target == "state.energy_level"
        assert edge.weight == 0.8
        assert edge.edge_type == "synapse"
    
    def test_edge_to_dict(self):
        """Test edge serialization."""
        edge = GraphEdge(
            source="state.comfort",
            target="mood.calm",
            weight=0.9,
            edge_type="synapse"
        )
        
        data = edge.to_dict()
        
        assert data["source"] == "state.comfort"
        assert data["target"] == "mood.calm"
        assert data["weight"] == 0.9
        assert data["type"] == "synapse"


class TestNeuronGraph:
    """Tests for NeuronGraph class."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_graph_initialization(self):
        """Test graph initializes with 14 neurons."""
        graph = NeuronGraph()
        
        assert len(graph.nodes) == 14
        assert len(graph.edges) > 0
    
    def test_graph_has_three_layers(self):
        """Test graph has context, state, and mood layers."""
        graph = NeuronGraph()
        
        context_nodes = graph.get_nodes_by_layer(0)
        state_nodes = graph.get_nodes_by_layer(1)
        mood_nodes = graph.get_nodes_by_layer(2)
        
        assert len(context_nodes) == 5
        assert len(state_nodes) == 5
        assert len(mood_nodes) == 4
    
    def test_get_node_by_id(self):
        """Test retrieving a node by ID."""
        graph = NeuronGraph()
        
        node = graph.get_node("context.presence")
        assert node is not None
        assert node.name == "Presence"
        
        node = graph.get_node("mood.focus")
        assert node is not None
        assert node.name == "Focus"
    
    def test_get_node_not_found(self):
        """Test retrieving non-existent node."""
        graph = NeuronGraph()
        
        node = graph.get_node("nonexistent.neuron")
        assert node is None
    
    def test_update_node_state(self):
        """Test updating a node's state."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        
        node = graph.get_node("context.presence")
        assert node.active is True
        assert node.value == 0.8
        assert node.metrics.confidence == 0.9
    
    def test_update_node_state_triggers_fire(self):
        """Test that updating with active=True records a fire."""
        graph = NeuronGraph()
        
        graph.update_node_state("state.energy_level", active=True, value=0.9, confidence=0.95)
        
        node = graph.get_node("state.energy_level")
        assert node.metrics.last_fire_time is not None
        assert node.metrics.fire_rate >= 0.0
    
    def test_get_outgoing_edges(self):
        """Test getting outgoing edges from a node."""
        graph = NeuronGraph()
        
        edges = graph.get_outgoing_edges("context.presence")
        
        assert len(edges) > 0
        for edge in edges:
            assert edge.source == "context.presence"
    
    def test_get_incoming_edges(self):
        """Test getting incoming edges to a node."""
        graph = NeuronGraph()
        
        edges = graph.get_incoming_edges("state.energy_level")
        
        assert len(edges) > 0
        for edge in edges:
            assert edge.target == "state.energy_level"
    
    def test_get_connected_nodes_single_hop(self):
        """Test getting connected nodes within 1 hop."""
        graph = NeuronGraph()
        
        connected = graph.get_connected_nodes("context.presence", hops=1)
        
        assert "context.presence" in connected
        # Should include connected nodes
        assert len(connected) > 1
    
    def test_get_connected_nodes_multi_hop(self):
        """Test getting connected nodes within multiple hops."""
        graph = NeuronGraph()
        
        connected_1hop = graph.get_connected_nodes("context.presence", hops=1)
        connected_2hop = graph.get_connected_nodes("context.presence", hops=2)
        
        # 2-hop should include at least as many nodes as 1-hop
        assert len(connected_2hop) >= len(connected_1hop)
    
    def test_graph_to_dict(self):
        """Test graph serialization."""
        graph = NeuronGraph()
        
        data = graph.to_dict()
        
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data
        
        assert len(data["nodes"]) == 14
        assert len(data["edges"]) > 0
        
        metadata = data["metadata"]
        assert metadata["total_nodes"] == 14
        assert "layers" in metadata
        assert metadata["layers"]["context"] == 5
        assert metadata["layers"]["state"] == 5
        assert metadata["layers"]["mood"] == 4
    
    def test_graph_stats(self):
        """Test graph statistics."""
        graph = NeuronGraph()
        
        # Update some nodes to be active
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.energy_level", active=True, value=0.7, confidence=0.85)
        
        stats = graph.get_stats()
        
        assert stats["total_nodes"] == 14
        assert stats["active_nodes"] == 2
        assert "avg_fire_rate" in stats
        assert "avg_confidence" in stats
        assert "layers" in stats


class TestNeuronGraphSingleton:
    """Tests for singleton pattern."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_get_neuron_graph_returns_singleton(self):
        """Test that get_neuron_graph returns same instance."""
        graph1 = get_neuron_graph()
        graph2 = get_neuron_graph()
        
        assert graph1 is graph2
    
    def test_reset_neuron_graph_creates_new_instance(self):
        """Test that reset creates a new instance."""
        graph1 = get_neuron_graph()
        reset_neuron_graph()
        graph2 = get_neuron_graph()
        
        assert graph1 is not graph2


class TestNeuronGraphConnections:
    """Tests for neuron connections."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_context_to_state_connections(self):
        """Test context neurons connect to state neurons."""
        graph = NeuronGraph()
        
        # Context.presence should connect to state.energy_level
        edges = graph.get_outgoing_edges("context.presence")
        target_ids = [e.target for e in edges]
        
        assert any("state." in target for target in target_ids)
    
    def test_state_to_mood_connections(self):
        """Test state neurons connect to mood neurons."""
        graph = NeuronGraph()
        
        # State.energy_level should connect to mood.energy
        edges = graph.get_outgoing_edges("state.energy_level")
        target_ids = [e.target for e in edges]
        
        assert any("mood." in target for target in target_ids)
    
    def test_feedback_connections_exist(self):
        """Test feedback connections from state to context."""
        graph = NeuronGraph()
        
        # Find feedback edges
        feedback_edges = [e for e in graph.edges if e.edge_type == "feedback"]
        
        assert len(feedback_edges) > 0
    
    def test_modulatory_connections_exist(self):
        """Test modulatory connections from mood to state."""
        graph = NeuronGraph()
        
        # Find modulatory edges
        modulatory_edges = [e for e in graph.edges if e.edge_type == "modulatory"]
        
        assert len(modulatory_edges) > 0


class TestNeuronGraphMetrics:
    """Tests for neuron metrics tracking."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_fire_rate_tracking(self):
        """Test fire rate is tracked."""
        graph = NeuronGraph()
        
        # Fire multiple times
        for i in range(5):
            graph.update_node_state("mood.focus", active=True, value=0.9, confidence=0.95)
        
        node = graph.get_node("mood.focus")
        assert node.metrics.fire_rate >= 0.0
    
    def test_confidence_tracking(self):
        """Test confidence is tracked per neuron."""
        graph = NeuronGraph()
        
        graph.update_node_state("context.weather", active=True, value=0.6, confidence=0.88)
        
        node = graph.get_node("context.weather")
        assert node.metrics.confidence == 0.88
    
    def test_trend_tracking(self):
        """Test trend is tracked based on value."""
        graph = NeuronGraph()
        
        # High value = increasing trend
        graph.update_node_state("state.productivity", active=True, value=0.85, confidence=0.9)
        node = graph.get_node("state.productivity")
        assert node.metrics.trend == "increasing"
        
        # Low value = decreasing trend
        graph.update_node_state("state.productivity", active=False, value=0.15, confidence=0.7)
        node = graph.get_node("state.productivity")
        assert node.metrics.trend == "decreasing"


class TestNeuronConnections:
    """Tests for get_neuron_connections function."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_get_all_connections(self):
        """Test getting all connections."""
        result = get_neuron_connections()
        
        assert "total_connections" in result
        assert "connections" in result
        assert "by_type" in result
        assert result["total_connections"] > 0
        assert len(result["connections"]) == result["total_connections"]
    
    def test_get_connections_by_type(self):
        """Test connections are categorized by type."""
        result = get_neuron_connections()
        
        assert "synapse" in result["by_type"]
        assert "feedback" in result["by_type"]
        assert "modulatory" in result["by_type"]
        assert result["by_type"]["synapse"] > 0
        assert result["by_type"]["feedback"] > 0
        assert result["by_type"]["modulatory"] > 0
    
    def test_get_connections_for_specific_node(self):
        """Test getting connections for a specific node."""
        result = get_neuron_connections("context.presence")
        
        assert "node_id" in result
        assert "node_name" in result
        assert "incoming" in result
        assert "outgoing" in result
        assert "total_connections" in result
        
        assert result["node_id"] == "context.presence"
        assert result["node_name"] == "Presence"
        assert isinstance(result["incoming"], list)
        assert isinstance(result["outgoing"], list)
    
    def test_get_connections_node_not_found(self):
        """Test getting connections for non-existent node."""
        result = get_neuron_connections("nonexistent.node")
        
        assert "error" in result
        assert "not found" in result["error"]


class TestFindPaths:
    """Tests for find_paths function."""
    
    def setup_method(self):
        """Reset graph before each test."""
        reset_neuron_graph()
    
    def test_find_path_context_to_mood(self):
        """Test finding path from context to mood neuron."""
        paths = find_paths("context.presence", "mood.energy")
        
        assert len(paths) > 0
        for path in paths:
            assert "path" in path
            assert "length" in path
            assert "nodes" in path
            assert path["path"][0] == "context.presence"
            assert path["path"][-1] == "mood.energy"
    
    def test_find_path_state_to_mood(self):
        """Test finding path from state to mood neuron."""
        paths = find_paths("state.energy_level", "mood.focus")
        
        assert len(paths) > 0
        for path in paths:
            assert path["path"][0] == "state.energy_level"
            assert path["path"][-1] == "mood.focus"
    
    def test_find_path_same_node(self):
        """Test finding path from node to itself."""
        paths = find_paths("context.presence", "context.presence")
        
        assert len(paths) > 0
        # Path should have length 0 (same node)
        assert paths[0]["length"] == 0
        assert paths[0]["path"] == ["context.presence"]
    
    def test_find_path_with_max_depth(self):
        """Test finding paths with limited depth."""
        paths_depth1 = find_paths("context.presence", "mood.energy", max_depth=1)
        paths_depth3 = find_paths("context.presence", "mood.energy", max_depth=3)
        
        # Depth 3 should find at least as many paths as depth 1
        assert len(paths_depth3) >= len(paths_depth1)
        
        # All paths in depth1 should have length <= 1
        for path in paths_depth1:
            assert path["length"] <= 1
    
    def test_find_path_invalid_start(self):
        """Test finding path with invalid start node."""
        with pytest.raises(ValueError, match="Start node not found"):
            find_paths("nonexistent.start", "mood.energy")
    
    def test_find_path_invalid_end(self):
        """Test finding path with invalid end node."""
        with pytest.raises(ValueError, match="End node not found"):
            find_paths("context.presence", "nonexistent.end")
    
    def test_path_node_names(self):
        """Test that path includes human-readable node names."""
        paths = find_paths("context.presence", "state.energy_level")
        
        assert len(paths) > 0
        path = paths[0]
        
        # Check that nodes list contains readable names
        assert len(path["nodes"]) == len(path["path"])
        assert "Presence" in path["nodes"]
        assert "Energy Level" in path["nodes"]


class TestNeuronGraphAPIIntegration:
    """Integration tests for Neuron Graph API endpoints."""
    
    def test_graph_structure_complete(self):
        """Test that graph has all required components."""
        graph = get_neuron_graph()
        
        # Check all 14 neurons exist
        assert len(graph.nodes) == 14
        
        # Check layers
        context_nodes = graph.get_nodes_by_layer(0)
        state_nodes = graph.get_nodes_by_layer(1)
        mood_nodes = graph.get_nodes_by_layer(2)
        
        assert len(context_nodes) == 5
        assert len(state_nodes) == 5
        assert len(mood_nodes) == 4
    
    def test_all_neurons_have_connections(self):
        """Test that all neurons have at least one connection."""
        graph = get_neuron_graph()
        
        for node_id in graph.nodes:
            incoming = graph.get_incoming_edges(node_id)
            outgoing = graph.get_outgoing_edges(node_id)
            
            # Each neuron should have at least one connection
            assert len(incoming) > 0 or len(outgoing) > 0, \
                f"Neuron {node_id} has no connections"
    
    def test_paths_exist_between_layers(self):
        """Test that paths exist between different layers."""
        # Context -> State
        paths = find_paths("context.presence", "state.energy_level")
        assert len(paths) > 0
        
        # State -> Mood
        paths = find_paths("state.energy_level", "mood.energy")
        assert len(paths) > 0
        
        # Context -> Mood (multi-hop)
        paths = find_paths("context.presence", "mood.focus")
        assert len(paths) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
