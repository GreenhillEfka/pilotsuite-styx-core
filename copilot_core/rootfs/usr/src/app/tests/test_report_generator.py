"""Tests for Energy Report Generator (v5.13.0)."""

import pytest
from datetime import date, timedelta
from copilot_core.energy.report_generator import (
    EnergyReportGenerator,
    EnergyReport,
    ConsumptionBreakdown,
    CostBreakdown,
    PeriodComparison,
    Recommendation,
)


@pytest.fixture
def gen():
    return EnergyReportGenerator(grid_price_eur_kwh=0.30, feed_in_tariff_eur_kwh=0.082)


@pytest.fixture
def gen_with_data(gen):
    """Generator with 30 days of sample data."""
    today = date.today()
    for i in range(30):
        d = today - timedelta(days=i)
        gen.add_daily_data(
            day=d,
            consumption_kwh=20.0 + (i % 5),
            production_kwh=8.0 + (i % 3),
            avg_price_eur_kwh=0.25 + (i % 7) * 0.02,
            devices=[
                {"device_name": "Waschmaschine", "kwh": 1.5, "runs": 1},
                {"device_name": "Trockner", "kwh": 3.0, "runs": 1 if i % 2 == 0 else 0},
            ],
        )
    return gen


@pytest.fixture
def gen_solar_heavy(gen):
    """Generator with high solar production."""
    today = date.today()
    for i in range(14):
        d = today - timedelta(days=i)
        gen.add_daily_data(
            day=d,
            consumption_kwh=15.0,
            production_kwh=25.0,  # More production than consumption
            avg_price_eur_kwh=0.30,
        )
    return gen


# ═══════════════════════════════════════════════════════════════════════════
# Add Daily Data
# ═══════════════════════════════════════════════════════════════════════════


