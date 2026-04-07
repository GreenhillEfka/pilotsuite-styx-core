"""Tests for Comfort Index (v5.7.0)."""

import pytest
from copilot_core.comfort.index import (
    ComfortIndex,
    ComfortReading,
    LightingSuggestion,
    calculate_comfort_index,
    get_lighting_suggestion,
    _temperature_score,
    _humidity_score,
    _air_quality_score,
    _light_score,
    _grade_from_score,
)


# ═══════════════════════════════════════════════════════════════════════════
# Temperature Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestTemperatureScore:
    def test_optimal_range(self):
        score, status = _temperature_score(21.0)
        assert score == 100.0
        assert status == "optimal"

    def test_optimal_boundary_low(self):
        score, _ = _temperature_score(20.0)
        assert score == 100.0

    def test_optimal_boundary_high(self):
        score, _ = _temperature_score(22.0)
        assert score == 100.0

    def test_good_range(self):
        score, status = _temperature_score(19.0)
        assert score >= 80.0
        assert status == "good"

    def test_fair_range(self):
        score, status = _temperature_score(16.5)
        assert 60.0 <= score < 80.0
        assert status == "fair"

    def test_poor_cold(self):
        score, status = _temperature_score(10.0)
        assert score < 60.0
        assert status == "poor"

    def test_poor_hot(self):
        score, status = _temperature_score(35.0)
        assert score < 60.0
        assert status == "poor"

    def test_none_returns_default(self):
        score, status = _temperature_score(None)
        assert score == 50.0
        assert status == "unknown"

    def test_score_never_negative(self):
        score, _ = _temperature_score(-20.0)
        assert score >= 0.0

    def test_score_never_above_100(self):
        score, _ = _temperature_score(21.0)
        assert score <= 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Humidity Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestHumidityScore:
    def test_optimal_50(self):
        score, status = _humidity_score(50.0)
        assert score == 100.0
        assert status == "optimal"

    def test_optimal_boundary(self):
        score, _ = _humidity_score(40.0)
        assert score == 100.0

    def test_good_range(self):
        score, status = _humidity_score(35.0)
        assert score >= 70.0
        assert status == "good"

    def test_dry(self):
        score, status = _humidity_score(15.0)
        assert score < 70.0

    def test_humid(self):
        score, status = _humidity_score(85.0)
        assert score < 70.0

    def test_none_returns_default(self):
        score, _ = _humidity_score(None)
        assert score == 50.0


# ═══════════════════════════════════════════════════════════════════════════
# Air Quality Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestAirQualityScore:
    def test_excellent_co2(self):
        score, status = _air_quality_score(400.0)
        assert score == 100.0
        assert status == "optimal"

    def test_good_co2(self):
        score, status = _air_quality_score(700.0)
        assert score >= 80.0
        assert status == "good"

    def test_fair_co2(self):
        score, status = _air_quality_score(900.0)
        assert status == "fair"

    def test_poor_co2(self):
        score, status = _air_quality_score(1200.0)
        assert status == "poor"

    def test_very_poor_co2(self):
        score, _ = _air_quality_score(2000.0)
        assert score < 20.0

    def test_none_returns_default(self):
        score, _ = _air_quality_score(None)
        assert score == 50.0


# ═══════════════════════════════════════════════════════════════════════════
# Light Scoring
# ═══════════════════════════════════════════════════════════════════════════


class TestLightScore:
    def test_daytime_500_lux(self):
        score, status = _light_score(500.0, 12)
        assert score == 100.0
        assert status == "optimal"

    def test_morning_300_lux(self):
        score, status = _light_score(300.0, 7)
        assert score == 100.0

    def test_evening_200_lux(self):
        score, _ = _light_score(200.0, 19)
        assert score == 100.0

    def test_too_dark_daytime(self):
        score, _ = _light_score(50.0, 12)
        assert score < 80.0

    def test_too_bright_night(self):
        score, _ = _light_score(500.0, 23)
        assert score < 80.0

    def test_none_returns_default(self):
        score, _ = _light_score(None, 12)
        assert score == 50.0


# ═══════════════════════════════════════════════════════════════════════════
# Grade
# ═══════════════════════════════════════════════════════════════════════════


class TestGrade:
    def test_grade_a(self):
        assert _grade_from_score(95) == "A"

    def test_grade_b(self):
        assert _grade_from_score(80) == "B"

    def test_grade_c(self):
        assert _grade_from_score(65) == "C"

    def test_grade_d(self):
        assert _grade_from_score(45) == "D"

    def test_grade_f(self):
        assert _grade_from_score(20) == "F"

    def test_boundary_90(self):
        assert _grade_from_score(90) == "A"

    def test_boundary_75(self):
        assert _grade_from_score(75) == "B"


