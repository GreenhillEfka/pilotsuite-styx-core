"""Tests for Entity Normalization Layer — Slice 69."""
import pytest
from copilot_core.integration.entity_normalization import (
    EntityNormalizationEngine,
    EntityMapping,
    NormalizedState,
    ZoneEntityRegistry,
    EntityType,
    NormalizedType,
    ZoneEntityType,
    create_entity_normalization_engine,
)
from datetime import datetime, timezone


class TestEntityType:
    """Test entity types."""
    
    def test_entity_type_enum_values(self):
        """Test entity type enum values."""
        assert EntityType.SENSOR.value == "sensor"
        assert EntityType.BINARY_SENSOR.value == "binary_sensor"
        assert EntityType.LIGHT.value == "light"
        assert EntityType.CLIMATE.value == "climate"


class TestNormalizedType:
    """Test normalized types."""
    
    def test_normalized_type_enum_values(self):
        """Test normalized type enum values."""
        assert NormalizedType.PRESENCE.value == "presence"
        assert NormalizedType.MOTION.value == "motion"
        assert NormalizedType.LIGHT_LEVEL.value == "light_level"
        assert NormalizedType.TEMPERATURE.value == "temperature"
        assert NormalizedType.HUMIDITY.value == "humidity"


class TestZoneEntityType:
    """Test zone entity types."""
    
    def test_zone_entity_type_enum_values(self):
        """Test zone entity type enum values."""
        assert ZoneEntityType.INPUT.value == "input"
        assert ZoneEntityType.OUTPUT.value == "output"
        assert ZoneEntityType.CONTEXT.value == "context"


class TestEntityMapping:
    """Test entity mapping."""
    
    def test_create_mapping(self):
        """Test creating entity mapping."""
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.living_room_temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
            entity_type=EntityType.SENSOR,
            name="Living Room Temperature",
        )
        
        assert mapping.mapping_id == "map_test"
        assert mapping.ha_entity_id == "sensor.living_room_temp"
    
    def test_mapping_to_dict(self):
        """Test mapping serialization."""
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.lux",
            zone_id="zone_office",
            normalized_type=NormalizedType.LIGHT_LEVEL,
            entity_type=EntityType.SENSOR,
            name="Office Lux",
            unit_of_measurement="lx",
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 1000},
        )
        
        d = mapping.to_dict()
        
        assert d["normalized_type"] == "light_level"
        assert d["normalization_params"]["max"] == 1000
    
    def test_mapping_defaults(self):
        """Test mapping default values."""
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.CUSTOM,
            entity_type=EntityType.CUSTOM,
            name="Test",
        )
        
        assert mapping.enabled is True
        assert mapping.normalization_fn is None
        assert mapping.normalization_params == {}


class TestNormalizedState:
    """Test normalized state."""
    
    def test_create_state(self):
        """Test creating normalized state."""
        state = NormalizedState(
            state_id="state_test",
            mapping_id="map_test",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
            value=22.5,
            raw_value="22.5",
            unit="°C",
            quality=0.95,
        )
        
        assert state.value == 22.5
        assert state.quality == 0.95
    
    def test_state_to_dict(self):
        """Test state serialization."""
        state = NormalizedState(
            state_id="state_test",
            mapping_id="map_test",
            zone_id="zone_bedroom",
            normalized_type=NormalizedType.PRESENCE,
            value=1.0,
            raw_value="on",
            unit=None,
            quality=1.0,
            entity_id="binary_sensor.bedroom_motion",
        )
        
        d = state.to_dict()
        
        assert d["entity_id"] == "binary_sensor.bedroom_motion"
        assert d["normalized_type"] == "presence"


