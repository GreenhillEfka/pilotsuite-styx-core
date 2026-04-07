"""Tag System Tests — Test suite for entity tagging and filtering."""
from __future__ import annotations

import pytest
from typing import Dict, List, Any


class TestTagSystem:
    """Test tag system operations."""

    @pytest.fixture
    def tag_system(self):
        """Create test tag system."""
        from copilot_core.tags.tag_system import TagSystem
        system = TagSystem()
        yield system
        system.clear()

    def test_add_tag(self, tag_system):
        """Test adding tag to entity."""
        entity_id = "light.living_room"
        tag = "living_room"
        
        result = tag_system.add_tag(entity_id, tag)
        
        assert result is True
        assert tag in tag_system.get_tags(entity_id)

    def test_remove_tag(self, tag_system):
        """Test removing tag from entity."""
        entity_id = "light.kitchen"
        tag = "kitchen"
        
        tag_system.add_tag(entity_id, tag)
        result = tag_system.remove_tag(entity_id, tag)
        
        assert result is True
        assert tag not in tag_system.get_tags(entity_id)

    def test_query_by_tag(self, tag_system):
        """Test querying entities by tag."""
        tag_system.add_tag("light.1", "living_room")
        tag_system.add_tag("light.2", "living_room")
        tag_system.add_tag("light.3", "bedroom")
        
        results = tag_system.query_by_tag("living_room")
        
        assert len(results) == 2
        assert all("living_room" in tag_system.get_tags(e) for e in results)

    def test_query_by_multiple_tags(self, tag_system):
        """Test querying with multiple tag filters."""
        tag_system.add_tag("device.1", "living_room")
        tag_system.add_tag("device.1", "smart")
        tag_system.add_tag("device.2", "living_room")
        tag_system.add_tag("device.2", "dumb")
        
        results = tag_system.query_by_tags(["living_room", "smart"])
        
        assert len(results) == 1
        assert results[0] == "device.1"

    def test_tag_hierarchy(self, tag_system):
        """Test tag hierarchy (parent/child tags)."""
        tag_system.add_tag("device.1", "room:living_room")
        tag_system.add_tag("device.1", "floor:ground_floor")
        
        # Query parent tag
        results = tag_system.query_by_tag("room:*")
        
        assert len(results) >= 1

    def test_bulk_tagging(self, tag_system):
        """Test bulk tagging multiple entities."""
        entities = [f"light.{i}" for i in range(10)]
        
        result = tag_system.bulk_add_tag(entities, "bulk_test")
        
        assert result["success"] is True
        assert result["tagged_count"] == 10

    def test_tag_metadata(self, tag_system):
        """Test tag with metadata."""
        entity_id = "climate.thermostat"
        tag = "energy_saver"
        metadata = {"priority": "high", "category": "automation"}
        
        tag_system.add_tag(entity_id, tag, metadata=metadata)
        retrieved_meta = tag_system.get_tag_metadata(entity_id, tag)
        
        assert retrieved_meta is not None
        assert retrieved_meta["priority"] == "high"

    def test_auto_tagging_rules(self, tag_system):
        """Test automatic tagging based on rules."""
        # Add rule: all lights in living_room get "ambient" tag
        tag_system.add_auto_rule(
            name="living_room_ambient",
            condition={"entity_id_pattern": "light.*", "room": "living_room"},
            tags=["ambient", "mood"]
        )
        
        # Add entity matching rule
        entity_id = "light.living_room_main"
        tag_system.add_tag(entity_id, "living_room")
        
        # Auto-tags should be applied
        tags = tag_system.get_tags(entity_id)
        
        assert "ambient" in tags or "mood" in tags  # At least one auto-tag

    def test_tag_conflicts(self, tag_system):
        """Test handling of conflicting tags."""
        entity_id = "switch.conflict_test"
        
        tag_system.add_tag(entity_id, "on")
        tag_system.add_tag(entity_id, "off")
        
        # Both tags can coexist (not mutually exclusive by default)
        tags = tag_system.get_tags(entity_id)
        
        assert "on" in tags
        assert "off" in tags

    def test_tag_statistics(self, tag_system):
        """Test tag statistics."""
        for i in range(20):
            tag_system.add_tag(f"device.{i}", f"room_{i % 5}")
        
        stats = tag_system.get_statistics()
        
        assert stats["total_tags"] >= 5
        assert stats["total_entities"] == 20

    def test_tag_export_import(self, tag_system):
        """Test exporting and importing tag database."""
        tag_system.add_tag("device.1", "export_test")
        tag_system.add_tag("device.2", "export_test")
        
        # Export
        export_data = tag_system.export_to_json()
        
        # Clear and import
        tag_system.clear()
        tag_system.import_from_json(export_data)
        
        # Verify
        results = tag_system.query_by_tag("export_test")
        assert len(results) == 2


class TestTagAPI:
    """Test tag API endpoints."""

    @pytest.fixture
    def tag_api(self):
        """Create test tag API."""
        from copilot_core.tags.tag_api import TagAPI
        api = TagAPI()
        yield api
        api.cleanup()

    def test_add_tag_api(self, tag_api):
        """Test add tag via API."""
        response = tag_api.add_tag({
            "entity_id": "api_test_device",
            "tag": "api_test"
        })
        
        assert response["success"] is True

    def test_query_tags_api(self, tag_api):
        """Test query tags via API."""
        tag_api.add_tag({"entity_id": "device.1", "tag": "test"})
        
        response = tag_api.get_tags({"entity_id": "device.1"})
        
        assert response["success"] is True
        assert "test" in response["tags"]

    def test_bulk_operations_api(self, tag_api):
        """Test bulk operations via API."""
        entities = [f"device.{i}" for i in range(5)]
        
        response = tag_api.bulk_add_tag({
            "entities": entities,
            "tag": "bulk_api_test"
        })
        
        assert response["success"] is True
        assert response["tagged_count"] == 5


# Run with: pytest tests/test_tag_system.py -v
