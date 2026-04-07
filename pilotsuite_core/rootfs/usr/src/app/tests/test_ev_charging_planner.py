"""Tests for EV Charging Planner (v5.25.0)."""

import pytest
from datetime import datetime, timedelta, timezone

from copilot_core.regional.ev_charging_planner import (
    EVConfig,
    EVChargingPlanner,
    ChargingHour,
    ChargingSchedule,
    EVStatus,
    DepartureSchedule,
)


# ── Config tests ──────────────────────────────────────────────────────────


class TestConfig:
    """Tests for EVConfig defaults and customization."""

    def test_defaults(self):
        cfg = EVConfig()
        assert cfg.battery_capacity_kwh == 60.0
        assert cfg.max_charge_rate_kw == 11.0
        assert cfg.current_soc_pct == 30.0
        assert cfg.target_soc_pct == 80.0
        assert cfg.connector_type == "type2"

    def test_custom(self):
        cfg = EVConfig(
            battery_capacity_kwh=77.0,
            max_charge_rate_kw=22.0,
            vehicle_name="Tesla Model 3",
        )
        assert cfg.battery_capacity_kwh == 77.0
        assert cfg.max_charge_rate_kw == 22.0
        assert cfg.vehicle_name == "Tesla Model 3"

    def test_update_config(self):
        planner = EVChargingPlanner()
        planner.update_config(battery_capacity_kwh=100.0, target_soc_pct=90.0)
        assert planner.config.battery_capacity_kwh == 100.0
        assert planner.config.target_soc_pct == 90.0


# ── Planner init tests ───────────────────────────────────────────────────


class TestPlannerInit:
    """Tests for planner initialization."""

    def test_default_init(self):
        planner = EVChargingPlanner()
        assert planner.config.vehicle_name == "EV"
        assert planner._strategy == "cost_optimized"

    def test_custom_config(self):
        cfg = EVConfig(vehicle_name="VW ID.4")
        planner = EVChargingPlanner(cfg)
        assert planner.config.vehicle_name == "VW ID.4"

    def test_set_strategy(self):
        planner = EVChargingPlanner()
        planner.set_strategy("solar_first")
        assert planner._strategy == "solar_first"

    def test_invalid_strategy_ignored(self):
        planner = EVChargingPlanner()
        planner.set_strategy("nonsense")
        assert planner._strategy == "cost_optimized"

    def test_set_soc(self):
        planner = EVChargingPlanner()
        planner.set_soc(55.0)
        assert planner.config.current_soc_pct == 55.0

    def test_set_soc_clamped(self):
        planner = EVChargingPlanner()
        planner.set_soc(-10)
        assert planner.config.current_soc_pct == 0.0
        planner.set_soc(150)
        assert planner.config.current_soc_pct == 100.0

    def test_set_departure(self):
        planner = EVChargingPlanner()
        dep = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        planner.set_departure(dep, 90.0, "weekdays")
        assert planner._departure.departure_time == dep
        assert planner._departure.departure_soc_pct == 90.0
        assert planner._departure.recurrence == "weekdays"

    def test_set_consumption(self):
        planner = EVChargingPlanner()
        planner.set_consumption(15.0)
        assert planner._consumption_kwh_100km == 15.0

    def test_set_consumption_clamped(self):
        planner = EVChargingPlanner()
        planner.set_consumption(1.0)
        assert planner._consumption_kwh_100km == 5.0
        planner.set_consumption(100.0)
        assert planner._consumption_kwh_100km == 40.0


# ── Energy calculation tests ─────────────────────────────────────────────


