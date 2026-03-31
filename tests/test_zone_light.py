"""Tests for Zone-Aware Light Module — Slice 71."""
import pytest
from copilot_core.light.zone_light import (
    LightModule,
    LightEntity,
    LightConfig,
    ZoneLightState,
    LightAction,
    LightHistoryEntry,
    LightState,
    LightScene,
    create_light_module,
)
from datetime import datetime, timezone, timedelta
import time


class TestLightState:
    """Test light states."""
    
    def test_light_state_enum_values(self):
        """Test light state enum values."""
        assert LightState.OFF.value == "off"
        assert LightState.ON.value == "on"
        assert LightState.DIMMED.value == "dimmed"
        assert LightState.SCENE.value == "scene"
        assert LightState.AUTO.value == "auto"


class TestLightScene:
    """Test light scenes."""
    
    def test_light_scene_enum_values(self):
        """Test light scene enum values."""
        assert LightScene.DEFAULT.value == "default"
        assert LightScene.READING.value == "reading"
        assert LightScene.RELAXING.value == "relaxing"
        assert LightScene.FOCUSED.value == "focused"
        assert LightScene.MOVIE.value == "movie"
        assert LightScene.NIGHT.value == "night"
        assert LightScene.AWAY.value == "away"


class TestLightEntity:
    """Test light entity."""
    
    def test_create_entity(self):
        """Test creating light entity."""
        entity = LightEntity(
            entity_id="light.living_room",
            zone_id="zone_living",
            name="Living Room Light",
        )
        
        assert entity.entity_id == "light.living_room"
        assert entity.enabled is True
    
    def test_entity_to_dict(self):
        """Test entity serialization."""
        entity = LightEntity(
            entity_id="light.bedroom",
            zone_id="zone_bedroom",
            name="Bedroom Light",
            is_primary=True,
            supports_brightness=True,
            supports_color_temp=True,
            supports_color=False,
            power_consumption_watts=10.0,
        )
        
        d = entity.to_dict()
        
        assert d["is_primary"] is True
        assert d["power_consumption_watts"] == 10.0
    
    def test_entity_defaults(self):
        """Test entity default values."""
        entity = LightEntity(
            entity_id="light.test",
            zone_id="zone_test",
            name="Test",
        )
        
        assert entity.enabled is True
        assert entity.is_primary is False
        assert entity.supports_brightness is True
        assert entity.supports_color_temp is False
        assert entity.supports_color is False
        assert entity.power_consumption_watts == 0.0


class TestLightConfig:
    """Test light configuration."""
    
    def test_create_config(self):
        """Test creating light config."""
        config = LightConfig(zone_id="zone_living")
        
        assert config.zone_id == "zone_living"
        assert config.brightness_threshold == 0.3
    
    def test_config_custom_values(self):
        """Test config with custom values."""
        config = LightConfig(
            zone_id="zone_bedroom",
            brightness_threshold=0.5,
            auto_on_enabled=False,
            auto_off_delay_seconds=600,
            default_brightness=0.6,
        )
        
        assert config.brightness_threshold == 0.5
        assert config.auto_on_enabled is False
        assert config.auto_off_delay_seconds == 600
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = LightConfig(
            zone_id="zone_office",
            brightness_threshold=0.4,
            default_color_temp=5000,
        )
        
        d = config.to_dict()
        
        assert d["brightness_threshold"] == 0.4
        assert d["default_color_temp"] == 5000


class TestZoneLightState:
    """Test zone light state."""
    
    def test_create_state(self):
        """Test creating zone light state."""
        state = ZoneLightState(
            zone_id="zone_living",
            state=LightState.ON,
            brightness=0.8,
        )
        
        assert state.zone_id == "zone_living"
        assert state.brightness == 0.8
    
    def test_state_to_dict(self):
        """Test state serialization."""
        state = ZoneLightState(
            zone_id="zone_bedroom",
            state=LightState.SCENE,
            brightness=0.5,
            scene=LightScene.RELAXING,
            color_temp=3000,
            manual_override=True,
        )
        
        d = state.to_dict()
        
        assert d["scene"] == "relaxing"
        assert d["manual_override"] is True
    
    def test_state_scene_none(self):
        """Test state with no scene."""
        state = ZoneLightState(
            zone_id="zone_living",
            state=LightState.ON,
            brightness=0.8,
        )
        
        d = state.to_dict()
        
        assert d["scene"] is None


