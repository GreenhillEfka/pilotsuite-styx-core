"""Brain Graph Tests (P1-007 - Ollama Worker 3).

Comprehensive test suite for Knowledge Graph functionality.
"""

import unittest
from copilot_core.brain.kg_schema import KnowledgeGraphSchema, KGNode, KGEdge


class BrainGraphTest(unittest.TestCase):
    """Tests for P1-007 Brain Graph Store."""

    def setUp(self):
        self.schema = KnowledgeGraphSchema()

    def test_node_creation(self):
        """Test creating nodes of different types."""
        node = KGNode("device_1", "device", {"type": "light"})
        self.schema.add_node(node)
        self.assertIn("device_1", self.schema.nodes)

    def test_edge_creation(self):
        """Test creating edges between nodes."""
        n1 = KGNode("zone_1", "zone", {"name": "Living"})
        n2 = KGNode("device_1", "device", {"type": "light"})
        self.schema.add_node(n1)
        self.schema.add_node(n2)
        
        edge = KGEdge("device_1", "zone_1", "located_in")
        self.schema.add_edge(edge)
        self.assertEqual(len(self.schema.edges), 1)

    def test_sparql_query(self):
        """Test SPARQL-like query execution."""
        # Setup
        self.schema.add_node(KGNode("zone_living", "zone", {}))
        self.schema.add_node(KGNode("dev_light", "device", {}))
        self.schema.add_edge(KGEdge("dev_light", "zone_living", "located_in"))
        
        # Query
        results = self.schema.sparql_query(
            "SELECT ?device WHERE { ?device located_in zone_living }"
        )
        self.assertEqual(len(results), 1)

    def test_node_type_validation(self):
        """Test that only valid node types are accepted."""
        with self.assertRaises(ValueError):
            KGNode("invalid", "not_a_valid_type", {})


if __name__ == "__main__":
    unittest.main()
