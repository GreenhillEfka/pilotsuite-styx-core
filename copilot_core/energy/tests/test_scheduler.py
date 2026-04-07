"""Energy Module Tests — OR-Tools Scheduler, Device Profiles, Integration."""
from __future__ import annotations

import pytest
from typing import Dict, Any


class TestORToolsScheduler:
    """Test OR-Tools CP-SAT Scheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create test scheduler."""
        from copilot_core.energy.or_tools_scheduler import ORToolsScheduler
        return ORToolsScheduler(slots=96, solver_timeout_sec=5.0)

    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler._slots == 96
        assert scheduler._solver_timeout == 5.0

    def test_optimize_with_ev_charging(self, scheduler):
        """Test optimization with EV charging."""
        from copilot_core.energy.device_profiles import ev_charging, ConstraintType
        
        devices = [
            ev_charging(
                device_id="wallbox.ev_charger",
                max_power_kw=11.0,
                deadline_slot=28,  # 7:00 AM
                min_charge_kwh=40.0,
                constraint_type=ConstraintType.HARD,
            )
        ]
        
        forecast = {
            'load': [0.5] * 96,
            'solar': [0.0] * 96,
            'price': [0.3] * 96,
        }
        prices = [0.3] * 96
        
        result = scheduler.optimize(devices, forecast, prices)
        
        assert result.success is True
        assert "wallbox.ev_charger" in result.device_schedules
        assert len(result.device_schedules["wallbox.ev_charger"]) == 96

    def test_optimize_with_battery(self, scheduler):
        """Test optimization with battery storage."""
        from copilot_core.energy.device_profiles import battery_storage
        
        devices = [
            battery_storage(
                device_id="battery.home",
                capacity_kwh=10.0,
                max_charge_kw=5.0,
                max_discharge_kw=5.0,
            )
        ]
        
        forecast = {
            'load': [1.0] * 96,
            'solar': [2.0] * 48 + [0.0] * 48,  # Solar during day
            'price': [0.3] * 96,
        }
        prices = [0.3] * 96
        
        result = scheduler.optimize(devices, forecast, prices)
        
        assert result.success is True
        assert result.total_solar_used_kwh >= 0

    def test_optimize_with_carbon_weighting(self, scheduler):
        """Test optimization with carbon intensity."""
        from copilot_core.energy.device_profiles import get_typical_home_setup
        
        devices = get_typical_home_setup()
        
        forecast = {
            'load': [1.0] * 96,
            'solar': [1.5] * 96,
            'price': [0.3] * 96,
        }
        prices = [0.3] * 96
        carbon = [400] * 48 + [600] * 48  # Higher carbon in evening
        
        result = scheduler.optimize(devices, forecast, prices, carbon_intensity=carbon)
        
        assert result.success is True
        assert result.total_cost >= 0

    def test_infeasible_constraints(self, scheduler):
        """Test handling of infeasible constraints."""
        from copilot_core.energy.or_tools_scheduler import DeviceConstraint, DeviceClass, ConstraintType
        
        # Impossible constraint: 100kWh in 1 hour with 11kW charger
        devices = [
            DeviceConstraint(
                device_id="impossible_ev",
                device_class=DeviceClass.EV_CHARGING,
                constraint_type=ConstraintType.HARD,
                description="Impossible charging",
                min_power_kw=0.0,
                max_power_kw=11.0,
                deadline_slot=4,  # 1 hour
                min_state=100.0,  # 100 kWh
            )
        ]
        
        forecast = {'load': [0.5] * 96, 'solar': [0.0] * 96, 'price': [0.3] * 96}
        prices = [0.3] * 96
        
        result = scheduler.optimize(devices, forecast, prices)
        
        # Should fail or return infeasible
        assert result.success is False or len(result.infeasible_constraints) > 0

    def test_scheduler_stats(self, scheduler):
        """Test scheduler statistics."""
        from copilot_core.energy.device_profiles import ev_charging
        
        # Run some optimizations
        for i in range(3):
            devices = [ev_charging(f"ev_{i}", deadline_slot=28, min_charge_kwh=20.0)]
            forecast = {'load': [0.5] * 96, 'solar': [0.0] * 96, 'price': [0.3] * 96}
            prices = [0.3] * 96
            scheduler.optimize(devices, forecast, prices)
        
        stats = scheduler.get_stats()
        
        assert stats["optimizations_run"] == 3
        assert stats["slots"] == 96