class TestAddData:
    def test_add_single_day(self, gen):
        gen.add_daily_data(date.today(), 20.0, 5.0)
        coverage = gen.get_data_coverage()
        assert coverage["days"] == 1

    def test_add_multiple_days(self, gen):
        today = date.today()
        gen.add_daily_data(today, 20.0, 5.0)
        gen.add_daily_data(today - timedelta(days=1), 18.0, 6.0)
        coverage = gen.get_data_coverage()
        assert coverage["days"] == 2

    def test_overwrite_day(self, gen):
        today = date.today()
        gen.add_daily_data(today, 20.0, 5.0)
        gen.add_daily_data(today, 25.0, 8.0)
        coverage = gen.get_data_coverage()
        assert coverage["days"] == 1

    def test_coverage_dates(self, gen_with_data):
        coverage = gen_with_data.get_data_coverage()
        assert coverage["first_date"] is not None
        assert coverage["last_date"] is not None

    def test_empty_coverage(self, gen):
        coverage = gen.get_data_coverage()
        assert coverage["days"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateReport:
    def test_returns_report(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert isinstance(r, EnergyReport)

    def test_report_type(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.report_type == "weekly"

    def test_daily_report(self, gen_with_data):
        r = gen_with_data.generate_report("daily")
        assert r.report_type == "daily"

    def test_monthly_report(self, gen_with_data):
        r = gen_with_data.generate_report("monthly")
        assert r.report_type == "monthly"

    def test_has_report_id(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.report_id.startswith("weekly_")

    def test_period_dates(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.period_start is not None
        assert r.period_end is not None

    def test_generated_at(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert "T" in r.generated_at

    def test_empty_generator(self, gen):
        r = gen.generate_report("weekly")
        assert r.consumption["total_consumption_kwh"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Consumption Breakdown
# ═══════════════════════════════════════════════════════════════════════════


class TestConsumption:
    def test_total_consumption(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.consumption["total_consumption_kwh"] > 0

    def test_total_production(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.consumption["total_production_kwh"] > 0

    def test_net_grid(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.consumption["net_grid_kwh"] >= 0

    def test_self_consumed(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.consumption["self_consumed_kwh"] >= 0

    def test_autarky_ratio(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert 0 <= r.consumption["autarky_ratio_pct"] <= 100

    def test_high_solar_autarky(self, gen_solar_heavy):
        r = gen_solar_heavy.generate_report("weekly")
        assert r.consumption["autarky_ratio_pct"] == 100.0  # production > consumption

    def test_fed_in_kwh(self, gen_solar_heavy):
        r = gen_solar_heavy.generate_report("weekly")
        assert r.consumption["fed_in_kwh"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Cost Breakdown
# ═══════════════════════════════════════════════════════════════════════════


class TestCosts:
    def test_net_cost(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.costs["net_cost_eur"] > 0

    def test_gross_cost(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.costs["gross_cost_eur"] >= r.costs["net_cost_eur"]

    def test_solar_savings(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.costs["solar_savings_eur"] >= 0

    def test_feed_in_revenue(self, gen_solar_heavy):
        r = gen_solar_heavy.generate_report("weekly")
        assert r.costs["feed_in_revenue_eur"] > 0

    def test_cheapest_day(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.costs["cheapest_day"] != ""

    def test_most_expensive_day(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.costs["most_expensive_day"] != ""


# ═══════════════════════════════════════════════════════════════════════════
# Comparison
# ═══════════════════════════════════════════════════════════════════════════


class TestComparison:
    def test_trend_valid(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert r.comparison["trend"] in ("improving", "stable", "worsening")

    def test_change_percentages(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert isinstance(r.comparison["consumption_change_pct"], float)
        assert isinstance(r.comparison["cost_change_pct"], float)

    def test_summary_german(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert isinstance(r.comparison["summary_de"], str)
        assert len(r.comparison["summary_de"]) > 0

    def test_empty_comparison(self, gen):
        r = gen.generate_report("weekly")
        assert r.comparison["trend"] == "stable"


# ═══════════════════════════════════════════════════════════════════════════
# Recommendations
# ═══════════════════════════════════════════════════════════════════════════


class TestRecommendations:
    def test_has_recommendations(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert isinstance(r.recommendations, list)

    def test_recommendation_fields(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        if r.recommendations:
            rec = r.recommendations[0]
            assert "category" in rec
            assert "title_de" in rec
            assert "description_de" in rec
            assert "potential_savings_eur" in rec
            assert "priority" in rec

    def test_sorted_by_priority(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        if len(r.recommendations) > 1:
            priorities = [rec["priority"] for rec in r.recommendations]
            assert priorities == sorted(priorities)

    def test_solar_recommendation_on_low_autarky(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        categories = [rec["category"] for rec in r.recommendations]
        # With moderate solar, should see solar recommendation
        assert "solar" in categories or "consumption" in categories


# ═══════════════════════════════════════════════════════════════════════════
# Highlights
# ═══════════════════════════════════════════════════════════════════════════


class TestHighlights:
    def test_has_highlights(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert len(r.highlights) >= 2

    def test_highlights_german(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        # Should contain German text
        assert any("kWh" in h for h in r.highlights)
        assert any("EUR" in h for h in r.highlights)

    def test_solar_highlight(self, gen_solar_heavy):
        r = gen_solar_heavy.generate_report("weekly")
        assert any("PV" in h or "Autarkie" in h for h in r.highlights)


# ═══════════════════════════════════════════════════════════════════════════
# Device Insights
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceInsights:
    def test_has_device_insights(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        assert len(r.device_insights) > 0

    def test_sorted_by_kwh(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        if len(r.device_insights) > 1:
            kwhs = [d["total_kwh"] for d in r.device_insights]
            assert kwhs == sorted(kwhs, reverse=True)

    def test_device_fields(self, gen_with_data):
        r = gen_with_data.generate_report("weekly")
        if r.device_insights:
            d = r.device_insights[0]
            assert "device_name" in d
            assert "total_kwh" in d
            assert "total_runs" in d

    def test_no_devices_empty(self, gen_solar_heavy):
        r = gen_solar_heavy.generate_report("weekly")
        assert r.device_insights == []
