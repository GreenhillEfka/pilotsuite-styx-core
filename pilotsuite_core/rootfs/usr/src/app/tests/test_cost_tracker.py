"""Tests for Energy Cost Tracker (v5.10.0)."""

import pytest
from datetime import date, timedelta
from copilot_core.energy.cost_tracker import (
    DailyCost,
    CostSummary,
    BudgetStatus,
    EnergyCostTracker,
)


@pytest.fixture
def tracker():
    return EnergyCostTracker(monthly_budget_eur=100.0)


@pytest.fixture
def tracker_with_data(tracker):
    """Tracker with 14 days of sample data."""
    today = date.today()
    for i in range(14):
        d = today - timedelta(days=i)
        tracker.record_day(
            consumption_kwh=15.0 + i * 0.5,
            production_kwh=5.0,
            avg_price_eur_kwh=0.30,
            record_date=d,
        )
    return tracker


# ═══════════════════════════════════════════════════════════════════════════
# Record Day
# ═══════════════════════════════════════════════════════════════════════════


class TestRecordDay:
    def test_returns_daily_cost(self, tracker):
        r = tracker.record_day(20.0, 5.0, 0.30)
        assert isinstance(r, DailyCost)

    def test_net_consumption(self, tracker):
        r = tracker.record_day(20.0, 5.0, 0.30)
        assert r.net_consumption_kwh == 15.0

    def test_net_never_negative(self, tracker):
        r = tracker.record_day(5.0, 20.0, 0.30)
        assert r.net_consumption_kwh == 0.0

    def test_cost_calculation(self, tracker):
        r = tracker.record_day(20.0, 5.0, 0.30)
        assert r.total_cost_eur == pytest.approx(4.50, abs=0.01)

    def test_solar_savings(self, tracker):
        r = tracker.record_day(20.0, 5.0, 0.30)
        assert r.savings_from_solar_eur == pytest.approx(1.50, abs=0.01)

    def test_full_solar_coverage(self, tracker):
        r = tracker.record_day(5.0, 20.0, 0.30)
        assert r.total_cost_eur == 0.0
        assert r.savings_from_solar_eur == pytest.approx(1.50, abs=0.01)

    def test_custom_date(self, tracker):
        d = date(2026, 1, 15)
        r = tracker.record_day(10.0, 3.0, 0.25, record_date=d)
        assert r.date == "2026-01-15"

    def test_replaces_existing_date(self, tracker):
        d = date(2026, 1, 15)
        tracker.record_day(10.0, 3.0, 0.25, record_date=d)
        tracker.record_day(20.0, 5.0, 0.30, record_date=d)
        history = tracker.get_daily_history(days=365)
        dates = [h["date"] for h in history]
        assert dates.count("2026-01-15") == 1


# ═══════════════════════════════════════════════════════════════════════════
# Daily History
# ═══════════════════════════════════════════════════════════════════════════


class TestDailyHistory:
    def test_empty_history(self, tracker):
        history = tracker.get_daily_history()
        assert history == []

    def test_returns_records(self, tracker_with_data):
        history = tracker_with_data.get_daily_history()
        assert len(history) > 0

    def test_limit_days(self, tracker_with_data):
        history = tracker_with_data.get_daily_history(days=5)
        assert len(history) <= 5

    def test_most_recent_first(self, tracker_with_data):
        history = tracker_with_data.get_daily_history()
        dates = [h["date"] for h in history]
        assert dates == sorted(dates, reverse=True)

    def test_has_required_fields(self, tracker_with_data):
        history = tracker_with_data.get_daily_history(days=1)
        h = history[0]
        assert "date" in h
        assert "consumption_kwh" in h
        assert "cost_eur" in h
        assert "savings_eur" in h


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════


class TestSummary:
    def test_weekly_summary(self, tracker_with_data):
        s = tracker_with_data.get_summary("weekly")
        assert s.period == "weekly"
        assert s.days_count <= 7

    def test_monthly_summary(self, tracker_with_data):
        s = tracker_with_data.get_summary("monthly")
        assert s.period == "monthly"

    def test_daily_summary(self, tracker_with_data):
        s = tracker_with_data.get_summary("daily")
        assert s.period == "daily"

    def test_total_cost_positive(self, tracker_with_data):
        s = tracker_with_data.get_summary("weekly")
        assert s.total_cost_eur > 0

    def test_avg_daily_cost(self, tracker_with_data):
        s = tracker_with_data.get_summary("weekly")
        assert s.avg_daily_cost_eur > 0

    def test_empty_tracker(self, tracker):
        s = tracker.get_summary("weekly")
        assert s.total_cost_eur == 0


# ═══════════════════════════════════════════════════════════════════════════
# Budget
# ═══════════════════════════════════════════════════════════════════════════


class TestBudget:
    def test_budget_status(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert isinstance(b, BudgetStatus)
        assert b.budget_eur == 100.0

    def test_spent_positive(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert b.spent_eur >= 0

    def test_percent_used(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert 0 <= b.percent_used <= 200  # Could exceed

    def test_projected_total(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert b.projected_total_eur > 0

    def test_on_track_boolean(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert isinstance(b.on_track, bool)

    def test_month_format(self, tracker_with_data):
        b = tracker_with_data.get_budget_status()
        assert len(b.month) == 7  # YYYY-MM


# ═══════════════════════════════════════════════════════════════════════════
# Period Comparison
# ═══════════════════════════════════════════════════════════════════════════


class TestComparison:
    def test_comparison_structure(self, tracker_with_data):
        c = tracker_with_data.compare_periods(7, 7)
        assert "current_period" in c
        assert "previous_period" in c
        assert "difference_eur" in c
        assert "trend" in c

    def test_trend_values(self, tracker_with_data):
        c = tracker_with_data.compare_periods(7, 7)
        assert c["trend"] in ("up", "down", "stable")

    def test_change_percent(self, tracker_with_data):
        c = tracker_with_data.compare_periods(7, 7)
        assert isinstance(c["change_percent"], float)

    def test_empty_comparison(self, tracker):
        c = tracker.compare_periods(7, 7)
        assert c["current_period"]["cost_eur"] == 0
        assert c["trend"] == "stable"


# ═══════════════════════════════════════════════════════════════════════════
# Rolling Average
# ═══════════════════════════════════════════════════════════════════════════


class TestRollingAverage:
    def test_7_day_average(self, tracker_with_data):
        avg = tracker_with_data.get_rolling_average(7)
        assert avg > 0

    def test_30_day_average(self, tracker_with_data):
        avg = tracker_with_data.get_rolling_average(30)
        assert avg > 0

    def test_empty_returns_zero(self, tracker):
        avg = tracker.get_rolling_average(7)
        assert avg == 0.0
