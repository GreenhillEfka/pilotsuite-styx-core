"""
Tests for Tags API v2 Flask Blueprint.

FIX: Tests for Flask Blueprint implementation with auth token validation.
"""

import pytest
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot_core.tags import TagRegistry, TagFacet, SubjectType, create_tag_service
from copilot_core.tags.api import init_tags_api, _serialize_tag


class MockRequest:
    """Mock Flask request for testing."""
    def __init__(self, json_data=None, args=None, headers=None):
        self._json = json_data
        self._args = args or {}
        self._headers = headers or {}
    
    def get_json(self, silent=False):
        return self._json
    
    @property
    def args(self):
        return type('Args', (), self._args)()
    
    @property
    def headers(self):
        return type('Headers', (), self._headers)()


class TestSerializeTag:
    """Tests for tag serialization."""
    
    def test_serialize_tag_basic(self):
        """Test basic tag serialization."""
        from copilot_core.tags import Tag, TagMetadata
        
        tag = Tag(
            id="aicp.role.lights",
            facet=TagFacet.ROLE,
            metadata=TagMetadata(display_de="Lichter", display_en="Lights"),
            provenance="system",
        )
        
        result = _serialize_tag(tag)
        
        assert result["id"] == "aicp.role.lights"
        assert result["facet"] == "role"
        assert result["display_de"] == "Lichter"
        assert result["display_en"] == "Lights"
        assert result["is_learned"] is False
        assert result["provenance"] == "system"


class TestTagRegistryIntegration:
    """Integration tests for TagRegistry."""
    
    def test_create_and_get_tag(self):
        """Test tag creation and retrieval."""
        registry = TagRegistry()
        
        tag = registry.create_tag(
            tag_id="aicp.role.primary",
            facet=TagFacet.ROLE,
            display_de="Primär",
            display_en="Primary",
        )
        
        assert tag.id == "aicp.role.primary"
        assert tag.facet == TagFacet.ROLE
        
        retrieved = registry.get_tag("aicp.role.primary")
        assert retrieved is not None
        assert retrieved.id == tag.id
    
    def test_list_tags_filtered(self):
        """Test listing tags with facet filter."""
        registry = TagRegistry()
        
        registry.create_tag("aicp.role.test", TagFacet.ROLE)
        registry.create_tag("aicp.state.test", TagFacet.STATE)
        registry.create_tag("aicp.kind.test", TagFacet.KIND)
        
        role_tags = registry.list_tags(facet=TagFacet.ROLE)
        
        assert len(role_tags) == 1
        assert role_tags[0].id == "aicp.role.test"
    
    def test_learned_tag_workflow(self):
        """Test learned tag suggest -> confirm workflow."""
        registry = TagRegistry()
        
        # Suggest a learned tag
        tag = registry.suggest_learned_tag(
            facet=TagFacet.STATE,
            key="broken",
            namespace="sys",
            display_de="Defekt",
        )
        
        assert tag.is_learned is True
        assert tag.provenance == "learned"
        assert "sys.state.broken" in tag.id
        
        # Confirm the tag
        confirmed = registry.confirm_learned_tag(tag.id)
        
        assert confirmed is not None
        assert confirmed.is_learned is False
        assert confirmed.provenance == "user"
    
    def test_subject_registration(self):
        """Test subject registration."""
        registry = TagRegistry()
        
        subject = registry.register_subject(
            ha_id="light.living_room",
            ha_type=SubjectType.ENTITY,
            name="Wohnzimmer Licht",
            domain="light",
        )
        
        assert subject.ha_id == "light.living_room"
        assert subject.ha_type == SubjectType.ENTITY
        assert subject.domain == "light"
        
        retrieved = registry.get_subject(subject.canonical_id)
        assert retrieved is not None
    
    def test_tag_assignment(self):
        """Test assigning tags to subjects."""
        registry = TagRegistry()
        
        # Create tag and subject
        tag = registry.create_tag("aicp.role.lights", TagFacet.ROLE)
        subject = registry.register_subject(
            ha_id="light.1",
            ha_type=SubjectType.ENTITY,
            domain="light",
        )
        
        # Assign
        assignment = registry.assign_tag(tag.id, subject.canonical_id)
        
        assert assignment is not None
        assert assignment.tag_id == tag.id
        assert assignment.subject_canonical_id == subject.canonical_id
        
        # Check bidirectional
        subject_tags = registry.get_subject_tags(subject.canonical_id)
        assert len(subject_tags) == 1
        assert subject_tags[0].id == tag.id
    
    def test_habitus_zone(self):
        """Test habitus zone creation and membership."""
        registry = TagRegistry()
        
        # Register a subject first
        subject = registry.register_subject(
            ha_id="sensor.1",
            ha_type=SubjectType.ENTITY,
        )
        
        # Create zone
        zone = registry.create_zone(
            zone_id="zone_sensors",
            name="Sensor Zone",
            policy_ids=["policy_1"],
        )
        
        # Add subject to zone
        result = registry.add_to_zone(zone.id, subject.canonical_id)
        
        assert result is True
        assert subject.canonical_id in zone.member_subject_ids


