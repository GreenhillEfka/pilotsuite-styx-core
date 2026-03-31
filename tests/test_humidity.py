"""Tests for Humidity Module — Slice 81."""
import pytest
from copilot_core.humidity.humidity import (
    HumidityModule,
    HumidityConfig,
    HumidityState,
    HumidityAction,
    HumidityMode,
    create_humidity_module,
)
from datetime import datetime, timezone


class TestHumidityMode:
    def test_mode_enum_values(self):
        assert HumidityMode.OFF.value == "off"
        assert HumidityMode.AUTO.value == "auto"
        assert HumidityMode.HUMIDIFY.value == "humidify"
        assert HumidityMode.DEHUMIDIFY.value == "dehumidify"


class TestHumidityConfig:
    def test_create_config(self):
        config = HumidityConfig(zone_id="zone_living")
        assert config.mode == HumidityMode.AUTO
        assert config.target_humidity_percent == 50.0
    
    def test_config_custom_values(self):
        config = HumidityConfig(
            zone_id="zone_bedroom",
            target_humidity_percent=45.0,
            mold_prevention_enabled=True,
            plant_mode_enabled=True,
        )
        assert config.target_humidity_percent == 45.0
        assert config.plant_mode_enabled is True
    
    def test_config_to_dict(self):
        config = HumidityConfig(
            zone_id="zone_test",
            mode=HumidityMode.DEHUMIDIFY,
            health_comfort_enabled=True,
        )
        d = config.to_dict()
        assert d["mode"] == "dehumidify"
        assert d["health_comfort_enabled"] is True


class TestHumidityState:
    def test_create_state(self):
        state = HumidityState(zone_id="zone_living")
        assert state.mode == HumidityMode.OFF
        assert state.is_humidifying is False
    
    def test_state_to_dict(self):
        state = HumidityState(
            zone_id="zone_living",
            current_humidity_percent=55.0,
            is_humidifying=True,
        )
        d = state.to_dict()
        assert d["is_humidifying"] is True


class TestHumidityAction:
    def test_create_action(self):
        action = HumidityAction(
            action_id="ha_test",
            zone_id="zone_living",
            action_type="humidify",
        )
        assert action.triggered_by == "auto"
    
    def test_action_to_dict(self):
        action = HumidityAction(
            action_id="ha_test",
            zone_id="zone_1",
            action_type="dehumidify",
            target_humidity=45.0,
            reason="mold_prevention",
        )
        d = action.to_dict()
        assert d["target_humidity"] == 45.0


