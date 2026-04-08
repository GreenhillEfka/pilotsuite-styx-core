"""Tests for Energy Advisor engine (v6.8.0)."""

import pytest
from copilot_core.hub.energy_advisor import (
    EnergyAdvisorEngine,
    DeviceConsumption,
    SavingsRecommendation,
    EcoScore,
    ConsumptionBreakdown,
    EnergyAdvisorDashboard,
)


@pytest.fixture
def engine():
    e = EnergyAdvisorEngine(electricity_price_ct_kwh=30.0)
    e.register_device("light.wohnzimmer", "Wohnzimmer Licht", "lighting")
    e.register_device("climate.heizung", "Heizung", "heating")
    e.register_device("sensor.waschmaschine", "Waschmaschine", "appliance")
    e.register_device("media_player.tv", "TV", "media")
    e.register_device("switch.standby", "Standby-Geräte", "standby")
    # Set consumption values
    e.update_consumption("light.wohnzimmer", 0.5)  # 0.5 kWh/day
    e.update_consumption("climate.heizung", 5.0)   # 5 kWh/day
    e.update_consumption("sensor.waschmaschine", 1.0)
    e.update_consumption("media_player.tv", 0.8)
    e.update_consumption("switch.standby", 0.3)
    return e


# ── Device tracking ────────────────────────────────────────────────────────


class TestDeviceTracking:
    def test_register_device(self, engine):
        consumers = engine.get_top_consumers()
        assert len(consumers) == 5

    def test_update_consumption(self, engine):
        consumers = engine.get_top_consumers()
        heizung = next(c for c in consumers if c["entity_id"] == "climate.heizung")
        assert heizung["daily_kwh"] == 5.0
        assert heizung["monthly_kwh"] == 150.0
        assert heizung["cost_monthly_eur"] == 45.0

    def test_invalid_category_fallback(self):
        e = EnergyAdvisorEngine()
        d = e.register_device("x", "X", "nonexistent")
        assert d.category == "other"

    def test_update_nonexistent_device(self, engine):
        result = engine.update_consumption("nonexistent", 1.0)
        assert result is False

    def test_electricity_price_update(self, engine):
        engine.set_electricity_price(40.0)
        consumers = engine.get_top_consumers()
        heizung = next(c for c in consumers if c["entity_id"] == "climate.heizung")
        assert heizung["cost_monthly_eur"] == 60.0  # 150 * 40 / 100


# ── Breakdown ──────────────────────────────────────────────────────────────


class TestBreakdown:
    def test_breakdown_categories(self, engine):
        breakdown = engine.get_breakdown()
        assert len(breakdown) == 5
        categories = {b.category for b in breakdown}
        assert "heating" in categories
        assert "lighting" in categories

    def test_breakdown_sorted_by_kwh(self, engine):
        breakdown = engine.get_breakdown()
        kwh_values = [b.kwh for b in breakdown]
        assert kwh_values == sorted(kwh_values, reverse=True)

    def test_breakdown_percentages(self, engine):
        breakdown = engine.get_breakdown()
        total_pct = sum(b.pct for b in breakdown)
        assert abs(total_pct - 100.0) < 1.0  # should be ~100%

    def test_breakdown_heating_dominant(self, engine):
        breakdown = engine.get_breakdown()
        heating = next(b for b in breakdown if b.category == "heating")
        assert heating.pct > 50  # heating should be > 50% of total


# ── Eco Score ──────────────────────────────────────────────────────────────


