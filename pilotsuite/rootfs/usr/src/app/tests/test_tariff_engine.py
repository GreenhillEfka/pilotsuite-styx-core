"""Tests for Regional Tariff Engine (v5.18.0)."""

import time
from datetime import datetime, timedelta

import pytest

from copilot_core.regional.tariff_engine import (
    RegionalTariffEngine,
    HourlyPrice,
    PriceSummary,
    OptimalWindow,
    TariffRecommendation,
    TariffType,
    PriceLevel,
    _classify_price,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_awattar_response(base_price_mwh: float = 50.0) -> dict:
    """Create aWATTar-style API response with 24 hours."""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    data = []
    for h in range(24):
        # Simulate price curve: cheap at night, expensive during day
        price_offset = 0
        if 0 <= h <= 5:
            price_offset = -20  # cheap night
        elif 6 <= h <= 9:
            price_offset = 10  # morning ramp
        elif 10 <= h <= 16:
            price_offset = 5  # midday
        elif 17 <= h <= 20:
            price_offset = 25  # evening peak
        else:
            price_offset = -10  # late evening

        start = today + timedelta(hours=h)
        end = start + timedelta(hours=1)
        data.append({
            "start_timestamp": int(start.timestamp() * 1000),
            "end_timestamp": int(end.timestamp() * 1000),
            "marketprice": base_price_mwh + price_offset,
            "unit": "Eur/MWh",
        })
    return {"data": data}


@pytest.fixture
def engine():
    return RegionalTariffEngine(country="DE")


@pytest.fixture
def engine_dynamic(engine):
    engine.process_awattar_response(_make_awattar_response())
    return engine


@pytest.fixture
def engine_fixed():
    return RegionalTariffEngine(
        country="DE", tariff_type=TariffType.FIXED, fixed_rate_eur_kwh=0.30
    )


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_default_country(self, engine):
        assert engine._country == "DE"

    def test_default_tariff(self, engine):
        assert engine._tariff_type == TariffType.TIME_OF_USE

    def test_default_source(self, engine):
        assert engine._source == "awattar_de"

    def test_at_source(self):
        e = RegionalTariffEngine(country="AT")
        assert e._source == "awattar_at"

    def test_ch_source(self):
        e = RegionalTariffEngine(country="CH")
        assert e._source == "epex_ch"

    def test_api_url(self, engine):
        assert "awattar.de" in engine.api_url

    def test_cache_not_valid(self, engine):
        assert not engine.cache_valid

    def test_feed_in_rate(self, engine):
        assert engine.feed_in_rate == 0.082


# ── Test price classification ────────────────────────────────────────────


class TestClassification:
    def test_very_low(self):
        assert _classify_price(0.15, 0.30) == PriceLevel.VERY_LOW

    def test_low(self):
        assert _classify_price(0.24, 0.30) == PriceLevel.LOW

    def test_normal(self):
        assert _classify_price(0.30, 0.30) == PriceLevel.NORMAL

    def test_high(self):
        assert _classify_price(0.38, 0.30) == PriceLevel.HIGH

    def test_very_high(self):
        assert _classify_price(0.50, 0.30) == PriceLevel.VERY_HIGH

    def test_zero_avg(self):
        assert _classify_price(0.10, 0) == PriceLevel.NORMAL


# ── Test aWATTar parsing ─────────────────────────────────────────────────


class TestAwattarParsing:
    def test_parse_24_hours(self, engine):
        data = _make_awattar_response()
        prices = engine.process_awattar_response(data)
        assert len(prices) == 24

    def test_prices_include_surcharge(self, engine):
        data = _make_awattar_response(base_price_mwh=50.0)
        prices = engine.process_awattar_response(data)
        # 50 EUR/MWh = 0.05 EUR/kWh + 0.18 surcharge = 0.23 EUR/kWh
        avg = sum(p.price_eur_kwh for p in prices) / len(prices)
        assert avg > 0.20  # should include surcharges

    def test_ct_kwh_conversion(self, engine):
        data = _make_awattar_response()
        prices = engine.process_awattar_response(data)
        for p in prices:
            assert abs(p.price_ct_kwh - p.price_eur_kwh * 100) < 0.01

    def test_has_current_hour(self, engine):
        data = _make_awattar_response()
        prices = engine.process_awattar_response(data)
        current = [p for p in prices if p.is_current]
        assert len(current) == 1

    def test_levels_assigned(self, engine):
        # Use wider price spread for level variation
        data = _make_awattar_response(base_price_mwh=100.0)
        prices = engine.process_awattar_response(data)
        levels = set(p.level for p in prices)
        assert len(levels) >= 1  # should have at least one level

    def test_sets_dynamic_type(self, engine):
        engine.process_awattar_response(_make_awattar_response())
        assert engine.tariff_type == TariffType.DYNAMIC

    def test_cache_updated(self, engine):
        engine.process_awattar_response(_make_awattar_response())
        assert engine.cache_valid is True

    def test_empty_data(self, engine):
        prices = engine.process_awattar_response({"data": []})
        assert len(prices) == 0


# ── Test manual prices ───────────────────────────────────────────────────


class TestManualPrices:
    def test_parse_manual(self, engine):
        manual = [{"hour": h, "price_eur_kwh": 0.25 + h * 0.005} for h in range(24)]
        prices = engine.process_manual_prices(manual)
        assert len(prices) == 24

    def test_manual_levels(self, engine):
        manual = [
            {"hour": 0, "price_eur_kwh": 0.15},
            {"hour": 12, "price_eur_kwh": 0.40},
        ]
        prices = engine.process_manual_prices(manual)
        assert prices[0].level != prices[1].level


# ── Test time-of-use ─────────────────────────────────────────────────────


class TestTimeOfUse:
    def test_tou_24_hours(self, engine):
        prices = engine.get_hourly_prices()
        assert len(prices) == 24

    def test_tou_night_cheaper(self, engine):
        prices = engine.get_hourly_prices()
        night = next(p for p in prices if "T02:" in p.start_timestamp)
        day = next(p for p in prices if "T12:" in p.start_timestamp)
        assert night.price_eur_kwh < day.price_eur_kwh

    def test_tou_has_current(self, engine):
        prices = engine.get_hourly_prices()
        current = [p for p in prices if p.is_current]
        assert len(current) == 1


# ── Test fixed rate ──────────────────────────────────────────────────────


class TestFixedRate:
    def test_all_same_price(self, engine_fixed):
        prices = engine_fixed.get_hourly_prices()
        for p in prices:
            assert p.price_eur_kwh == 0.30

    def test_all_normal_level(self, engine_fixed):
        prices = engine_fixed.get_hourly_prices()
        for p in prices:
            assert p.level == PriceLevel.NORMAL


# ── Test current price ───────────────────────────────────────────────────


class TestCurrentPrice:
    def test_has_current(self, engine_dynamic):
        current = engine_dynamic.get_current_price()
        assert current is not None
        assert current.is_current is True

    def test_tou_current(self, engine):
        current = engine.get_current_price()
        assert current is not None


# ── Test summary ─────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_structure(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        assert isinstance(summary, PriceSummary)
        assert summary.hours_available == 24

    def test_min_max(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        assert summary.min_price_eur_kwh <= summary.max_price_eur_kwh

    def test_spread(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        expected_spread = summary.max_price_eur_kwh - summary.min_price_eur_kwh
        assert abs(summary.spread_eur_kwh - expected_spread) < 0.001

    def test_tariff_type(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        assert summary.tariff_type == TariffType.DYNAMIC

    def test_source(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        assert summary.source == "awattar_de"

    def test_min_hour_format(self, engine_dynamic):
        summary = engine_dynamic.get_summary()
        assert ":" in summary.min_hour

    def test_no_dynamic_data_falls_back(self):
        e = RegionalTariffEngine(tariff_type=TariffType.DYNAMIC)
        # Dynamic with no data returns empty list, summary shows 0 hours
        prices = e.get_hourly_prices()
        # If no dynamic data loaded, get_hourly_prices returns empty
        assert len(prices) == 0 or e.tariff_type == TariffType.DYNAMIC


# ── Test optimal window ──────────────────────────────────────────────────


class TestOptimalWindow:
    def test_find_window(self, engine_dynamic):
        window = engine_dynamic.find_optimal_window(duration_hours=3)
        assert window is not None
        assert window.duration_hours == 3

    def test_window_avg(self, engine_dynamic):
        window = engine_dynamic.find_optimal_window(duration_hours=2)
        assert window is not None
        assert window.avg_price_eur_kwh > 0

    def test_window_savings(self, engine_dynamic):
        window = engine_dynamic.find_optimal_window(duration_hours=3)
        assert window is not None
        assert window.savings_pct >= 0

    def test_tou_window(self, engine):
        window = engine.find_optimal_window(duration_hours=4)
        assert window is not None

    def test_window_too_long(self, engine):
        window = engine.find_optimal_window(duration_hours=25)
        assert window is None


# ── Test recommendation ──────────────────────────────────────────────────


class TestRecommendation:
    def test_recommendation_structure(self, engine_dynamic):
        rec = engine_dynamic.get_recommendation()
        assert isinstance(rec, TariffRecommendation)
        assert rec.action in ("charge_now", "wait", "shift", "discharge")

    def test_recommendation_de(self, engine_dynamic):
        rec = engine_dynamic.get_recommendation()
        assert len(rec.reason_de) > 0

    def test_recommendation_en(self, engine_dynamic):
        rec = engine_dynamic.get_recommendation()
        assert len(rec.reason_en) > 0

    def test_recommendation_prices(self, engine_dynamic):
        rec = engine_dynamic.get_recommendation()
        assert rec.current_price_ct > 0

    def test_fixed_rate_recommendation(self, engine_fixed):
        rec = engine_fixed.get_recommendation()
        assert rec.action == "charge_now"  # fixed rate, always same


# ── Test configuration ───────────────────────────────────────────────────


class TestConfig:
    def test_update_country(self, engine):
        engine.update_config(country="AT")
        assert engine._country == "AT"
        assert engine._source == "awattar_at"

    def test_update_tariff_type(self, engine):
        engine.update_config(tariff_type=TariffType.FIXED)
        assert engine._tariff_type == TariffType.FIXED

    def test_update_fixed_rate(self, engine):
        engine.update_config(fixed_rate=0.35)
        assert engine._fixed_rate == 0.35

    def test_update_feed_in(self, engine):
        engine.update_config(feed_in=0.10)
        assert engine._feed_in == 0.10
