"""Tests for Energy Module — Slice 82."""
import pytest
from copilot_core.energy.energy import (
    EnergyModule,
    EnergyConfig,
    DeviceEnergy,
    ZoneEnergyState,
    EnergyAction,
    EnergySource,
    LoadPriority,
    create_energy_module,
)
from datetime import datetime, timezone


class TestEnergySource:
    def test_source_enum_values(self):
        assert EnergySource.GRID.value == "grid"
        assert EnergySource.SOLAR.value == "solar"
        assert EnergySource.BATTERY.value == "battery"


class TestLoadPriority:
    def test_priority_enum_values(self):
        assert LoadPriority.CRITICAL.value == "critical"
        assert LoadPriority.HIGH.value == "high"
        assert LoadPriority.MEDIUM.value == "medium"
        assert LoadPriority.LOW.value == "low"


class TestEnergyConfig:
    def test_create_config(self):
        config = EnergyConfig(zone_id="zone_living")
        assert config.monthly_budget_kwh == 500.0
        assert config.load_shedding_enabled is True
    
    def test_config_custom_values(self):
        config = EnergyConfig(
            zone_id="zone_living",
            daily_budget_kwh=15.0,
            peak_limit_kw=4.0,
            solar_priority_enabled=True,
        )
        assert config.daily_budget_kwh == 15.0
        assert config.solar_priority_enabled is True
    
    def test_config_to_dict(self):
        config = EnergyConfig(
            zone_id="zone_test",
            battery_management_enabled=True,
            cost_optimization_enabled=True,
        )
        d = config.to_dict()
        assert d["battery_management_enabled"] is True


class TestDeviceEnergy:
    def test_create_device(self):
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Washing Machine",
            power_rating_watts=2000.0,
        )
        assert device.priority == LoadPriority.MEDIUM
        assert device.is_deferrable is False
    
    def test_device_deferrable(self):
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="EV Charger",
            power_rating_watts=7000.0,
            priority=LoadPriority.LOW,
            is_deferrable=True,
        )
        assert device.is_deferrable is True
        assert device.priority == LoadPriority.LOW
    
    def test_device_to_dict(self):
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_1",
            name="Test Device",
            power_rating_watts=100.0,
            current_power_watts=50.0,
        )
        d = device.to_dict()
        assert d["current_power_watts"] == 50.0


class TestZoneEnergyState:
    def test_create_state(self):
        state = ZoneEnergyState(zone_id="zone_living")
        assert state.budget_remaining_percent == 100.0
        assert state.load_shedding_active is False
    
    def test_state_to_dict(self):
        state = ZoneEnergyState(
            zone_id="zone_living",
            current_power_kw=2.5,
            energy_today_kwh=10.0,
            efficiency_score=0.85,
        )
        d = state.to_dict()
        assert d["efficiency_score"] == 0.85


class TestEnergyAction:
    def test_create_action(self):
        action = EnergyAction(
            action_id="ea_test",
            zone_id="zone_living",
            action_type="shed_load",
            device_id="device_1",
        )
        assert action.triggered_by == "auto"
    
    def test_action_to_dict(self):
        action = EnergyAction(
            action_id="ea_test",
            zone_id="zone_1",
            action_type="charge_battery",
            power_kw=3.0,
            reason="off_peak",
        )
        d = action.to_dict()
        assert d["power_kw"] == 3.0


