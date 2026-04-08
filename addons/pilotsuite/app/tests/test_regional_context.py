"""Tests for Regional Context Provider (v5.15.0)."""

import pytest
from datetime import datetime, date
from copilot_core.regional.context_provider import (
    RegionalContextProvider,
    RegionalContext,
    Location,
    SolarPosition,
    RegionalDefaults,
    calculate_solar_position,
    detect_country,
    detect_region,
)


@pytest.fixture
def berlin():
    return RegionalContextProvider(52.52, 13.405, 34.0, "Europe/Berlin")


@pytest.fixture
def vienna():
    return RegionalContextProvider(48.2082, 16.3738, 171.0, "Europe/Vienna")


@pytest.fixture
def zurich():
    return RegionalContextProvider(47.3769, 8.5417, 408.0, "Europe/Zurich")


@pytest.fixture
def munich():
    return RegionalContextProvider(48.1351, 11.582, 519.0, "Europe/Berlin")


# ═══════════════════════════════════════════════════════════════════════════
# Country Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestCountryDetection:
    def test_berlin_is_de(self):
        assert detect_country(52.52, 13.405) == "DE"

    def test_vienna_is_at(self):
        assert detect_country(48.2082, 16.3738) == "AT"

    def test_zurich_is_ch(self):
        assert detect_country(47.3769, 8.5417) == "CH"

    def test_munich_is_de(self):
        assert detect_country(48.1351, 11.582) == "DE"

    def test_hamburg_is_de(self):
        assert detect_country(53.5511, 9.9937) == "DE"

    def test_unknown_defaults_de(self):
        assert detect_country(0, 0) == "DE"


class TestRegionDetection:
    def test_berlin_region(self):
        r = detect_region(52.52, 13.405, "DE")
        assert "Brandenburg" in r or "Berlin" in r

    def test_munich_region(self):
        r = detect_region(48.1351, 11.582, "DE")
        assert "Bayern" in r

    def test_vienna_region(self):
        r = detect_region(48.2082, 16.3738, "AT")
        assert "Wien" in r

    def test_zurich_region(self):
        r = detect_region(47.3769, 8.5417, "CH")
        assert "Mittelland" in r or "Ostschweiz" in r


# ═══════════════════════════════════════════════════════════════════════════
# Location
# ═══════════════════════════════════════════════════════════════════════════


class TestLocation:
    def test_location_fields(self, berlin):
        loc = berlin.location
        assert isinstance(loc, Location)
        assert loc.latitude == 52.52
        assert loc.longitude == 13.405
        assert loc.country_code == "DE"

    def test_vienna_country(self, vienna):
        assert vienna.location.country_code == "AT"

    def test_zurich_country(self, zurich):
        assert zurich.location.country_code == "CH"


# ═══════════════════════════════════════════════════════════════════════════
# Solar Position
# ═══════════════════════════════════════════════════════════════════════════


class TestSolarPosition:
    def test_returns_solar_position(self, berlin):
        s = berlin.get_solar_position()
        assert isinstance(s, SolarPosition)

    def test_sunrise_before_sunset(self, berlin):
        s = berlin.get_solar_position()
        assert s.sunrise < s.sunset

    def test_day_length_positive(self, berlin):
        s = berlin.get_solar_position()
        assert s.day_length_hours > 0

    def test_solar_noon_midday(self, berlin):
        s = berlin.get_solar_position()
        noon_h = int(s.solar_noon.split(":")[0])
        assert 11 <= noon_h <= 14

    def test_summer_longer_days(self):
        provider = RegionalContextProvider(52.52, 13.405)
        summer = provider.get_solar_position(datetime(2026, 6, 21, 12, 0))
        winter = provider.get_solar_position(datetime(2026, 12, 21, 12, 0))
        assert summer.day_length_hours > winter.day_length_hours

    def test_elevation_noon_positive(self, berlin):
        s = berlin.get_solar_position(datetime(2026, 6, 15, 12, 0))
        assert s.elevation_deg > 0

    def test_elevation_midnight_low(self, berlin):
        s = berlin.get_solar_position(datetime(2026, 6, 15, 0, 0))
        assert s.elevation_deg < 10

    def test_azimuth_range(self, berlin):
        s = berlin.get_solar_position(datetime(2026, 6, 15, 12, 0))
        assert 0 <= s.azimuth_deg <= 360


