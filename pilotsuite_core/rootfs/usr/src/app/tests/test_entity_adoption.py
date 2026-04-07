"""Tests für Entity Adoption System.

Tests für Auto-Vererbung von Entities (Raum → Zone):
- Automatische Vererbung: Alle Entities eines Raums → Zone
- Aggregation: Zone-Temperatur = Durchschnitt aller Raum-Temperaturen
- Priority-System: Spezifische Entities haben Vorrang
- Override-Möglichkeit: Manuelle Zuordnung möglich
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from copilot_core.homeassistant.entity_adoption import (
    EntityAdoptionService,
    AdoptionAssignment,
    AdoptionPriority,
    ZoneAdoptionState,
    get_adoption_service,
)


class TestAdoptionPriority:
    """Tests für Priority-Enum."""
    
    def test_priority_values(self):
        """Test priority values are correct."""
        assert AdoptionPriority.OVERRIDE.value == 100
        assert AdoptionPriority.SPECIFIC.value == 50
        assert AdoptionPriority.INHERITED.value == 10
    
    def test_priority_ordering(self):
        """Test that OVERRIDE has highest priority."""
        assert AdoptionPriority.OVERRIDE.value > AdoptionPriority.SPECIFIC.value
        assert AdoptionPriority.SPECIFIC.value > AdoptionPriority.INHERITED.value


class TestAdoptionAssignment:
    """Tests für AdoptionAssignment dataclass."""
    
    def test_assignment_creation(self):
        """Test creating an assignment."""
        assignment = AdoptionAssignment(
            id="sensor.temp:zone_og",
            entity_id="sensor.temp",
            zone_id="zone_og",
            source_room_id="room_living",
            priority=AdoptionPriority.OVERRIDE,
        )
        
        assert assignment.id == "sensor.temp:zone_og"
        assert assignment.entity_id == "sensor.temp"
        assert assignment.zone_id == "zone_og"
        assert assignment.source_room_id == "room_living"
        assert assignment.priority == AdoptionPriority.OVERRIDE
    
    def test_assignment_to_dict(self):
        """Test converting assignment to dictionary."""
        assignment = AdoptionAssignment(
            id="sensor.temp:zone_og",
            entity_id="sensor.temp",
            zone_id="zone_og",
            source_room_id="room_living",
            priority=AdoptionPriority.OVERRIDE,
            metadata={"test": "value"},
        )
        
        result = assignment.to_dict()
        
        assert result["id"] == "sensor.temp:zone_og"
        assert result["entity_id"] == "sensor.temp"
        assert result["zone_id"] == "zone_og"
        assert result["source_room_id"] == "room_living"
        assert result["priority"] == 100
        assert result["priority_name"] == "OVERRIDE"
        assert result["metadata"] == {"test": "value"}
        assert "created_at" in result
        assert "updated_at" in result


class TestZoneAdoptionState:
    """Tests für ZoneAdoptionState dataclass."""
    
    def test_zone_state_creation(self):
        """Test creating a zone state."""
        state = ZoneAdoptionState(
            zone_id="zone_og",
            zone_name="Obergeschoss",
            inherited_entities=["sensor.temp1", "sensor.temp2"],
            overridden_entities=["sensor.manual"],
        )
        
        assert state.zone_id == "zone_og"
        assert state.zone_name == "Obergeschoss"
        assert len(state.inherited_entities) == 2
        assert len(state.overridden_entities) == 1
    
    def test_zone_state_to_dict(self):
        """Test converting zone state to dictionary."""
        state = ZoneAdoptionState(
            zone_id="zone_eg",
            zone_name="Erdgeschoss",
            inherited_entities=["sensor.temp1"],
            overridden_entities=[],
            aggregated_sensors={"temperature": 21.5},
        )
        
        result = state.to_dict()
        
        assert result["zone_id"] == "zone_eg"
        assert result["zone_name"] == "Erdgeschoss"
        assert result["inherited_entities"] == ["sensor.temp1"]
        assert result["overridden_entities"] == []
        assert result["aggregated_sensors"] == {"temperature": 21.5}
        assert result["entity_count"] == 1


class TestEntityAdoptionService:
    """Tests für EntityAdoptionService."""
    
    @pytest.fixture
    def service(self):
        """Create fresh service instance for each test."""
        return EntityAdoptionService()
    
    def test_initial_state(self, service):
        """Test service starts with empty state."""
        assert len(service._assignments) == 0
        assert len(service._zone_states) == 0
        assert len(service._room_zone_map) == 0
        assert len(service._entity_room_map) == 0
    
    def test_set_room_zone_mapping(self, service):
        """Test mapping room to zone."""
        service.set_room_zone_mapping("room_living", "zone_og")
        
        assert service._room_zone_map["room_living"] == "zone_og"
    
    def test_set_entity_room_mapping(self, service):
        """Test mapping entity to room."""
        service.set_entity_room_mapping("sensor.temp", "room_living")
        
        assert service._entity_room_map["sensor.temp"] == "room_living"
    
    @pytest.mark.asyncio
    async def test_assign_entity_override(self, service):
        """Test assigning entity with override priority."""
        assignment = await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
            source_room_id="room_living",
            priority=AdoptionPriority.OVERRIDE,
        )
        
        assert assignment.entity_id == "sensor.temp"
        assert assignment.zone_id == "zone_og"
        assert assignment.priority == AdoptionPriority.OVERRIDE
        assert assignment.source_room_id == "room_living"
        
        # Check assignment is stored
        assert "sensor.temp:zone_og" in service._assignments
    
    @pytest.mark.asyncio
    async def test_assign_entity_update_existing(self, service):
        """Test updating existing assignment."""
        # Create initial assignment
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
            priority=AdoptionPriority.INHERITED,
        )
        
        # Update assignment
        assignment = await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
            priority=AdoptionPriority.OVERRIDE,
            metadata={"updated": True},
        )
        
        assert assignment.priority == AdoptionPriority.OVERRIDE
        assert assignment.metadata == {"updated": True}
        
        # Should still be only one assignment
        assert len(service._assignments) == 1
    
    @pytest.mark.asyncio
    async def test_remove_assignment(self, service):
        """Test removing an assignment."""
        # Create assignment
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        assert len(service._assignments) == 1
        
        # Remove assignment
        success = await service.remove_assignment("sensor.temp:zone_og")
        
        assert success is True
        assert len(service._assignments) == 0
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_assignment(self, service):
        """Test removing assignment that doesn't exist."""
        success = await service.remove_assignment("nonexistent:zone")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_get_zone_entities(self, service):
        """Test getting entities for a zone."""
        # Setup mappings
        service.set_room_zone_mapping("room_living", "zone_og")
        service.set_entity_room_mapping("sensor.temp1", "room_living")
        service.set_entity_room_mapping("sensor.temp2", "room_living")
        
        # Add override
        await service.assign_entity(
            entity_id="sensor.manual",
            zone_id="zone_og",
            priority=AdoptionPriority.OVERRIDE,
        )
        
        # Get zone entities
        result = await service.get_zone_entities("zone_og")
        
        assert result["zone_id"] == "zone_og"
        assert result["total_count"] == 3  # 2 inherited + 1 overridden
        assert result["inherited_count"] == 2
        assert result["overridden_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_zone_entities_empty(self, service):
        """Test getting entities for non-existent zone."""
        result = await service.get_zone_entities("nonexistent_zone")
        
        assert result["zone_id"] == "nonexistent_zone"
        assert result["total_count"] == 0
        assert result["entities"] == []
    
    @pytest.mark.asyncio
    async def test_get_assignments_for_zone(self, service):
        """Test getting all assignments for a zone."""
        await service.assign_entity(
            entity_id="sensor.temp1",
            zone_id="zone_og",
        )
        await service.assign_entity(
            entity_id="sensor.temp2",
            zone_id="zone_og",
        )
        await service.assign_entity(
            entity_id="sensor.temp3",
            zone_id="zone_eg",
        )
        
        zone_og_assignments = service.get_assignments_for_zone("zone_og")
        
        assert len(zone_og_assignments) == 2
    
    @pytest.mark.asyncio
    async def test_get_assignment(self, service):
        """Test getting specific assignment."""
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        assignment = service.get_assignment("sensor.temp:zone_og")
        
        assert assignment is not None
        assert assignment.entity_id == "sensor.temp"
    
    @pytest.mark.asyncio
    async def test_get_assignment_not_found(self, service):
        """Test getting non-existent assignment."""
        assignment = service.get_assignment("nonexistent:zone")
        
        assert assignment is None
    
    @pytest.mark.asyncio
    async def test_get_all_assignments(self, service):
        """Test getting all assignments."""
        await service.assign_entity(
            entity_id="sensor.temp1",
            zone_id="zone_og",
        )
        await service.assign_entity(
            entity_id="sensor.temp2",
            zone_id="zone_eg",
        )
        
        all_assignments = service.get_all_assignments()
        
        assert len(all_assignments) == 2
    
    @pytest.mark.asyncio
    async def test_get_stats(self, service):
        """Test getting adoption statistics."""
        # Setup some data
        service.set_room_zone_mapping("room_living", "zone_og")
        service.set_entity_room_mapping("sensor.temp", "room_living")
        
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
            priority=AdoptionPriority.INHERITED,
        )
        await service.assign_entity(
            entity_id="sensor.manual",
            zone_id="zone_og",
            priority=AdoptionPriority.OVERRIDE,
        )
        
        stats = service.get_stats()
        
        assert stats["total_assignments"] == 2
        assert stats["total_zones"] >= 1
        assert stats["total_rooms_mapped"] == 1
        assert stats["override_assignments"] == 1
        assert stats["inherited_assignments"] == 1
    
    @pytest.mark.asyncio
    async def test_refresh_zone(self, service):
        """Test forcing zone refresh."""
        service.set_room_zone_mapping("room_living", "zone_og")
        service.set_entity_room_mapping("sensor.temp", "room_living")
        
        state = await service.refresh_zone("zone_og")
        
        assert state is not None
        assert state.zone_id == "zone_og"
    
    @pytest.mark.asyncio
    async def test_clear(self, service):
        """Test clearing all adoption data."""
        # Setup some data
        service.set_room_zone_mapping("room_living", "zone_og")
        service.set_entity_room_mapping("sensor.temp", "room_living")
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        # Clear
        service.clear()
        
        assert len(service._assignments) == 0
        assert len(service._zone_states) == 0
        assert len(service._room_zone_map) == 0
        assert len(service._entity_room_map) == 0