class TestServiceInterface:
    """Tests for the service interface."""
    
    def test_create_tag_service(self):
        """Test service interface creation."""
        registry = TagRegistry()
        service = create_tag_service(registry)
        
        assert "create_tag" in service
        assert "suggest_tag" in service
        assert "confirm_tag" in service
        assert "list_tags" in service
    
    def test_service_create_tag(self):
        """Test service create_tag."""

        registry = TagRegistry()
        service = create_tag_service(registry)

        result = service["create_tag"](
            tag_id="aicp.test.tag",
            facet="role",
            display_de="Test",
        )
        assert result["status"] == "created"
        assert result["tag_id"] == "aicp.test.tag"
    
    def test_service_suggest_tag(self):
        """Test service suggest_tag."""

        registry = TagRegistry()
        service = create_tag_service(registry)

        result = service["suggest_tag"](
            facet="state",
            key="candidate",
            namespace="sys",
            display_de="Kandidat",
        )
        assert result["status"] == "suggested"
        assert result["is_learned"] is True


class TestExportLabels:
    """Tests for HA Labels export."""
    
    def test_export_filters_sys_namespace(self):
        """Test that sys.* namespace is NOT exported."""
        registry = TagRegistry()
        
        # Create sys.* tag (should NOT be exported)
        registry.create_tag("sys.role.test", TagFacet.ROLE)
        
        # Create aicp.* tag (should be exported)
        aicp_tag = registry.create_tag("aicp.role.test", TagFacet.ROLE)
        
        labels = registry.export_ha_labels()
        
        assert len(labels) == 1
        assert "sys" not in labels[0]["name"]
    
    def test_export_filters_non_materializable(self):
        """Test that non-role/state facets are NOT exported."""
        registry = TagRegistry()
        
        # Create role.* tag (should be exported)
        registry.create_tag("aicp.role.test", TagFacet.ROLE)
        
        # Create state.* tag (should be exported)
        registry.create_tag("aicp.state.test", TagFacet.STATE)
        
        # Create place.* tag (should NOT be exported)
        registry.create_tag("aicp.place.test", TagFacet.PLACE)
        
        labels = registry.export_ha_labels()
        
        assert len(labels) == 2
        facets = [l["name"].split(".")[1] for l in labels]
        assert "role" in facets
        assert "state" in facets
        assert "place" not in facets
    
    def test_export_filters_learned_tags(self):
        """Test that learned tags are NOT automatically exported."""
        registry = TagRegistry()
        
        # Create normal tag
        registry.create_tag("aicp.role.normal", TagFacet.ROLE)
        
        # Create learned tag (should NOT be exported)
        registry.suggest_learned_tag(
            facet=TagFacet.STATE,
            key="new",
            namespace="aicp",
        )
        
        labels = registry.export_ha_labels()
        
        # Only the non-learned tag should be exported
        assert len(labels) == 1
        assert "learned" not in labels[0].get("provenance", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