class TestDeviceProfiles:
    """Test device profile library."""

    def test_ev_charging_profile(self):
        """Test EV charging profile."""
        from copilot_core.energy.device_profiles import ev_charging, DeviceClass, ConstraintType
        
        profile = ev_charging(
            device_id="wallbox.test",
            max_power_kw=11.0,
            deadline_slot=28,
            min_charge_kwh=40.0,
        )
        
        assert profile.device_id == "wallbox.test"
        assert profile.device_class == DeviceClass.EV_CHARGING
        assert profile.max_power_kw == 11.0
        assert profile.deadline_slot == 28
        assert profile.min_state == 40.0
        assert profile.constraint_type == ConstraintType.HARD

    def test_heat_pump_profile(self):
        """Test heat pump profile."""
        from copilot_core.energy.device_profiles import heat_pump, DeviceClass
        
        profile = heat_pump(
            device_id="climate.hp_test",
            max_power_kw=8.0,
            comfort_temp_min=20.0,
            comfort_temp_max=22.0,
        )
        
        assert profile.device_class == DeviceClass.HEAT_PUMP
        assert profile.max_power_kw == 8.0
        assert profile.comfort_temp_min == 20.0
        assert profile.comfort_temp_max == 22.0

    def test_battery_profile(self):
        """Test battery storage profile."""
        from copilot_core.energy.device_profiles import battery_storage, DeviceClass
        
        profile = battery_storage(
            device_id="battery.test",
            capacity_kwh=10.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
            min_soc=0.1,
            max_soc=0.9,
        )
        
        assert profile.device_class == DeviceClass.BATTERY
        assert profile.max_power_kw == 5.0
        assert profile.min_power_kw == -5.0  # Negative for discharge
        assert profile.min_state == 1.0  # 10% of 10kWh
        assert profile.max_state == 9.0  # 90% of 10kWh

    def test_typical_home_setup(self):
        """Test typical home setup."""
        from copilot_core.energy.device_profiles import get_typical_home_setup
        
        devices = get_typical_home_setup()
        
        assert len(devices) >= 3  # At least EV, heat pump, battery
        assert any(d.device_class.value == "ev_charging" for d in devices)
        assert any(d.device_class.value == "heat_pump" for d in devices)
        assert any(d.device_class.value == "battery_storage" for d in devices)


class TestSchedulerIntegration:
    """Test scheduler integration."""

    def test_integration_initialization(self):
        """Test integration initialization."""
        from copilot_core.energy.scheduler_integration import SchedulerIntegration
        
        integration = SchedulerIntegration()
        
        assert integration._forecast_provider is None
        assert integration._scheduler is None
        assert integration._action_executor is None

    def test_register_components(self):
        """Test registering components."""
        from copilot_core.energy.scheduler_integration import SchedulerIntegration
        
        integration = SchedulerIntegration()
        
        # Mock components
        def mock_forecast():
            return {}
        
        def mock_executor(device_id, action):
            pass
        
        integration.register_forecast_provider(mock_forecast)
        integration.register_scheduler("mock_scheduler")
        integration.register_action_executor(mock_executor)
        
        assert integration._forecast_provider is not None
        assert integration._scheduler is not None
        assert integration._action_executor is not None

    def test_get_stats(self):
        """Test integration statistics."""
        from copilot_core.energy.scheduler_integration import SchedulerIntegration
        
        integration = SchedulerIntegration()
        stats = integration.get_stats()
        
        assert "components" in stats
        assert "pending" in stats
        assert "active" in stats


# Run with: pytest copilot_core/energy/tests/test_scheduler.py -v
