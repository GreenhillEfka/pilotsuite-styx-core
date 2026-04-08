"""Tests for Heat Pump Controller (v5.24.0)."""

import pytest
from copilot_core.regional.heat_pump_controller import (
    HeatPumpConfig,
    HeatPumpController,
    HeatPumpHour,
    HeatPumpSchedule,
    HeatPumpStatus,
    calculate_cop,
    needs_defrost,
)


# ── COP calculation tests ────────────────────────────────────────────────


class TestCOP:
    """Tests for COP calculation."""

    def test_air_water_basic(self):
        cop = calculate_cop("air_water", 7.0, 35.0)
        assert 2.0 < cop < 6.0

    def test_ground_water_higher_cop(self):
        """Ground-source should give higher COP than air-source at low temps."""
        cop_air = calculate_cop("air_water", -5.0, 45.0)
        cop_ground = calculate_cop("ground_water", -5.0, 45.0)
        assert cop_ground > cop_air

    def test_higher_outdoor_temp_gives_higher_cop(self):
        cop_cold = calculate_cop("air_water", -10.0, 45.0)
        cop_warm = calculate_cop("air_water", 10.0, 45.0)
        assert cop_warm > cop_cold

    def test_lower_flow_temp_gives_higher_cop(self):
        cop_high_flow = calculate_cop("air_water", 7.0, 55.0)
        cop_low_flow = calculate_cop("air_water", 7.0, 35.0)
        assert cop_low_flow > cop_high_flow

    def test_cop_clamped_max(self):
        cop = calculate_cop("air_water", 50.0, 35.0)
        assert cop <= 7.0

    def test_cop_clamped_min(self):
        cop = calculate_cop("air_water", -25.0, 55.0)
        assert cop >= 1.0

    def test_air_air_type(self):
        cop = calculate_cop("air_air", 10.0, 35.0)
        assert 1.0 <= cop <= 7.0

    def test_defrost_needed(self):
        assert needs_defrost(1.0) is True
        assert needs_defrost(-1.0) is True

    def test_defrost_not_needed(self):
        assert needs_defrost(10.0) is False
        assert needs_defrost(-5.0) is False


# ── Config tests ──────────────────────────────────────────────────────────


class TestConfig:
    """Tests for HeatPumpConfig."""

    def test_defaults(self):
        cfg = HeatPumpConfig()
        assert cfg.pump_type == "air_water"
        assert cfg.nominal_power_kw == 8.0
        assert cfg.target_room_temp_c == 21.0
        assert cfg.hot_water_tank_l == 300.0

    def test_custom(self):
        cfg = HeatPumpConfig(
            pump_type="ground_water",
            nominal_power_kw=12.0,
            max_flow_temp_c=45.0,
        )
        assert cfg.pump_type == "ground_water"
        assert cfg.nominal_power_kw == 12.0

    def test_update_config(self):
        ctrl = HeatPumpController()
        ctrl.update_config(nominal_power_kw=10.0, target_room_temp_c=22.0)
        assert ctrl.config.nominal_power_kw == 10.0
        assert ctrl.config.target_room_temp_c == 22.0


# ── Controller init tests ────────────────────────────────────────────────


class TestControllerInit:
    """Tests for controller initialization."""

    def test_default_init(self):
        ctrl = HeatPumpController()
        assert ctrl.config.pump_type == "air_water"
        assert ctrl._strategy == "cop_optimized"

    def test_custom_config(self):
        cfg = HeatPumpConfig(pump_type="ground_water")
        ctrl = HeatPumpController(cfg)
        assert ctrl.config.pump_type == "ground_water"

    def test_set_strategy(self):
        ctrl = HeatPumpController()
        ctrl.set_strategy("price_optimized")
        assert ctrl._strategy == "price_optimized"

    def test_invalid_strategy_ignored(self):
        ctrl = HeatPumpController()
        ctrl.set_strategy("invalid")
        assert ctrl._strategy == "cop_optimized"

    def test_set_room_temp(self):
        ctrl = HeatPumpController()
        ctrl.set_room_temp(19.5)
        assert ctrl.config.current_room_temp_c == 19.5

    def test_set_room_temp_clamped(self):
        ctrl = HeatPumpController()
        ctrl.set_room_temp(0.0)
        assert ctrl.config.current_room_temp_c == 5.0
        ctrl.set_room_temp(50.0)
        assert ctrl.config.current_room_temp_c == 35.0

    def test_set_hot_water_temp(self):
        ctrl = HeatPumpController()
        ctrl.set_hot_water_temp(48.0)
        assert ctrl.config.current_hot_water_temp_c == 48.0