class TestHumidityModule:
    def test_create_module(self):
        module = create_humidity_module()
        assert module is not None
    
    def test_set_zone_config(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living", target_humidity_percent=55.0)
        result = module.set_zone_config(config)
        
        assert result is True
        assert module.get_zone_config("zone_living").target_humidity_percent == 55.0
    
    def test_get_nonexistent_config(self):
        module = HumidityModule()
        
        config = module.get_zone_config("nonexistent")
        
        assert config is None
    
    def test_update_sensor_data(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", humidity=55.0)
        
        state = module.get_state("zone_living")
        
        assert state.current_humidity_percent == 55.0
    
    def test_evaluate_zone_humidify(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mode=HumidityMode.AUTO,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Too dry
        module.update_sensor_data("zone_living", humidity=40.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "humidify"
    
    def test_evaluate_zone_dehumidify(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mode=HumidityMode.AUTO,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Too humid
        module.update_sensor_data("zone_living", humidity=60.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "dehumidify"
    
    def test_evaluate_zone_in_tolerance(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mode=HumidityMode.AUTO,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # In tolerance
        module.update_sensor_data("zone_living", humidity=50.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should not turn on
        assert len(actions) == 0 or actions[0].action_type == "turn_off"
    
    def test_mold_prevention(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mold_prevention_enabled=True,
            mold_threshold_percent=65.0,
        )
        module.set_zone_config(config)
        
        # High humidity - mold risk
        module.update_sensor_data("zone_living", humidity=70.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "dehumidify"
        assert "mold" in actions[0].reason.lower()
        
        state = module.get_state("zone_living")
        assert state.mold_risk_active is True
    
    def test_plant_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            plant_mode_enabled=True,
            plant_target_percent=70.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Low humidity for plants
        module.update_sensor_data("zone_living", humidity=50.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "humidify"
        assert "plant" in actions[0].reason.lower()
        
        state = module.get_state("zone_living")
        assert state.plant_mode_active is True
    
    def test_health_comfort_low(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            health_comfort_enabled=True,
            health_min_percent=30.0,
            health_max_percent=60.0,
        )
        module.set_zone_config(config)
        
        # Too dry for health
        module.update_sensor_data("zone_living", humidity=25.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "humidify"
        
        state = module.get_state("zone_living")
        assert state.health_comfort_active is True
    
    def test_health_comfort_high(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            health_comfort_enabled=True,
            health_min_percent=30.0,
            health_max_percent=60.0,
        )
        module.set_zone_config(config)
        
        # Too humid for health
        module.update_sensor_data("zone_living", humidity=65.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "dehumidify"
        
        state = module.get_state("zone_living")
        assert state.health_comfort_active is True
    
    def test_manual_humidify_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mode=HumidityMode.HUMIDIFY,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Below target
        module.update_sensor_data("zone_living", humidity=40.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "humidify"
    
    def test_manual_dehumidify_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            mode=HumidityMode.DEHUMIDIFY,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Above target
        module.update_sensor_data("zone_living", humidity=60.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "dehumidify"
    
    def test_set_target_humidity(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        actions = module.set_target_humidity("zone_living", 55.0)
        
        assert len(actions) == 1
        assert actions[0].target_humidity == 55.0
        assert actions[0].triggered_by == "user"
    
    def test_set_target_humidity_clamped(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_living",
            min_humidity_percent=30.0,
            max_humidity_percent=70.0,
        )
        module.set_zone_config(config)
        
        # Try to set too low
        actions = module.set_target_humidity("zone_living", 20.0)
        
        assert actions[0].target_humidity == 30.0  # Clamped to min
    
    def test_set_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        actions = module.set_mode("zone_living", HumidityMode.DEHUMIDIFY)
        
        assert len(actions) == 1
        assert actions[0].mode == HumidityMode.DEHUMIDIFY
    
    def test_enable_plant_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        result = module.enable_plant_mode("zone_living")
        
        assert result is True
        assert module.get_zone_config("zone_living").plant_mode_enabled is True
    
    def test_disable_plant_mode(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living", plant_mode_enabled=True)
        module.set_zone_config(config)
        
        result = module.disable_plant_mode("zone_living")
        
        assert result is True
        assert module.get_zone_config("zone_living").plant_mode_enabled is False
    
    def test_get_state(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living")
        module.set_zone_config(config)
        module.update_sensor_data("zone_living", humidity=55.0)
        
        state = module.get_state("zone_living")
        
        assert state is not None
        assert state.current_humidity_percent == 55.0
    
    def test_get_nonexistent_state(self):
        module = HumidityModule()
        
        state = module.get_state("nonexistent")
        
        assert state is None
    
    def test_get_pending_actions(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living", mode=HumidityMode.AUTO)
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", humidity=40.0)  # Low
        module.evaluate_zone("zone_living")
        
        actions = module.get_pending_actions("zone_living")
        
        assert len(actions) >= 1
    
    def test_clear_pending_actions(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_living", mode=HumidityMode.AUTO)
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", humidity=40.0)
        module.evaluate_zone("zone_living")
        
        count = module.clear_pending_actions("zone_living")
        
        assert count >= 1
        assert len(module.get_pending_actions("zone_living")) == 0
    
    def test_get_statistics(self):
        module = HumidityModule()
        
        config1 = HumidityConfig(zone_id="zone_1", mode=HumidityMode.AUTO)
        config2 = HumidityConfig(zone_id="zone_2", mode=HumidityMode.AUTO)
        
        module.set_zone_config(config1)
        module.set_zone_config(config2)
        
        module.update_sensor_data("zone_1", humidity=40.0)  # Should humidify
        module.update_sensor_data("zone_2", humidity=70.0)  # Should dehumidify
        
        module.evaluate_zone("zone_1")
        module.evaluate_zone("zone_2")
        
        stats = module.get_statistics()
        
        assert stats["total_zones"] == 2
        assert stats["zones_humidifying"] >= 1
        assert stats["zones_dehumidifying"] >= 1
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_humidity_module(), HumidityModule)
    
    def test_evaluate_zone_no_config(self):
        module = HumidityModule()
        
        actions = module.evaluate_zone("nonexistent")
        
        assert actions == []
    
    def test_enable_plant_mode_nonexistent_zone(self):
        module = HumidityModule()
        
        result = module.enable_plant_mode("nonexistent")
        
        assert result is False
    
    def test_disable_plant_mode_nonexistent_zone(self):
        module = HumidityModule()
        
        result = module.disable_plant_mode("nonexistent")
        
        assert result is False
    
    def test_set_target_humidity_nonexistent_zone(self):
        module = HumidityModule()
        
        actions = module.set_target_humidity("nonexistent", 50.0)
        
        assert actions == []
    
    def test_set_mode_nonexistent_zone(self):
        module = HumidityModule()
        
        actions = module.set_mode("nonexistent", HumidityMode.AUTO)
        
        assert actions == []
    
    def test_clear_pending_actions_nonexistent_zone(self):
        module = HumidityModule()
        
        count = module.clear_pending_actions("nonexistent")
        
        assert count == 0
    
    def test_statistics_mold_risk_zones(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            mold_prevention_enabled=True,
            mold_threshold_percent=65.0,
        )
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", humidity=70.0)
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["mold_risk_zones"] >= 1
    
    def test_statistics_plant_mode_zones(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            plant_mode_enabled=True,
        )
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", humidity=50.0)
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["plant_mode_zones"] >= 1
    
    def test_state_last_update_set(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", humidity=50.0)
        
        state = module.get_state("zone_1")
        
        assert state.last_update is not None
    
    def test_action_timestamp_set(self):
        module = HumidityModule()
        
        config = HumidityConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        actions = module.set_target_humidity("zone_1", 55.0)
        
        assert actions[0].timestamp is not None
    
    def test_config_to_dict_all_fields(self):
        config = HumidityConfig(
            zone_id="zone_test",
            mode=HumidityMode.AUTO,
            target_humidity_percent=50.0,
            min_humidity_percent=30.0,
            max_humidity_percent=70.0,
            humidity_tolerance_percent=5.0,
            mold_prevention_enabled=True,
            mold_threshold_percent=65.0,
            health_comfort_enabled=True,
            plant_mode_enabled=True,
            plant_target_percent=75.0,
            schedule_enabled=True,
        )
        d = config.to_dict()
        assert d["mold_prevention_enabled"] is True
        assert d["plant_target_percent"] == 75.0
    
    def test_state_to_dict_all_fields(self):
        state = HumidityState(
            zone_id="zone_test",
            current_humidity_percent=55.0,
            target_humidity_percent=50.0,
            mode=HumidityMode.AUTO,
            is_humidifying=True,
            is_dehumidifying=False,
            mold_risk_active=False,
        )
        d = state.to_dict()
        assert d["is_humidifying"] is True
        assert d["current_humidity_percent"] == 55.0
    
    def test_action_to_dict_all_fields(self):
        action = HumidityAction(
            action_id="ha_test",
            zone_id="zone_test",
            action_type="set_target",
            target_humidity=55.0,
            mode=HumidityMode.AUTO,
            reason="manual",
            triggered_by="user",
        )
        d = action.to_dict()
        assert d["target_humidity"] == 55.0
        assert d["mode"] == "auto"
    
    def test_statistics_health_comfort_zones(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            health_comfort_enabled=True,
        )
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", humidity=25.0)  # Below health min
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["health_comfort_zones"] >= 1
    
    def test_multiple_zones_independent(self):
        module = HumidityModule()
        
        config1 = HumidityConfig(zone_id="zone_1", target_humidity_percent=50.0)
        config2 = HumidityConfig(zone_id="zone_2", target_humidity_percent=50.0)
        
        module.set_zone_config(config1)
        module.set_zone_config(config2)
        
        module.update_sensor_data("zone_1", humidity=40.0)  # Low
        module.update_sensor_data("zone_2", humidity=60.0)  # High
        
        module.evaluate_zone("zone_1")
        module.evaluate_zone("zone_2")
        
        state1 = module.get_state("zone_1")
        state2 = module.get_state("zone_2")
        
        assert state1.is_humidifying is True
        assert state2.is_dehumidifying is True
    
    def test_humidity_tolerance_prevents_rapid_cycling(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            mode=HumidityMode.AUTO,
            target_humidity_percent=50.0,
            humidity_tolerance_percent=5.0,
        )
        module.set_zone_config(config)
        
        # Just below target but within tolerance
        module.update_sensor_data("zone_1", humidity=47.0)
        
        actions = module.evaluate_zone("zone_1")
        
        # Should not turn on (within tolerance)
        assert len(actions) == 0 or actions[0].action_type == "turn_off"
    
    def test_mold_prevention_overrides_other_modes(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            mode=HumidityMode.HUMIDIFY,  # Manual humidify
            mold_prevention_enabled=True,
            mold_threshold_percent=65.0,
        )
        module.set_zone_config(config)
        
        # High humidity - mold risk should override humidify mode
        module.update_sensor_data("zone_1", humidity=70.0)
        
        actions = module.evaluate_zone("zone_1")
        
        # Should dehumidify despite humidify mode
        assert len(actions) >= 1
        assert actions[0].action_type == "dehumidify"
    
    def test_plant_mode_overrides_health_comfort(self):
        module = HumidityModule()
        
        config = HumidityConfig(
            zone_id="zone_1",
            plant_mode_enabled=True,
            plant_target_percent=70.0,
            health_comfort_enabled=True,
            health_max_percent=60.0,
        )
        module.set_zone_config(config)
        
        # Above health max but below plant target
        module.update_sensor_data("zone_1", humidity=65.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Plant mode should take precedence
        state = module.get_state("zone_1")
        assert state.plant_mode_active is True
