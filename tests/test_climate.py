"""Tests for Climate Module — Slice 80."""
import pytest
from copilot_core.climate.climate import (
    ClimateModule,
    ClimateConfig,
    ClimateState,
    ClimateSchedule,
    ClimateAction,
    HVACMode,
    FanMode,
    create_climate_module,
)
from datetime import datetime, timezone


class TestHVACMode:
    def test_mode_enum_values(self):
        assert HVACMode.OFF.value == "off"
        assert HVACMode.HEAT.value == "heat"
        assert HVACMode.COOL.value == "cool"
        assert HVACMode.AUTO.value == "auto"


class TestFanMode:
    def test_fan_enum_values(self):
        assert FanMode.OFF.value == "off"
        assert FanMode.LOW.value == "low"
        assert FanMode.AUTO.value == "auto"


class TestClimateConfig:
    def test_create_config(self):
        config = ClimateConfig(zone_id="zone_living")
        assert config.hvac_mode == HVACMode.AUTO
        assert config.target_temp_celsius == 21.0
    
    def test_config_custom_values(self):
        config = ClimateConfig(
            zone_id="zone_bedroom",
            target_temp_celsius=19.0,
            min_temp_celsius=15.0,
            max_temp_celsius=25.0,
            eco_mode_enabled=True,
        )
        assert config.target_temp_celsius == 19.0
        assert config.eco_mode_enabled is True
    
    def test_config_to_dict(self):
        config = ClimateConfig(
            zone_id="zone_test",
            hvac_mode=HVACMode.HEAT,
            fan_mode=FanMode.HIGH,
        )
        d = config.to_dict()
        assert d["hvac_mode"] == "heat"
        assert d["fan_mode"] == "high"


class TestClimateSchedule:
    def test_create_schedule(self):
        schedule = ClimateSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning",
            start_time="06:00",
            target_temp=22.0,
        )
        assert len(schedule.days_of_week) == 7
        assert schedule.enabled is True
    
    def test_schedule_weekdays_only(self):
        schedule = ClimateSchedule(
            schedule_id="sched_weekday",
            zone_id="zone_living",
            name="Weekday",
            days_of_week=[0, 1, 2, 3, 4],
        )
        assert len(schedule.days_of_week) == 5
    
    def test_schedule_to_dict(self):
        schedule = ClimateSchedule(
            schedule_id="sched_1",
            zone_id="zone_1",
            name="Test",
            target_temp=20.0,
            hvac_mode=HVACMode.HEAT,
        )
        d = schedule.to_dict()
        assert d["hvac_mode"] == "heat"


class TestClimateState:
    def test_create_state(self):
        state = ClimateState(zone_id="zone_living")
        assert state.hvac_mode == HVACMode.OFF
        assert state.is_heating is False
    
    def test_state_to_dict(self):
        state = ClimateState(
            zone_id="zone_living",
            current_temp_celsius=21.5,
            target_temp_celsius=22.0,
            is_heating=True,
        )
        d = state.to_dict()
        assert d["is_heating"] is True


class TestClimateAction:
    def test_create_action(self):
        action = ClimateAction(
            action_id="ca_test",
            zone_id="zone_living",
            action_type="set_temp",
            target_temp=22.0,
        )
        assert action.triggered_by == "auto"
    
    def test_action_to_dict(self):
        action = ClimateAction(
            action_id="ca_test",
            zone_id="zone_1",
            action_type="turn_on",
            hvac_mode=HVACMode.HEAT,
            reason="temperature_low",
        )
        d = action.to_dict()
        assert d["hvac_mode"] == "heat"


