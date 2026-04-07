"""Tests for Weather-Aware Energy Optimizer (v5.11.0)."""

import pytest
from datetime import date
from copilot_core.prediction.weather_optimizer import (
    WeatherAwareOptimizer,
    WeatherOptimizationPlan,
    HourForecast,
    BatteryAction,
    OptimizationWindow,
    _cloud_to_efficiency,
    _estimate_pv,
    _condition_from_cloud_rain,
)


@pytest.fixture
def optimizer():
    return WeatherAwareOptimizer(pv_peak_kwp=8.0, battery_capacity_kwh=10.0, battery_soc=0.50)


@pytest.fixture
def sunny_weather():
    """48 hours of sunny weather."""
    return [
        {"cloud_cover_pct": 10.0, "precipitation_mm": 0.0,
         "wind_speed_kmh": 5.0, "temperature_c": 22.0}
        for _ in range(48)
    ]


@pytest.fixture
def mixed_weather():
    """48 hours: 24h sunny then 24h rainy."""
    sunny = [{"cloud_cover_pct": 10.0, "precipitation_mm": 0.0,
              "wind_speed_kmh": 5.0, "temperature_c": 20.0}
             for _ in range(24)]
    rainy = [{"cloud_cover_pct": 90.0, "precipitation_mm": 3.0,
              "wind_speed_kmh": 20.0, "temperature_c": 12.0}
             for _ in range(24)]
    return sunny + rainy


@pytest.fixture
def low_prices():
    """48 hours of low prices."""
    return [0.10] * 48


@pytest.fixture
def high_prices():
    """48 hours of high prices."""
    return [0.45] * 48


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestCloudToEfficiency:
    def test_clear_sky(self):
        assert _cloud_to_efficiency(0) == 1.0

    def test_full_overcast(self):
        assert _cloud_to_efficiency(100) == 0.08

    def test_partial_cloud(self):
        eff = _cloud_to_efficiency(50)
        assert 0.3 < eff < 0.7

    def test_monotone_decreasing(self):
        values = [_cloud_to_efficiency(c) for c in range(0, 101, 10)]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1]


class TestEstimatePV:
    def test_night_zero(self):
        assert _estimate_pv(2, 0.0, 8.0) == 0.0

    def test_noon_clear(self):
        pv = _estimate_pv(12, 0.0, 8.0)
        assert pv > 6.0  # near peak

    def test_noon_overcast(self):
        pv_clear = _estimate_pv(12, 0.0, 8.0)
        pv_cloudy = _estimate_pv(12, 80.0, 8.0)
        assert pv_cloudy < pv_clear * 0.5

    def test_zero_kwp(self):
        assert _estimate_pv(12, 0.0, 0.0) == 0.0


class TestConditionFromCloudRain:
    def test_sunny(self):
        assert _condition_from_cloud_rain(5, 0, 5) == "sunny"

    def test_rainy(self):
        assert _condition_from_cloud_rain(80, 5, 10) == "rainy"

    def test_stormy(self):
        assert _condition_from_cloud_rain(90, 5, 70) == "stormy"

    def test_partly_cloudy(self):
        assert _condition_from_cloud_rain(35, 0, 10) == "partly_cloudy"

    def test_cloudy(self):
        assert _condition_from_cloud_rain(60, 0, 10) == "cloudy"


# ═══════════════════════════════════════════════════════════════════════════
# Optimizer — Basic Plan
# ═══════════════════════════════════════════════════════════════════════════