class TestLightAction:
    """Test light action."""
    
    def test_create_action(self):
        """Test creating light action."""
        action = LightAction(
            action_id="la_test",
            zone_id="zone_living",
            action_type="turn_on",
            target_entities=["light.living"],
            brightness=0.8,
        )
        
        assert action.action_type == "turn_on"
        assert action.triggered_by == "auto"
    
    def test_action_to_dict(self):
        """Test action serialization."""
        action = LightAction(
            action_id="la_test",
            zone_id="zone_living",
            action_type="scene",
            target_entities=["light.living"],
            brightness=0.5,
            color_temp=4000,
            scene=LightScene.READING,
            reason="Reading time",
            triggered_by="manual",
        )
        
        d = action.to_dict()
        
        assert d["scene"] == "reading"
        assert d["triggered_by"] == "manual"


class TestLightHistoryEntry:
    """Test light history entry."""
    
    def test_create_history_entry(self):
        """Test creating history entry."""
        entry = LightHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_living",
            state=LightState.ON,
            brightness=0.8,
            action_type="turn_on",
            triggered_by="auto",
            energy_wh=5.0,
        )
        
        assert entry.energy_wh == 5.0
    
    def test_history_entry_to_dict(self):
        """Test history entry serialization."""
        entry = LightHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_bedroom",
            state=LightState.OFF,
            brightness=0.0,
            action_type="turn_off",
            triggered_by="manual",
        )
        
        d = entry.to_dict()
        
        assert d["state"] == "off"
        assert d["brightness"] == 0.0


