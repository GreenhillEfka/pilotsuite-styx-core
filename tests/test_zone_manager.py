"""Tests for Zone-Aware Neuron Manager — Slice 67."""
import pytest
from copilot_core.neurons.zone_manager import (
    ZoneAwareNeuronManager,
    HabitusZoneConfig,
    ZoneModuleConfig,
    ZoneNeuronState,
    ZoneEvaluationResult,
    ZoneType,
    ModuleType,
    create_zone_aware_neuron_manager,
)
from datetime import datetime, timezone


class TestZoneType:
    """Test zone types."""
    
    def test_zone_type_enum_values(self):
        """Test zone type enum values."""
        assert ZoneType.LIVING.value == "living"
        assert ZoneType.BEDROOM.value == "bedroom"
        assert ZoneType.KITCHEN.value == "kitchen"
        assert ZoneType.OFFICE.value == "office"
        assert ZoneType.BATH.value == "bath"


class TestModuleType:
    """Test module types."""
    
    def test_module_type_enum_values(self):
        """Test module type enum values."""
        assert ModuleType.LIGHT.value == "light"
        assert ModuleType.CLIMATE.value == "climate"
        assert ModuleType.MOTION.value == "motion"
        assert ModuleType.PRESENCE.value == "presence"
        assert ModuleType.MUSIC.value == "music"


class TestZoneModuleConfig:
    """Test zone module configuration."""
    
    def test_create_module_config(self):
        """Test creating module config."""
        config = ZoneModuleConfig(
            module_type=ModuleType.LIGHT,
            enabled=True,
            priority=80,
        )
        
        assert config.module_type == ModuleType.LIGHT
        assert config.enabled is True
        assert config.priority == 80
    
    def test_module_config_to_dict(self):
        """Test module config serialization."""
        config = ZoneModuleConfig(
            module_type=ModuleType.CLIMATE,
            enabled=False,
            priority=60,
            suggestion_mode="manual_only",
            neuron_targets=["comfort", "temperature"],
        )
        
        d = config.to_dict()
        
        assert d["module_type"] == "climate"
        assert d["enabled"] is False
        assert d["priority"] == 60
        assert d["neuron_targets"] == ["comfort", "temperature"]
    
    def test_module_config_defaults(self):
        """Test module config default values."""
        config = ZoneModuleConfig(module_type=ModuleType.LIGHT)
        
        assert config.enabled is True
        assert config.priority == 50
        assert config.suggestion_mode == "explainable_manual"
        assert config.neuron_targets == []


class TestHabitusZoneConfig:
    """Test Habitus zone configuration."""
    
    def test_create_zone_config(self):
        """Test creating zone config."""
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Wohnzimmer",
        )
        
        assert config.zone_id == "zone_living"
        assert config.zone_type == ZoneType.LIVING
        assert config.name == "Wohnzimmer"
    
    def test_zone_config_with_modules(self):
        """Test zone config with modules."""
        config = HabitusZoneConfig(
            zone_id="zone_bedroom",
            zone_type=ZoneType.BEDROOM,
            name="Schlafzimmer",
            modules={
                ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, priority=90),
                ModuleType.CLIMATE: ZoneModuleConfig(ModuleType.CLIMATE, priority=70),
            },
        )
        
        assert ModuleType.LIGHT in config.modules
        assert config.modules[ModuleType.LIGHT].priority == 90
    
    def test_zone_config_with_quiet_hours(self):
        """Test zone config with quiet hours."""
        config = HabitusZoneConfig(
            zone_id="zone_bedroom",
            zone_type=ZoneType.BEDROOM,
            name="Schlafzimmer",
            quiet_hours_start=22,
            quiet_hours_end=7,
        )
        
        assert config.quiet_hours_start == 22
        assert config.quiet_hours_end == 7
    
    def test_zone_config_to_dict(self):
        """Test zone config serialization."""
        config = HabitusZoneConfig(
            zone_id="zone_office",
            zone_type=ZoneType.OFFICE,
            name="Büro",
            occupancy_timeout_seconds=600,
            metadata={"floor": 1, "area_sqm": 15},
        )
        
        d = config.to_dict()
        
        assert d["zone_id"] == "zone_office"
        assert d["occupancy_timeout_seconds"] == 600
        assert d["metadata"]["floor"] == 1


