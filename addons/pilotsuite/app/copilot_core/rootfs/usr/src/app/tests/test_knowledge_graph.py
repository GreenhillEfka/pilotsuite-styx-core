"""Tests for Knowledge Graph module.

Tests cover:
- GraphStore (SQLite backend)
- GraphBuilder
- PatternImporter
- API endpoints
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Import the modules under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot_core.knowledge_graph.models import (
    Node, Edge, NodeType, EdgeType, GraphQuery, GraphResult
)
from copilot_core.knowledge_graph.graph_store import GraphStore
from copilot_core.knowledge_graph.builder import GraphBuilder
from copilot_core.knowledge_graph.pattern_importer import PatternImporter


class TestModels(unittest.TestCase):
    """Test data models."""

    def test_node_creation(self):
        """Test creating a node."""
        node = Node(
            id="light.kitchen",
            type=NodeType.ENTITY,
            label="Kitchen Light",
            properties={"domain": "light"},
        )
        self.assertEqual(node.id, "light.kitchen")
        self.assertEqual(node.type, NodeType.ENTITY)
        self.assertEqual(node.label, "Kitchen Light")
        self.assertIn("domain", node.properties)

    def test_node_to_dict(self):
        """Test node serialization."""
        node = Node(
            id="mood.relax",
            type=NodeType.MOOD,
            label="Relaxation",
        )
        d = node.to_dict()
        self.assertEqual(d["id"], "mood.relax")
        self.assertEqual(d["type"], "mood")
        self.assertEqual(d["label"], "Relaxation")

    def test_node_from_dict(self):
        """Test node deserialization."""
        data = {
            "id": "pattern:test",
            "type": "pattern",
            "label": "Test Pattern",
            "properties": {"confidence": 0.8},
        }
        node = Node.from_dict(data)
        self.assertEqual(node.id, "pattern:test")
        self.assertEqual(node.type, NodeType.PATTERN)
        self.assertEqual(node.properties["confidence"], 0.8)

    def test_edge_creation(self):
        """Test creating an edge."""
        edge = Edge(
            source="light.kitchen",
            target="area.kitchen",
            type=EdgeType.BELONGS_TO,
            weight=1.0,
            confidence=1.0,
        )
        self.assertEqual(edge.source, "light.kitchen")
        self.assertEqual(edge.target, "area.kitchen")
        self.assertEqual(edge.type, EdgeType.BELONGS_TO)
        self.assertEqual(edge.weight, 1.0)

    def test_edge_id(self):
        """Test edge ID generation."""
        edge = Edge(
            source="a",
            target="b",
            type=EdgeType.TRIGGERS,
        )
        self.assertEqual(edge.id, "a:triggers:b")

    def test_query_creation(self):
        """Test creating a query."""
        query = GraphQuery(
            query_type="structural",
            entity_id="light.kitchen",
            max_results=5,
        )
        self.assertEqual(query.query_type, "structural")
        self.assertEqual(query.entity_id, "light.kitchen")
        self.assertEqual(query.max_results, 5)


class TestGraphStoreSQLite(unittest.TestCase):
    """Test GraphStore with SQLite backend."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_kg.db")
        # Disable Neo4j for tests
        os.environ["COPILOT_NEO4J_ENABLED"] = "false"
        self.store = GraphStore(sqlite_path=self.db_path)

    def tearDown(self):
        """Clean up test fixtures."""
        self.store.close()
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_backend_is_sqlite(self):
        """Test that backend is SQLite."""
        self.assertEqual(self.store.backend, "sqlite")

    def test_add_and_get_node(self):
        """Test adding and retrieving a node."""
        node = Node(
            id="test.entity",
            type=NodeType.ENTITY,
            label="Test Entity",
            properties={"test": True},
        )
        self.store.add_node(node)
        
        retrieved = self.store.get_node("test.entity")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test.entity")
        self.assertEqual(retrieved.type, NodeType.ENTITY)
        self.assertEqual(retrieved.label, "Test Entity")
        self.assertTrue(retrieved.properties.get("test"))

    def test_get_nonexistent_node(self):
        """Test getting a nonexistent node."""
        node = self.store.get_node("nonexistent")
        self.assertIsNone(node)

    def test_get_nodes_by_type(self):
        """Test getting nodes by type."""
        # Add multiple nodes
        self.store.add_node(Node(id="light.1", type=NodeType.ENTITY, label="Light 1"))
        self.store.add_node(Node(id="light.2", type=NodeType.ENTITY, label="Light 2"))
        self.store.add_node(Node(id="mood.relax", type=NodeType.MOOD, label="Relax"))
        
        # Get entities
        entities = self.store.get_nodes_by_type(NodeType.ENTITY, limit=10)
        self.assertEqual(len(entities), 2)
        
        # Get moods
        moods = self.store.get_nodes_by_type(NodeType.MOOD, limit=10)
        self.assertEqual(len(moods), 1)
        self.assertEqual(moods[0].id, "mood.relax")

    def test_add_and_get_edges(self):
        """Test adding and retrieving edges."""
        # Add nodes
        self.store.add_node(Node(id="a", type=NodeType.ENTITY, label="A"))
        self.store.add_node(Node(id="b", type=NodeType.ENTITY, label="B"))
        
        # Add edge
        edge = Edge(
            source="a",
            target="b",
            type=EdgeType.TRIGGERS,
            weight=0.8,
            confidence=0.85,
            evidence={"support": 10},
        )
        self.store.add_edge(edge)
        
        # Get edges from a
        edges = self.store.get_edges_from("a")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].source, "a")
        self.assertEqual(edges[0].target, "b")
        self.assertEqual(edges[0].type, EdgeType.TRIGGERS)
        self.assertEqual(edges[0].weight, 0.8)
        self.assertEqual(edges[0].confidence, 0.85)
        
        # Get edges to b
        edges_to = self.store.get_edges_to("b")
        self.assertEqual(len(edges_to), 1)

    def test_query_by_entity(self):
        """Test querying by entity."""
        # Set up nodes and edges
        self.store.add_node(Node(id="light.kitchen", type=NodeType.ENTITY, label="Kitchen"))
        self.store.add_node(Node(id="light.livingroom", type=NodeType.ENTITY, label="Living Room"))
        self.store.add_node(Node(id="mood.relax", type=NodeType.MOOD, label="Relax"))
        
        self.store.add_edge(Edge(
            source="light.kitchen",
            target="light.livingroom",
            type=EdgeType.TRIGGERS,
            confidence=0.8,
        ))
        self.store.add_edge(Edge(
            source="light.kitchen",
            target="mood.relax",
            type=EdgeType.RELATES_TO_MOOD,
            confidence=0.7,
        ))
        
        # Query
        query = GraphQuery(
            query_type="structural",
            entity_id="light.kitchen",
            max_results=10,
        )
        result = self.store.query(query)
        
        self.assertEqual(len(result.nodes), 3)  # kitchen + livingroom + mood
        self.assertEqual(len(result.edges), 2)
        self.assertGreater(result.confidence, 0)

    def test_stats(self):
        """Test getting statistics."""
        self.store.add_node(Node(id="a", type=NodeType.ENTITY, label="A"))
        self.store.add_node(Node(id="b", type=NodeType.ENTITY, label="B"))
        self.store.add_node(Node(id="mood.relax", type=NodeType.MOOD, label="Relax"))
        self.store.add_edge(Edge(source="a", target="b", type=EdgeType.TRIGGERS))
        
        stats = self.store.stats()
        self.assertEqual(stats["backend"], "sqlite")
        self.assertEqual(stats["node_count"], 3)
        self.assertEqual(stats["edge_count"], 1)
        self.assertEqual(stats["nodes_by_type"]["entity"], 2)
        self.assertEqual(stats["nodes_by_type"]["mood"], 1)