class TestLightModule:
    """Test light module."""
    
    def test_create_module(self):
        """Test module creation."""
        module = create_light_module()
        assert module is not None
    
    def test_add_light_entity(self):
        """Test adding light entity."""
        module = LightModule()
        
        entity = LightEntity(
            entity_id="light.living",
            zone_id="zone_living",
            name="Living Light",
        )
        
        entity_id = module.add_light_entity(entity)
        
        assert entity_id == "light.living"
        
        retrieved = module.get_light_entity("light.living")
        
        assert retrieved is not None
        assert retrieved.zone_id == "zone_living"
    
    def test_remove_light_entity(self):
        """Test removing light entity."""
        module = LightModule()
        
        entity = LightEntity(
            entity_id="light.living",
            zone_id="zone_living",
            name="Living Light",
        )
        
        module.add_light_entity(entity)
        
        result = module.remove_light_entity("light.living")
        
        assert result is True
        assert module.get_light_entity("light.living") is None
    
    def test_remove_nonexistent_entity(self):
        """Test removing nonexistent entity."""
        module = LightModule()
        
        result = module.remove_light_entity("nonexistent")
        
        assert result is False
    
    def test_set_zone_config(self):
        """Test setting zone config."""
        module = LightModule()
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
        )
        
        result = module.set_zone_config("zone_living", config)
        
        assert result is True
        
        retrieved = module.get_zone_config("zone_living")
        
        assert retrieved.brightness_threshold == 0.5
    
    def test_set_zone_config_adds_default_scenes(self):
        """Test that zone config gets default scenes."""
        module = LightModule()
        
        config = LightConfig(zone_id="zone_living")
        
        module.set_zone_config("zone_living", config)
        
        assert "reading" in config.scene_presets
        assert "relaxing" in config.scene_presets
    
    def test_update_zone_context(self):
        """Test updating zone context."""
        module = LightModule()
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        
        ctx = module._zone_context["zone_living"]
        
        assert ctx["light_level"] == 0.2
        assert ctx["presence"] is True
    
    def test_update_zone_context_merge(self):
        """Test that context updates merge."""
        module = LightModule()
        
        module.update_zone_context("zone_living", light_level=0.2)
        module.update_zone_context("zone_living", presence=True)
        
        ctx = module._zone_context["zone_living"]
        
        assert ctx["light_level"] == 0.2
        assert ctx["presence"] is True
    
    def test_evaluate_zone_auto_on(self):
        """Test zone evaluation triggers auto-on."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_on"
    
    def test_evaluate_zone_no_auto_on_high_light(self):
        """Test zone evaluation doesn't trigger auto-on with high light."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_zone_context("zone_living", light_level=0.8, presence=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) == 0
    
    def test_evaluate_zone_auto_off(self):
        """Test zone evaluation triggers auto-off."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            auto_off_enabled=True,
            auto_off_delay_seconds=1,  # 1 second for testing
        )
        module.set_zone_config("zone_living", config)
        
        # Turn on first
        module.turn_on("zone_living")
        
        # Wait for off-delay
        time.sleep(1.5)
        
        # No presence
        module.update_zone_context("zone_living", presence=False)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_off"
    
    def test_evaluate_zone_no_auto_off_disabled(self):
        """Test zone evaluation doesn't trigger auto-off when disabled."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            auto_off_enabled=False,
        )
        module.set_zone_config("zone_living", config)
        
        module.turn_on("zone_living")
        
        module.update_zone_context("zone_living", presence=False)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) == 0
    
    def test_manual_override_blocks_auto(self):
        """Test that manual override blocks auto actions."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        # Set manual override
        module.set_manual_override("zone_living", duration_seconds=60)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) == 0
    
    def test_manual_override_expires(self):
        """Test that manual override expires."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        # Set short manual override
        module.set_manual_override("zone_living", duration_seconds=1)
        
        # Wait for expiry
        time.sleep(1.5)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should work after override expires
        assert len(actions) >= 1
    
    def test_clear_manual_override(self):
        """Test clearing manual override."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.set_manual_override("zone_living", duration_seconds=60)
        
        result = module.clear_manual_override("zone_living")
        
        assert result is True
    
    def test_clear_nonexistent_override(self):
        """Test clearing nonexistent override."""
        module = LightModule()
        
        result = module.clear_manual_override("nonexistent")
        
        assert result is False
    
    def test_apply_scene(self):
        """Test applying scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.READING)
        
        assert len(actions) == 1
        assert actions[0].action_type == "scene"
        assert actions[0].scene == LightScene.READING
    
    def test_apply_scene_updates_state(self):
        """Test that applying scene updates zone state."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        module.apply_scene("zone_living", LightScene.RELAXING)
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.state == LightState.SCENE
        assert state.scene == LightScene.RELAXING
    
    def test_turn_on(self):
        """Test turning on lights."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        actions = module.turn_on("zone_living")
        
        assert len(actions) == 1
        assert actions[0].action_type == "turn_on"
    
    def test_turn_on_with_brightness(self):
        """Test turning on with custom brightness."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        actions = module.turn_on("zone_living", brightness=0.5)
        
        assert actions[0].brightness == 0.5
    
    def test_turn_on_with_color_temp(self):
        """Test turning on with custom color temp."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        actions = module.turn_on("zone_living", color_temp=5000)
        
        assert actions[0].color_temp == 5000
    
    def test_turn_on_updates_state(self):
        """Test that turn_on updates zone state."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.state == LightState.ON
        assert state.brightness > 0
    
    def test_turn_off(self):
        """Test turning off lights."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        actions = module.turn_off("zone_living")
        
        assert len(actions) == 1
        assert actions[0].action_type == "turn_off"
    
    def test_turn_off_updates_state(self):
        """Test that turn_off updates zone state."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        module.turn_off("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.state == LightState.OFF
        assert state.brightness == 0.0
    
    def test_is_light_on(self):
        """Test is_light_on check."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        assert module.is_light_on("zone_living") is False
        
        module.turn_on("zone_living")
        
        assert module.is_light_on("zone_living") is True
    
    def test_get_zone_light_state(self):
        """Test getting zone light state."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state is not None
        assert state.state == LightState.ON
    
    def test_get_zone_light_state_nonexistent(self):
        """Test getting state for nonexistent zone."""
        module = LightModule()
        
        state = module.get_zone_light_state("nonexistent")
        
        assert state is None
    
    def test_get_light_entity(self):
        """Test getting light entity."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        retrieved = module.get_light_entity("light.living")
        
        assert retrieved is not None
        assert retrieved.name == "Living Light"
    
    def test_get_light_entity_nonexistent(self):
        """Test getting nonexistent entity."""
        module = LightModule()
        
        entity = module.get_light_entity("nonexistent")
        
        assert entity is None
    
    def test_get_zone_entities(self):
        """Test getting zone entities."""
        module = LightModule()
        
        module.add_light_entity(LightEntity("light.living1", "zone_living", "L1"))
        module.add_light_entity(LightEntity("light.living2", "zone_living", "L2"))
        module.add_light_entity(LightEntity("light.bedroom1", "zone_bedroom", "B1"))
        
        entities = module.get_zone_entities("zone_living")
        
        assert len(entities) == 2
    
    def test_get_light_history(self):
        """Test getting light history."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        module.turn_off("zone_living")
        
        history = module.get_light_history("zone_living")
        
        assert len(history) >= 2
    
    def test_get_light_history_limit(self):
        """Test getting history with limit."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        for i in range(150):
            module.turn_on("zone_living")
            module.turn_off("zone_living")
        
        history = module.get_light_history("zone_living", limit=50)
        
        assert len(history) <= 50
    
    def test_history_limited_to_1000(self):
        """Test that history is limited to 1000 entries."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        for i in range(1500):
            module.turn_on("zone_living")
            module.turn_off("zone_living")
        
        history = module._light_history["zone_living"]
        
        assert len(history) == 1000
    
    def test_get_energy_consumption(self):
        """Test getting energy consumption."""
        module = LightModule()
        
        entity = LightEntity(
            "light.living",
            "zone_living",
            "Living Light",
            power_consumption_watts=10.0,
        )
        module.add_light_entity(entity)
        
        module.turn_on("zone_living", brightness=0.5)
        module.turn_off("zone_living")
        
        energy = module.get_energy_consumption("zone_living")
        
        assert energy >= 0
    
    def test_get_statistics(self):
        """Test getting statistics."""
        module = LightModule()
        
        module.add_light_entity(LightEntity("light.living", "zone_living", "L1"))
        module.add_light_entity(LightEntity("light.bedroom", "zone_bedroom", "B1"))
        
        module.turn_on("zone_living")
        
        stats = module.get_statistics()
        
        assert stats["total_entities"] == 2
        assert stats["zones_with_lights_on"] >= 1
    
    def test_statistics_enabled_disabled(self):
        """Test that statistics track enabled/disabled entities."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        entity.enabled = False
        
        stats = module.get_statistics()
        
        assert stats["disabled_entities"] == 1
    
    def test_statistics_manual_overrides(self):
        """Test that statistics track manual overrides."""
        module = LightModule()
        
        module.add_light_entity(LightEntity("light.living", "zone_living", "L1"))
        
        module.set_manual_override("zone_living", duration_seconds=60)
        
        stats = module.get_statistics()
        
        assert stats["active_manual_overrides"] == 1
    
    def test_get_pending_actions(self):
        """Test getting pending actions."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        module.evaluate_zone("zone_living")
        
        actions = module.get_pending_actions("zone_living")
        
        assert len(actions) >= 1
    
    def test_clear_pending_actions(self):
        """Test clearing pending actions."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        module.evaluate_zone("zone_living")
        
        count = module.clear_pending_actions("zone_living")
        
        assert count >= 1
        
        actions = module.get_pending_actions("zone_living")
        
        assert len(actions) == 0
    
    def test_clear_pending_actions_empty(self):
        """Test clearing empty pending actions."""
        module = LightModule()
        
        count = module.clear_pending_actions("nonexistent")
        
        assert count == 0
    
    def test_multiple_entities_same_zone(self):
        """Test multiple entities in same zone."""
        module = LightModule()
        
        module.add_light_entity(LightEntity("light.living1", "zone_living", "L1"))
        module.add_light_entity(LightEntity("light.living2", "zone_living", "L2"))
        
        module.turn_on("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.lights_on_count >= 1
    
    def test_primary_entity(self):
        """Test primary entity flag."""
        module = LightModule()
        
        module.add_light_entity(
            LightEntity("light.living1", "zone_living", "L1", is_primary=True)
        )
        module.add_light_entity(
            LightEntity("light.living2", "zone_living", "L2", is_primary=False)
        )
        
        actions = module.apply_scene("zone_living", LightScene.READING)
        
        # Should target primary entity
        assert "light.living1" in actions[0].target_entities
    
    def test_zone_state_last_change_set(self):
        """Test that zone state last_change is set."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.last_change is not None
    
    def test_zone_state_last_auto_action_set(self):
        """Test that zone state last_auto_action is set."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.last_auto_action is not None
    
    def test_action_timestamp_set(self):
        """Test that action timestamp is set."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        actions = module.turn_on("zone_living")
        
        assert actions[0].timestamp is not None
    
    def test_history_entry_timestamp_set(self):
        """Test that history entry timestamp is set."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        history = module._light_history["zone_living"]
        
        assert history[0].timestamp is not None
    
    def test_entity_id_unique(self):
        """Test that entity IDs are unique (user-provided)."""
        module = LightModule()
        
        e1 = LightEntity("light_1", "zone_1", "L1")
        e2 = LightEntity("light_1", "zone_2", "L2")  # Same ID, different zone
        
        module.add_light_entity(e1)
        module.add_light_entity(e2)  # Overwrites e1
        
        entity = module.get_light_entity("light_1")
        
        assert entity.zone_id == "zone_2"
    
    def test_multiple_zones_independent(self):
        """Test that multiple zones are independent."""
        module = LightModule()
        
        module.add_light_entity(LightEntity("light.living", "zone_living", "L1"))
        module.add_light_entity(LightEntity("light.bedroom", "zone_bedroom", "B1"))
        
        module.turn_on("zone_living")
        
        assert module.is_light_on("zone_living") is True
        assert module.is_light_on("zone_bedroom") is False
    
    def test_create_module_returns_instance(self):
        """Test that factory function returns instance."""
        module = create_light_module()
        
        assert isinstance(module, LightModule)
    
    def test_light_entity_to_dict_includes_all_fields(self):
        """Test that light entity to_dict includes all fields."""
        entity = LightEntity(
            entity_id="light.test",
            zone_id="zone_test",
            name="Test Light",
            is_primary=True,
            supports_brightness=True,
            supports_color_temp=True,
            supports_color=True,
            power_consumption_watts=15.0,
        )
        
        d = entity.to_dict()
        
        assert d["supports_color"] is True
        assert d["power_consumption_watts"] == 15.0
    
    def test_light_config_to_dict_includes_all_fields(self):
        """Test that light config to_dict includes all fields."""
        config = LightConfig(
            zone_id="zone_test",
            brightness_threshold=0.4,
            auto_on_enabled=True,
            auto_off_enabled=True,
            auto_off_delay_seconds=300,
            default_brightness=0.7,
            default_color_temp=4500,
            min_brightness=0.1,
            max_brightness=1.0,
        )
        
        d = config.to_dict()
        
        assert d["min_brightness"] == 0.1
        assert d["max_brightness"] == 1.0
    
    def test_zone_light_state_to_dict_includes_all_fields(self):
        """Test that zone light state to_dict includes all fields."""
        state = ZoneLightState(
            zone_id="zone_test",
            state=LightState.DIMMED,
            brightness=0.5,
            color_temp=4000,
            scene=None,
            manual_override=False,
            lights_on_count=2,
            lights_off_count=1,
        )
        
        d = state.to_dict()
        
        assert d["lights_on_count"] == 2
        assert d["lights_off_count"] == 1
    
    def test_light_action_to_dict_includes_all_fields(self):
        """Test that light action to_dict includes all fields."""
        action = LightAction(
            action_id="la_test",
            zone_id="zone_test",
            action_type="dim",
            target_entities=["light.test"],
            brightness=0.6,
            color_temp=5000,
            scene=None,
            reason="Testing",
            triggered_by="manual",
        )
        
        d = action.to_dict()
        
        assert d["brightness"] == 0.6
        assert d["color_temp"] == 5000
    
    def test_light_history_entry_to_dict_includes_all_fields(self):
        """Test that history entry to_dict includes all fields."""
        entry = LightHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_test",
            state=LightState.ON,
            brightness=0.8,
            action_type="turn_on",
            triggered_by="auto",
            energy_wh=5.0,
        )
        
        d = entry.to_dict()
        
        assert d["energy_wh"] == 5.0
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        module = LightModule()
        
        stats = module.get_statistics()
        
        assert stats["total_entities"] == 0
        assert stats["total_zones"] == 0
        assert stats["zones_with_lights_on"] == 0
    
    def test_statistics_total_history_entries(self):
        """Test that statistics track total history entries."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        stats = module.get_statistics()
        
        assert stats["total_history_entries"] >= 1
    
    def test_get_light_history_by_hours(self):
        """Test getting light history filtered by hours."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        for i in range(10):
            module.turn_on("zone_living")
            module.turn_off("zone_living")
        
        history = module.get_light_history("zone_living", hours=1)
        
        assert isinstance(history, list)
    
    def test_get_light_history_empty(self):
        """Test getting light history when empty."""
        module = LightModule()
        
        history = module.get_light_history("nonexistent")
        
        assert history == []
    
    def test_evaluate_zone_no_context(self):
        """Test zone evaluation with no context."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        # No context set
        actions = module.evaluate_zone("zone_living")
        
        # Should not crash, may return empty actions
        assert isinstance(actions, list)
    
    def test_evaluate_zone_no_config(self):
        """Test zone evaluation with no config."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        # No config set - should use defaults
        actions = module.evaluate_zone("zone_living")
        
        assert isinstance(actions, list)
    
    def test_turn_on_updates_entity_states(self):
        """Test that turn_on updates entity states."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        
        assert module._entity_states["light.living"] is True
    
    def test_turn_off_updates_entity_states(self):
        """Test that turn_off updates entity states."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.turn_on("zone_living")
        module.turn_off("zone_living")
        
        assert module._entity_states["light.living"] is False
    
    def test_apply_scene_with_custom_brightness(self):
        """Test applying scene with custom brightness in config."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            scene_presets={"reading": {"brightness": 0.95, "color_temp": 5500}},
        )
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.READING)
        
        assert actions[0].brightness == 0.95
    
    def test_zone_state_manual_override_flag(self):
        """Test that zone state manual_override flag is set."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        module.set_manual_override("zone_living", duration_seconds=60)
        
        state = module.get_zone_light_state("zone_living")
        
        assert state.manual_override is True
    
    def test_apply_scene_default_scene(self):
        """Test applying default scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.DEFAULT)
        
        assert len(actions) == 1
    
    def test_turn_on_default_brightness_from_config(self):
        """Test that turn_on uses default brightness from config."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            default_brightness=0.6,
        )
        module.set_zone_config("zone_living", config)
        
        actions = module.turn_on("zone_living")
        
        assert actions[0].brightness == 0.6
    
    def test_turn_on_default_color_temp_from_config(self):
        """Test that turn_on uses default color temp from config."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            default_color_temp=4500,
        )
        module.set_zone_config("zone_living", config)
        
        actions = module.turn_on("zone_living")
        
        assert actions[0].color_temp == 4500
    
    def test_apply_scene_night(self):
        """Test applying night scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.NIGHT)
        
        assert actions[0].scene == LightScene.NIGHT
        # Night scene should have low brightness
        assert actions[0].brightness < 0.3
    
    def test_apply_scene_movie(self):
        """Test applying movie scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.MOVIE)
        
        assert actions[0].scene == LightScene.MOVIE
    
    def test_apply_scene_away(self):
        """Test applying away scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.AWAY)
        
        assert actions[0].scene == LightScene.AWAY
    
    def test_apply_scene_focused(self):
        """Test applying focused scene."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(zone_id="zone_living")
        module.set_zone_config("zone_living", config)
        
        actions = module.apply_scene("zone_living", LightScene.FOCUSED)
        
        assert actions[0].scene == LightScene.FOCUSED
    
    def test_history_energy_calculated(self):
        """Test that history energy is calculated."""
        module = LightModule()
        
        entity = LightEntity(
            "light.living",
            "zone_living",
            "Living Light",
            power_consumption_watts=10.0,
        )
        module.add_light_entity(entity)
        
        module.turn_on("zone_living", brightness=0.5)
        
        history = module._light_history["zone_living"]
        
        # Energy should be calculated based on power * brightness
        assert history[-1].energy_wh >= 0
    
    def test_energy_consumption_zero_when_off(self):
        """Test that energy consumption is zero when lights are off."""
        module = LightModule()
        
        entity = LightEntity(
            "light.living",
            "zone_living",
            "Living Light",
            power_consumption_watts=10.0,
        )
        module.add_light_entity(entity)
        
        module.turn_off("zone_living")
        
        history = module._light_history["zone_living"]
        
        # Last entry should be off with zero energy
        assert history[-1].state == LightState.OFF
    
    def test_get_energy_consumption_nonexistent_zone(self):
        """Test getting energy consumption for nonexistent zone."""
        module = LightModule()
        
        energy = module.get_energy_consumption("nonexistent")
        
        assert energy == 0.0
    
    def test_set_manual_override_nonexistent_zone(self):
        """Test setting manual override for nonexistent zone."""
        module = LightModule()
        
        result = module.set_manual_override("nonexistent", duration_seconds=60)
        
        assert result is False
    
    def test_apply_scene_nonexistent_zone(self):
        """Test applying scene to nonexistent zone."""
        module = LightModule()
        
        actions = module.apply_scene("nonexistent", LightScene.READING)
        
        # Should handle gracefully
        assert isinstance(actions, list)
    
    def test_turn_on_nonexistent_zone(self):
        """Test turning on nonexistent zone."""
        module = LightModule()
        
        actions = module.turn_on("nonexistent")
        
        # Should handle gracefully
        assert isinstance(actions, list)
    
    def test_turn_off_nonexistent_zone(self):
        """Test turning off nonexistent zone."""
        module = LightModule()
        
        actions = module.turn_off("nonexistent")
        
        # Should handle gracefully
        assert isinstance(actions, list)
    
    def test_evaluate_zone_updates_pending_actions(self):
        """Test that evaluate_zone updates pending actions."""
        module = LightModule()
        
        entity = LightEntity("light.living", "zone_living", "Living Light")
        module.add_light_entity(entity)
        
        config = LightConfig(
            zone_id="zone_living",
            brightness_threshold=0.5,
            auto_on_enabled=True,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_zone_context("zone_living", light_level=0.2, presence=True)
        module.evaluate_zone("zone_living")
        
        pending = module._pending_actions.get("zone_living")
        
        assert pending is not None
        assert len(pending) >= 1
    
    def test_scene_presets_merged_from_defaults(self):
        """Test that scene presets are merged from defaults."""
        module = LightModule()
        
        config = LightConfig(zone_id="zone_living")
        
        module.set_zone_config("zone_living", config)
        
        # Should have all default scenes
        assert "reading" in config.scene_presets
        assert "relaxing" in config.scene_presets
        assert "focused" in config.scene_presets
        assert "movie" in config.scene_presets
        assert "night" in config.scene_presets
        assert "away" in config.scene_presets
