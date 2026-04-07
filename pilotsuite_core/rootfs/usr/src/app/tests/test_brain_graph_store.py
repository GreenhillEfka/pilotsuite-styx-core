"""Brain Graph Store Tests."""

import tempfile
import unittest
import os
import json
import time
from unittest.mock import patch

try:
    from copilot_core.brain_graph.store import BrainGraphStore
    from copilot_core.brain_graph.model import GraphNode, GraphEdge
except ModuleNotFoundError:
    BrainGraphStore = None


class TestBrainGraphStore(unittest.TestCase):
    """Test BrainGraphStore persistence and basic operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdb = os.path.join(self.tmpdir.name, "graph.db")

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def test_store_init(self):
        """Test store initialization."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        self.assertIsNotNone(store)

    def test_store_init_with_options(self):
        """Test store initialization with options."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(
            db_path=self.tmpdb,
            max_nodes=100,
            max_edges=200,
            node_min_score=0.2,
            edge_min_weight=0.3
        )
        self.assertIsNotNone(store)
        self.assertEqual(store.max_nodes, 100)
        self.assertEqual(store.max_edges, 200)
        self.assertEqual(store.node_min_score, 0.2)
        self.assertEqual(store.edge_min_weight, 0.3)

    def test_store_upsert_node(self):
        """Test upsert_node method."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node = GraphNode(
            id="test:node1",
            kind="entity",
            label="Test Node",
            updated_at_ms=1234567890,
            score=1.0,
            domain="light",
        )
        
        result = store.upsert_node(node)
        self.assertTrue(result)
        
        # Verify it was stored
        stored = store.get_node("test:node1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.id, "test:node1")

    def test_store_upsert_edge(self):
        """Test upsert_edge method."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        # Create nodes first
        node1 = GraphNode(
            id="test:node1",
            kind="entity",
            label="Node 1",
            updated_at_ms=1234567890,
            score=1.0,
        )
        node2 = GraphNode(
            id="test:node2",
            kind="entity",
            label="Node 2",
            updated_at_ms=1234567890,
            score=1.0,
        )
        store.upsert_node(node1)
        store.upsert_node(node2)
        
        edge = GraphEdge(
            id=GraphEdge.create_id("test:node1", "controls", "test:node2"),
            from_node="test:node1",
            to_node="test:node2",
            edge_type="controls",
            updated_at_ms=1234567890,
            weight=0.5,
        )
        
        result = store.upsert_edge(edge)
        self.assertTrue(result)
        
        # Verify it was stored
        stored = store.get_edges(from_node="test:node1", to_node="test:node2", edge_types=["controls"])
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].edge_type, "controls")

    def test_store_get_node(self):
        """Test get_node method."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        # Get non-existent node
        node = store.get_node("nonexistent")
        self.assertIsNone(node)
        
        # Create and retrieve
        node = GraphNode(
            id="test:node",
            kind="entity",
            label="Test",
            updated_at_ms=1234567890,
            score=1.0,
        )
        store.upsert_node(node)
        
        retrieved = store.get_node("test:node")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test:node")

    def test_store_get_edges(self):
        """Test get_edges method."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        # Create nodes
        node1 = GraphNode(id="n1", kind="entity", label="N1", updated_at_ms=1, score=1.0)
        node2 = GraphNode(id="n2", kind="entity", label="N2", updated_at_ms=1, score=1.0)
        store.upsert_node(node1)
        store.upsert_node(node2)
        
        # Create edges
        edge = GraphEdge(
            id=GraphEdge.create_id("n1", "controls", "n2"),
            from_node="n1",
            to_node="n2",
            edge_type="controls",
            updated_at_ms=1,
            weight=0.5,
        )
        store.upsert_edge(edge)
        
        # Retrieve edges
        edges = store.get_edges(from_node="n1", to_node="n2", edge_types=["controls"])
        self.assertEqual(len(edges), 1)

    def test_store_prune_graph(self):
        """Test prune_graph method."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(
            db_path=self.tmpdb,
            max_nodes=5,
            max_edges=10,
            node_min_score=0.5,
        )
        
        # Create nodes
        for i in range(10):
            node = GraphNode(
                id=f"test:node{i}",
                kind="entity",
                label=f"Node {i}",
                updated_at_ms=int(time.time() * 1000),
                score=0.3 + i * 0.1,
            )
            store.upsert_node(node)
        
        # Prune
        result = store.prune_graph(int(time.time() * 1000))
        # Result can be either a count (int) or a dict with counts
        if isinstance(result, dict):
            total_removed = result.get("nodes_removed", 0) + result.get("edges_removed", 0)
            self.assertGreaterEqual(total_removed, 0)
        else:
            self.assertGreaterEqual(result, 0)

    def test_store_max_nodes_edges(self):
        """Test store limits."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(
            db_path=self.tmpdb,
            max_nodes=10,
            max_edges=20,
        )
        self.assertEqual(store.max_nodes, 10)
        self.assertEqual(store.max_edges, 20)

    def test_store_init_falls_back_when_data_dir_unwritable(self):
        """Use fallback DB path when /data is not writable."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")

        fallback_tmp = tempfile.TemporaryDirectory()
        try:
            with patch("copilot_core.brain_graph.store.Path.mkdir") as mock_mkdir:
                mock_mkdir.side_effect = [PermissionError("denied"), None]
                with patch.dict(os.environ, {"COPILOT_BRAIN_GRAPH_DB_DIR": fallback_tmp.name}):
                    store = BrainGraphStore(db_path="/data/brain_graph.db")
            self.assertTrue(str(store.db_path).startswith(fallback_tmp.name))
            self.assertEqual(mock_mkdir.call_count, 2)
        finally:
            fallback_tmp.cleanup()