class TestEnergyCalc:
    """Tests for energy calculation helpers."""

    def test_energy_needed(self):
        planner = EVChargingPlanner(EVConfig(
            battery_capacity_kwh=60.0,
            current_soc_pct=30.0,
            target_soc_pct=80.0,
            charger_efficiency=0.92,
        ))
        needed = planner._energy_needed_kwh()
        # 50% of 60 kWh = 30 kWh / 0.92 ≈ 32.6 kWh
        assert 30 < needed < 35

    def test_energy_needed_already_full(self):
        planner = EVChargingPlanner(EVConfig(
            current_soc_pct=90.0,
            target_soc_pct=80.0,
        ))
        assert planner._energy_needed_kwh() == 0.0

    def test_estimated_range(self):
        planner = EVChargingPlanner(EVConfig(battery_capacity_kwh=60.0))
        planner.set_consumption(18.0)
        # At 100% SoC: 60 kWh / 18 kWh per 100km * 100 = 333 km
        assert abs(planner._estimated_range_km(100.0) - 333.3) < 1.0

    def test_estimated_range_partial(self):
        planner = EVChargingPlanner(EVConfig(battery_capacity_kwh=60.0))
        planner.set_consumption(18.0)
        # At 50% SoC: 30 kWh / 18 * 100 ≈ 166.7 km
        assert abs(planner._estimated_range_km(50.0) - 166.7) < 1.0


# ── Optimization tests ────────────────────────────────────────────────────