class TestZoneEntityRegistry:
    """Test zone entity registry."""
    
    def test_create_registry(self):
        """Test creating zone registry."""
        registry = ZoneEntityRegistry(zone_id="zone_living")
        
        assert registry.zone_id == "zone_living"
        assert registry.input_entities == {}
    
    def test_registry_to_dict(self):
        """Test registry serialization."""
        registry = ZoneEntityRegistry(zone_id="zone_office")
        registry.input_entities[NormalizedType.TEMPERATURE] = ["map_1", "map_2"]
        registry.output_entities[NormalizedType.LIGHT] = ["map_3"]
        
        d = registry.to_dict()
        
        assert "temperature" in d["input_entities"]
        assert "light" in d["output_entities"]


class TestEntityNormalizationEngine:
    """Test entity normalization engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_entity_normalization_engine()
        assert engine is not None
    
    def test_map_entity(self):
        """Test mapping entity."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.living_room_temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        assert mapping_id is not None
        assert mapping_id.startswith("map_")
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping is not None
        assert mapping.ha_entity_id == "sensor.living_room_temp"
    
    def test_map_entity_with_name(self):
        """Test mapping entity with custom name."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
            name="Custom Name",
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.name == "Custom Name"
    
    def test_map_entity_auto_detect_type(self):
        """Test that entity type is auto-detected."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="binary_sensor.motion",
            zone_id="zone_living",
            normalized_type=NormalizedType.MOTION,
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.entity_type == EntityType.BINARY_SENSOR
    
    def test_map_entity_auto_generate_name(self):
        """Test that name is auto-generated."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.living_room_temperature",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert "Living" in mapping.name or "Room" in mapping.name or "Temperature" in mapping.name
    
    def test_map_entity_with_normalization(self):
        """Test mapping entity with normalization config."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.lux",
            zone_id="zone_office",
            normalized_type=NormalizedType.LIGHT_LEVEL,
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 1000},
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.normalization_fn == "linear"
        assert mapping.normalization_params["max"] == 1000
    
    def test_map_entity_with_unit(self):
        """Test mapping entity with unit."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
            unit_of_measurement="°C",
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.unit_of_measurement == "°C"
    
    def test_update_state(self):
        """Test updating entity state."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        normalized_state = engine.update_state("sensor.temp", 22.5)
        
        assert normalized_state is not None
        assert normalized_state.value == 22.5
        assert normalized_state.raw_value == 22.5
    
    def test_update_state_nonexistent_entity(self):
        """Test updating state for nonexistent entity."""
        engine = EntityNormalizationEngine()
        
        state = engine.update_state("nonexistent_entity", 22.5)
        
        assert state is None
    
    def test_update_state_disabled_mapping(self):
        """Test updating state for disabled mapping."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        engine.disable_mapping(mapping_id)
        
        state = engine.update_state("sensor.temp", 22.5)
        
        assert state is None
    
    def test_update_state_with_attributes(self):
        """Test updating state with attributes."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        state = engine.update_state(
            "sensor.temp",
            22.5,
            attributes={"unit_of_measurement": "°C", "battery_level": 80},
        )
        
        assert state.unit == "°C"
        assert state.quality < 1.0  # Battery affects quality
    
    def test_get_normalized_state(self):
        """Test getting normalized state."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            ha_entity_id="sensor.temp",
            zone_id="zone_living",
            normalized_type=NormalizedType.TEMPERATURE,
        )
        
        engine.update_state("sensor.temp", 22.5)
        
        state = engine.get_normalized_state("zone_living", NormalizedType.TEMPERATURE)
        
        assert state is not None
        assert state.value == 22.5
    
    def test_get_normalized_state_nonexistent(self):
        """Test getting nonexistent normalized state."""
        engine = EntityNormalizationEngine()
        
        state = engine.get_normalized_state("zone_nonexistent", NormalizedType.TEMPERATURE)
        
        assert state is None
    
    def test_get_zone_states(self):
        """Test getting all zone states."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.humidity", "zone_living", NormalizedType.HUMIDITY)
        
        engine.update_state("sensor.temp", 22.5)
        engine.update_state("sensor.humidity", 50.0)
        
        states = engine.get_zone_states("zone_living")
        
        assert "temperature" in states
        assert "humidity" in states
    
    def test_get_mappings_for_zone(self):
        """Test getting mappings for zone."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp1", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp2", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp3", "zone_bedroom", NormalizedType.TEMPERATURE)
        
        mappings = engine.get_mappings_for_zone("zone_living")
        
        assert len(mappings) == 2
    
    def test_get_mappings_for_entity(self):
        """Test getting mappings for entity."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        mappings = engine.get_mappings_for_entity("sensor.temp")
        
        assert len(mappings) == 1
        assert mappings[0].mapping_id == mapping_id
    
    def test_get_zone_registry(self):
        """Test getting zone registry."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
            zone_entity_type=ZoneEntityType.INPUT,
        )
        
        registry = engine.get_zone_registry("zone_living")
        
        assert registry is not None
        assert NormalizedType.TEMPERATURE in registry.input_entities
    
    def test_enable_mapping(self):
        """Test enabling mapping."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        engine.disable_mapping(mapping_id)
        result = engine.enable_mapping(mapping_id)
        
        assert result is True
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.enabled is True
    
    def test_disable_mapping(self):
        """Test disabling mapping."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        result = engine.disable_mapping(mapping_id)
        
        assert result is True
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.enabled is False
    
    def test_unmap_entity(self):
        """Test unmapping entity."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        result = engine.unmap_entity(mapping_id)
        
        assert result is True
        assert engine.get_mapping(mapping_id) is None
    
    def test_unmap_nonexistent_entity(self):
        """Test unmapping nonexistent entity."""
        engine = EntityNormalizationEngine()
        
        result = engine.unmap_entity("nonexistent")
        
        assert result is False
    
    def test_list_mappings(self):
        """Test listing mappings."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp1", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp2", "zone_bedroom", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.humidity1", "zone_living", NormalizedType.HUMIDITY)
        
        mappings = engine.list_mappings()
        
        assert len(mappings) == 3
    
    def test_list_mappings_filtered_by_zone(self):
        """Test listing mappings filtered by zone."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp1", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp2", "zone_bedroom", NormalizedType.TEMPERATURE)
        
        mappings = engine.list_mappings(zone_id="zone_living")
        
        assert len(mappings) == 1
    
    def test_list_mappings_filtered_by_type(self):
        """Test listing mappings filtered by normalized type."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.humidity", "zone_living", NormalizedType.HUMIDITY)
        
        mappings = engine.list_mappings(normalized_type=NormalizedType.TEMPERATURE)
        
        assert len(mappings) == 1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        engine.update_state("sensor.temp", 22.5)
        
        stats = engine.get_statistics()
        
        assert stats["total_mappings"] == 1
        assert stats["enabled_mappings"] == 1
    
    def test_statistics_disabled_mappings(self):
        """Test that statistics track disabled mappings."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        engine.disable_mapping(mapping_id)
        
        stats = engine.get_statistics()
        
        assert stats["disabled_mappings"] == 1
    
    def test_clear_history(self):
        """Test clearing history."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        for i in range(10):
            engine.update_state("sensor.temp", 20.0 + i)
        
        count = engine.clear_history()
        
        assert count >= 10
    
    def test_clear_history_specific_mapping(self):
        """Test clearing history for specific mapping."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        for i in range(10):
            engine.update_state("sensor.temp", 20.0 + i)
        
        count = engine.clear_history(mapping_id)
        
        assert count == 10
    
    def test_get_state_history(self):
        """Test getting state history."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        for i in range(10):
            engine.update_state("sensor.temp", 20.0 + i)
        
        history = engine.get_state_history(mapping_id, limit=5)
        
        assert len(history) == 5
    
    def test_history_limited_to_100(self):
        """Test that history is limited to 100 entries."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        for i in range(150):
            engine.update_state("sensor.temp", 20.0 + i)
        
        history = engine._state_history[mapping_id]
        
        assert len(history) == 100
    
    def test_normalize_linear(self):
        """Test linear normalization."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.LIGHT_LEVEL,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 100},
        )
        
        value = engine._normalize_linear(50, mapping)
        
        assert value == 0.5
    
    def test_normalize_linear_clamped(self):
        """Test that linear normalization is clamped to 0-1."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.LIGHT_LEVEL,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 100},
        )
        
        value_low = engine._normalize_linear(-50, mapping)
        value_high = engine._normalize_linear(150, mapping)
        
        assert value_low == 0.0
        assert value_high == 1.0
    
    def test_normalize_threshold(self):
        """Test threshold normalization."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.MOTION,
            entity_type=EntityType.BINARY_SENSOR,
            name="Test",
            normalization_fn="threshold",
            normalization_params={"threshold": 0.5},
        )
        
        value_below = engine._normalize_threshold(0.3, mapping)
        value_above = engine._normalize_threshold(0.7, mapping)
        
        assert value_below == 0.0
        assert value_above == 1.0
    
    def test_normalize_threshold_inverted(self):
        """Test inverted threshold normalization."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.MOTION,
            entity_type=EntityType.BINARY_SENSOR,
            name="Test",
            normalization_fn="threshold",
            normalization_params={"threshold": 0.5, "invert": True},
        )
        
        value = engine._normalize_threshold(0.3, mapping)
        
        assert value == 1.0  # Inverted: below threshold = 1.0
    
    def test_normalize_boolean_on(self):
        """Test boolean normalization (on)."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="binary_sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.PRESENCE,
            entity_type=EntityType.BINARY_SENSOR,
            name="Test",
            normalization_fn="boolean",
        )
        
        assert engine._normalize_boolean(True, mapping) == 1.0
        assert engine._normalize_boolean("on", mapping) == 1.0
        assert engine._normalize_boolean("true", mapping) == 1.0
        assert engine._normalize_boolean(1, mapping) == 1.0
    
    def test_normalize_boolean_off(self):
        """Test boolean normalization (off)."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="binary_sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.PRESENCE,
            entity_type=EntityType.BINARY_SENSOR,
            name="Test",
            normalization_fn="boolean",
        )
        
        assert engine._normalize_boolean(False, mapping) == 0.0
        assert engine._normalize_boolean("off", mapping) == 0.0
        assert engine._normalize_boolean("false", mapping) == 0.0
        assert engine._normalize_boolean(0, mapping) == 0.0
    
    def test_normalize_percentage(self):
        """Test percentage normalization."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.battery",
            zone_id="zone_test",
            normalized_type=NormalizedType.VOLUME,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="percentage",
        )
        
        assert engine._normalize_percentage(50, mapping) == 0.5
        assert engine._normalize_percentage(100, mapping) == 1.0
        assert engine._normalize_percentage(0, mapping) == 0.0
    
    def test_normalize_temperature(self):
        """Test temperature normalization (returns as-is)."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.temp",
            zone_id="zone_test",
            normalized_type=NormalizedType.TEMPERATURE,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="temperature",
        )
        
        assert engine._normalize_temperature(22.5, mapping) == 22.5
    
    def test_calculate_quality_unavailable(self):
        """Test quality calculation for unavailable state."""
        engine = EntityNormalizationEngine()
        
        quality = engine._calculate_quality("unavailable")
        
        assert quality == 0.0
    
    def test_calculate_quality_unknown(self):
        """Test quality calculation for unknown state."""
        engine = EntityNormalizationEngine()
        
        quality = engine._calculate_quality("unknown")
        
        assert quality == 0.1
    
    def test_calculate_quality_with_battery(self):
        """Test quality calculation with battery level."""
        engine = EntityNormalizationEngine()
        
        quality = engine._calculate_quality(22.5, {"battery_level": 50})
        
        assert quality < 1.0
        assert quality > 0.5
    
    def test_bulk_map_entities(self):
        """Test bulk mapping entities."""
        engine = EntityNormalizationEngine()
        
        patterns = [
            {"entity_id": "sensor.temp1", "normalized_type": "temperature"},
            {"entity_id": "sensor.temp2", "normalized_type": "temperature"},
            {"entity_id": "sensor.humidity", "normalized_type": "humidity"},
        ]
        
        mapping_ids = engine.bulk_map_entities("zone_living", patterns)
        
        assert len(mapping_ids) == 3
    
    def test_auto_detect_zone_entities(self):
        """Test auto-detecting zone entities."""
        engine = EntityNormalizationEngine()
        
        ha_entities = {
            "sensor.living_room_temperature": {"state": "22.5"},
            "sensor.bedroom_motion": {"state": "on"},
            "sensor.kitchen_lux": {"state": "500"},
        }
        
        zone_keywords = {
            "zone_living": ["living", "room"],
            "zone_bedroom": ["bedroom"],
            "zone_kitchen": ["kitchen"],
        }
        
        suggestions = engine.auto_detect_zone_entities(ha_entities, zone_keywords)
        
        assert len(suggestions) >= 2
    
    def test_detect_normalized_type_from_keywords(self):
        """Test detecting normalized type from entity keywords."""
        engine = EntityNormalizationEngine()
        
        # Temperature
        norm_type = engine._detect_normalized_type("sensor.room_temperature", {"state": "22.5"})
        assert norm_type == NormalizedType.TEMPERATURE
        
        # Motion
        norm_type = engine._detect_normalized_type("binary_sensor.motion", {"state": "on"})
        assert norm_type == NormalizedType.MOTION
        
        # Light level
        norm_type = engine._detect_normalized_type("sensor.lux", {"state": "500"})
        assert norm_type == NormalizedType.LIGHT_LEVEL
    
    def test_detect_normalized_type_from_device_class(self):
        """Test detecting normalized type from device class."""
        engine = EntityNormalizationEngine()
        
        state_data = {
            "attributes": {"device_class": "motion"},
            "state": "on",
        }
        
        norm_type = engine._detect_normalized_type("binary_sensor.test", state_data)
        
        assert norm_type == NormalizedType.MOTION
    
    def test_mapping_id_unique(self):
        """Test that mapping IDs are unique."""
        engine = EntityNormalizationEngine()
        
        ids = set()
        for i in range(50):
            mapping_id = engine.map_entity(
                f"sensor.temp{i}",
                "zone_living",
                NormalizedType.TEMPERATURE,
            )
            ids.add(mapping_id)
        
        assert len(ids) == 50
    
    def test_state_id_unique(self):
        """Test that state IDs are unique."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        ids = set()
        for i in range(50):
            state = engine.update_state("sensor.temp", 20.0 + i)
            ids.add(state.state_id)
        
        assert len(ids) == 50
    
    def test_multiple_zones_independent(self):
        """Test that multiple zones are independent."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp1", "zone_living", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp2", "zone_bedroom", NormalizedType.TEMPERATURE)
        
        engine.update_state("sensor.temp1", 22.0)
        engine.update_state("sensor.temp2", 18.0)
        
        living_state = engine.get_normalized_state("zone_living", NormalizedType.TEMPERATURE)
        bedroom_state = engine.get_normalized_state("zone_bedroom", NormalizedType.TEMPERATURE)
        
        assert living_state.value == 22.0
        assert bedroom_state.value == 18.0
    
    def test_entity_mapping_to_dict_includes_all_fields(self):
        """Test that entity mapping to_dict includes all fields."""
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.TEMPERATURE,
            entity_type=EntityType.SENSOR,
            name="Test Sensor",
            unit_of_measurement="°C",
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 100},
            enabled=True,
        )
        
        d = mapping.to_dict()
        
        assert d["unit_of_measurement"] == "°C"
        assert d["normalization_params"]["min"] == 0
    
    def test_normalized_state_to_dict_includes_all_fields(self):
        """Test that normalized state to_dict includes all fields."""
        state = NormalizedState(
            state_id="state_test",
            mapping_id="map_test",
            zone_id="zone_test",
            normalized_type=NormalizedType.PRESENCE,
            value=1.0,
            raw_value="on",
            unit=None,
            quality=0.95,
            entity_id="binary_sensor.motion",
        )
        
        d = state.to_dict()
        
        assert d["quality"] == 0.95
        assert d["entity_id"] == "binary_sensor.motion"
    
    def test_zone_registry_to_dict_includes_all_fields(self):
        """Test that zone registry to_dict includes all fields."""
        registry = ZoneEntityRegistry(zone_id="zone_test")
        registry.input_entities[NormalizedType.TEMPERATURE] = ["map_1"]
        registry.output_entities[NormalizedType.LIGHT] = ["map_2"]
        registry.context_entities[NormalizedType.PRESENCE] = ["map_3"]
        
        d = registry.to_dict()
        
        assert "input_entities" in d
        assert "output_entities" in d
        assert "context_entities" in d
    
    def test_get_statistics_total_zones(self):
        """Test that statistics track total zones."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp1", "zone_1", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp2", "zone_2", NormalizedType.TEMPERATURE)
        engine.map_entity("sensor.temp3", "zone_3", NormalizedType.TEMPERATURE)
        
        stats = engine.get_statistics()
        
        assert stats["total_zones"] == 3
    
    def test_get_statistics_total_history_entries(self):
        """Test that statistics track total history entries."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        for i in range(10):
            engine.update_state("sensor.temp", 20.0 + i)
        
        stats = engine.get_statistics()
        
        assert stats["total_history_entries"] == 10
    
    def test_update_state_preserves_raw_value(self):
        """Test that update_state preserves raw value."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        state = engine.update_state("sensor.temp", "22.5")
        
        assert state.raw_value == "22.5"
        assert state.value == 22.5
    
    def test_update_state_string_to_float(self):
        """Test that string values are converted to float."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        state = engine.update_state("sensor.temp", "22.5")
        
        assert isinstance(state.value, float)
        assert state.value == 22.5
    
    def test_normalize_linear_invalid_value(self):
        """Test linear normalization with invalid value."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.LIGHT_LEVEL,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="linear",
            normalization_params={"min": 0, "max": 100},
        )
        
        value = engine._normalize_linear("invalid", mapping)
        
        assert value == 0.0
    
    def test_normalize_percentage_invalid_value(self):
        """Test percentage normalization with invalid value."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.VOLUME,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="percentage",
        )
        
        value = engine._normalize_percentage("invalid", mapping)
        
        assert value == 0.0
    
    def test_normalize_temperature_invalid_value(self):
        """Test temperature normalization with invalid value."""
        engine = EntityNormalizationEngine()
        
        mapping = EntityMapping(
            mapping_id="map_test",
            ha_entity_id="sensor.test",
            zone_id="zone_test",
            normalized_type=NormalizedType.TEMPERATURE,
            entity_type=EntityType.SENSOR,
            name="Test",
            normalization_fn="temperature",
        )
        
        value = engine._normalize_temperature("invalid", mapping)
        
        assert value == 20.0  # Default room temperature
    
    def test_create_engine_returns_instance(self):
        """Test that factory function returns instance."""
        engine = create_entity_normalization_engine()
        
        assert isinstance(engine, EntityNormalizationEngine)
    
    def test_state_timestamp_set(self):
        """Test that state timestamp is set."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity("sensor.temp", "zone_living", NormalizedType.TEMPERATURE)
        
        state = engine.update_state("sensor.temp", 22.5)
        
        assert state.timestamp is not None
    
    def test_mapping_created_at_set(self):
        """Test that mapping created_at is set."""
        engine = EntityNormalizationEngine()
        
        mapping_id = engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        mapping = engine.get_mapping(mapping_id)
        
        assert mapping.created_at is not None
    
    def test_list_mappings_empty(self):
        """Test listing mappings when empty."""
        engine = EntityNormalizationEngine()
        
        mappings = engine.list_mappings()
        
        assert mappings == []
    
    def test_get_zone_states_empty(self):
        """Test getting zone states when empty."""
        engine = EntityNormalizationEngine()
        
        states = engine.get_zone_states("zone_nonexistent")
        
        assert states == {}
    
    def test_get_state_history_empty(self):
        """Test getting state history when empty."""
        engine = EntityNormalizationEngine()
        
        history = engine.get_state_history("nonexistent_mapping")
        
        assert history == []
    
    def test_clear_history_empty(self):
        """Test clearing empty history."""
        engine = EntityNormalizationEngine()
        
        count = engine.clear_history()
        
        assert count == 0
    
    def test_clear_history_nonexistent_mapping(self):
        """Test clearing history for nonexistent mapping."""
        engine = EntityNormalizationEngine()
        
        count = engine.clear_history("nonexistent")
        
        assert count == 0
    
    def test_enable_nonexistent_mapping(self):
        """Test enabling nonexistent mapping."""
        engine = EntityNormalizationEngine()
        
        result = engine.enable_mapping("nonexistent")
        
        assert result is False
    
    def test_disable_nonexistent_mapping(self):
        """Test disabling nonexistent mapping."""
        engine = EntityNormalizationEngine()
        
        result = engine.disable_mapping("nonexistent")
        
        assert result is False
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = EntityNormalizationEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_mappings"] == 0
        assert stats["enabled_mappings"] == 0
        assert stats["total_zones"] == 0
        assert stats["total_history_entries"] == 0
    
    def test_zone_entity_type_input(self):
        """Test zone entity type INPUT."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
            zone_entity_type=ZoneEntityType.INPUT,
        )
        
        registry = engine.get_zone_registry("zone_living")
        
        assert NormalizedType.TEMPERATURE in registry.input_entities
    
    def test_zone_entity_type_output(self):
        """Test zone entity type OUTPUT."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "light.main",
            "zone_living",
            NormalizedType.BRIGHTNESS,
            zone_entity_type=ZoneEntityType.OUTPUT,
        )
        
        registry = engine.get_zone_registry("zone_living")
        
        assert NormalizedType.BRIGHTNESS in registry.output_entities
    
    def test_zone_entity_type_context(self):
        """Test zone entity type CONTEXT."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.time",
            "zone_living",
            NormalizedType.CUSTOM,
            zone_entity_type=ZoneEntityType.CONTEXT,
        )
        
        registry = engine.get_zone_registry("zone_living")
        
        assert NormalizedType.CUSTOM in registry.context_entities
    
    def test_bulk_map_returns_mapping_ids(self):
        """Test that bulk_map_entities returns mapping IDs."""
        engine = EntityNormalizationEngine()
        
        patterns = [
            {"entity_id": "sensor.temp1", "normalized_type": "temperature"},
        ]
        
        mapping_ids = engine.bulk_map_entities("zone_living", patterns)
        
        assert len(mapping_ids) == 1
        assert all(id.startswith("map_") for id in mapping_ids)
    
    def test_auto_detect_returns_suggestions(self):
        """Test that auto_detect returns suggestions list."""
        engine = EntityNormalizationEngine()
        
        ha_entities = {
            "sensor.living_room_temperature": {"state": "22.5"},
        }
        
        zone_keywords = {
            "zone_living": ["living"],
        }
        
        suggestions = engine.auto_detect_zone_entities(ha_entities, zone_keywords)
        
        assert isinstance(suggestions, list)
        
        if len(suggestions) > 0:
            assert "entity_id" in suggestions[0]
            assert "zone_id" in suggestions[0]
            assert "normalized_type" in suggestions[0]
    
    def test_detect_normalized_type_returns_none_for_unknown(self):
        """Test that detect_normalized_type returns None for unknown types."""
        engine = EntityNormalizationEngine()
        
        norm_type = engine._detect_normalized_type("sensor.unknown_entity", {"state": "value"})
        
        assert norm_type is None
    
    def test_update_state_with_none_state(self):
        """Test updating state with None value."""
        engine = EntityNormalizationEngine()
        
        engine.map_entity(
            "sensor.temp",
            "zone_living",
            NormalizedType.TEMPERATURE,
        )
        
        state = engine.update_state("sensor.temp", None)
        
        # Should handle None gracefully
        assert state is not None
        assert state.value == 0.0 or state.quality == 0.0
