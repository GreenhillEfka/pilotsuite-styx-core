"""Brain Graph Store Tests — Test suite for knowledge graph persistence."""
from __future__ import annotations

import pytest
from typing import Dict, List, Any


class TestBrainGraphStore:
    """Test brain graph store operations."""

    @pytest.fixture
    def graph_store(self):
        """Create test graph store with clean state."""
        from copilot_core.brain.graph_store import BrainGraphStore
        import shutil
        from pathlib import Path
        
        # Clean up any existing test data
        test_path = Path("/tmp/test_brain_graph")
        if test_path.exists():
            shutil.rmtree(test_path)
        
        store = BrainGraphStore(storage_path="/tmp/test_brain_graph", auto_load=False)
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

    def test_persistence(self, graph_store):
        """Test graph persistence across restarts."""
        entity_id = "persistent_entity"
        graph_store.add_entity(entity_id, {"type": "persistent"})
        graph_store.save()
        
        # Create new instance (with auto_load=True to load saved data)
        new_store = type(graph_store)(storage_path="/tmp/test_brain_graph")
        
        entity = new_store.get_entity(entity_id)
        assert entity is not None
        assert entity["type"] == "persistent"

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

    def test_concurrent_access(self, graph_store):
        """Test concurrent read/write access."""
        import threading
        
        errors = []
        
        def writer():
            try:
                for i in range(10):
                    graph_store.add_entity(f"concurrent_{i}", {"type": "test"})
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for i in range(10):
                    graph_store.get_entity(f"concurrent_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Concurrent access errors: {errors}"

    def test_memory_usage(self, graph_store):
        """Test memory usage with large graph."""
        # Add 1000 entities
        for i in range(1000):
            graph_store.add_entity(f"entity_{i}", {"type": "test", "index": i})
        
        stats = graph_store.get_stats()
        
        assert stats["entity_count"] == 1000
        assert stats["memory_usage_mb"] < 100  # Should be efficient

    def test_serialization_formats(self, graph_store):
        """Test different serialization formats."""
        entity_id = "serialization_test"
        graph_store.add_entity(entity_id, {
            "type": "test",
            "data": {"nested": {"value": 42}}
        })
        
        # Test JSON export
        json_export = graph_store.export_to_json()
        assert entity_id in json_export
        
        # Test GraphML export (if supported)
        graphml_export = graph_store.export_to_graphml()
        assert len(graphml_export) > 0


class TestBrainGraphAPI:
    """Test brain graph API endpoints."""

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


# Run with: pytest tests/test_brain_graph_store.py -v