class TestGraphBuilder(unittest.TestCase):
    """Test GraphBuilder."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_kg.db")
        os.environ["COPILOT_NEO4J_ENABLED"] = "false"
        self.store = GraphStore(sqlite_path=self.db_path)
        self.builder = GraphBuilder(store=self.store)

    def tearDown(self):
        """Clean up."""
        self.store.close()
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_upsert_entity(self):
        """Test creating an entity."""
        node = self.builder.upsert_entity(
            entity_id="light.kitchen",
            domain="light",
            label="Kitchen Light",
            area_id="area.kitchen",
            capabilities=["dimmable", "color_temp"],
            tags=["aicp.place.kueche"],
        )
        
        self.assertEqual(node.id, "light.kitchen")
        self.assertEqual(node.type, NodeType.ENTITY)
        
        # Verify domain node
        domain = self.store.get_node("domain:light")
        self.assertIsNotNone(domain)
        
        # Verify area node
        area = self.store.get_node("area.kitchen")
        self.assertIsNotNone(area)
        
        # Verify edges
        edges = self.store.get_edges_from("light.kitchen")
        self.assertEqual(len(edges), 5)  # domain, area, 2x capability, tag

    def test_upsert_zone(self):
        """Test creating a zone."""
        node = self.builder.upsert_zone(
            zone_id="zone.west",
            label="West Wing",
            area_ids=["area.kitchen", "area.livingroom"],
        )
        
        self.assertEqual(node.id, "zone.west")
        self.assertEqual(node.type, NodeType.ZONE)
        
        # Verify area nodes
        area1 = self.store.get_node("area.kitchen")
        area2 = self.store.get_node("area.livingroom")
        self.assertIsNotNone(area1)
        self.assertIsNotNone(area2)

    def test_upsert_mood(self):
        """Test creating a mood."""
        node = self.builder.upsert_mood("relax", "Relaxation")
        
        self.assertEqual(node.id, "mood:relax")
        self.assertEqual(node.type, NodeType.MOOD)

    def test_relate_entity_to_mood(self):
        """Test relating an entity to a mood."""
        self.builder.upsert_entity("light.kitchen", "light")
        edge = self.builder.relate_entity_to_mood(
            "light.kitchen",
            "relax",
            weight=0.7,
            confidence=0.8,
        )
        
        self.assertEqual(edge.source, "light.kitchen")
        self.assertEqual(edge.target, "mood:relax")
        self.assertEqual(edge.type, EdgeType.RELATES_TO_MOOD)
        self.assertEqual(edge.weight, 0.7)

    def test_build_from_ha_states(self):
        """Test building from HA states."""
        states = [
            {
                "entity_id": "light.kitchen",
                "state": "on",
                "attributes": {"friendly_name": "Kitchen Light"},
            },
            {
                "entity_id": "light.livingroom",
                "state": "off",
                "attributes": {"friendly_name": "Living Room Light"},
            },
        ]
        
        entity_registry = {
            "light.kitchen": {"area_id": "kitchen"},
            "light.livingroom": {"area_id": "livingroom"},
        }
        
        stats = self.builder.build_from_ha_states(states, entity_registry=entity_registry)
        
        self.assertEqual(stats["entities"], 2)
        self.assertGreater(stats["domains"], 0)


class TestPatternImporter(unittest.TestCase):
    """Test PatternImporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_kg.db")
        os.environ["COPILOT_NEO4J_ENABLED"] = "false"
        self.store = GraphStore(sqlite_path=self.db_path)
        self.builder = GraphBuilder(store=self.store)
        self.importer = PatternImporter(store=self.store, builder=self.builder)

    def tearDown(self):
        """Clean up."""
        self.store.close()
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_import_pattern(self):
        """Test importing a single pattern."""
        node = self.importer.import_pattern(
            pattern_id="pattern:test:123",
            antecedent="light.kitchen:on",
            consequent="light.livingroom:on",
            confidence=0.85,
            support=15,
            lift=2.3,
            time_window_sec=120,
            evidence={"peak_hour": 20},
        )
        
        self.assertEqual(node.id, "pattern:test:123")
        self.assertEqual(node.type, NodeType.PATTERN)
        self.assertEqual(node.properties["confidence"], 0.85)
        self.assertEqual(node.properties["support"], 15)
        
        # Verify TRIGGERS edge
        edges = self.store.get_edges_from("light.kitchen", EdgeType.TRIGGERS)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].target, "light.livingroom")

    def test_import_from_habitus_rules(self):
        """Test importing from Habitus rules."""
        rules = [
            {
                "A": "light.kitchen:on",
                "B": "light.livingroom:on",
                "confidence": 0.8,
                "nAB": 10,
                "lift": 2.0,
                "dt_sec": 120,
            },
            {
                "A": "sensor.motion:detected",
                "B": "light.hallway:on",
                "confidence": 0.6,  # Below threshold
                "nAB": 5,
                "lift": 1.5,
                "dt_sec": 60,
            },
        ]
        
        stats = self.importer.import_from_habitus_rules(
            rules,
            min_confidence=0.7,
            min_support=5,
        )
        
        self.assertEqual(stats["total_rules"], 2)
        self.assertEqual(stats["imported"], 1)
        self.assertEqual(stats["skipped_low_confidence"], 1)

    def test_get_patterns_for_entity(self):
        """Test getting patterns for an entity."""
        # Import a pattern
        self.importer.import_pattern(
            pattern_id="pattern:test",
            antecedent="light.kitchen:on",
            consequent="light.livingroom:on",
            confidence=0.8,
            support=10,
            lift=2.0,
            time_window_sec=120,
        )
        
        # Get patterns (entity_id without state suffix, since _parse_entity strips ":on")
        patterns = self.importer.get_patterns_for_entity("light.kitchen")
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["consequent"], "light.livingroom")