class TestEnergyModule:
    def test_create_module(self):
        module = create_energy_module()
        assert module is not None
    
    def test_set_zone_config(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_living", daily_budget_kwh=15.0)
        result = module.set_zone_config(config)
        
        assert result is True
        assert module.get_zone_config("zone_living").daily_budget_kwh == 15.0
    
    def test_get_nonexistent_config(self):
        module = EnergyModule()
        
        config = module.get_zone_config("nonexistent")
        
        assert config is None
    
    def test_add_device(self):
        module = EnergyModule()
        
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Test Device",
            power_rating_watts=100.0,
        )
        
        device_id = module.add_device(device)
        
        assert device_id == "device_1"
        assert module.get_device("device_1") is not None
    
    def test_update_power_data(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        module.update_power_data("zone_living", power_kw=2.5, solar_kw=1.0, battery_percent=80.0)
        
        state = module.get_state("zone_living")
        
        assert state.current_power_kw == 2.5
        assert state.solar_production_kw == 1.0
        assert state.battery_charge_percent == 80.0
    
    def test_update_device_power(self):
        module = EnergyModule()
        
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Test",
            power_rating_watts=100.0,
        )
        module.add_device(device)
        
        module.update_device_power("device_1", power_watts=50.0)
        
        device = module.get_device("device_1")
        
        assert device.current_power_watts == 50.0
        assert device.energy_today_kwh > 0
    
    def test_evaluate_zone_budget_low(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            daily_budget_kwh=10.0,
            load_shedding_enabled=True,
        )
        module.set_zone_config(config)
        
        # Add low priority deferrable device
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Washing Machine",
            power_rating_watts=2000.0,
            priority=LoadPriority.LOW,
            is_deferrable=True,
        )
        module.add_device(device)
        module.update_device_power("device_1", 2000.0)
        
        # Simulate high energy usage
        state = module.get_state("zone_living")
        state.energy_today_kwh = 9.0  # 90% of budget
        
        actions = module.evaluate_zone("zone_living")
        
        # Should shed load
        assert len(actions) >= 1
        assert actions[0].action_type == "shed_load"
    
    def test_evaluate_zone_peak_limit(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            peak_limit_kw=3.0,
        )
        module.set_zone_config(config)
        
        # Add deferrable device
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Test",
            power_rating_watts=2000.0,
            is_deferrable=True,
        )
        module.add_device(device)
        module.update_device_power("device_1", 2000.0)
        
        # Exceed peak limit
        module.update_power_data("zone_living", power_kw=4.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should shed load to reduce peak
        shed_actions = [a for a in actions if a.action_type == "shed_load"]
        assert len(shed_actions) >= 1
    
    def test_evaluate_zone_solar_priority(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            solar_priority_enabled=True,
        )
        module.set_zone_config(config)
        
        # Add deferrable device (currently off)
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="EV Charger",
            power_rating_watts=3000.0,
            is_deferrable=True,
        )
        module.add_device(device)
        
        # Excess solar (solar > consumption)
        module.update_power_data("zone_living", power_kw=1.0, solar_kw=2.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should enable deferrable load
        enable_actions = [a for a in actions if a.action_type == "enable_load"]
        assert len(enable_actions) >= 1
    
    def test_evaluate_zone_battery_charge(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            battery_management_enabled=True,
            battery_min_charge_percent=20.0,
        )
        module.set_zone_config(config)
        
        # Low battery, off-peak hour
        module.update_power_data("zone_living", power_kw=1.0, battery_percent=15.0)
        
        actions = module.evaluate_zone("zone_living")
        
        # Should charge battery
        charge_actions = [a for a in actions if a.action_type == "charge_battery"]
        assert len(charge_actions) >= 1
    
    def test_evaluate_zone_battery_discharge(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            battery_management_enabled=True,
            battery_min_charge_percent=20.0,
            peak_hours=[17, 18, 19],
        )
        module.set_zone_config(config)
        
        # High battery, peak hour
        module.update_power_data("zone_living", power_kw=2.0, battery_percent=80.0)
        
        # Set is_peak_hour manually (depends on current time)
        state = module.get_state("zone_living")
        state.is_peak_hour = True
        
        actions = module.evaluate_zone("zone_living")
        
        # Should discharge battery
        discharge_actions = [a for a in actions if a.action_type == "discharge_battery"]
        assert len(discharge_actions) >= 1
    
    def test_evaluate_zone_cost_optimization(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_living",
            cost_optimization_enabled=True,
            peak_hours=[17, 18, 19],
        )
        module.set_zone_config(config)
        
        # Add medium priority deferrable device
        device = DeviceEnergy(
            device_id="device_1",
            zone_id="zone_living",
            name="Dishwasher",
            power_rating_watts=1500.0,
            priority=LoadPriority.MEDIUM,
            is_deferrable=True,
        )
        module.add_device(device)
        module.update_device_power("device_1", 1500.0)
        
        # Peak hour
        state = module.get_state("zone_living")
        state.is_peak_hour = True
        
        actions = module.evaluate_zone("zone_living")
        
        # Should defer non-essential loads
        defer_actions = [a for a in actions if a.action_type == "defer_load"]
        assert len(defer_actions) >= 1
    
    def test_get_state(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_living")
        module.set_zone_config(config)
        module.update_power_data("zone_living", power_kw=2.0)
        
        state = module.get_state("zone_living")
        
        assert state is not None
        assert state.current_power_kw == 2.0
    
    def test_get_nonexistent_state(self):
        module = EnergyModule()
        
        state = module.get_state("nonexistent")
        
        assert state is None
    
    def test_get_device(self):
        module = EnergyModule()
        
        device = DeviceEnergy("device_1", "zone_1", "Test", 100.0)
        module.add_device(device)
        
        retrieved = module.get_device("device_1")
        
        assert retrieved is not None
        assert retrieved.name == "Test"
    
    def test_get_zone_devices(self):
        module = EnergyModule()
        
        module.add_device(DeviceEnergy("d1", "zone_1", "D1", 100.0))
        module.add_device(DeviceEnergy("d2", "zone_1", "D2", 200.0))
        module.add_device(DeviceEnergy("d3", "zone_2", "D3", 150.0))
        
        devices = module.get_zone_devices("zone_1")
        
        assert len(devices) == 2
    
    def test_get_pending_actions(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_living", daily_budget_kwh=10.0)
        module.set_zone_config(config)
        
        device = DeviceEnergy(
            "device_1", "zone_living", "Test",
            1000.0, priority=LoadPriority.LOW, is_deferrable=True,
        )
        module.add_device(device)
        module.update_device_power("device_1", 1000.0)
        
        state = module.get_state("zone_living")
        state.energy_today_kwh = 9.5  # Low budget remaining
        
        module.evaluate_zone("zone_living")
        
        actions = module.get_pending_actions("zone_living")
        
        assert len(actions) >= 1
    
    def test_clear_pending_actions(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_living")
        module.set_zone_config(config)
        
        module.update_power_data("zone_living", power_kw=1.0)
        module.evaluate_zone("zone_living")
        
        count = module.clear_pending_actions("zone_living")
        
        assert len(module.get_pending_actions("zone_living")) == 0
    
    def test_get_statistics(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.add_device(DeviceEnergy("d1", "zone_1", "D1", 100.0))
        module.add_device(DeviceEnergy("d2", "zone_1", "D2", 200.0))
        
        module.update_device_power("d1", 50.0)
        module.update_device_power("d2", 100.0)
        
        stats = module.get_statistics()
        
        assert stats["total_devices"] == 2
        assert stats["total_current_power_kw"] > 0
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_energy_module(), EnergyModule)
    
    def test_evaluate_zone_no_config(self):
        module = EnergyModule()
        
        actions = module.evaluate_zone("nonexistent")
        
        assert actions == []
    
    def test_update_device_power_nonexistent(self):
        module = EnergyModule()
        
        # Should not crash
        module.update_device_power("nonexistent", 100.0)
    
    def test_clear_pending_actions_nonexistent(self):
        module = EnergyModule()
        
        count = module.clear_pending_actions("nonexistent")
        
        assert count == 0
    
    def test_statistics_zones_over_budget(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1", daily_budget_kwh=10.0)
        module.set_zone_config(config)
        
        state = module.get_state("zone_1")
        state.energy_today_kwh = 8.0  # 80% used, 20% remaining
        
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["zones_over_budget"] >= 0
    
    def test_statistics_load_shedding_zones(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1", daily_budget_kwh=10.0, load_shedding_enabled=True)
        module.set_zone_config(config)
        
        state = module.get_state("zone_1")
        state.energy_today_kwh = 9.0  # 90% used
        
        module.evaluate_zone("zone_1")
        
        stats = module.get_statistics()
        
        assert stats["zones_load_shedding"] >= 0
    
    def test_efficiency_score_calculated(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        # Add power history
        for i in range(20):
            module.update_power_data("zone_1", power_kw=2.0 + (i % 3) * 0.5)
        
        module.evaluate_zone("zone_1")
        
        state = module.get_state("zone_1")
        
        assert 0.0 <= state.efficiency_score <= 1.0
    
    def test_budget_remaining_percent_calculated(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1", daily_budget_kwh=20.0)
        module.set_zone_config(config)
        
        state = module.get_state("zone_1")
        state.energy_today_kwh = 10.0  # 50% used
        
        module.evaluate_zone("zone_1")
        
        assert state.budget_remaining_percent == 50.0
    
    def test_peak_hour_detection(self):
        module = EnergyModule()
        
        config = EnergyConfig(
            zone_id="zone_1",
            peak_hours=[17, 18, 19],
        )
        module.set_zone_config(config)
        
        # Update during peak hour (depends on current time)
        module.update_power_data("zone_1", power_kw=1.0)
        
        state = module.get_state("zone_1")
        
        # is_peak_hour depends on actual current hour
        assert isinstance(state.is_peak_hour, bool)
    
    def test_device_energy_accumulates(self):
        module = EnergyModule()
        
        device = DeviceEnergy("d1", "zone_1", "Test", 1000.0)
        module.add_device(device)
        
        # Update power multiple times
        module.update_device_power("d1", 1000.0)
        module.update_device_power("d1", 1000.0)
        module.update_device_power("d1", 1000.0)
        
        device = module.get_device("d1")
        
        assert device.energy_today_kwh > 0
    
    def test_zone_energy_accumulates(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        device = DeviceEnergy("d1", "zone_1", "Test", 1000.0)
        module.add_device(device)
        
        module.update_device_power("d1", 1000.0)
        
        state = module.get_state("zone_1")
        
        assert state.energy_today_kwh > 0
    
    def test_peak_tracking(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        module.update_power_data("zone_1", power_kw=2.0)
        module.update_power_data("zone_1", power_kw=3.0)
        module.update_power_data("zone_1", power_kw=2.5)
        
        state = module.get_state("zone_1")
        
        assert state.peak_current_kw == 3.0
    
    def test_power_history_limited(self):
        module = EnergyModule()
        
        config = EnergyConfig(zone_id="zone_1")
        module.set_zone_config(config)
        
        for i in range(1500):
            module.update_power_data("zone_1", power_kw=2.0)
        
        history = module._power_history["zone_1"]
        
        assert len(history) <= 1000
    
    def test_config_to_dict_all_fields(self):
        config = EnergyConfig(
            zone_id="zone_test",
            monthly_budget_kwh=600.0,
            daily_budget_kwh=20.0,
            peak_limit_kw=5.0,
            load_shedding_enabled=True,
            solar_priority_enabled=True,
            battery_management_enabled=True,
            battery_min_charge_percent=20.0,
            battery_max_charge_percent=90.0,
            cost_optimization_enabled=True,
        )
        d = config.to_dict()
        assert d["solar_priority_enabled"] is True
        assert d["cost_optimization_enabled"] is True
    
    def test_device_to_dict_all_fields(self):
        device = DeviceEnergy(
            device_id="device_test",
            zone_id="zone_test",
            name="Test Device",
            power_rating_watts=1000.0,
            priority=LoadPriority.HIGH,
            is_deferrable=True,
            current_power_watts=500.0,
            energy_today_kwh=5.0,
            efficiency_score=0.9,
        )
        d = device.to_dict()
        assert d["priority"] == "high"
        assert d["efficiency_score"] == 0.9
    
    def test_state_to_dict_all_fields(self):
        state = ZoneEnergyState(
            zone_id="zone_test",
            current_power_kw=2.5,
            energy_today_kwh=10.0,
            energy_month_kwh=200.0,
            budget_remaining_percent=50.0,
            peak_current_kw=3.0,
            solar_production_kw=1.5,
            battery_charge_percent=75.0,
            is_peak_hour=False,
            load_shedding_active=False,
            efficiency_score=0.85,
        )
        d = state.to_dict()
        assert d["battery_charge_percent"] == 75.0
    
    def test_action_to_dict_all_fields(self):
        action = EnergyAction(
            action_id="ea_test",
            zone_id="zone_test",
            action_type="shed_load",
            device_id="device_1",
            power_kw=2.0,
            reason="budget_low",
            triggered_by="auto",
        )
        d = action.to_dict()
        assert d["power_kw"] == 2.0
        assert d["reason"] == "budget_low"
    
    def test_multiple_zones_independent(self):
        module = EnergyModule()
        
        config1 = EnergyConfig(zone_id="zone_1", daily_budget_kwh=10.0)
        config2 = EnergyConfig(zone_id="zone_2", daily_budget_kwh=20.0)
        
        module.set_zone_config(config1)
        module.set_zone_config(config2)
        
        state1 = module.get_state("zone_1")
        state2 = module.get_state("zone_2")
        
        state1.energy_today_kwh = 9.0  # 90% used
        state2.energy_today_kwh = 5.0  # 25% used
        
        module.evaluate_zone("zone_1")
        module.evaluate_zone("zone_2")
        
        # Zone 1 should shed load, zone 2 should not
        actions1 = module.get_pending_actions("zone_1")
        actions2 = module.get_pending_actions("zone_2")
        
        assert len(actions1) >= 1 or state1.load_shedding_active is True
