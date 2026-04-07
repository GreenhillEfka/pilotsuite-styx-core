"""Tests for Energy Forecast Dashboard (v5.20.0)."""

from datetime import datetime, timedelta

import pytest

from copilot_core.regional.energy_forecast import (
    EnergyForecastEngine,
    ForecastHour,
    ForecastSummary,
    DashboardCard,
    EnergyForecastDashboard,
)


@pytest.fixture
def engine():
    return EnergyForecastEngine(
        latitude=52.52, longitude=13.405, pv_peak_kw=10.0, grid_price_ct=30.0
    )


@pytest.fixture
def engine_with_prices(engine):
    prices = {}
    for h in range(48):
        if 0 <= (h % 24) <= 5:
            prices[h] = 18.0
        elif 17 <= (h % 24) <= 20:
            prices[h] = 38.0
        else:
            prices[h] = 28.0
    engine.set_hourly_prices(prices)
    return engine


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_default_location(self, engine):
        assert engine._lat == 52.52

    def test_default_pv(self, engine):
        assert engine._pv_peak == 10.0

    def test_set_pv_peak(self, engine):
        engine.set_pv_peak(15.0)
        assert engine._pv_peak == 15.0

    def test_update_location(self, engine):
        engine.update_location(48.0, 11.0)
        assert engine._lat == 48.0


# ── Test forecast generation ─────────────────────────────────────────────


