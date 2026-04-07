"""Tests for Gas Meter & Gastherme Engine (v6.3.0)."""

from datetime import datetime, timedelta, timezone

import pytest

from copilot_core.regional.gas_meter import (
    GasDashboard,
    GasForecast,
    GasMeterConfig,
    GasMeterEngine,
    GasPeriodStats,
    _DEFAULT_CALORIFIC_VALUE_KWH_M3,
    _DEFAULT_Z_NUMBER,
    _REGIONAL_GAS_PRICES_CT_KWH,
)


@pytest.fixture
def engine():
    return GasMeterEngine()


@pytest.fixture
def configured_engine():
    config = GasMeterConfig(
        impulse_factor_m3=0.01,
        gas_price_ct_kwh=9.0,
        initial_meter_reading_m3=1000.0,
        region="sued",
    )
    return GasMeterEngine(config)


def _now():
    return datetime.now(tz=timezone.utc)


class TestConfiguration:
    def test_default_config(self, engine):
        assert engine._config.impulse_factor_m3 == 0.01
        assert engine._config.calorific_value_kwh_m3 == _DEFAULT_CALORIFIC_VALUE_KWH_M3
        assert engine._config.z_number == _DEFAULT_Z_NUMBER
        assert engine._gas_price_ct_kwh == _REGIONAL_GAS_PRICES_CT_KWH["default"]

    def test_regional_price(self):
        config = GasMeterConfig(region="nord")
        engine = GasMeterEngine(config)
        assert engine._gas_price_ct_kwh == 8.5

    def test_manual_price(self):
        config = GasMeterConfig(gas_price_ct_kwh=12.0)
        engine = GasMeterEngine(config)
        assert engine._gas_price_ct_kwh == 12.0

    def test_initial_reading(self, configured_engine):
        assert configured_engine._current_meter_m3 == 1000.0

    def test_update_config(self, engine):
        result = engine.update_config(impulse_factor_m3=0.10)
        assert result.impulse_factor_m3 == 0.10

    def test_set_gas_price(self, engine):
        engine.set_gas_price(11.5)
        assert engine._gas_price_ct_kwh == 11.5

    def test_set_initial_reading(self, engine):
        engine.set_initial_reading(500.0)
        assert engine._current_meter_m3 == 500.0
        assert engine._config.initial_meter_reading_m3 == 500.0


class TestImpulseRecording:
    def test_single_impulse(self, engine):
        result = engine.record_impulse()
        assert result == pytest.approx(0.01, abs=0.001)
        assert engine._impulse_count == 1

    def test_multiple_single_impulses(self, engine):
        for _ in range(100):
            engine.record_impulse()
        assert engine._current_meter_m3 == pytest.approx(1.0, abs=0.01)
        assert engine._impulse_count == 100

    def test_batch_impulses(self, engine):
        result = engine.record_impulses(50)
        assert result == pytest.approx(0.5, abs=0.01)
        assert engine._impulse_count == 50

    def test_impulse_with_initial_reading(self, configured_engine):
        result = configured_engine.record_impulse()
        assert result == pytest.approx(1000.01, abs=0.001)

    def test_impulse_creates_reading(self, engine):
        engine.record_impulse()
        assert len(engine._readings) == 1
        assert engine._readings[0].source == "impulse"
        assert engine._readings[0].impulses_delta == 1


class TestMeterReading:
    def test_direct_reading(self, configured_engine):
        delta = configured_engine.record_meter_reading(1005.0)
        assert delta == pytest.approx(5.0, abs=0.01)
        assert configured_engine._current_meter_m3 == 1005.0

    def test_reading_no_decrease(self, configured_engine):
        delta = configured_engine.record_meter_reading(999.0)
        assert delta == 0.0
        assert configured_engine._current_meter_m3 == 999.0

    def test_reading_creates_entry(self, engine):
        engine.record_meter_reading(10.0)
        assert len(engine._readings) == 1
        assert engine._readings[0].source == "counter"


class TestConversions:
    def test_m3_to_kwh(self, engine):
        kwh = engine.m3_to_kwh(1.0)
        expected = 1.0 * _DEFAULT_CALORIFIC_VALUE_KWH_M3 * _DEFAULT_Z_NUMBER
        assert kwh == pytest.approx(expected, rel=0.01)

    def test_m3_to_kwh_configured(self, configured_engine):
        kwh = configured_engine.m3_to_kwh(1.0)
        expected = 1.0 * _DEFAULT_CALORIFIC_VALUE_KWH_M3 * _DEFAULT_Z_NUMBER
        assert kwh == pytest.approx(expected, rel=0.01)

    def test_kwh_to_cost(self, engine):
        cost = engine.kwh_to_cost_eur(100.0)
        expected = 100.0 * _REGIONAL_GAS_PRICES_CT_KWH["default"] / 100.0
        assert cost == pytest.approx(expected, rel=0.01)

    def test_m3_to_cost(self, engine):
        cost = engine.m3_to_cost_eur(1.0)
        kwh = engine.m3_to_kwh(1.0)
        expected = kwh * _REGIONAL_GAS_PRICES_CT_KWH["default"] / 100.0
        assert cost == pytest.approx(expected, rel=0.01)

    def test_gas_price_eur_per_m3(self, engine):
        price = engine.gas_price_eur_per_m3
        assert price > 0