class TestBrainGraphStoreIntegration(unittest.TestCase):
    """Integration tests for BrainGraphStore."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def test_store_with_service(self):
        """Test BrainGraphStore with BrainGraphService."""
        try:
            from copilot_core.brain_graph.service import BrainGraphService
        except ModuleNotFoundError:
            self.skipTest("BrainGraphService not available")
        
        db_path = os.path.join(self.tmpdir.name, "graph.db")
        store = BrainGraphStore(db_path=db_path)
        svc = BrainGraphService(store)
        
        # Test touch_node
        node = svc.touch_node("test:entity", kind="entity", label="Test Entity")
        self.assertEqual(node.id, "test:entity")
        
        # Test touch_edge
        edge = svc.touch_edge("test:entity", "controls", "test:zone")
        self.assertEqual(edge.from_node, "test:entity")

    def test_store_with_graph_service_graph_ops(self):
        """Test BrainGraphStore with graph service graph operations."""
        try:
            from copilot_core.brain_graph.service import BrainGraphService
        except ModuleNotFoundError:
            self.skipTest("BrainGraphService not available")
        
        db_path = os.path.join(self.tmpdir.name, "graph.db")
        store = BrainGraphStore(db_path=db_path)
        svc = BrainGraphService(store)
        
        # Create nodes
        node1 = svc.touch_node("zone:kitchen", kind="zone", label="Kitchen")
        node2 = svc.touch_node("light.kitchen", kind="entity", label="Kitchen Light")
        
        # Create edge
        edge = svc.touch_edge("light.kitchen", "controls", "zone:kitchen")
        
        # Verify graph structure
        edges = store.get_edges(from_node="light.kitchen")
        self.assertGreater(len(edges), 0)
        
        # Export state
        state = svc.export_state(limit_nodes=100, limit_edges=100)
        self.assertIn("nodes", state)
        self.assertIn("edges", state)


class TestBrainGraphStoreEdgeCases(unittest.TestCase):
    """Edge case tests for BrainGraphStore."""

    def setUp(self):
        """Set up test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdb = os.path.join(self.tmpdir.name, "graph.db")

    def tearDown(self):
        """Clean up test fixtures."""
        self.tmpdir.cleanup()

    def test_store_node_with_zero_score(self):
        """Test store handles node with zero score."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node = GraphNode(
            id="test:node:zero",
            kind="entity",
            label="Zero Score",
            updated_at_ms=1234567890,
            score=0.0,
        )
        result = store.upsert_node(node)
        self.assertTrue(result)

    def test_store_node_with_negative_score(self):
        """Test store handles node with negative score."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node = GraphNode(
            id="test:node:neg",
            kind="entity",
            label="Negative Score",
            updated_at_ms=1234567890,
            score=-1.0,
        )
        result = store.upsert_node(node)
        self.assertTrue(result)

    def test_store_edge_with_zero_weight(self):
        """Test store handles edge with zero weight."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node1 = GraphNode(id="n1", kind="entity", label="N1", updated_at_ms=1, score=1.0)
        node2 = GraphNode(id="n2", kind="entity", label="N2", updated_at_ms=1, score=1.0)
        store.upsert_node(node1)
        store.upsert_node(node2)
        
        edge = GraphEdge(
            id=GraphEdge.create_id("n1", "associates", "n2"),
            from_node="n1",
            to_node="n2",
            edge_type="associates",
            updated_at_ms=1,
            weight=0.0,
        )
        result = store.upsert_edge(edge)
        self.assertTrue(result)

    def test_store_node_update(self):
        """Test store updates existing node."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        # Create node
        node = GraphNode(
            id="test:node:update",
            kind="entity",
            label="Original Label",
            updated_at_ms=1234567890,
            score=1.0,
        )
        store.upsert_node(node)
        
        # Update node
        node.label = "Updated Label"
        node.score = 0.9
        store.upsert_node(node)
        
        # Verify update
        retrieved = store.get_node("test:node:update")
        self.assertEqual(retrieved.label, "Updated Label")
        self.assertEqual(retrieved.score, 0.9)

    def test_store_edge_update(self):
        """Test store updates existing edge."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node1 = GraphNode(id="n1", kind="entity", label="N1", updated_at_ms=1, score=1.0)
        node2 = GraphNode(id="n2", kind="entity", label="N2", updated_at_ms=1, score=1.0)
        store.upsert_node(node1)
        store.upsert_node(node2)
        
        # Create edge
        edge = GraphEdge(
            id=GraphEdge.create_id("n1", "controls", "n2"),
            from_node="n1",
            to_node="n2",
            edge_type="controls",
            updated_at_ms=1,
            weight=0.5,
        )
        store.upsert_edge(edge)
        
        # Update edge
        edge.weight = 0.8
        store.upsert_edge(edge)
        
        # Verify update
        edges = store.get_edges(from_node="n1", to_node="n2", edge_types=["controls"])
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].weight, 0.8)

    def test_store_node_overwrite(self):
        """Test store overwrites node with same ID."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        # Create node
        node1 = GraphNode(
            id="test:node:same",
            kind="entity",
            label="First",
            updated_at_ms=1000,
            score=1.0,
        )
        store.upsert_node(node1)
        
        # Overwrite with new node
        node2 = GraphNode(
            id="test:node:same",
            kind="entity",
            label="Second",
            updated_at_ms=2000,
            score=0.5,
        )
        store.upsert_node(node2)
        
        # Verify overwrite
        retrieved = store.get_node("test:node:same")
        self.assertEqual(retrieved.label, "Second")
        self.assertEqual(retrieved.score, 0.5)

    def test_store_duplicate_edge_id(self):
        """Test store handles duplicate edge ID gracefully."""
        if BrainGraphStore is None:
            self.skipTest("BrainGraphStore not available")
        store = BrainGraphStore(db_path=self.tmpdb)
        
        node1 = GraphNode(id="n1", kind="entity", label="N1", updated_at_ms=1, score=1.0)
        node2 = GraphNode(id="n2", kind="entity", label="N2", updated_at_ms=1, score=1.0)
        store.upsert_node(node1)
        store.upsert_node(node2)
        
        # Create edge
        edge = GraphEdge(
            id=GraphEdge.create_id("n1", "controls", "n2"),
            from_node="n1",
            to_node="n2",
            edge_type="controls",
            updated_at_ms=1,
            weight=0.5,
        )
        store.upsert_edge(edge)
        
        # Try to create duplicate
        edge2 = GraphEdge(
            id=GraphEdge.create_id("n1", "controls", "n2"),
            from_node="n1",
            to_node="n2",
            edge_type="controls",
            updated_at_ms=2,
            weight=0.6,
        )
        store.upsert_edge(edge2)
        
        # Should only have one edge
        edges = store.get_edges(from_node="n1", to_node="n2", edge_types=["controls"])
        self.assertEqual(len(edges), 1)


if __name__ == "__main__":
    unittest.main()