class TestClimateModule:
    def test_create_module(self):
        module = create_climate_module()
        assert module is not None
    
    def test_set_zone_config(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living", target_temp_celsius=22.0)
        result = module.set_zone_config(config)
        
        assert result is True
        assert module.get_zone_config("zone_living").target_temp_celsius == 22.0
    
    def test_get_nonexistent_config(self):
        module = ClimateModule()
        
        config = module.get_zone_config("nonexistent")
        
        assert config is None
    
    def test_add_schedule(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        schedule = ClimateSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning",
            start_time="06:00",
            target_temp=22.0,
        )
        
        schedule_id = module.add_schedule(schedule)
        
        assert schedule_id == "sched_1"
    
    def test_update_sensor_data(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", temperature=21.5, humidity=45.0)
        
        state = module.get_state("zone_living")
        
        assert state.current_temp_celsius == 21.5
        assert state.current_humidity_percent == 45.0
    
    def test_update_window_state(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            window_contact_entity="binary_sensor.window",
        )
        module.set_zone_config(config)
        
        module.update_window_state("zone_living", is_open=True)
        
        state = module.get_state("zone_living")
        
        assert state.window_open is True
    
    def test_update_door_state(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            door_contact_entity="binary_sensor.door",
        )
        module.set_zone_config(config)
        
        module.update_door_state("zone_living", is_open=True)
        
        state = module.get_state("zone_living")
        
        assert state.door_open is True
    
    def test_evaluate_zone_heating(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            hvac_mode=HVACMode.HEAT,
            target_temp_celsius=22.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # Too cold
        module.update_sensor_data("zone_living", temperature=20.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_on"
        assert actions[0].hvac_mode == HVACMode.HEAT
    
    def test_evaluate_zone_cooling(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            hvac_mode=HVACMode.COOL,
            target_temp_celsius=20.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # Too warm
        module.update_sensor_data("zone_living", temperature=22.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_on"
        assert actions[0].hvac_mode == HVACMode.COOL
    
    def test_evaluate_zone_auto_mode_heat(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            hvac_mode=HVACMode.AUTO,
            target_temp_celsius=21.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # Too cold - should heat
        module.update_sensor_data("zone_living", temperature=19.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].hvac_mode == HVACMode.HEAT
    
    def test_evaluate_zone_auto_mode_cool(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            hvac_mode=HVACMode.AUTO,
            target_temp_celsius=21.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # Too warm - should cool
        module.update_sensor_data("zone_living", temperature=23.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].hvac_mode == HVACMode.COOL
    
    def test_evaluate_zone_in_tolerance(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            hvac_mode=HVACMode.HEAT,
            target_temp_celsius=21.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # In tolerance
        module.update_sensor_data("zone_living", temperature=21.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should not turn on heating
        assert len(actions) == 0 or actions[0].action_type != "turn_on"
    
    def test_evaluate_zone_window_open(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            window_contact_entity="binary_sensor.window",
            window_open_action="hvac_off",
        )
        module.set_zone_config(config)
        
        module.update_window_state("zone_living", is_open=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_off"
        assert "window" in actions[0].reason.lower()
    
    def test_evaluate_zone_window_open_reduce_temp(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            window_contact_entity="binary_sensor.window",
            window_open_action="reduce_temp",
        )
        module.set_zone_config(config)
        
        module.update_window_state("zone_living", is_open=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "set_temp"
    
    def test_frost_protection(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            frost_protection_temp=5.0,
        )
        module.set_zone_config(config)
        
        # Very cold
        module.update_sensor_data("zone_living", temperature=3.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert "frost" in actions[0].reason.lower()
        
        state = module.get_state("zone_living")
        assert state.frost_protection_active is True
    
    def test_overheat_protection(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            overheat_protection_temp=35.0,
        )
        module.set_zone_config(config)
        
        # Very hot
        module.update_sensor_data("zone_living", temperature=37.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert "overheat" in actions[0].reason.lower()
        
        state = module.get_state("zone_living")
        assert state.overheat_protection_active is True
    
    def test_eco_mode(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            eco_mode_enabled=True,
            eco_temp_offset_celsius=2.0,
            target_temp_celsius=21.0,
        )
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", temperature=20.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should have eco mode action
        assert len(actions) >= 1
        
        state = module.get_state("zone_living")
        assert state.eco_mode_active is True
    
    def test_disable_eco_mode(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living", eco_mode_enabled=True)
        module.set_zone_config(config)
        
        result = module.disable_eco_mode("zone_living")
        
        assert result is True
        assert module.get_zone_config("zone_living").eco_mode_enabled is False
    
    def test_set_target_temperature(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        actions = module.set_target_temperature("zone_living", 23.0)
        
        assert len(actions) == 1
        assert actions[0].target_temp == 23.0
        assert actions[0].triggered_by == "user"
    
    def test_set_target_temperature_clamped(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            min_temp_celsius=16.0,
            max_temp_celsius=26.0,
        )
        module.set_zone_config(config)
        
        # Try to set too high
        actions = module.set_target_temperature("zone_living", 30.0)
        
        assert actions[0].target_temp == 26.0  # Clamped to max
    
    def test_set_hvac_mode(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        actions = module.set_hvac_mode("zone_living", HVACMode.COOL)
        
        assert len(actions) == 1
        assert actions[0].hvac_mode == HVACMode.COOL
    
    def test_set_fan_mode(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        actions = module.set_fan_mode("zone_living", FanMode.HIGH)
        
        assert len(actions) == 1
        assert actions[0].fan_mode == FanMode.HIGH
    
    def test_get_state(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living")
        module.set_zone_config(config)
        module.update_sensor_data("zone_living", temperature=21.5)
        
        state = module.get_state("zone_living")
        
        assert state is not None
        assert state.current_temp_celsius == 21.5
    
    def test_get_nonexistent_state(self):
        module = ClimateModule()
        
        state = module.get_state("nonexistent")
        
        assert state is None
    
    def test_get_pending_actions(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living", hvac_mode=HVACMode.HEAT)
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", temperature=19.0)
        module.evaluate_zone("zone_living")
        
        actions = module.get_pending_actions("zone_living")
        
        assert len(actions) >= 1
    
    def test_clear_pending_actions(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_living", hvac_mode=HVACMode.HEAT)
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_living", temperature=19.0)
        module.evaluate_zone("zone_living")
        
        count = module.clear_pending_actions("zone_living")
        
        assert count >= 1
        assert len(module.get_pending_actions("zone_living")) == 0
    
    def test_get_statistics(self):
        module = ClimateModule()
        
        config1 = ClimateConfig(zone_id="zone_1", hvac_mode=HVACMode.HEAT)
        config2 = ClimateConfig(zone_id="zone_2", hvac_mode=HVACMode.COOL)
        
        module.set_zone_config(config1)
        module.set_zone_config(config2)
        
        module.update_sensor_data("zone_1", temperature=19.0)  # Should heat
        module.update_sensor_data("zone_2", temperature=25.0)  # Should cool
        
        module.evaluate_zone("zone_1")
        module.evaluate_zone("zone_2")
        
        stats = module.get_statistics()
        
        assert stats["total_zones"] == 2
        assert stats["zones_heating"] >= 1
        assert stats["zones_cooling"] >= 1
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_climate_module(), ClimateModule)
    
    def test_evaluate_zone_no_config(self):
        module = ClimateModule()
        
        actions = module.evaluate_zone("nonexistent")
        
        assert actions == []
    
    def test_evaluate_zone_door_open(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            door_contact_entity="binary_sensor.door",
            window_open_action="hvac_off",
        )
        module.set_zone_config(config)
        
        module.update_door_state("zone_living", is_open=True)
        
        actions = module.evaluate_zone("zone_living")
        
        assert len(actions) >= 1
        assert actions[0].action_type == "turn_off"
    
    def test_evaluate_schedule(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            schedule_enabled=True,
            target_temp_celsius=20.0,
        )
        module.set_zone_config(config)
        
        schedule = ClimateSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning",
            start_time="06:00",
            target_temp=22.0,
        )
        module.add_schedule(schedule)
        
        module.update_sensor_data("zone_living", temperature=20.0)
        
        # Schedule evaluation depends on current time
        actions = module.evaluate_zone("zone_living")
        
        # Should not crash
        assert isinstance(actions, list)
    
    def test_evaluate_schedule_disabled(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_living",
            schedule_enabled=False,
        )
        module.set_zone_config(config)
        
        schedule = ClimateSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Test",
            start_time="06:00",
            target_temp=22.0,
            enabled=False,
        )
        module.add_schedule(schedule)
        
        module.update_sensor_data("zone_living", temperature=20.0)
        
        actions = module.evaluate_zone("zone_living")
        
        assert isinstance(actions, list)
    
    def test_enable_eco_mode_nonexistent_zone(self):
        module = ClimateModule()
        
        result = module.enable_eco_mode("nonexistent")
        
        assert result is False
    
    def test_disable_eco_mode_nonexistent_zone(self):
        module = ClimateModule()
        
        result = module.disable_eco_mode("nonexistent")
        
        assert result is False
    
    def test_set_target_temperature_nonexistent_zone(self):
        module = ClimateModule()
        
        actions = module.set_target_temperature("nonexistent", 22.0)
        
        assert actions == []
    
    def test_set_hvac_mode_nonexistent_zone(self):
        module = ClimateModule()
        
        actions = module.set_hvac_mode("nonexistent", HVACMode.HEAT)
        
        assert actions == []
    
    def test_set_fan_mode_nonexistent_zone(self):
        module = ClimateModule()
        
        actions = module.set_fan_mode("nonexistent", FanMode.HIGH)
        
        assert actions == []
    
    def test_clear_pending_actions_nonexistent_zone(self):
        module = ClimateModule()
        
        count = module.clear_pending_actions("nonexistent")
        
        assert count == 0
    
    def test_statistics_windows_open(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_1",
            window_contact_entity="binary_sensor.window",
        )
        module.set_zone_config(config)
        
        module.update_window_state("zone_1", is_open=True)
        
        stats = module.get_statistics()
        
        assert stats["windows_open"] >= 1
    
    def test_statistics_frost_protection(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1", frost_protection_temp=5.0)
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", temperature=3.0)
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["frost_protection_active"] >= 1
    
    def test_state_last_update_set(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", temperature=21.0)
        
        state = module.get_state("zone_1")
        
        assert state.last_update is not None
    
    def test_action_timestamp_set(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        actions = module.set_target_temperature("zone_1", 22.0)
        
        assert actions[0].timestamp is not None
    
    def test_config_to_dict_all_fields(self):
        config = ClimateConfig(
            zone_id="zone_test",
            hvac_mode=HVACMode.AUTO,
            fan_mode=FanMode.MEDIUM,
            target_temp_celsius=21.0,
            min_temp_celsius=16.0,
            max_temp_celsius=28.0,
            temp_tolerance_celsius=0.5,
            humidity_target_percent=50.0,
            eco_mode_enabled=True,
            eco_temp_offset_celsius=2.0,
            frost_protection_temp=5.0,
            overheat_protection_temp=35.0,
            window_open_action="reduce_temp",
            schedule_enabled=True,
        )
        d = config.to_dict()
        assert d["eco_mode_enabled"] is True
        assert d["schedule_enabled"] is True
    
    def test_schedule_to_dict_all_fields(self):
        schedule = ClimateSchedule(
            schedule_id="sched_test",
            zone_id="zone_test",
            name="Test Schedule",
            days_of_week=[0, 1, 2, 3, 4],
            start_time="07:00",
            target_temp=21.0,
            hvac_mode=HVACMode.HEAT,
            enabled=True,
        )
        d = schedule.to_dict()
        assert d["days_of_week"] == [0, 1, 2, 3, 4]
    
    def test_state_to_dict_all_fields(self):
        state = ClimateState(
            zone_id="zone_test",
            current_temp_celsius=21.5,
            current_humidity_percent=45.0,
            target_temp_celsius=22.0,
            hvac_mode=HVACMode.HEAT,
            fan_mode=FanMode.AUTO,
            is_heating=True,
            is_cooling=False,
            is_fan_on=False,
            window_open=False,
            door_open=False,
        )
        d = state.to_dict()
        assert d["is_heating"] is True
        assert d["current_humidity_percent"] == 45.0
    
    def test_action_to_dict_all_fields(self):
        action = ClimateAction(
            action_id="ca_test",
            zone_id="zone_test",
            action_type="set_temp",
            target_temp=22.0,
            hvac_mode=None,
            fan_mode=None,
            reason="manual",
            triggered_by="user",
        )
        d = action.to_dict()
        assert d["target_temp"] == 22.0
        assert d["triggered_by"] == "user"
    
    def test_statistics_total_schedules(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1", schedule_enabled=True)
        module.set_zone_config(config)
        
        module.add_schedule(ClimateSchedule("s1", "zone_1", "S1", start_time="06:00", target_temp=21.0))
        module.add_schedule(ClimateSchedule("s2", "zone_1", "S2", start_time="18:00", target_temp=22.0))
        
        stats = module.get_statistics()
        
        assert stats["total_schedules"] == 2
    
    def test_multiple_zones_independent(self):
        module = ClimateModule()
        
        config1 = ClimateConfig(zone_id="zone_1", target_temp_celsius=20.0, hvac_mode=HVACMode.HEAT)
        config2 = ClimateConfig(zone_id="zone_2", target_temp_celsius=24.0, hvac_mode=HVACMode.COOL)
        
        module.set_zone_config(config1)
        module.set_zone_config(config2)
        
        module.update_sensor_data("zone_1", temperature=18.0)  # Cold
        module.update_sensor_data("zone_2", temperature=26.0)  # Warm
        
        module.evaluate_zone("zone_1")
        module.evaluate_zone("zone_2")
        
        state1 = module.get_state("zone_1")
        state2 = module.get_state("zone_2")
        
        assert state1.is_heating is True
        assert state2.is_cooling is True
    
    def test_temp_tolerance_prevents_rapid_cycling(self):
        module = ClimateModule()
        
        config = ClimateConfig(
            zone_id="zone_1",
            hvac_mode=HVACMode.HEAT,
            target_temp_celsius=21.0,
            temp_tolerance_celsius=0.5,
        )
        module.set_zone_config(config)
        
        # Just below target but within tolerance
        module.update_sensor_data("zone_1", temperature=20.7)
        
        actions = module.evaluate_zone("zone_1")
        
        # Should not turn on (within tolerance)
        heating_actions = [a for a in actions if a.action_type == "turn_on"]
        assert len(heating_actions) == 0
    
    def test_humidity_tracked_in_state(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", temperature=21.0, humidity=55.0)
        
        state = module.get_state("zone_1")
        
        assert state.current_humidity_percent == 55.0
    
    def test_humidity_optional(self):
        module = ClimateModule()
        
        config = ClimateConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.update_sensor_data("zone_1", temperature=21.0)
        
        state = module.get_state("zone_1")
        
        assert state.current_humidity_percent == 0.0  # Default
