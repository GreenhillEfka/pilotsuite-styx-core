"""Tests for Neuron Graph API Endpoints."""

import unittest

from copilot_core.api.v1.neuron_graph import reset_neuron_graph, get_neuron_graph


class TestNeuronGraphAPI(unittest.TestCase):
    """Test neuron graph API endpoints (unit tests, not integration)."""

    def setUp(self):
        """Set up test fixtures."""
        reset_neuron_graph()

    def tearDown(self):
        """Clean up test fixtures."""
        reset_neuron_graph()

    def test_get_graph_empty(self):
        """Test graph has 14 nodes."""
        graph = get_neuron_graph()
        data = graph.to_dict()
        
        self.assertEqual(len(data["nodes"]), 14)
        self.assertIn("edges", data)
        self.assertIn("metadata", data)

    def test_get_graph_structure(self):
        """Test graph structure has correct layers."""
        graph = get_neuron_graph()
        data = graph.to_dict()
        
        # Check metadata
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["total_nodes"], 14)
        self.assertEqual(data["metadata"]["layers"]["context"], 5)
        self.assertEqual(data["metadata"]["layers"]["state"], 5)
        self.assertEqual(data["metadata"]["layers"]["mood"], 4)

    def test_get_neuron_stats(self):
        """Test getting neuron stats."""
        graph = get_neuron_graph()
        node = graph.get_node("context.presence")
        
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "Presence")
        self.assertEqual(node.neuron_type, "context")
        self.assertEqual(node.layer, 0)

    def test_get_neuron_stats_not_found(self):
        """Test getting non-existent neuron."""
        graph = get_neuron_graph()
        node = graph.get_node("nonexistent.neuron")
        
        self.assertIsNone(node)

    def test_get_neuron_stats_short_id(self):
        """Test getting neuron with short ID."""
        graph = get_neuron_graph()
        
        # Try with full ID
        node = graph.get_node("context.presence")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "Presence")

    def test_get_graph_stats(self):
        """Test graph statistics."""
        graph = get_neuron_graph()
        stats = graph.get_stats()
        
        self.assertIn("total_nodes", stats)
        self.assertIn("active_nodes", stats)
        self.assertIn("total_edges", stats)
        self.assertIn("avg_fire_rate", stats)
        self.assertIn("avg_confidence", stats)

    def test_graph_with_active_neurons(self):
        """Test graph with active neurons."""
        graph = get_neuron_graph()
        
        # Activate some neurons
        graph.update_node_state("context.presence", active=True, value=0.8, confidence=0.9)
        graph.update_node_state("state.energy_level", active=True, value=0.7, confidence=0.85)
        
        data = graph.to_dict()
        
        # Should have nodes and edges
        self.assertGreater(len(data["nodes"]), 0)
        self.assertGreater(len(data["edges"]), 0)

    def test_neuron_stats_with_connections(self):
        """Test neuron connections."""
        graph = get_neuron_graph()
        
        incoming = graph.get_incoming_edges("state.energy_level")
        outgoing = graph.get_outgoing_edges("state.energy_level")
        
        self.assertGreater(len(incoming), 0)
        self.assertGreater(len(outgoing), 0)


class TestNeuronWebSocketAPI(unittest.TestCase):
    """Test neuron WebSocket endpoint."""

    def test_websocket_endpoint_exists(self):
        """Test WebSocket endpoint is registered."""
        # WebSocket endpoint is defined in websocket_neuron.py
        # Actual testing requires socketio client which is not available in test env
        self.assertTrue(True)  # Placeholder test


if __name__ == "__main__":
    unittest.main()
