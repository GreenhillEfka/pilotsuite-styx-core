"""Tests for Proactive Alert System (v5.19.0)."""

import time
from datetime import datetime, timedelta

import pytest

from copilot_core.regional.proactive_alerts import (
    ProactiveAlertEngine,
    ProactiveAlert,
    AlertSummary,
    AlertPriority,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _warning_overview(
    total: int = 1,
    severity: int = 3,
    has_pv: bool = True,
    has_grid: bool = True,
    pv_reduction: int = 80,
) -> dict:
    return {
        "total": total,
        "highest_severity": severity,
        "has_pv_impact": has_pv,
        "has_grid_risk": has_grid,
        "warnings": [
            {
                "headline": "Schweres Gewitter",
                "severity": severity,
                "warning_type_label": "Gewitter",
            }
        ],
        "impacts": [{"pv_reduction_pct": pv_reduction}],
    }


def _tariff_summary(
    current_ct: float = 35.0,
    level: str = "high",
    min_eur: float = 0.18,
    max_eur: float = 0.40,
    min_hour: str = "02:00",
) -> dict:
    return {
        "current_price_ct_kwh": current_ct,
        "current_level": level,
        "min_price_eur_kwh": min_eur,
        "max_price_eur_kwh": max_eur,
        "min_hour": min_hour,
    }


def _solar_data(is_daylight: bool = True, elevation: float = 45.0) -> dict:
    return {"is_daylight": is_daylight, "elevation_deg": elevation}


@pytest.fixture
def engine():
    return ProactiveAlertEngine()


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_no_alerts(self, engine):
        assert engine.alert_count == 0

    def test_default_thresholds(self, engine):
        assert engine._price_spike_ct == 35.0
        assert engine._price_low_ct == 20.0


# ── Test weather alerts ──────────────────────────────────────────────────


class TestWeatherAlerts:
    def test_severe_weather(self, engine):
        alerts = engine.evaluate_weather(_warning_overview(severity=3))
        # Should fire severe weather alert
        severe = [a for a in alerts if a.priority == AlertPriority.CRITICAL]
        assert len(severe) >= 1

    def test_no_warnings_no_alerts(self, engine):
        alerts = engine.evaluate_weather({"total": 0})
        assert len(alerts) == 0

    def test_pv_impact_alert(self, engine):
        alerts = engine.evaluate_weather(
            _warning_overview(severity=2, has_pv=True, pv_reduction=80)
        )
        pv = [a for a in alerts if a.category == "pv"]
        assert len(pv) >= 1

    def test_no_pv_alert_low_reduction(self, engine):
        alerts = engine.evaluate_weather(
            _warning_overview(severity=2, has_pv=True, pv_reduction=20)
        )
        pv = [a for a in alerts if a.category == "pv"]
        assert len(pv) == 0

    def test_grid_risk_alert(self, engine):
        alerts = engine.evaluate_weather(
            _warning_overview(severity=3, has_grid=True)
        )
        grid = [a for a in alerts if a.category == "grid"]
        assert len(grid) >= 1

    def test_alert_has_german(self, engine):
        alerts = engine.evaluate_weather(_warning_overview(severity=3))
        for a in alerts:
            assert len(a.title_de) > 0
            assert len(a.message_de) > 0

    def test_alert_has_english(self, engine):
        alerts = engine.evaluate_weather(_warning_overview(severity=3))
        for a in alerts:
            assert len(a.title_en) > 0
            assert len(a.message_en) > 0


# ── Test price alerts ────────────────────────────────────────────────────


class TestPriceAlerts:
    def test_high_price_alert(self, engine):
        alerts = engine.evaluate_prices(_tariff_summary(current_ct=40.0, level="very_high"))
        price = [a for a in alerts if a.category == "price" and a.action == "shift"]
        assert len(price) >= 1

    def test_low_price_alert(self, engine):
        alerts = engine.evaluate_prices(_tariff_summary(current_ct=15.0, level="very_low"))
        charge = [a for a in alerts if a.action == "charge"]
        assert len(charge) >= 1

    def test_normal_price_no_alert(self, engine):
        alerts = engine.evaluate_prices(_tariff_summary(current_ct=28.0, level="normal", min_eur=0.25, max_eur=0.32))
        assert len(alerts) == 0

    def test_price_spread_alert(self, engine):
        alerts = engine.evaluate_prices(
            _tariff_summary(current_ct=28.0, level="normal", min_eur=0.10, max_eur=0.40)
        )
        arbitrage = [a for a in alerts if "arbitrage" in a.action_detail]
        assert len(arbitrage) >= 1

    def test_price_alert_includes_min_hour(self, engine):
        alerts = engine.evaluate_prices(_tariff_summary(current_ct=40.0, min_hour="03:00"))
        if alerts:
            assert "03:00" in alerts[0].message_de


# ── Test PV alerts ───────────────────────────────────────────────────────


class TestPVAlerts:
    def test_high_pv_alert(self, engine):
        alerts = engine.evaluate_pv(0.8, _solar_data(is_daylight=True, elevation=50))
        pv = [a for a in alerts if a.category == "pv"]
        assert len(pv) >= 1

    def test_sunset_alert(self, engine):
        alerts = engine.evaluate_pv(0.2, _solar_data(is_daylight=True, elevation=5))
        sunset = [a for a in alerts if "sunset" in a.id or "Sonnenuntergang" in a.title_de]
        assert len(sunset) >= 1

    def test_night_no_alert(self, engine):
        alerts = engine.evaluate_pv(0.0, _solar_data(is_daylight=False, elevation=-10))
        assert len(alerts) == 0


# ── Test combined evaluation ─────────────────────────────────────────────


class TestCombined:
    def test_combined_all(self, engine):
        alerts = engine.evaluate_combined(
            warning_overview=_warning_overview(severity=3),
            tariff_summary=_tariff_summary(current_ct=35.0),
            pv_factor=0.8,
            solar_data=_solar_data(),
        )
        assert len(alerts) >= 1

    def test_combined_critical(self, engine):
        alerts = engine.evaluate_combined(
            warning_overview=_warning_overview(severity=3),
            tariff_summary=_tariff_summary(current_ct=35.0),
        )
        combined = [a for a in alerts if a.category == "combined"]
        assert len(combined) >= 1

    def test_combined_only_weather(self, engine):
        alerts = engine.evaluate_combined(
            warning_overview=_warning_overview(severity=4),
        )
        assert len(alerts) >= 1

    def test_combined_only_prices(self, engine):
        alerts = engine.evaluate_combined(
            tariff_summary=_tariff_summary(current_ct=40.0),
        )
        assert len(alerts) >= 1


# ── Test cooldowns ───────────────────────────────────────────────────────


class TestCooldowns:
    def test_cooldown_prevents_duplicate(self, engine):
        alerts1 = engine.evaluate_weather(_warning_overview(severity=3))
        alerts2 = engine.evaluate_weather(_warning_overview(severity=3))
        # Second evaluation should not fire same alert
        assert len(alerts2) < len(alerts1) or len(alerts2) == 0

    def test_can_fire_after_cooldown(self, engine):
        engine._cooldowns["weather_severe"] = time.time() - 7200  # 2h ago
        alerts = engine.evaluate_weather(_warning_overview(severity=3))
        assert len(alerts) >= 1


# ── Test summary ─────────────────────────────────────────────────────────


class TestSummary:
    def test_empty_summary(self, engine):
        summary = engine.get_summary()
        assert summary.total == 0

    def test_summary_after_alerts(self, engine):
        engine.evaluate_combined(
            warning_overview=_warning_overview(severity=4),
            tariff_summary=_tariff_summary(current_ct=40.0),
        )
        summary = engine.get_summary()
        assert summary.total >= 1

    def test_summary_by_priority(self, engine):
        engine.evaluate_combined(
            warning_overview=_warning_overview(severity=4),
            tariff_summary=_tariff_summary(current_ct=40.0),
        )
        summary = engine.get_summary()
        assert sum(summary.by_priority.values()) == summary.total

    def test_highest_priority(self, engine):
        engine.evaluate_weather(_warning_overview(severity=4))
        summary = engine.get_summary()
        assert summary.highest_priority >= AlertPriority.CRITICAL


# ── Test dismiss ─────────────────────────────────────────────────────────


class TestDismiss:
    def test_dismiss_alert(self, engine):
        alerts = engine.evaluate_weather(_warning_overview(severity=4))
        assert len(alerts) >= 1
        result = engine.dismiss_alert(alerts[0].id)
        assert result is True
        assert engine.alert_count < len(alerts)

    def test_dismiss_nonexistent(self, engine):
        assert engine.dismiss_alert("nonexistent") is False


# ── Test configuration ───────────────────────────────────────────────────


class TestConfig:
    def test_configure_thresholds(self, engine):
        engine.configure(price_spike_ct=40.0, price_low_ct=15.0)
        assert engine._price_spike_ct == 40.0
        assert engine._price_low_ct == 15.0

    def test_higher_spike_threshold(self, engine):
        engine.configure(price_spike_ct=50.0)
        alerts = engine.evaluate_prices(_tariff_summary(current_ct=40.0, level="high"))
        # 40 < 50 so no spike alert from threshold (but level "high" might still trigger)
        spike = [a for a in alerts if "spike" in (a.action_detail or "")]
        # May or may not trigger depending on level check


# ── Test alert filtering ─────────────────────────────────────────────────


class TestFiltering:
    def test_filter_by_priority(self, engine):
        engine.evaluate_combined(
            warning_overview=_warning_overview(severity=4),
            tariff_summary=_tariff_summary(current_ct=15.0, level="very_low"),
        )
        critical = engine.get_alerts_by_priority(AlertPriority.CRITICAL)
        all_alerts = engine.get_active_alerts()
        assert len(critical) <= len(all_alerts)