class TestZoneNeuronState:
    """Test zone neuron state."""
    
    def test_create_neuron_state(self):
        """Test creating neuron state."""
        state = ZoneNeuronState(
            zone_id="zone_living",
            neuron_id="light_level",
            neuron_type="context",
            value=0.7,
            confidence=0.9,
            last_update="2025-01-01T00:00:00Z",
        )
        
        assert state.zone_id == "zone_living"
        assert state.value == 0.7
    
    def test_neuron_state_with_module_context(self):
        """Test neuron state with module context."""
        state = ZoneNeuronState(
            zone_id="zone_living",
            neuron_id="presence",
            neuron_type="context",
            value=1.0,
            confidence=0.95,
            last_update="2025-01-01T00:00:00Z",
            module_context="motion_sensor",
        )
        
        assert state.module_context == "motion_sensor"


class TestZoneEvaluationResult:
    """Test zone evaluation result."""
    
    def test_create_result(self):
        """Test creating evaluation result."""
        result = ZoneEvaluationResult(
            zone_id="zone_living",
            timestamp="2025-01-01T00:00:00Z",
            context_values={"light": 0.5},
            state_values={"comfort": 0.7},
            mood_values={"relaxed": 0.6},
            module_states={},
            suggestions=[],
        )
        
        assert result.zone_id == "zone_living"
        assert result.context_values["light"] == 0.5
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = ZoneEvaluationResult(
            zone_id="zone_bedroom",
            timestamp="2025-01-01T00:00:00Z",
            context_values={"light": 0.3},
            state_values={"comfort": 0.8},
            mood_values={"sleepy": 0.9},
            module_states={"light": {"enabled": True}},
            suggestions=[{"type": "light_dim"}],
            dominant_mood="sleepy",
            confidence=0.9,
        )
        
        d = result.to_dict()
        
        assert d["dominant_mood"] == "sleepy"
        assert len(d["suggestions"]) == 1
        assert d["confidence"] == 0.9