class TestOptimize:
    def test_returns_plan(self, optimizer):
        plan = optimizer.optimize()
        assert isinstance(plan, WeatherOptimizationPlan)

    def test_default_48h(self, optimizer):
        plan = optimizer.optimize()
        assert plan.horizon_hours == 48
        assert len(plan.hourly_forecast) == 48

    def test_custom_horizon(self, optimizer):
        plan = optimizer.optimize(horizon=24)
        assert plan.horizon_hours == 24
        assert len(plan.hourly_forecast) == 24

    def test_has_summary(self, optimizer):
        plan = optimizer.optimize()
        assert "total_pv_kwh" in plan.summary
        assert "avg_price_eur_kwh" in plan.summary
        assert "best_hours" in plan.summary

    def test_has_windows(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        assert isinstance(plan.top_windows, list)

    def test_has_battery_plan(self, optimizer):
        plan = optimizer.optimize()
        assert isinstance(plan.battery_plan, list)
        assert len(plan.battery_plan) == 48

    def test_generated_at(self, optimizer):
        plan = optimizer.optimize()
        assert "T" in plan.generated_at

    def test_base_date(self, optimizer):
        d = date(2026, 3, 15)
        plan = optimizer.optimize(base_date=d)
        assert plan.base_date == "2026-03-15"


# ═══════════════════════════════════════════════════════════════════════════
# Hourly Forecast Quality
# ═══════════════════════════════════════════════════════════════════════════


class TestHourlyForecast:
    def test_forecast_fields(self, optimizer):
        plan = optimizer.optimize()
        h = plan.hourly_forecast[0]
        assert "hour" in h
        assert "timestamp" in h
        assert "temperature_c" in h
        assert "cloud_cover_pct" in h
        assert "pv_production_kwh" in h
        assert "price_eur_kwh" in h
        assert "composite_score" in h
        assert "condition" in h

    def test_scores_bounded(self, optimizer):
        plan = optimizer.optimize()
        for h in plan.hourly_forecast:
            assert 0 <= h["composite_score"] <= 1.0

    def test_sunny_higher_pv(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        noon_hours = [h for h in plan.hourly_forecast
                      if h["hour"] in (12, 13, 36, 37)]
        night_hours = [h for h in plan.hourly_forecast
                       if h["hour"] in (0, 1, 24, 25)]
        avg_noon_pv = sum(h["pv_production_kwh"] for h in noon_hours) / max(len(noon_hours), 1)
        avg_night_pv = sum(h["pv_production_kwh"] for h in night_hours) / max(len(night_hours), 1)
        assert avg_noon_pv > avg_night_pv

    def test_weather_data_applied(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        h = plan.hourly_forecast[0]
        assert h["cloud_cover_pct"] == 10.0

    def test_price_data_applied(self, optimizer, low_prices):
        plan = optimizer.optimize(price_hours=low_prices)
        for h in plan.hourly_forecast:
            assert h["price_eur_kwh"] == 0.10


# ═══════════════════════════════════════════════════════════════════════════
# Optimization Windows
# ═══════════════════════════════════════════════════════════════════════════


class TestWindows:
    def test_windows_sorted_by_score(self, optimizer, sunny_weather, low_prices):
        plan = optimizer.optimize(weather_hours=sunny_weather, price_hours=low_prices)
        if len(plan.top_windows) > 1:
            scores = [w["avg_score"] for w in plan.top_windows]
            assert scores == sorted(scores, reverse=True)

    def test_window_has_fields(self, optimizer, sunny_weather, low_prices):
        plan = optimizer.optimize(weather_hours=sunny_weather, price_hours=low_prices)
        if plan.top_windows:
            w = plan.top_windows[0]
            assert "start_hour" in w
            assert "end_hour" in w
            assert "duration_hours" in w
            assert "avg_score" in w
            assert "reason" in w

    def test_max_5_windows(self, optimizer, sunny_weather, low_prices):
        plan = optimizer.optimize(weather_hours=sunny_weather, price_hours=low_prices)
        assert len(plan.top_windows) <= 5


# ═══════════════════════════════════════════════════════════════════════════
# Battery Plan
# ═══════════════════════════════════════════════════════════════════════════


class TestBatteryPlan:
    def test_battery_actions_valid(self, optimizer):
        plan = optimizer.optimize()
        valid = {"charge_from_pv", "charge_from_grid", "discharge", "hold"}
        for b in plan.battery_plan:
            assert b["action"] in valid

    def test_sunny_charges_from_pv(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        pv_charges = [b for b in plan.battery_plan if b["action"] == "charge_from_pv"]
        assert len(pv_charges) > 0

    def test_high_price_discharges(self, optimizer, high_prices):
        plan = optimizer.optimize(price_hours=high_prices)
        discharges = [b for b in plan.battery_plan if b["action"] == "discharge"]
        assert len(discharges) > 0

    def test_power_watts_non_negative(self, optimizer):
        plan = optimizer.optimize()
        for b in plan.battery_plan:
            assert b["power_watts"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════════════════════


class TestAlerts:
    def test_storm_alert(self, optimizer):
        weather = [{"cloud_cover_pct": 90, "precipitation_mm": 5,
                     "wind_speed_kmh": 70, "temperature_c": 10}
                    for _ in range(48)]
        plan = optimizer.optimize(weather_hours=weather)
        assert any("Sturmwarnung" in a for a in plan.alerts)

    def test_extended_cloud_alert(self, optimizer):
        weather = [{"cloud_cover_pct": 95, "precipitation_mm": 0,
                     "wind_speed_kmh": 5, "temperature_c": 15}
                    for _ in range(48)]
        plan = optimizer.optimize(weather_hours=weather)
        assert any("Bewoelkung" in a for a in plan.alerts)

    def test_price_spike_alert(self, optimizer):
        prices = [0.20] * 10 + [0.55] + [0.20] * 37
        plan = optimizer.optimize(price_hours=prices)
        assert any("Preisspitze" in a for a in plan.alerts)

    def test_frost_alert(self, optimizer):
        weather = [{"cloud_cover_pct": 50, "precipitation_mm": 0,
                     "wind_speed_kmh": 10, "temperature_c": -8}
                    for _ in range(48)]
        plan = optimizer.optimize(weather_hours=weather)
        assert any("Frostwarnung" in a for a in plan.alerts)

    def test_no_alerts_on_good_weather(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        # Sunny weather with default prices should produce no storm/frost alerts
        storm_frost = [a for a in plan.alerts
                       if "Sturmwarnung" in a or "Frostwarnung" in a]
        assert len(storm_frost) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Best Window
# ═══════════════════════════════════════════════════════════════════════════


class TestBestWindow:
    def test_returns_window(self, optimizer):
        w = optimizer.get_best_window(duration_hours=3)
        assert "start_hour" in w
        assert "end_hour" in w
        assert "avg_score" in w

    def test_correct_duration(self, optimizer):
        w = optimizer.get_best_window(duration_hours=4)
        assert w["duration_hours"] == 4
        assert w["end_hour"] - w["start_hour"] == 4

    def test_sunny_window_midday(self, optimizer, sunny_weather, low_prices):
        w = optimizer.get_best_window(
            duration_hours=3, weather_hours=sunny_weather, price_hours=low_prices
        )
        # With sunny weather + low prices, best window should be during daylight
        assert 6 <= w["start_hour"] <= 18 or 30 <= w["start_hour"] <= 42

    def test_short_horizon_error(self, optimizer):
        w = optimizer.get_best_window(duration_hours=3)
        # Default 48h horizon is enough for 3h window
        assert "error" not in w


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════


class TestSummary:
    def test_summary_fields(self, optimizer):
        plan = optimizer.optimize()
        s = plan.summary
        assert "total_pv_kwh" in s
        assert "avg_price_eur_kwh" in s
        assert "best_hours" in s
        assert "worst_hours" in s
        assert "pv_self_consumption_potential_pct" in s
        assert "optimal_windows_count" in s

    def test_sunny_high_pv(self, optimizer, sunny_weather):
        plan = optimizer.optimize(weather_hours=sunny_weather)
        assert plan.summary["total_pv_kwh"] > 30  # 8kWp system, sunny

    def test_best_hours_list(self, optimizer):
        plan = optimizer.optimize()
        assert isinstance(plan.summary["best_hours"], list)
        assert len(plan.summary["best_hours"]) <= 5

    def test_worst_hours_list(self, optimizer):
        plan = optimizer.optimize()
        assert isinstance(plan.summary["worst_hours"], list)
        assert len(plan.summary["worst_hours"]) <= 5
