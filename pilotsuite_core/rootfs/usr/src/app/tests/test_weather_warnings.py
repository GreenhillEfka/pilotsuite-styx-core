"""Tests for DWD/ZAMG/MeteoSchweiz Weather Warnings Manager (v5.16.0)."""

import time
from datetime import datetime, timedelta

import pytest

from copilot_core.regional.weather_warnings import (
    WeatherWarningManager,
    WeatherWarning,
    WarningImpact,
    WarningSeverity,
    WarningType,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_dwd_warning(
    event: str = "GEWITTER",
    level: int = 2,
    headline: str = "Starkes Gewitter",
    start_offset_h: float = -1,
    end_offset_h: float = 2,
    region: str = "Brandenburg",
) -> dict:
    """Create a DWD-format warning dict."""
    now = datetime.now()
    return {
        "event": event,
        "level": level,
        "headline": headline,
        "description": f"Es wird {event.lower()} erwartet.",
        "instruction": "Fenster schließen.",
        "regionName": region,
        "start": int((now + timedelta(hours=start_offset_h)).timestamp() * 1000),
        "end": int((now + timedelta(hours=end_offset_h)).timestamp() * 1000),
    }


def _make_generic_warning(
    severity: int = 2,
    warning_type: int = WarningType.THUNDERSTORM,
    headline: str = "Gewitter",
    start_offset_h: float = -1,
    end_offset_h: float = 2,
) -> dict:
    """Create a generic-format warning dict."""
    now = datetime.now()
    return {
        "severity": severity,
        "type": warning_type,
        "headline": headline,
        "description": "Test description",
        "instruction": "Test instruction",
        "region": "Berlin",
        "start": (now + timedelta(hours=start_offset_h)).isoformat(),
        "end": (now + timedelta(hours=end_offset_h)).isoformat(),
    }


@pytest.fixture
def manager():
    return WeatherWarningManager(country="DE", region="Brandenburg/Berlin")


@pytest.fixture
def manager_at():
    return WeatherWarningManager(country="AT", region="Wien")


# ── Test WeatherWarningManager init ───────────────────────────────────────


class TestManagerInit:
    def test_default_country(self, manager):
        assert manager._country == "DE"

    def test_source_de(self, manager):
        assert manager.source == "dwd"

    def test_source_at(self, manager_at):
        assert manager_at.source == "zamg"

    def test_source_ch(self):
        m = WeatherWarningManager(country="CH")
        assert m.source == "meteoschweiz"

    def test_no_warnings_initially(self, manager):
        assert manager.warning_count == 0

    def test_cache_not_valid_initially(self, manager):
        assert not manager.cache_valid


# ── Test DWD warning parsing ─────────────────────────────────────────────


class TestDWDParsing:
    def test_parse_single_warning(self, manager):
        raw = {"warnings": {"12345": [_make_dwd_warning()]}}
        warnings = manager.process_dwd_warnings(raw)
        assert len(warnings) == 1
        assert warnings[0].source == "dwd"

    def test_parse_event_type(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER")]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].warning_type == WarningType.THUNDERSTORM

    def test_parse_wind_event(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="STURMBÖEN", level=3)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].warning_type == WarningType.WIND
        assert warnings[0].severity == WarningSeverity.SEVERE

    def test_parse_snow_event(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="STARKER SCHNEEFALL")]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].warning_type == WarningType.SNOW

    def test_parse_ice_event(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GLATTEIS")]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].warning_type == WarningType.ICE

    def test_parse_multiple_cells(self, manager):
        raw = {
            "warnings": {
                "100": [_make_dwd_warning(event="GEWITTER")],
                "200": [_make_dwd_warning(event="WIND")],
            }
        }
        warnings = manager.process_dwd_warnings(raw)
        assert len(warnings) == 2

    def test_parse_list_format(self, manager):
        raw = {"warnings": [_make_dwd_warning(), _make_dwd_warning(event="FROST")]}
        warnings = manager.process_dwd_warnings(raw)
        assert len(warnings) == 2

    def test_parse_severity_levels(self, manager):
        for level, expected in [(1, 1), (2, 2), (3, 3), (4, 4)]:
            raw = {"warnings": {"1": [_make_dwd_warning(level=level)]}}
            warnings = manager.process_dwd_warnings(raw)
            assert warnings[0].severity == expected

    def test_severity_label(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(level=3)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].severity_label == "Unwetterwarnung"

    def test_extreme_label(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(level=4)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].severity_label == "Extreme Unwetterwarnung"

    def test_is_active(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(start_offset_h=-1, end_offset_h=2)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].is_active is True

    def test_expired_not_active(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(start_offset_h=-3, end_offset_h=-1)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].is_active is False

    def test_color_mapping(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(level=1)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].color == "#FFFF00"

    def test_red_color(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(level=3)]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].color == "#FF0000"

    def test_region_name_string(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(region="Berlin")]}}
        warnings = manager.process_dwd_warnings(raw)
        assert warnings[0].region == "Berlin"

    def test_region_name_list(self, manager):
        w = _make_dwd_warning()
        w["regionName"] = ["Berlin", "Brandenburg"]
        raw = {"warnings": {"1": [w]}}
        warnings = manager.process_dwd_warnings(raw)
        assert "Berlin" in warnings[0].region

    def test_empty_warnings(self, manager):
        raw = {"warnings": {}}
        warnings = manager.process_dwd_warnings(raw)
        assert len(warnings) == 0

    def test_cache_updated(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning()]}}
        manager.process_dwd_warnings(raw)
        assert manager.cache_valid is True