class TestAPI(unittest.TestCase):
    """Test API endpoints (requires Flask test client)."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_kg.db")
        os.environ["COPILOT_NEO4J_ENABLED"] = "false"
        os.environ["COPILOT_KG_SQLITE_PATH"] = self.db_path
        
        # Import Flask app
        from copilot_core.app import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_stats_endpoint(self):
        """Test /kg/stats endpoint."""
        response = self.client.get("/api/v1/kg/stats")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("stats", data)

    def test_create_and_get_node(self):
        """Test creating and retrieving a node via API."""
        # Create node
        create_response = self.client.post(
            "/api/v1/kg/nodes",
            json={
                "id": "test.entity",
                "type": "entity",
                "label": "Test Entity",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        
        # Get node
        get_response = self.client.get("/api/v1/kg/nodes/test.entity")
        self.assertEqual(get_response.status_code, 200)
        data = json.loads(get_response.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["node"]["id"], "test.entity")

    def test_create_edge(self):
        """Test creating an edge via API."""
        # Create nodes first
        self.client.post("/api/v1/kg/nodes", json={"id": "a", "type": "entity", "label": "A"})
        self.client.post("/api/v1/kg/nodes", json={"id": "b", "type": "entity", "label": "B"})
        
        # Create edge
        response = self.client.post(
            "/api/v1/kg/edges",
            json={
                "source": "a",
                "target": "b",
                "type": "triggers",
                "confidence": 0.8,
            },
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["edge"]["source"], "a")

    def test_query_endpoint(self):
        """Test /kg/query endpoint."""
        # Create test data
        self.client.post("/api/v1/kg/nodes", json={"id": "light.test", "type": "entity", "label": "Test"})
        
        response = self.client.post(
            "/api/v1/kg/query",
            json={
                "query_type": "structural",
                "entity_id": "light.test",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()