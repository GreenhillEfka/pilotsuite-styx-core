"""Tests for Tag System v0.2 (Decision Matrix Implementation)."""
import pytest
from copilot_core.tags import (
    TagRegistry,
    Tag,
    TagFacet,
    TagNamespace,
    Subject,
    SubjectType,
    HabitusZone,
    TagAssignment,
    TagMetadata,
)


class TestTagRegistry:
    """Test TagRegistry CRUD operations."""
    
    def setup_method(self):
        self.registry = TagRegistry()
    
    def test_create_tag(self):
        """Test tag creation."""
        tag = self.registry.create_tag(
            tag_id="aicp.role.safety_critical",
            facet=TagFacet.ROLE,
            display_de="Sicherheits-kritisch",
        )
        assert tag.id == "aicp.role.safety_critical"
        assert tag.facet == TagFacet.ROLE
        assert tag.metadata.display_de == "Sicherheits-kritisch"
        assert tag.provenance == "system"
    
    def test_get_tag(self):
        """Test tag retrieval."""
        self.registry.create_tag("aicp.kind.light", TagFacet.KIND)
        tag = self.registry.get_tag("aicp.kind.light")
        assert tag is not None
        assert tag.id == "aicp.kind.light"
    
    def test_list_tags_by_facet(self):
        """Test tag listing filtered by facet."""
        self.registry.create_tag("aicp.role.safety", TagFacet.ROLE)
        self.registry.create_tag("aicp.role.primary", TagFacet.ROLE)
        self.registry.create_tag("aicp.kind.light", TagFacet.KIND)
        
        role_tags = self.registry.list_tags(facet=TagFacet.ROLE)
        assert len(role_tags) == 2
        
        all_tags = self.registry.list_tags()
        assert len(all_tags) == 3
    
    def test_should_materialize_role(self):
        """Test that role.* tags should materialize."""
        tag = self.registry.create_tag(
            "aicp.role.safety_critical",
            TagFacet.ROLE,
        )
        assert tag.should_materialize() is True
    
    def test_should_materialize_state(self):
        """Test that state.* tags should materialize."""
        tag = self.registry.create_tag(
            "aicp.state.needs_repair",
            TagFacet.STATE,
        )
        assert tag.should_materialize() is True
    
    def test_should_not_materialize_kind(self):
        """Test that kind.* tags should NOT materialize."""
        tag = self.registry.create_tag(
            "aicp.kind.light",
            TagFacet.KIND,
        )
        assert tag.should_materialize() is False
    
    def test_learned_tag_not_materialized(self):
        """Test that learned tags are NOT materialized automatically."""
        tag = self.registry.suggest_learned_tag(
            facet=TagFacet.PLACE,
            key="test_zone",
            display_de="Test Zone",
        )
        assert tag.is_learned is True
        assert tag.should_materialize() is False
    
    def test_confirm_learned_tag(self):
        """Test confirming a learned tag."""
        tag = self.registry.suggest_learned_tag(
            TagFacet.PLACE,
            "test_zone",
        )
        confirmed = self.registry.confirm_learned_tag(tag.id)
        assert confirmed is not None
        assert confirmed.is_learned is False
        assert confirmed.provenance == "user"


class TestSubject:
    """Test Subject registration and ID handling."""
    
    def test_canonical_id_unique_id_priority(self):
        """Test canonical ID prefers unique_id over ha_id."""
        subject = Subject(
            ha_id="light.kitchen",
            ha_type=SubjectType.ENTITY,
            unique_id="abc123",
            domain="light",
        )
        assert subject.canonical_id == "abc123"
    
    def test_canonical_id_fallback(self):
        """Test canonical ID falls back to ha_id."""
        subject = Subject(
            ha_id="light.living_room",
            ha_type=SubjectType.ENTITY,
            domain="light",
        )
        assert subject.canonical_id == "light.living_room"


class TestTagAssignment:
    """Test Tag-Subject assignments."""
    
    def setup_method(self):
        self.registry = TagRegistry()
    
    def test_assign_tag_to_subject(self):
        """Test assigning a tag to a subject."""
        self.registry.create_tag("aicp.role.safety", TagFacet.ROLE)
        self.registry.register_subject(
            ha_id="switch.outdoor",
            ha_type=SubjectType.ENTITY,
            domain="switch",
        )
        
        result = self.registry.assign_tag(
            "aicp.role.safety",
            "switch.outdoor",
        )
        assert result is not None
    
    def test_get_subject_tags(self):
        """Test retrieving tags for a subject."""
        self.registry.create_tag("aicp.role.safety", TagFacet.ROLE)
        self.registry.create_tag("aicp.kind.switch", TagFacet.KIND)
        self.registry.register_subject("switch.garage", SubjectType.ENTITY)
        
        self.registry.assign_tag("aicp.role.safety", "switch.garage")
        self.registry.assign_tag("aicp.kind.switch", "switch.garage")
        
        tags = self.registry.get_subject_tags("switch.garage")
        assert len(tags) == 2
    
    def test_assign_nonexistent_tag_fails(self):
        """Test assigning a non-existent tag fails."""
        self.registry.register_subject("light.test", SubjectType.ENTITY)
        result = self.registry.assign_tag("nonexistent", "light.test")
        assert result is None


class TestHabitusZones:
    """Test Habitus Zone functionality."""
    
    def setup_method(self):
        self.registry = TagRegistry()
    
    def test_create_zone(self):
        """Test creating a habitus zone."""
        zone = self.registry.create_zone(
            zone_id="zone.morning_routine",
            name="Morning Routine",
            policy_ids=["policy.auto_lights"],
        )
        assert zone.id == "zone.morning_routine"
        assert zone.name == "Morning Routine"
        assert zone.is_active is True
    
    def test_add_subject_to_zone(self):
        """Test adding a subject to a zone."""
        self.registry.create_zone("zone.evening", "Evening Zone")
        self.registry.register_subject("light.living", SubjectType.ENTITY)
        
        result = self.registry.add_to_zone("zone.evening", "light.living")
        assert result is True


class TestHALabelsExport:
    """Test HA Labels export functionality."""
    
    def test_export_skips_sys_namespace(self):
        """Test that sys.* tags are NOT exported."""
        registry = TagRegistry()
        registry.create_tag("sys.role.internal", TagFacet.ROLE)
        registry.create_tag("aicp.role.safety", TagFacet.ROLE)
        
        labels = registry.export_ha_labels()
        assert len(labels) == 1
        assert labels[0]["name"] == "aicp.role.safety"
    
    def test_export_only_role_and_state(self):
        """Test that only role.* and state.* facets are exported."""
        registry = TagRegistry()
        registry.create_tag("aicp.role.safety", TagFacet.ROLE)
        registry.create_tag("aicp.state.broken", TagFacet.STATE)
        registry.create_tag("aicp.kind.light", TagFacet.KIND)
        registry.create_tag("aicp.place.kitchen", TagFacet.PLACE)
        
        labels = registry.export_ha_labels()
        assert len(labels) == 2
        names = {l["name"] for l in labels}
        assert "aicp.role.safety" in names
        assert "aicp.state.broken" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