# ── Test generic warning parsing ─────────────────────────────────────────


class TestGenericParsing:
    def test_parse_single(self, manager):
        warnings = manager.process_generic_warnings([_make_generic_warning()])
        assert len(warnings) == 1

    def test_parse_zamg_source(self, manager_at):
        warnings = manager_at.process_generic_warnings(
            [_make_generic_warning()], source="zamg"
        )
        assert warnings[0].source == "zamg"

    def test_severity_clamped(self, manager):
        w = _make_generic_warning(severity=10)
        warnings = manager.process_generic_warnings([w])
        assert warnings[0].severity == 4

    def test_severity_min(self, manager):
        w = _make_generic_warning(severity=0)
        warnings = manager.process_generic_warnings([w])
        assert warnings[0].severity == 1


# ── Test impact assessment ───────────────────────────────────────────────


class TestImpactAssessment:
    def test_thunderstorm_high_pv(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER", level=3)]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert impact.pv_impact == "high"
        assert impact.pv_reduction_pct > 50

    def test_wind_moderate_pv(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="WIND", level=2)]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert impact.pv_impact in ("low", "moderate")

    def test_snow_high_pv(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="SCHNEEFALL", level=3)]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert impact.pv_reduction_pct >= 80

    def test_fog_moderate(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="NEBEL", level=1)]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert impact.pv_impact == "moderate"

    def test_thunderstorm_high_grid(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER", level=2)]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert impact.grid_risk == "high"

    def test_severity_scaling(self, manager):
        # Minor severity should reduce PV impact
        raw1 = {"warnings": {"1": [_make_dwd_warning(event="STARKREGEN", level=1)]}}
        w1 = manager.process_dwd_warnings(raw1)
        i1 = manager.assess_impact(w1[0])

        raw3 = {"warnings": {"1": [_make_dwd_warning(event="STARKREGEN", level=3)]}}
        w3 = manager.process_dwd_warnings(raw3)
        i3 = manager.assess_impact(w3[0])

        assert i3.pv_reduction_pct >= i1.pv_reduction_pct

    def test_recommendation_de(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER")]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert "Batterie" in impact.recommendation_de

    def test_recommendation_en(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER")]}}
        warnings = manager.process_dwd_warnings(raw)
        impact = manager.assess_impact(warnings[0])
        assert "battery" in impact.recommendation_en.lower()

    def test_uv_no_impact(self, manager):
        warnings = manager.process_generic_warnings([
            _make_generic_warning(warning_type=WarningType.UV)
        ])
        impact = manager.assess_impact(warnings[0])
        assert impact.pv_impact == "none"
        assert impact.pv_reduction_pct == 0


# ── Test filtering ───────────────────────────────────────────────────────


class TestFiltering:
    def test_active_only(self, manager):
        raw = {
            "warnings": {
                "1": [
                    _make_dwd_warning(start_offset_h=-1, end_offset_h=2),
                    _make_dwd_warning(start_offset_h=-5, end_offset_h=-3),
                ]
            }
        }
        manager.process_dwd_warnings(raw)
        active = manager.get_active_warnings()
        assert len(active) == 1

    def test_by_severity(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(level=1)],
                "2": [_make_dwd_warning(level=3)],
            }
        }
        manager.process_dwd_warnings(raw)
        severe = manager.get_warnings_by_severity(WarningSeverity.SEVERE)
        assert len(severe) == 1

    def test_pv_warnings(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(event="GEWITTER")],
                "2": [_make_dwd_warning(event="HOCHWASSER")],
            }
        }
        manager.process_dwd_warnings(raw)
        pv = manager.get_pv_warnings()
        assert len(pv) >= 1

    def test_grid_warnings(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(event="STURMBÖEN", level=3)],
            }
        }
        manager.process_dwd_warnings(raw)
        grid = manager.get_grid_warnings()
        assert len(grid) == 1


