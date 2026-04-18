"""Knowledge Graph Tests — Neo4j/NetworkX integration test suite."""
from __future__ import annotations

import pytest
from typing import Dict, Any, List


class TestBrainGraphStore:
    """Test brain graph store operations."""

    @pytest.fixture
    def graph_store(self):
        """Create test graph store."""
        from copilot_core.brain.graph_store import BrainGraphStore
        import tempfile
        temp_dir = tempfile.mkdtemp()
        store = BrainGraphStore(storage_path=temp_dir)
        yield store
        store.clear()

    def test_add_entity(self, graph_store):
        """Test adding entity to graph."""
        entity_id = "test_entity_1"
        entity_data = {
            "type": "device",
            "name": "Test Device",
            "attributes": {"state": "on", "brightness": 80}
        }
        
        result = graph_store.add_entity(entity_id, entity_data)
        
        assert result is True
        assert graph_store.get_entity(entity_id) is not None

    def test_get_entity(self, graph_store):
        """Test retrieving entity from graph."""
        entity_id = "test_entity_2"
        entity_data = {"type": "sensor", "name": "Test Sensor"}
        
        graph_store.add_entity(entity_id, entity_data)
        retrieved = graph_store.get_entity(entity_id)
        
        assert retrieved is not None
        assert retrieved["name"] == "Test Sensor"

    def test_add_relationship(self, graph_store):
        """Test adding relationship between entities."""
        entity1 = "light.living_room"
        entity2 = "switch.living_room"
        
        graph_store.add_entity(entity1, {"type": "light"})
        graph_store.add_entity(entity2, {"type": "switch"})
        
        result = graph_store.add_relationship(entity1, "controlled_by", entity2)
        
        assert result is True
        relationships = graph_store.get_relationships(entity1)
        assert any(r["type"] == "controlled_by" for r in relationships)

    def test_query_by_type(self, graph_store):
        """Test querying entities by type."""
        graph_store.add_entity("light.1", {"type": "light"})
        graph_store.add_entity("light.2", {"type": "light"})
        graph_store.add_entity("switch.1", {"type": "switch"})
        
        lights = graph_store.query_by_type("light")
        
        assert len(lights) == 2
        assert all(e["type"] == "light" for e in lights)

    def test_delete_entity(self, graph_store):
        """Test deleting entity from graph."""
        entity_id = "to_delete"
        graph_store.add_entity(entity_id, {"type": "test"})
        
        result = graph_store.delete_entity(entity_id)
        
        assert result is True
        assert graph_store.get_entity(entity_id) is None

    def test_temporal_reasoning(self, graph_store):
        """Test temporal reasoning with time windows."""
        import time
        
        now = time.time()
        hour_ago = now - 3600
        
        # Add entity with temporal context
        graph_store.add_entity(
            "sensor.temp",
            {
                "type": "sensor",
                "value": 22.5,
                "temporal": {"valid_from": hour_ago, "valid_to": now}
            }
        )
        
        # Query historical state
        historical = graph_store.get_entity_at_time("sensor.temp", hour_ago + 1800)
        
        assert historical is not None
        assert historical["attributes"]["value"] == 22.5

    def test_graph_traversal(self, graph_store):
        """Test traversing graph relationships."""
        # Create chain: A → B → C
        graph_store.add_entity("A", {"type": "node"})
        graph_store.add_entity("B", {"type": "node"})
        graph_store.add_entity("C", {"type": "node"})
        
        graph_store.add_relationship("A", "connects_to", "B")
        graph_store.add_relationship("B", "connects_to", "C")
        
        # Traverse from A
        connected = graph_store.traverse_from("A", "connects_to", max_depth=2)
        
        assert len(connected) >= 1
        assert "C" in [e["id"] for e in connected]

    def test_sparql_like_query(self, graph_store):
        """Test SPARQL-like query interface."""
        graph_store.add_entity("device.1", {"type": "device", "name": "Light"})
        graph_store.add_entity("device.2", {"type": "device", "name": "Switch"})
        graph_store.add_entity("sensor.1", {"type": "sensor", "name": "Temp"})
        
        # Query: SELECT ?e WHERE { ?e type "device" }
        results = graph_store.query("SELECT ?e WHERE { ?e type \"device\" }")
        
        assert len(results) == 2
        assert all(e["type"] == "device" for e in results)

    def test_export_json(self, graph_store):
        """Test JSON export."""
        graph_store.add_entity("test.1", {"type": "test"})
        graph_store.add_entity("test.2", {"type": "test"})
        
        json_export = graph_store.export_to_json()
        
        assert "entities" in json_export
        assert len(json_export["entities"]) == 2

    def test_stats(self, graph_store):
        """Test graph statistics."""
        for i in range(10):
            graph_store.add_entity(f"entity_{i}", {"type": "test"})
            if i > 0:
                graph_store.add_relationship(f"entity_{i}", "related_to", f"entity_{i-1}")
        
        stats = graph_store.get_stats()
        
        assert stats["node_count"] == 10
        assert stats["edge_count"] == 9


class TestGraphAPI:
    """Test graph API endpoints."""

    @pytest.fixture
    def graph_api(self):
        """Create test graph API."""
        from copilot_core.brain.graph_api import BrainGraphAPI
        api = BrainGraphAPI()
        yield api
        api.cleanup()

    def test_add_entity_api(self, graph_api):
        """Test add entity via API."""
        response = graph_api.add_entity({
            "id": "api_test_1",
            "type": "device",
            "name": "API Test Device"
        })
        
        assert response["success"] is True
        assert response["entity_id"] == "api_test_1"

    def test_query_api(self, graph_api):
        """Test query via API."""
        graph_api.add_entity({"id": "query_test", "type": "sensor"})
        
        response = graph_api.query({"type": "sensor"})
        
        assert response["success"] is True
        assert len(response["entities"]) > 0

    def test_relationship_api(self, graph_api):
        """Test relationship operations via API."""
        graph_api.add_entity({"id": "device_1", "type": "device"})
        graph_api.add_entity({"id": "sensor_1", "type": "sensor"})
        
        response = graph_api.add_relationship({
            "from": "device_1",
            "type": "monitored_by",
            "to": "sensor_1"
        })
        
        assert response["success"] is True


# Run with: pytest copilot_core/brain/tests/test_graph.py -v