class TestOptimize:
    """Tests for schedule optimization."""

    def test_generates_48h(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize(horizon_hours=48)
        assert len(schedule.hours) == 48

    def test_generates_24h(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize(horizon_hours=24)
        assert len(schedule.hours) == 24

    def test_valid_actions(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize()
        valid = {"charge", "solar_charge", "pause", "complete"}
        for h in schedule.hours:
            assert h["action"] in valid

    def test_soc_never_exceeds_100(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize()
        for h in schedule.hours:
            assert h["soc_end_pct"] <= 100.0

    def test_total_cost_positive(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize()
        assert schedule.total_cost_eur >= 0

    def test_total_energy_matches_need(self):
        planner = EVChargingPlanner(EVConfig(
            battery_capacity_kwh=60.0,
            current_soc_pct=30.0,
            target_soc_pct=80.0,
        ))
        schedule = planner.optimize()
        # Should charge roughly 50% of 60kWh / 0.92 ≈ 32.6 kWh
        assert 25 < schedule.total_energy_kwh < 40

    def test_cost_optimized_prefers_cheap(self):
        """Cost-optimized should prefer cheapest hours."""
        planner = EVChargingPlanner(EVConfig(current_soc_pct=50.0, target_soc_pct=70.0))
        planner.set_strategy("cost_optimized")
        planner.set_prices({h: (10.0 if h < 6 else 40.0) for h in range(24)})
        schedule = planner.optimize(horizon_hours=24)
        cheap = sum(1 for h in schedule.hours if h["hour"] < 6 and h["action"] == "charge")
        expensive = sum(1 for h in schedule.hours if h["hour"] >= 18 and h["action"] == "charge")
        assert cheap >= expensive

    def test_solar_first_uses_pv(self):
        """Solar-first should prefer hours with PV surplus."""
        planner = EVChargingPlanner(EVConfig(current_soc_pct=50.0, target_soc_pct=70.0))
        planner.set_strategy("solar_first")
        planner.set_pv_forecast({h: (8.0 if 10 <= h <= 14 else 0.0) for h in range(24)})
        schedule = planner.optimize(horizon_hours=24)
        solar = sum(1 for h in schedule.hours if h["action"] == "solar_charge")
        assert solar >= 1

    def test_fastest_charges_immediately(self):
        """Fastest should start charging from hour 0."""
        planner = EVChargingPlanner(EVConfig(current_soc_pct=30.0, target_soc_pct=50.0))
        planner.set_strategy("fastest")
        schedule = planner.optimize(horizon_hours=24)
        # First non-complete hour should be charge
        first_charge = next(
            (h for h in schedule.hours if h["action"] in ("charge", "solar_charge")),
            None,
        )
        assert first_charge is not None
        assert first_charge["hour"] == 0

    def test_already_charged_no_action(self):
        """If already at target, no charging needed."""
        planner = EVChargingPlanner(EVConfig(current_soc_pct=90.0, target_soc_pct=80.0))
        schedule = planner.optimize(horizon_hours=24)
        assert schedule.charge_hours == 0
        assert schedule.total_energy_kwh == 0

    def test_end_soc_reaches_target(self):
        planner = EVChargingPlanner(EVConfig(
            current_soc_pct=30.0,
            target_soc_pct=80.0,
        ))
        schedule = planner.optimize()
        assert schedule.end_soc_pct >= 79.0  # allow small rounding

    def test_schedule_strategy_field(self):
        planner = EVChargingPlanner()
        planner.set_strategy("balanced")
        schedule = planner.optimize()
        assert schedule.strategy == "balanced"

    def test_solar_share_percentage(self):
        planner = EVChargingPlanner(EVConfig(current_soc_pct=60.0, target_soc_pct=80.0))
        planner.set_strategy("solar_first")
        planner.set_pv_forecast({h: (15.0 if 10 <= h <= 14 else 0.0) for h in range(24)})
        schedule = planner.optimize(horizon_hours=24)
        assert 0 <= schedule.solar_share_pct <= 100

    def test_timestamps_present(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize(horizon_hours=24)
        for h in schedule.hours:
            assert h["timestamp"]
            assert "T" in h["timestamp"]

    def test_estimated_range(self):
        planner = EVChargingPlanner()
        schedule = planner.optimize()
        assert schedule.estimated_range_km > 0


# ── Departure tests ───────────────────────────────────────────────────────


class TestDeparture:
    """Tests for departure scheduling."""

    def test_departure_ready_when_charged(self):
        planner = EVChargingPlanner(EVConfig(current_soc_pct=90.0, target_soc_pct=80.0))
        dep = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        planner.set_departure(dep, 80.0)
        schedule = planner.optimize(horizon_hours=24)
        assert schedule.departure_ready is True

    def test_departure_time_in_schedule(self):
        planner = EVChargingPlanner()
        dep = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        planner.set_departure(dep, 80.0)
        schedule = planner.optimize(horizon_hours=24)
        assert schedule.departure_time == dep


# ── Data import tests ─────────────────────────────────────────────────────


class TestDataImport:
    """Tests for data import methods."""

    def test_import_tariff_data(self):
        planner = EVChargingPlanner()
        planner.import_tariff_data([
            {"hour": 0, "price_ct": 15.0},
            {"hour": 12, "price_ct": 35.0},
        ])
        assert planner._prices[0] == 15.0
        assert planner._prices[12] == 35.0

    def test_set_pv_forecast(self):
        planner = EVChargingPlanner()
        planner.set_pv_forecast({10: 5.0, 12: 8.0})
        assert planner._pv_forecast[12] == 8.0


# ── Status tests ──────────────────────────────────────────────────────────


class TestStatus:
    """Tests for status reporting."""

    def test_status_before_optimize(self):
        planner = EVChargingPlanner()
        status = planner.get_status()
        assert status.ok is True
        assert status.vehicle_name == "EV"
        assert status.strategy == "cost_optimized"

    def test_status_after_optimize(self):
        planner = EVChargingPlanner()
        planner.optimize()
        status = planner.get_status()
        assert status.ok is True

    def test_status_range(self):
        planner = EVChargingPlanner(EVConfig(
            battery_capacity_kwh=60.0,
            current_soc_pct=50.0,
        ))
        status = planner.get_status()
        assert status.estimated_range_km > 0

    def test_status_time_to_target(self):
        planner = EVChargingPlanner(EVConfig(
            current_soc_pct=30.0,
            target_soc_pct=80.0,
        ))
        status = planner.get_status()
        assert status.time_to_target_h > 0

    def test_status_departure_ready(self):
        planner = EVChargingPlanner(EVConfig(current_soc_pct=90.0))
        dep = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
        planner.set_departure(dep, 80.0)
        status = planner.get_status()
        assert status.departure_ready is True