class TestStatistics:
    def test_today_stats_empty(self, engine):
        stats = engine.get_period_stats("today")
        assert stats.period == "today"
        assert stats.consumption_m3 == 0.0

    def test_today_stats_with_data(self, engine):
        now = _now()
        engine.record_impulses(100, now)
        stats = engine.get_period_stats("today")
        assert stats.consumption_m3 == pytest.approx(1.0, abs=0.01)
        assert stats.consumption_kwh > 0
        assert stats.cost_eur > 0

    def test_yesterday_stats(self, engine):
        yesterday = _now() - timedelta(days=1)
        engine.record_impulses(200, yesterday)
        stats = engine.get_period_stats("yesterday")
        assert stats.consumption_m3 == pytest.approx(2.0, abs=0.01)

    def test_week_stats(self, engine):
        # Add data for each day this week
        now = _now()
        for i in range(min(now.weekday() + 1, 7)):
            day = now - timedelta(days=i)
            engine.record_impulses(50, day)
        stats = engine.get_period_stats("week")
        assert stats.consumption_m3 > 0

    def test_avg_daily(self, engine):
        now = _now()
        engine.record_impulses(300, now)
        stats = engine.get_period_stats("today")
        assert stats.avg_daily_m3 > 0
        assert stats.avg_daily_kwh > 0
        assert stats.avg_daily_cost > 0


class TestForecast:
    def test_empty_forecast(self, engine):
        forecast = engine.get_forecast("month")
        assert forecast.confidence == 0.0
        assert forecast.based_on_days == 0

    def test_month_forecast(self, engine):
        now = _now()
        # Simulate 14 days of data
        for i in range(14):
            day = now - timedelta(days=i)
            engine.record_impulses(100, day)  # 1 m³/day
        forecast = engine.get_forecast("month")
        assert forecast.estimated_m3 > 0
        assert forecast.estimated_kwh > 0
        assert forecast.estimated_cost_eur > 0
        assert forecast.confidence == pytest.approx(1.0, abs=0.01)
        assert forecast.based_on_days == 14

    def test_year_forecast(self, engine):
        now = _now()
        for i in range(7):
            day = now - timedelta(days=i)
            engine.record_impulses(100, day)
        forecast = engine.get_forecast("year")
        assert forecast.estimated_m3 > 0
        assert forecast.based_on_days == 7

    def test_trend_detection(self, engine):
        now = _now()
        # Increasing consumption: older days less, recent days more
        for i in range(14):
            day = now - timedelta(days=13 - i)
            impulses = 50 + i * 20  # 50 -> 310
            engine.record_impulses(impulses, day)
        forecast = engine.get_forecast("month")
        assert forecast.trend == "steigend"


class TestDashboard:
    def test_empty_dashboard(self, engine):
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, GasDashboard)
        assert dashboard.current_meter_m3 == 0.0
        assert dashboard.total_impulses == 0
        assert dashboard.gas_price_ct_kwh > 0

    def test_dashboard_with_data(self, engine):
        engine.record_impulses(500, _now())
        dashboard = engine.get_dashboard()
        assert dashboard.current_meter_m3 == pytest.approx(5.0, abs=0.1)
        assert dashboard.total_impulses == 500
        assert dashboard.today.consumption_m3 > 0
        assert dashboard.gas_price_eur_m3 > 0

    def test_dashboard_config(self, engine):
        dashboard = engine.get_dashboard()
        assert "impulse_factor_m3" in dashboard.config
        assert "binary_sensor_entity" in dashboard.config
        assert "counter_entity" in dashboard.config

    def test_dashboard_calorific_value(self, engine):
        dashboard = engine.get_dashboard()
        assert dashboard.calorific_value == _DEFAULT_CALORIFIC_VALUE_KWH_M3


class TestRegionalPrices:
    def test_all_regions(self):
        for region in ["nord", "ost", "sued", "west", "default"]:
            config = GasMeterConfig(region=region)
            engine = GasMeterEngine(config)
            assert engine._gas_price_ct_kwh == _REGIONAL_GAS_PRICES_CT_KWH[region]

    def test_unknown_region_uses_default(self):
        config = GasMeterConfig(region="unknown")
        engine = GasMeterEngine(config)
        assert engine._gas_price_ct_kwh == _REGIONAL_GAS_PRICES_CT_KWH["default"]


class TestEdgeCases:
    def test_large_impulse_count(self, engine):
        engine.record_impulses(100000)
        assert engine._current_meter_m3 == pytest.approx(1000.0, abs=0.1)

    def test_alt_impulse_factor(self):
        config = GasMeterConfig(impulse_factor_m3=0.10)
        engine = GasMeterEngine(config)
        engine.record_impulse()
        assert engine._current_meter_m3 == pytest.approx(0.10, abs=0.01)

    def test_mixed_sources(self, engine):
        engine.record_impulses(100)
        engine.record_meter_reading(5.0)
        engine.record_impulses(50)
        assert engine._current_meter_m3 == pytest.approx(5.5, abs=0.1)
        assert len(engine._readings) == 3