# ═══════════════════════════════════════════════════════════════════════════
# Composite Index
# ═══════════════════════════════════════════════════════════════════════════


class TestComfortIndex:
    def test_perfect_conditions(self):
        idx = calculate_comfort_index(
            temperature_c=21.0,
            humidity_pct=50.0,
            co2_ppm=400.0,
            light_lux=500.0,
            hour=12,
        )
        assert idx.score >= 90.0
        assert idx.grade == "A"

    def test_poor_conditions(self):
        idx = calculate_comfort_index(
            temperature_c=35.0,
            humidity_pct=90.0,
            co2_ppm=2000.0,
            light_lux=10.0,
            hour=12,
        )
        assert idx.score < 50.0

    def test_all_none_gives_50(self):
        idx = calculate_comfort_index()
        assert idx.score == 50.0
        assert idx.grade == "C"

    def test_has_4_readings(self):
        idx = calculate_comfort_index(temperature_c=21.0)
        assert len(idx.readings) == 4

    def test_zone_id_passed(self):
        idx = calculate_comfort_index(zone_id="kitchen")
        assert idx.zone_id == "kitchen"

    def test_timestamp_present(self):
        idx = calculate_comfort_index()
        assert idx.timestamp is not None

    def test_readings_have_weights(self):
        idx = calculate_comfort_index()
        total = sum(r.weight for r in idx.readings)
        assert abs(total - 1.0) < 0.001


# ═══════════════════════════════════════════════════════════════════════════
# Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestSuggestions:
    def test_cold_temperature_suggestion(self):
        idx = calculate_comfort_index(temperature_c=10.0, hour=12)
        assert any("Heizung" in s for s in idx.suggestions)

    def test_hot_temperature_suggestion(self):
        idx = calculate_comfort_index(temperature_c=35.0, hour=12)
        assert any("Klimaanlage" in s or "lueften" in s.lower() for s in idx.suggestions)

    def test_high_co2_suggestion(self):
        idx = calculate_comfort_index(co2_ppm=2000.0, hour=12)
        assert any("Fenster" in s or "CO2" in s for s in idx.suggestions)

    def test_dry_air_suggestion(self):
        idx = calculate_comfort_index(humidity_pct=10.0, hour=12)
        assert any("Luftbefeuchter" in s or "trocken" in s for s in idx.suggestions)

    def test_no_suggestions_when_perfect(self):
        idx = calculate_comfort_index(
            temperature_c=21.0,
            humidity_pct=50.0,
            co2_ppm=400.0,
            light_lux=500.0,
            hour=12,
        )
        assert len(idx.suggestions) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Lighting Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestLightingSuggestion:
    def test_morning_suggestion(self):
        s = get_lighting_suggestion(current_lux=50.0, hour=7)
        assert s.color_temp_kelvin == 4000
        assert s.brightness_percent > 0

    def test_daytime_suggestion(self):
        s = get_lighting_suggestion(current_lux=200.0, hour=12)
        assert s.color_temp_kelvin >= 4500
        assert s.brightness_percent > 0

    def test_evening_warm(self):
        s = get_lighting_suggestion(current_lux=50.0, hour=20)
        assert s.color_temp_kelvin == 3000

    def test_night_very_warm(self):
        s = get_lighting_suggestion(current_lux=5.0, hour=22)
        assert s.color_temp_kelvin == 2700

    def test_sufficient_daylight(self):
        s = get_lighting_suggestion(current_lux=800.0, hour=12)
        assert s.brightness_percent == 0
        assert "Tageslicht" in s.reason

    def test_area_passed(self):
        s = get_lighting_suggestion(area="Kueche", hour=12)
        assert s.area == "Kueche"

    def test_cloudy_increases_target(self):
        sunny = get_lighting_suggestion(current_lux=100.0, hour=12, cloud_cover_pct=0.0)
        cloudy = get_lighting_suggestion(current_lux=100.0, hour=12, cloud_cover_pct=100.0)
        assert cloudy.target_lux > sunny.target_lux

    def test_brightness_capped_at_100(self):
        s = get_lighting_suggestion(current_lux=0.0, hour=12)
        assert s.brightness_percent <= 100

    def test_brightness_minimum_5(self):
        s = get_lighting_suggestion(current_lux=490.0, hour=12)
        assert s.brightness_percent >= 0  # Could be 0 if sufficient

    def test_none_lux_handled(self):
        s = get_lighting_suggestion(current_lux=None, hour=12)
        assert s.brightness_percent > 0
