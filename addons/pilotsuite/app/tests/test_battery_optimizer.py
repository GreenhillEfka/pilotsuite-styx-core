"""Tests for Battery Strategy Optimizer (v5.23.0)."""

import pytest

from copilot_core.regional.battery_optimizer import (
    BatteryConfig,
    BatterySchedule,
    BatteryStatus,
    BatteryStrategyOptimizer,
    ScheduleHour,
)


@pytest.fixture
def optimizer():
    return BatteryStrategyOptimizer(BatteryConfig(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        min_soc_pct=10.0,
        max_soc_pct=95.0,
        current_soc_pct=50.0,
        round_trip_efficiency=0.92,
    ))


@pytest.fixture
def optimizer_with_prices(optimizer):
    prices = {}
    for h in range(48):
        hod = h % 24
        if 0 <= hod <= 5:
            prices[h] = 15.0  # very cheap at night
        elif 17 <= hod <= 20:
            prices[h] = 40.0  # expensive evening peak
        else:
            prices[h] = 28.0  # normal
    optimizer.set_prices(prices)
    return optimizer


@pytest.fixture
def optimizer_with_solar(optimizer_with_prices):
    pv = {}
    for h in range(48):
        hod = h % 24
        if 9 <= hod <= 16:
            pv[h] = 4.0 + 2.0 * (1.0 - abs(hod - 12.5) / 4.0)
        else:
            pv[h] = 0.0
    optimizer_with_prices.set_pv_forecast(pv)
    return optimizer_with_prices


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_default_config(self):
        opt = BatteryStrategyOptimizer()
        assert opt.config.capacity_kwh == 10.0
        assert opt.config.current_soc_pct == 50.0

    def test_custom_config(self):
        cfg = BatteryConfig(capacity_kwh=20.0, current_soc_pct=80.0)
        opt = BatteryStrategyOptimizer(cfg)
        assert opt.config.capacity_kwh == 20.0

    def test_update_config(self, optimizer):
        optimizer.update_config(capacity_kwh=15.0, max_charge_kw=7.5)
        assert optimizer.config.capacity_kwh == 15.0
        assert optimizer.config.max_charge_kw == 7.5

    def test_set_soc(self, optimizer):
        optimizer.set_soc(75.0)
        assert optimizer.config.current_soc_pct == 75.0

    def test_set_soc_clamp(self, optimizer):
        optimizer.set_soc(150.0)
        assert optimizer.config.current_soc_pct == 100.0
        optimizer.set_soc(-10.0)
        assert optimizer.config.current_soc_pct == 0.0


# ── Test optimization ────────────────────────────────────────────────────


class TestOptimize:
    def test_generates_48_hours(self, optimizer):
        schedule = optimizer.optimize(horizon_hours=48)
        assert isinstance(schedule, BatterySchedule)
        assert schedule.total_hours == 48

    def test_generates_24_hours(self, optimizer):
        schedule = optimizer.optimize(horizon_hours=24)
        assert schedule.total_hours == 24

    def test_has_valid_actions(self, optimizer):
        schedule = optimizer.optimize()
        valid_actions = {"charge", "discharge", "hold", "charge_solar"}
        for h in schedule.hours:
            assert h["action"] in valid_actions

    def test_soc_never_below_min(self, optimizer):
        schedule = optimizer.optimize()
        for h in schedule.hours:
            assert h["soc_end_pct"] >= optimizer.config.min_soc_pct - 0.1

    def test_soc_never_above_max(self, optimizer):
        schedule = optimizer.optimize()
        for h in schedule.hours:
            assert h["soc_end_pct"] <= optimizer.config.max_soc_pct + 0.1

    def test_prices_result_in_arbitrage(self, optimizer_with_prices):
        schedule = optimizer_with_prices.optimize()
        assert schedule.total_charge_kwh > 0
        assert schedule.total_discharge_kwh > 0

    def test_avg_charge_price_lower(self, optimizer_with_prices):
        schedule = optimizer_with_prices.optimize()
        if schedule.avg_charge_price_ct > 0 and schedule.avg_discharge_price_ct > 0:
            assert schedule.avg_charge_price_ct < schedule.avg_discharge_price_ct

    def test_solar_charging(self, optimizer_with_solar):
        schedule = optimizer_with_solar.optimize()
        assert schedule.total_solar_charge_kwh > 0

    def test_solar_first_strategy(self, optimizer_with_solar):
        # With lots of solar, solar_first should dominate
        optimizer_with_solar.set_soc(20.0)  # Start low to need charging
        schedule = optimizer_with_solar.optimize()
        if schedule.total_solar_charge_kwh > schedule.total_grid_charge_kwh:
            assert schedule.strategy == "solar_first"

    def test_savings_non_negative(self, optimizer_with_prices):
        schedule = optimizer_with_prices.optimize()
        assert schedule.estimated_savings_eur >= 0

    def test_estimated_cycles(self, optimizer_with_prices):
        schedule = optimizer_with_prices.optimize()
        assert schedule.estimated_cycles >= 0

    def test_strategy_assigned(self, optimizer):
        schedule = optimizer.optimize()
        valid_strategies = {"arbitrage", "solar_first", "peak_shaving", "backup"}
        assert schedule.strategy in valid_strategies

    def test_generated_at(self, optimizer):
        schedule = optimizer.optimize()
        assert len(schedule.generated_at) > 0


# ── Test with forecast data import ───────────────────────────────────────


class TestForecastImport:
    def test_import_forecast(self, optimizer):
        forecast = [
            {"hour": 0, "price_ct_kwh": 20.0, "pv_kw_estimated": 0.0},
            {"hour": 6, "price_ct_kwh": 35.0, "pv_kw_estimated": 0.0},
            {"hour": 12, "price_ct_kwh": 25.0, "pv_kw_estimated": 5.0},
        ]
        optimizer.import_forecast_data(forecast)
        schedule = optimizer.optimize()
        assert schedule.total_hours == 48


# ── Test battery status ──────────────────────────────────────────────────


class TestStatus:
    def test_status_before_optimize(self, optimizer):
        status = optimizer.get_status()
        assert isinstance(status, BatteryStatus)
        assert status.soc_pct == 50.0
        assert status.strategy == "none"

    def test_status_after_optimize(self, optimizer_with_prices):
        optimizer_with_prices.optimize()
        status = optimizer_with_prices.get_status()
        assert status.strategy != "none"
        assert status.soc_pct > 0

    def test_status_capacity(self, optimizer):
        status = optimizer.get_status()
        assert status.capacity_kwh == 10.0
        assert status.soc_kwh == 5.0  # 50% of 10kWh


# ── Test consumption patterns ────────────────────────────────────────────


class TestConsumption:
    def test_custom_consumption(self, optimizer_with_prices):
        cons = {h: 3.0 for h in range(48)}  # high constant load
        optimizer_with_prices.set_consumption_forecast(cons)
        schedule = optimizer_with_prices.optimize()
        assert schedule.total_hours == 48