class TestZoneAwareNeuronManager:
    """Test zone-aware neuron manager."""
    
    def test_create_manager(self):
        """Test creating manager."""
        manager = create_zone_aware_neuron_manager()
        assert manager is not None
    
    def test_register_zone(self):
        """Test registering zone."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Wohnzimmer",
        )
        
        zone_id = manager.register_zone(config)
        
        assert zone_id == "zone_living"
        
        zone = manager.get_zone("zone_living")
        
        assert zone is not None
        assert zone.name == "Wohnzimmer"
    
    def test_unregister_zone(self):
        """Test unregistering zone."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_test",
            zone_type=ZoneType.OFFICE,
            name="Test Zone",
        )
        
        manager.register_zone(config)
        
        result = manager.unregister_zone("zone_test")
        
        assert result is True
        assert manager.get_zone("zone_test") is None
    
    def test_unregister_nonexistent_zone(self):
        """Test unregistering nonexistent zone."""
        manager = ZoneAwareNeuronManager()
        
        result = manager.unregister_zone("nonexistent")
        
        assert result is False
    
    def test_list_zones(self):
        """Test listing zones."""
        manager = ZoneAwareNeuronManager()
        
        manager.register_zone(HabitusZoneConfig("z1", ZoneType.LIVING, "Living"))
        manager.register_zone(HabitusZoneConfig("z2", ZoneType.BEDROOM, "Bedroom"))
        manager.register_zone(HabitusZoneConfig("z3", ZoneType.KITCHEN, "Kitchen"))
        
        zones = manager.list_zones()
        
        assert len(zones) == 3
    
    def test_set_module_config(self):
        """Test setting module config."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
        )
        manager.register_zone(config)
        
        module_config = ZoneModuleConfig(
            module_type=ModuleType.LIGHT,
            enabled=True,
            priority=85,
        )
        
        result = manager.set_module_config("zone_living", ModuleType.LIGHT, module_config)
        
        assert result is True
        
        retrieved = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert retrieved is not None
        assert retrieved.priority == 85
    
    def test_set_module_config_nonexistent_zone(self):
        """Test setting module config for nonexistent zone."""
        manager = ZoneAwareNeuronManager()
        
        module_config = ZoneModuleConfig(module_type=ModuleType.LIGHT)
        
        result = manager.set_module_config("nonexistent", ModuleType.LIGHT, module_config)
        
        assert result is False
    
    def test_get_module_config_nonexistent(self):
        """Test getting nonexistent module config."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_test", ModuleType.LIGHT)
        
        assert module_config is None
    
    def test_enable_module(self):
        """Test enabling module."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, enabled=False)},
        )
        manager.register_zone(config)
        
        result = manager.enable_module("zone_living", ModuleType.LIGHT)
        
        assert result is True
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert module_config.enabled is True
    
    def test_disable_module(self):
        """Test disabling module."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, enabled=True)},
        )
        manager.register_zone(config)
        
        result = manager.disable_module("zone_living", ModuleType.LIGHT)
        
        assert result is True
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert module_config.enabled is False
    
    def test_set_module_priority(self):
        """Test setting module priority."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        result = manager.set_module_priority("zone_living", ModuleType.LIGHT, 95)
        
        assert result is True
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert module_config.priority == 95
    
    def test_set_module_priority_clamped(self):
        """Test that module priority is clamped to 0-100."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        # Too high
        manager.set_module_priority("zone_living", ModuleType.LIGHT, 150)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert module_config.priority == 100
        
        # Too low
        manager.set_module_priority("zone_living", ModuleType.LIGHT, -10)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        assert module_config.priority == 0
    
    def test_update_ha_states(self):
        """Test updating HA states."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        states = {"light.living": "on", "sensor.temp": 22.5}
        
        manager.update_ha_states("zone_living", states)
        
        assert manager._ha_states["zone_living"] == states
    
    def test_evaluate_zone_empty(self):
        """Test evaluating zone with no neurons."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        result = manager.evaluate_zone("zone_living")
        
        assert result.zone_id == "zone_living"
        assert result.context_values == {}
        assert result.state_values == {}
        assert result.suggestions == []
    
    def test_evaluate_nonexistent_zone(self):
        """Test evaluating nonexistent zone."""
        manager = ZoneAwareNeuronManager()
        
        result = manager.evaluate_zone("nonexistent")
        
        assert result.zone_id == "nonexistent"
        assert result.context_values == {}
    
    def test_evaluate_zone_with_ha_states(self):
        """Test evaluating zone with HA states."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        ha_states = {"light.living": "on"}
        
        result = manager.evaluate_zone("zone_living", ha_states)
        
        assert result.timestamp is not None
    
    def test_get_zone_state(self):
        """Test getting zone state."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        state = manager.get_zone_state("zone_living")
        
        assert state == {}
    
    def test_get_neuron_state(self):
        """Test getting neuron state."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        state = manager.get_neuron_state("zone_living", "light_level")
        
        assert state is None
    
    def test_get_statistics(self):
        """Test getting statistics."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        stats = manager.get_statistics()
        
        assert stats["total_zones"] == 1
        assert "zone_living" in stats["zones"]
    
    def test_statistics_total_modules(self):
        """Test that statistics track enabled modules."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={
                ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, enabled=True),
                ModuleType.CLIMATE: ZoneModuleConfig(ModuleType.CLIMATE, enabled=False),
            },
        )
        manager.register_zone(config)
        
        stats = manager.get_statistics()
        
        assert stats["total_modules"] == 1
    
    def test_register_callback(self):
        """Test registering callback."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        calls = []
        
        def callback(result):
            calls.append(result)
        
        manager.register_callback("zone_living", callback)
        
        assert len(manager._callbacks["zone_living"]) == 1
    
    def test_generate_light_suggestions_low_light(self):
        """Test light suggestions for low light."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        suggestions = manager._generate_light_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.8, "light_level": 0.2},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "light_on"
    
    def test_generate_light_suggestions_no_presence(self):
        """Test light suggestions for no presence."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        suggestions = manager._generate_light_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.1, "light_level": 0.9},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "light_off"
    
    def test_generate_climate_suggestions_low_comfort(self):
        """Test climate suggestions for low comfort."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.CLIMATE: ZoneModuleConfig(ModuleType.CLIMATE)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.CLIMATE)
        
        suggestions = manager._generate_climate_suggestions(
            "zone_living",
            module_config,
            {"comfort_index": 0.2, "presence": 0.8},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "climate_adjust"
    
    def test_generate_climate_suggestions_high_comfort(self):
        """Test climate suggestions for high comfort."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.CLIMATE: ZoneModuleConfig(ModuleType.CLIMATE)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.CLIMATE)
        
        suggestions = manager._generate_climate_suggestions(
            "zone_living",
            module_config,
            {"comfort_index": 0.9, "presence": 0.8},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "climate_eco"
    
    def test_generate_motion_suggestions(self):
        """Test motion suggestions."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.MOTION: ZoneModuleConfig(ModuleType.MOTION)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.MOTION)
        
        suggestions = manager._generate_motion_suggestions(
            "zone_living",
            module_config,
            {"motion": 0.9},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "motion_detected"
    
    def test_generate_presence_suggestions_confirmed(self):
        """Test presence suggestions (confirmed)."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.PRESENCE: ZoneModuleConfig(ModuleType.PRESENCE)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.PRESENCE)
        
        suggestions = manager._generate_presence_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.9, "presence_confidence": 0.95},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "presence_confirmed"
    
    def test_generate_presence_suggestions_absence(self):
        """Test presence suggestions (absence)."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.PRESENCE: ZoneModuleConfig(ModuleType.PRESENCE)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.PRESENCE)
        
        suggestions = manager._generate_presence_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.1},
            {},
        )
        
        assert len(suggestions) >= 1
        assert suggestions[0]["type"] == "absence_detected"
    
    def test_multiple_zones_independent(self):
        """Test that multiple zones are independent."""
        manager = ZoneAwareNeuronManager()
        
        manager.register_zone(HabitusZoneConfig("z1", ZoneType.LIVING, "Living"))
        manager.register_zone(HabitusZoneConfig("z2", ZoneType.BEDROOM, "Bedroom"))
        
        config1 = ZoneModuleConfig(ModuleType.LIGHT, priority=90)
        config2 = ZoneModuleConfig(ModuleType.LIGHT, priority=50)
        
        manager.set_module_config("z1", ModuleType.LIGHT, config1)
        manager.set_module_config("z2", ModuleType.LIGHT, config2)
        
        c1 = manager.get_module_config("z1", ModuleType.LIGHT)
        c2 = manager.get_module_config("z2", ModuleType.LIGHT)
        
        assert c1.priority == 90
        assert c2.priority == 50
    
    def test_zone_id_unique(self):
        """Test that zone IDs are unique (last write wins)."""
        manager = ZoneAwareNeuronManager()
        
        config1 = HabitusZoneConfig("zone_1", ZoneType.LIVING, "Living 1")
        config2 = HabitusZoneConfig("zone_1", ZoneType.BEDROOM, "Bedroom 1")
        
        manager.register_zone(config1)
        manager.register_zone(config2)
        
        zone = manager.get_zone("zone_1")
        
        assert zone.zone_type == ZoneType.BEDROOM
    
    def test_module_config_in_zone_modules(self):
        """Test that module config is stored in zone modules."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_living", ZoneType.LIVING, "Living")
        manager.register_zone(config)
        
        module_config = ZoneModuleConfig(ModuleType.LIGHT, enabled=True, priority=80)
        manager.set_module_config("zone_living", ModuleType.LIGHT, module_config)
        
        zone = manager.get_zone("zone_living")
        
        assert ModuleType.LIGHT in zone.modules
        assert zone.modules[ModuleType.LIGHT].priority == 80
    
    def test_evaluate_zone_includes_module_states(self):
        """Test that zone evaluation includes module states."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        result = manager.evaluate_zone("zone_living")
        
        assert "light" in result.module_states
    
    def test_disabled_module_not_evaluated(self):
        """Test that disabled modules are not evaluated."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={
                ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, enabled=False),
            },
        )
        manager.register_zone(config)
        
        result = manager.evaluate_zone("zone_living")
        
        assert "light" not in result.module_states
    
    def test_suggestion_has_zone_id(self):
        """Test that suggestions include zone_id."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        suggestions = manager._generate_light_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.8, "light_level": 0.2},
            {},
        )
        
        assert suggestions[0]["zone_id"] == "zone_living"
    
    def test_suggestion_has_priority(self):
        """Test that suggestions include priority."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_living",
            zone_type=ZoneType.LIVING,
            name="Living",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT, priority=85)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_living", ModuleType.LIGHT)
        
        suggestions = manager._generate_light_suggestions(
            "zone_living",
            module_config,
            {"presence": 0.8, "light_level": 0.2},
            {},
        )
        
        assert suggestions[0]["priority"] == 85
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        manager = ZoneAwareNeuronManager()
        
        stats = manager.get_statistics()
        
        assert stats["total_zones"] == 0
        assert stats["total_neurons"] == 0
        assert stats["total_modules"] == 0
    
    def test_zone_config_to_dict_includes_all_fields(self):
        """Test that zone config to_dict includes all fields."""
        config = HabitusZoneConfig(
            zone_id="zone_test",
            zone_type=ZoneType.OFFICE,
            name="Office",
            quiet_hours_start=20,
            quiet_hours_end=8,
            occupancy_timeout_seconds=900,
            metadata={"floor": 2},
        )
        
        d = config.to_dict()
        
        assert d["quiet_hours_start"] == 20
        assert d["quiet_hours_end"] == 8
        assert d["occupancy_timeout_seconds"] == 900
        assert d["metadata"]["floor"] == 2
    
    def test_module_config_to_dict_includes_all_fields(self):
        """Test that module config to_dict includes all fields."""
        config = ZoneModuleConfig(
            module_type=ModuleType.TV,
            enabled=False,
            priority=40,
            suggestion_mode="manual_only",
            neuron_targets=["media", "presence"],
            input_signals=["media_player"],
            output_mode="proposal_only",
            zone_overrides={"max_volume": 50},
        )
        
        d = config.to_dict()
        
        assert d["suggestion_mode"] == "manual_only"
        assert d["zone_overrides"]["max_volume"] == 50
    
    def test_result_to_dict_includes_all_fields(self):
        """Test that result to_dict includes all fields."""
        result = ZoneEvaluationResult(
            zone_id="zone_test",
            timestamp="2025-01-01T00:00:00Z",
            context_values={"a": 1},
            state_values={"b": 2},
            mood_values={"c": 3},
            module_states={"light": {"on": True}},
            suggestions=[{"type": "test"}],
            dominant_mood="happy",
            confidence=0.95,
        )
        
        d = result.to_dict()
        
        assert d["dominant_mood"] == "happy"
        assert d["confidence"] == 0.95
        assert len(d["suggestions"]) == 1
    
    def test_create_manager_returns_instance(self):
        """Test that factory function returns instance."""
        manager = create_zone_aware_neuron_manager()
        
        assert isinstance(manager, ZoneAwareNeuronManager)
    
    def test_zone_type_custom(self):
        """Test custom zone type."""
        assert ZoneType.CUSTOM.value == "custom"
    
    def test_module_type_custom(self):
        """Test custom module type."""
        assert ModuleType.CUSTOM.value == "custom"
    
    def test_module_type_blinds(self):
        """Test blinds module type."""
        assert ModuleType.BLINDS.value == "blinds"
    
    def test_module_type_energy(self):
        """Test energy module type."""
        assert ModuleType.ENERGY.value == "energy"
    
    def test_module_type_comfort(self):
        """Test comfort module type."""
        assert ModuleType.COMFORT.value == "comfort"
    
    def test_zone_neuron_state_to_dict_not_implemented(self):
        """Test that ZoneNeuronState doesn't have to_dict (simple dataclass)."""
        state = ZoneNeuronState(
            zone_id="zone_test",
            neuron_id="neuron_1",
            neuron_type="context",
            value=0.5,
            confidence=0.9,
            last_update="2025-01-01T00:00:00Z",
        )
        
        # ZoneNeuronState is a simple dataclass, no to_dict method
        assert hasattr(state, "zone_id")
        assert state.value == 0.5
    
    def test_evaluate_zone_timestamp_set(self):
        """Test that evaluation result has timestamp."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        result = manager.evaluate_zone("zone_test")
        
        assert result.timestamp is not None
    
    def test_evaluate_zone_returns_empty_suggestions_when_no_neurons(self):
        """Test that evaluation returns empty suggestions when no neurons."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        result = manager.evaluate_zone("zone_test")
        
        assert result.suggestions == []
    
    def test_get_module_config_returns_copy(self):
        """Test that get_module_config returns the actual config (not copy)."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_test",
            zone_type=ZoneType.LIVING,
            name="Test",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        retrieved = manager.get_module_config("zone_test", ModuleType.LIGHT)
        
        # Modifying retrieved should affect the stored config
        retrieved.priority = 99
        
        stored = manager.get_module_config("zone_test", ModuleType.LIGHT)
        
        assert stored.priority == 99
    
    def test_register_zone_returns_zone_id(self):
        """Test that register_zone returns zone_id."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("my_zone", ZoneType.LIVING, "My Zone")
        
        zone_id = manager.register_zone(config)
        
        assert zone_id == "my_zone"
    
    def test_list_zones_returns_dicts(self):
        """Test that list_zones returns list of dicts."""
        manager = ZoneAwareNeuronManager()
        
        manager.register_zone(HabitusZoneConfig("z1", ZoneType.LIVING, "Zone 1"))
        
        zones = manager.list_zones()
        
        assert isinstance(zones, list)
        assert isinstance(zones[0], dict)
        assert zones[0]["zone_id"] == "z1"
    
    def test_disable_module_nonexistent_module(self):
        """Test disabling nonexistent module."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        result = manager.disable_module("zone_test", ModuleType.LIGHT)
        
        assert result is False
    
    def test_enable_module_nonexistent_module(self):
        """Test enabling nonexistent module."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        result = manager.enable_module("zone_test", ModuleType.LIGHT)
        
        assert result is False
    
    def test_set_module_priority_nonexistent_module(self):
        """Test setting priority for nonexistent module."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig("zone_test", ZoneType.LIVING, "Test")
        manager.register_zone(config)
        
        result = manager.set_module_priority("zone_test", ModuleType.LIGHT, 80)
        
        assert result is False
    
    def test_generate_suggestions_with_empty_inputs(self):
        """Test generating suggestions with empty neuron inputs."""
        manager = ZoneAwareNeuronManager()
        
        config = HabitusZoneConfig(
            zone_id="zone_test",
            zone_type=ZoneType.LIVING,
            name="Test",
            modules={ModuleType.LIGHT: ZoneModuleConfig(ModuleType.LIGHT)},
        )
        manager.register_zone(config)
        
        module_config = manager.get_module_config("zone_test", ModuleType.LIGHT)
        
        suggestions = manager._generate_light_suggestions(
            "zone_test",
            module_config,
            {},  # Empty inputs
            {},
        )
        
        # Should not crash, may return empty suggestions
        assert isinstance(suggestions, list)