# ── Test overview ────────────────────────────────────────────────────────


class TestOverview:
    def test_overview_counts(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(level=1)],
                "2": [_make_dwd_warning(level=3)],
            }
        }
        manager.process_dwd_warnings(raw)
        overview = manager.get_overview()
        assert overview.total == 2

    def test_highest_severity(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(level=1)],
                "2": [_make_dwd_warning(level=4)],
            }
        }
        manager.process_dwd_warnings(raw)
        overview = manager.get_overview()
        assert overview.highest_severity == 4

    def test_by_severity_breakdown(self, manager):
        raw = {
            "warnings": {
                "1": [_make_dwd_warning(level=2)],
                "2": [_make_dwd_warning(level=2)],
                "3": [_make_dwd_warning(level=3)],
            }
        }
        manager.process_dwd_warnings(raw)
        overview = manager.get_overview()
        assert overview.by_severity["moderate"] == 2
        assert overview.by_severity["severe"] == 1

    def test_has_pv_impact(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning(event="GEWITTER")]}}
        manager.process_dwd_warnings(raw)
        overview = manager.get_overview()
        assert overview.has_pv_impact is True

    def test_no_warnings_overview(self, manager):
        overview = manager.get_overview()
        assert overview.total == 0
        assert overview.highest_severity == 0


# ── Test summary text ────────────────────────────────────────────────────


class TestSummaryText:
    def test_no_warnings_de(self, manager):
        text = manager.get_summary_text("de")
        assert "Keine" in text

    def test_no_warnings_en(self, manager):
        text = manager.get_summary_text("en")
        assert "No active" in text

    def test_with_warnings_de(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning()]}}
        manager.process_dwd_warnings(raw)
        text = manager.get_summary_text("de")
        assert "aktive" in text
        assert "PV" in text

    def test_with_warnings_en(self, manager):
        raw = {"warnings": {"1": [_make_dwd_warning()]}}
        manager.process_dwd_warnings(raw)
        text = manager.get_summary_text("en")
        assert "active" in text


# ── Test update region ───────────────────────────────────────────────────


class TestUpdateRegion:
    def test_update(self, manager):
        manager.update_region("AT", "Wien")
        assert manager._country == "AT"
        assert manager._region == "Wien"
        assert manager.source == "zamg"


# ── Test warning count property ──────────────────────────────────────────


class TestWarningCount:
    def test_count_active(self, manager):
        raw = {
            "warnings": {
                "1": [
                    _make_dwd_warning(start_offset_h=-1, end_offset_h=2),
                    _make_dwd_warning(start_offset_h=-5, end_offset_h=-3),
                ]
            }
        }
        manager.process_dwd_warnings(raw)
        assert manager.warning_count == 1