class TestEcoScore:
    def test_eco_score_calculation(self, engine):
        eco = engine.calculate_eco_score()
        assert 0 <= eco.score <= 100
        assert eco.grade in ("A+", "A", "B", "C", "D", "E", "F")

    def test_eco_score_empty(self):
        e = EnergyAdvisorEngine()
        eco = e.calculate_eco_score()
        assert eco.score == 50

    def test_eco_score_low_consumption(self):
        e = EnergyAdvisorEngine()
        e.register_device("light", "Light", "lighting")
        e.update_consumption("light", 1.0)  # 30 kWh/month = very low
        eco = e.calculate_eco_score()
        assert eco.score >= 85

    def test_eco_score_high_consumption(self):
        e = EnergyAdvisorEngine()
        e.register_device("all", "All", "heating")
        e.update_consumption("all", 30.0)  # 900 kWh/month = very high
        eco = e.calculate_eco_score()
        assert eco.score <= 35

    def test_eco_score_trend_stable(self, engine):
        eco = engine.calculate_eco_score()
        assert eco.trend == "stabil"


# ── Recommendations ───────────────────────────────────────────────────────


class TestRecommendations:
    def test_builtin_recommendations(self, engine):
        recs = engine.get_recommendations()
        assert len(recs) >= 7

    def test_recommendations_sorted_by_priority(self, engine):
        recs = engine.get_recommendations()
        priorities = [r["potential_savings_eur"] for r in recs]
        # First rec should be highest priority (not necessarily highest savings)
        assert recs[0]["rec_id"] == "heating_schedule"  # priority 95

    def test_filter_by_category(self, engine):
        recs = engine.get_recommendations(category="lighting")
        assert len(recs) >= 1
        assert all(r["category"] == "lighting" for r in recs)

    def test_mark_applied(self, engine):
        result = engine.mark_recommendation_applied("standby_killer")
        assert result is True
        recs = engine.get_recommendations()
        standby = next(r for r in recs if r["rec_id"] == "standby_killer")
        assert standby["applied"] is True

    def test_mark_nonexistent(self, engine):
        result = engine.mark_recommendation_applied("nonexistent")
        assert result is False

    def test_add_custom_recommendation(self, engine):
        result = engine.add_recommendation(
            "custom_tip", "Eigener Tipp", "Custom Tip",
            "Beschreibung", "Description",
            category="lighting",
            potential_savings_kwh=50,
            potential_savings_eur=15,
        )
        assert result is True
        recs = engine.get_recommendations()
        assert any(r["rec_id"] == "custom_tip" for r in recs)

    def test_add_duplicate_rejected(self, engine):
        result = engine.add_recommendation("standby_killer", "Dup")
        assert result is False


# ── Top consumers ─────────────────────────────────────────────────────────


class TestTopConsumers:
    def test_top_consumers_sorted(self, engine):
        consumers = engine.get_top_consumers()
        kwh = [c["monthly_kwh"] for c in consumers]
        assert kwh == sorted(kwh, reverse=True)

    def test_top_consumers_limit(self, engine):
        consumers = engine.get_top_consumers(limit=3)
        assert len(consumers) == 3

    def test_top_consumer_is_heating(self, engine):
        consumers = engine.get_top_consumers()
        assert consumers[0]["entity_id"] == "climate.heizung"


# ── Dashboard ─────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_totals(self, engine):
        db = engine.get_dashboard()
        assert db.total_daily_kwh == 7.6  # 0.5 + 5 + 1 + 0.8 + 0.3
        assert db.total_monthly_kwh == 228.0
        assert db.total_monthly_eur == 68.4  # 228 * 30 / 100

    def test_dashboard_eco_score(self, engine):
        db = engine.get_dashboard()
        assert "score" in db.eco_score
        assert "grade" in db.eco_score

    def test_dashboard_breakdown(self, engine):
        db = engine.get_dashboard()
        assert len(db.breakdown) == 5

    def test_dashboard_recommendations(self, engine):
        db = engine.get_dashboard()
        assert len(db.recommendations) >= 1

    def test_dashboard_savings_potential(self, engine):
        db = engine.get_dashboard()
        assert db.savings_potential_eur > 0

    def test_empty_dashboard(self):
        e = EnergyAdvisorEngine()
        db = e.get_dashboard()
        assert db.total_daily_kwh == 0.0
        assert db.total_monthly_kwh == 0.0