class TestCalculateSolar:
    def test_basic_calculation(self):
        s = calculate_solar_position(52.52, 13.405)
        assert s.sunrise != ""
        assert s.sunset != ""

    def test_tropical_long_days(self):
        s = calculate_solar_position(0.0, 0.0, datetime(2026, 3, 21, 12, 0), 0)
        assert abs(s.day_length_hours - 12.0) < 1.0

    def test_high_latitude(self):
        s = calculate_solar_position(65.0, 25.0, datetime(2026, 6, 21, 12, 0), 2)
        assert s.day_length_hours > 18


# ═══════════════════════════════════════════════════════════════════════════
# Regional Defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestDefaults:
    def test_de_defaults(self, berlin):
        d = berlin.defaults
        assert isinstance(d, RegionalDefaults)
        assert d.price_api == "awattar_de"
        assert d.weather_service == "dwd"
        assert d.language == "de"
        assert d.currency == "EUR"

    def test_at_defaults(self, vienna):
        d = vienna.defaults
        assert d.price_api == "awattar_at"
        assert d.weather_service == "zamg"

    def test_ch_defaults(self, zurich):
        d = zurich.defaults
        assert d.price_api == "epex_ch"
        assert d.weather_service == "meteoschweiz"
        assert d.currency == "CHF"

    def test_grid_price_positive(self, berlin):
        assert berlin.defaults.grid_price_eur_kwh > 0

    def test_pv_optimal_tilt(self, berlin):
        assert 25 <= berlin.defaults.pv_optimal_tilt_deg <= 45

    def test_news_sources(self, berlin):
        assert len(berlin.defaults.news_sources) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Complete Context
# ═══════════════════════════════════════════════════════════════════════════


class TestContext:
    def test_returns_context(self, berlin):
        ctx = berlin.get_context()
        assert isinstance(ctx, RegionalContext)

    def test_context_has_location(self, berlin):
        ctx = berlin.get_context()
        assert "latitude" in ctx.location
        assert "country_code" in ctx.location

    def test_context_has_solar(self, berlin):
        ctx = berlin.get_context()
        assert "sunrise" in ctx.solar
        assert "sunset" in ctx.solar

    def test_context_has_defaults(self, berlin):
        ctx = berlin.get_context()
        assert "grid_price_eur_kwh" in ctx.defaults

    def test_generated_at(self, berlin):
        ctx = berlin.get_context()
        assert "T" in ctx.generated_at


# ═══════════════════════════════════════════════════════════════════════════
# PV Factor
# ═══════════════════════════════════════════════════════════════════════════


class TestPVFactor:
    def test_night_zero(self, berlin):
        f = berlin.get_pv_factor(datetime(2026, 6, 15, 2, 0))
        assert f == 0.0

    def test_noon_positive(self, berlin):
        f = berlin.get_pv_factor(datetime(2026, 6, 15, 12, 0))
        assert f > 0.5

    def test_bounded_0_1(self, berlin):
        f = berlin.get_pv_factor(datetime(2026, 6, 15, 12, 0))
        assert 0 <= f <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Day Info
# ═══════════════════════════════════════════════════════════════════════════


class TestDayInfo:
    def test_day_info_fields(self, berlin):
        info = berlin.get_day_info()
        assert "date" in info
        assert "sunrise" in info
        assert "sunset" in info
        assert "country" in info
        assert "grid_price_eur_kwh" in info
        assert "weather_service" in info

    def test_specific_date(self, berlin):
        info = berlin.get_day_info(date(2026, 6, 21))
        assert info["date"] == "2026-06-21"


# ═══════════════════════════════════════════════════════════════════════════
# Update Location
# ═══════════════════════════════════════════════════════════════════════════


class TestUpdateLocation:
    def test_update_changes_country(self):
        p = RegionalContextProvider(52.52, 13.405)
        assert p.location.country_code == "DE"
        p.update_location(48.2082, 16.3738)
        assert p.location.country_code == "AT"

    def test_update_changes_region(self):
        p = RegionalContextProvider(52.52, 13.405)
        p.update_location(48.1351, 11.582)
        assert "Bayern" in p.location.region

    def test_update_changes_defaults(self):
        p = RegionalContextProvider(52.52, 13.405)
        assert p.defaults.price_api == "awattar_de"
        p.update_location(48.2082, 16.3738)
        assert p.defaults.price_api == "awattar_at"