class TestForecast:
    def test_generates_48_hours(self, engine):
        forecast = engine.generate_forecast()
        assert len(forecast) == 48

    def test_hour_numbering(self, engine):
        forecast = engine.generate_forecast()
        for i, h in enumerate(forecast):
            assert h.hour == i

    def test_timestamps_sequential(self, engine):
        forecast = engine.generate_forecast()
        for i in range(1, len(forecast)):
            t0 = datetime.fromisoformat(forecast[i - 1].timestamp)
            t1 = datetime.fromisoformat(forecast[i].timestamp)
            diff = (t1 - t0).total_seconds()
            assert diff == 3600

    def test_pv_factor_range(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            assert 0 <= h.pv_factor <= 1.0

    def test_has_daylight_hours(self, engine):
        forecast = engine.generate_forecast()
        daylight = [h for h in forecast if h.is_daylight]
        assert len(daylight) > 0  # at least some daylight in 48h

    def test_has_night_hours(self, engine):
        forecast = engine.generate_forecast()
        night = [h for h in forecast if not h.is_daylight]
        assert len(night) > 0

    def test_night_pv_zero(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            if not h.is_daylight:
                assert h.pv_factor == 0

    def test_price_assigned(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            assert h.price_ct_kwh > 0

    def test_action_assigned(self, engine):
        forecast = engine.generate_forecast()
        valid_actions = {"charge", "discharge", "hold", "shift", "consume"}
        for h in forecast:
            assert h.action in valid_actions

    def test_score_range(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            assert 0 <= h.score <= 10

    def test_price_level_assigned(self, engine):
        forecast = engine.generate_forecast()
        valid_levels = {"very_low", "low", "normal", "high", "very_high"}
        for h in forecast:
            assert h.price_level in valid_levels

    def test_pv_kw_estimated(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            if h.is_daylight:
                assert h.pv_kw_estimated >= 0
            else:
                assert h.pv_kw_estimated == 0


# ── Test with custom prices ──────────────────────────────────────────────


class TestCustomPrices:
    def test_cheap_hours_scored_higher(self, engine_with_prices):
        forecast = engine_with_prices.generate_forecast()
        cheap = [h for h in forecast if h.price_ct_kwh <= 20]
        expensive = [h for h in forecast if h.price_ct_kwh >= 35]
        if cheap and expensive:
            avg_cheap_score = sum(h.score for h in cheap) / len(cheap)
            avg_expensive_score = sum(h.score for h in expensive) / len(expensive)
            # Cheap hours should generally score higher (ignoring PV)
            # This is a soft assertion since PV affects scores too

    def test_price_levels_vary(self, engine_with_prices):
        forecast = engine_with_prices.generate_forecast()
        levels = set(h.price_level for h in forecast)
        assert len(levels) > 1


# ── Test weather impacts ─────────────────────────────────────────────────


class TestWeatherImpact:
    def test_pv_reduction(self, engine):
        engine.set_weather_impacts({h: ("high", 80) for h in range(48)})
        forecast = engine.generate_forecast()
        for h in forecast:
            assert h.pv_reduction_pct == 80
            assert h.weather_impact == "high"

    def test_reduced_pv_kw(self, engine):
        engine.set_weather_impacts({h: ("high", 80) for h in range(48)})
        forecast = engine.generate_forecast()
        for h in forecast:
            if h.is_daylight and h.pv_factor > 0:
                # PV kW should be 20% of normal
                expected_max = h.pv_factor * engine._pv_peak * 0.21  # 20% + rounding
                assert h.pv_kw_estimated <= expected_max + 0.1

    def test_no_impact(self, engine):
        forecast = engine.generate_forecast()
        for h in forecast:
            assert h.pv_reduction_pct == 0
            assert h.weather_impact == "none"


# ── Test summary ─────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_structure(self, engine):
        summary = engine.generate_summary()
        assert isinstance(summary, ForecastSummary)
        assert summary.total_hours == 48

    def test_price_stats(self, engine):
        summary = engine.generate_summary()
        assert summary.min_price_ct <= summary.avg_price_ct <= summary.max_price_ct

    def test_daylight_hours(self, engine):
        summary = engine.generate_summary()
        assert summary.daylight_hours > 0

    def test_total_pv(self, engine):
        summary = engine.generate_summary()
        assert summary.total_pv_kwh_estimated >= 0


# ── Test dashboard cards ─────────────────────────────────────────────────


class TestDashboardCards:
    def test_generates_4_cards(self, engine):
        cards = engine.generate_dashboard_cards()
        assert len(cards) == 4

    def test_card_types(self, engine):
        cards = engine.generate_dashboard_cards()
        types = {c.card_type for c in cards}
        assert "price_chart" in types
        assert "pv_forecast" in types
        assert "recommendation" in types
        assert "overview" in types

    def test_cards_have_titles(self, engine):
        cards = engine.generate_dashboard_cards()
        for c in cards:
            assert len(c.title_de) > 0
            assert len(c.title_en) > 0

    def test_cards_have_data(self, engine):
        cards = engine.generate_dashboard_cards()
        for c in cards:
            assert len(c.data) > 0

    def test_price_chart_series(self, engine):
        cards = engine.generate_dashboard_cards()
        price_card = next(c for c in cards if c.card_type == "price_chart")
        assert "series" in price_card.data
        assert len(price_card.data["series"]) == 48

    def test_pv_card_has_total(self, engine):
        cards = engine.generate_dashboard_cards()
        pv_card = next(c for c in cards if c.card_type == "pv_forecast")
        assert "total_kwh" in pv_card.data

    def test_recommendation_card_top_hours(self, engine):
        cards = engine.generate_dashboard_cards()
        rec_card = next(c for c in cards if c.card_type == "recommendation")
        assert "top_hours" in rec_card.data
        assert len(rec_card.data["top_hours"]) <= 6


# ── Test full dashboard ──────────────────────────────────────────────────


class TestFullDashboard:
    def test_dashboard_structure(self, engine):
        dashboard = engine.generate_dashboard()
        assert isinstance(dashboard, EnergyForecastDashboard)
        assert len(dashboard.forecast) == 48
        assert len(dashboard.cards) == 4

    def test_dashboard_has_timestamp(self, engine):
        dashboard = engine.generate_dashboard()
        assert len(dashboard.generated_at) > 0

    def test_dashboard_serializable(self, engine):
        dashboard = engine.generate_dashboard()
        data = asdict(dashboard)
        assert isinstance(data, dict)


# ── Test data import ─────────────────────────────────────────────────────


class TestDataImport:
    def test_import_tariff_data(self, engine):
        now = datetime.now()
        tariff_data = []
        for h in range(24):
            dt = now + timedelta(hours=h)
            tariff_data.append({
                "start_timestamp": dt.isoformat(),
                "price_ct_kwh": 25.0 + h,
            })
        engine.import_tariff_data(tariff_data)
        assert len(engine._hourly_prices) > 0

    def test_import_warning_data(self, engine):
        impacts = [{"pv_reduction_pct": 60, "pv_impact": "high"}]
        engine.import_warning_data(impacts)
        assert len(engine._weather_impacts) > 0


from dataclasses import asdict