class TestAdoptionListeners:
    """Tests für Listener-Mechanismus."""
    
    @pytest.fixture
    def service(self):
        """Create fresh service instance."""
        return EntityAdoptionService()
    
    @pytest.mark.asyncio
    async def test_add_listener(self, service):
        """Test adding a listener."""
        listener_called = []
        
        def listener(event_type, data):
            listener_called.append((event_type, data))
        
        service.add_listener(listener)
        
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        assert len(listener_called) == 1
        assert listener_called[0][0] == "entity_assigned"
    
    @pytest.mark.asyncio
    async def test_remove_listener(self, service):
        """Test removing a listener."""
        listener_called = []
        
        def listener(event_type, data):
            listener_called.append((event_type, data))
        
        service.add_listener(listener)
        service.remove_listener(listener)
        
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        assert len(listener_called) == 0
    
    @pytest.mark.asyncio
    async def test_async_listener(self, service):
        """Test async listener."""
        listener_called = []
        
        async def async_listener(event_type, data):
            listener_called.append((event_type, data))
        
        service.add_listener(async_listener)
        
        await service.assign_entity(
            entity_id="sensor.temp",
            zone_id="zone_og",
        )
        
        assert len(listener_called) == 1


class TestAggregation:
    """Tests für Aggregations-Logik."""
    
    @pytest.fixture
    def service(self):
        """Create fresh service instance."""
        return EntityAdoptionService()
    
    @pytest.mark.asyncio
    async def test_aggregation_identifies_sensor_types(self, service):
        """Test that aggregation correctly identifies sensor types."""
        # Setup entities
        service.set_room_zone_mapping("room_living", "zone_og")
        service.set_entity_room_mapping("sensor.living_temperature", "room_living")
        service.set_entity_room_mapping("sensor.living_humidity", "room_living")
        service.set_entity_room_mapping("sensor.living_co2", "room_living")
        
        await service.refresh_zone("zone_og")
        
        result = await service.get_zone_entities("zone_og")
        aggregated = result["aggregated"]
        
        assert "temperature_entities" in aggregated
        assert "humidity_entities" in aggregated
        assert "co2_entities" in aggregated
        
        assert "sensor.living_temperature" in aggregated["temperature_entities"]
        assert "sensor.living_humidity" in aggregated["humidity_entities"]
        assert "sensor.living_co2" in aggregated["co2_entities"]


class TestGetAdoptionService:
    """Tests für globale Service-Instance."""
    
    def test_get_adoption_service_singleton(self):
        """Test that get_adoption_service returns singleton."""
        service1 = get_adoption_service()
        service2 = get_adoption_service()
        
        assert service1 is service2


# Integration tests for API endpoints would go here
# These would test the Flask routes using test_client