# ── Optimization tests ────────────────────────────────────────────────────


class TestOptimize:
    """Tests for schedule optimization."""

    def test_generates_48h(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize(horizon_hours=48)
        assert len(schedule.hours) == 48

    def test_generates_24h(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize(horizon_hours=24)
        assert len(schedule.hours) == 24

    def test_valid_actions(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize()
        valid = {"heat", "dhw", "off", "defrost", "solar_boost"}
        for h in schedule.hours:
            assert h["action"] in valid

    def test_cop_in_range(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize()
        for h in schedule.hours:
            assert 1.0 <= h["cop"] <= 7.0

    def test_runtime_within_limits(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize(horizon_hours=24)
        assert schedule.runtime_hours <= ctrl.config.max_runtime_hours_per_day + 5  # +margin for DHW/defrost

    def test_total_cost_positive(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize()
        assert schedule.total_cost_eur >= 0

    def test_total_heat_positive(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize()
        assert schedule.total_heat_kwh >= 0

    def test_avg_cop_reasonable(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize()
        if schedule.total_electricity_kwh > 0:
            assert 1.0 <= schedule.avg_cop <= 7.0

    def test_cop_optimized_prefers_warm_hours(self):
        """COP-optimized should prefer warmer hours (higher COP)."""
        ctrl = HeatPumpController()
        ctrl.set_outdoor_temps({h: (-5.0 if h < 12 else 10.0) for h in range(24)})
        schedule = ctrl.optimize(horizon_hours=24)
        # Count heating hours in warm vs cold periods
        warm_heat = sum(1 for h in schedule.hours if h["hour"] >= 12 and h["action"] == "heat")
        cold_heat = sum(1 for h in schedule.hours if h["hour"] < 12 and h["action"] == "heat")
        # Should have more or equal heating in warm period
        assert warm_heat >= cold_heat or schedule.runtime_hours == 0

    def test_price_optimized_prefers_cheap_hours(self):
        """Price-optimized should prefer cheapest hours."""
        ctrl = HeatPumpController()
        ctrl.set_strategy("price_optimized")
        ctrl.set_prices({h: (10.0 if h < 6 else 40.0) for h in range(24)})
        schedule = ctrl.optimize(horizon_hours=24)
        cheap_heat = sum(1 for h in schedule.hours if h["hour"] < 6 and h["action"] == "heat")
        expensive_heat = sum(1 for h in schedule.hours if h["hour"] >= 18 and h["action"] == "heat")
        assert cheap_heat >= expensive_heat

    def test_solar_boost_uses_pv(self):
        """Solar boost should activate when PV surplus available."""
        ctrl = HeatPumpController()
        ctrl.set_strategy("solar_boost")
        ctrl.set_pv_forecast({h: (5.0 if 10 <= h <= 14 else 0.0) for h in range(24)})
        schedule = ctrl.optimize(horizon_hours=24)
        solar_hours = sum(1 for h in schedule.hours if h["action"] == "solar_boost")
        assert solar_hours >= 1

    def test_dhw_reheat_when_cold(self):
        """DHW should trigger when water drops below minimum."""
        ctrl = HeatPumpController(HeatPumpConfig(
            current_hot_water_temp_c=40.0,
            hot_water_min_c=45.0,
        ))
        schedule = ctrl.optimize(horizon_hours=24)
        assert schedule.dhw_cycles >= 1

    def test_comfort_first_maintains_temp(self):
        """Comfort-first should heat whenever room is below target."""
        ctrl = HeatPumpController(HeatPumpConfig(
            current_room_temp_c=18.0,
            target_room_temp_c=21.0,
        ))
        ctrl.set_strategy("comfort_first")
        schedule = ctrl.optimize(horizon_hours=24)
        assert schedule.runtime_hours >= 1

    def test_timestamps_present(self):
        ctrl = HeatPumpController()
        schedule = ctrl.optimize(horizon_hours=24)
        for h in schedule.hours:
            assert h["timestamp"]
            assert "T" in h["timestamp"]

    def test_schedule_strategy_field(self):
        ctrl = HeatPumpController()
        ctrl.set_strategy("price_optimized")
        schedule = ctrl.optimize()
        assert schedule.strategy == "price_optimized"


# ── Data import tests ─────────────────────────────────────────────────────


class TestDataImport:
    """Tests for data import methods."""

    def test_import_weather_data(self):
        ctrl = HeatPumpController()
        ctrl.import_weather_data([
            {"hour": 0, "temperature_c": -2.0},
            {"hour": 6, "temperature_c": 0.0},
            {"hour": 12, "temperature_c": 8.0},
        ])
        assert ctrl._outdoor_temps[0] == -2.0
        assert ctrl._outdoor_temps[12] == 8.0

    def test_import_tariff_data(self):
        ctrl = HeatPumpController()
        ctrl.import_tariff_data([
            {"hour": 0, "price_ct": 20.0},
            {"hour": 12, "price_ct": 35.0},
        ])
        assert ctrl._prices[0] == 20.0
        assert ctrl._prices[12] == 35.0

    def test_set_pv_forecast(self):
        ctrl = HeatPumpController()
        ctrl.set_pv_forecast({10: 3.0, 11: 5.0, 12: 4.0})
        assert ctrl._pv_forecast[11] == 5.0


# ── Status tests ──────────────────────────────────────────────────────────


class TestStatus:
    """Tests for status reporting."""

    def test_status_before_optimize(self):
        ctrl = HeatPumpController()
        status = ctrl.get_status()
        assert status.ok is True
        assert status.pump_type == "air_water"
        assert status.strategy == "cop_optimized"

    def test_status_after_optimize(self):
        ctrl = HeatPumpController()
        ctrl.optimize()
        status = ctrl.get_status()
        assert status.ok is True
        assert status.current_cop > 0

    def test_status_room_temp(self):
        ctrl = HeatPumpController(HeatPumpConfig(current_room_temp_c=19.5))
        status = ctrl.get_status()
        assert status.room_temp_c == 19.5

    def test_status_ground_water(self):
        ctrl = HeatPumpController(HeatPumpConfig(pump_type="ground_water"))
        status = ctrl.get_status()
        assert status.pump_type == "ground_water"


# ── Effective cost tests ──────────────────────────────────────────────────


class TestEffectiveCost:
    """Tests for effective cost calculations."""

    def test_effective_cost_cheaper_with_high_cop(self):
        ctrl = HeatPumpController()
        ctrl.set_prices({0: 30.0, 12: 30.0})
        ctrl.set_outdoor_temps({0: -5.0, 12: 10.0})
        cost_cold = ctrl.get_effective_cost(0)
        cost_warm = ctrl.get_effective_cost(12)
        # Warm hour has higher COP → lower effective cost
        assert cost_warm < cost_cold

    def test_effective_cost_uses_cop(self):
        ctrl = HeatPumpController()
        ctrl.set_prices({0: 30.0})
        ctrl.set_outdoor_temps({0: 7.0})
        cop = ctrl.get_cop(7.0)
        expected = 30.0 / cop
        assert abs(ctrl.get_effective_cost(0) - expected) < 0.01
