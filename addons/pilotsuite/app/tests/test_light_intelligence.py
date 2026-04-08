"""Tests for Light Intelligence Engine (v6.5.0)."""

import pytest

from copilot_core.hub.light_intelligence import (
    LightDashboard,
    LightIntelligenceEngine,
    MoodScene,
    SunPosition,
    ZoneBrightness,
    _CLOUD_HYSTERESIS_PCT,
    _MOOD_SCENES,
)


@pytest.fixture
def engine():
    return LightIntelligenceEngine(latitude=50.0, longitude=10.0)


@pytest.fixture
def configured_engine():
    e = LightIntelligenceEngine()
    e.register_sensor("sensor.outdoor_lux", zone_id="garten", location="outdoor")
    e.register_sensor("sensor.wohnzimmer_lux", zone_id="wohnbereich", location="indoor")
    e.register_sensor("sensor.kueche_lux", zone_id="kueche", location="indoor")
    e.configure_zone("wohnbereich", name="Wohnbereich", target_lux=300, min_lux=100)
    e.configure_zone("kueche", name="Küche", target_lux=400, min_lux=150)
    return e


class TestSunPosition:
    def test_update_sun(self, engine):
        sun = engine.update_sun(elevation=45.0, azimuth=180.0)
        assert sun.elevation == 45.0
        assert sun.azimuth == 180.0
        assert sun.phase == "day"

    def test_sun_phases(self, engine):
        # Day
        engine.update_sun(30, 180)
        assert engine.get_sun().phase == "day"

        # Sunrise
        engine.update_sun(3, 90)
        assert engine.get_sun().phase == "sunrise"

        # Dawn/civil twilight
        engine.update_sun(-3, 80)
        assert engine.get_sun().phase == "dawn"

        # Dusk/nautical twilight
        engine.update_sun(-9, 270)
        assert engine.get_sun().phase == "dusk"

        # Night
        engine.update_sun(-15, 0)
        assert engine.get_sun().phase == "night"

    def test_solar_noon(self, engine):
        sun = engine.update_sun(elevation=50, azimuth=180)
        assert sun.solar_noon is True

    def test_not_solar_noon(self, engine):
        sun = engine.update_sun(elevation=50, azimuth=90)
        assert sun.solar_noon is False


class TestBrightnessTracking:
    def test_register_sensor(self, engine):
        engine.register_sensor("sensor.lux1", zone_id="z1", location="indoor")
        assert engine._sensor_zones["sensor.lux1"] == "z1"
        assert engine._sensor_locations["sensor.lux1"] == "indoor"

    def test_update_brightness(self, configured_engine):
        configured_engine.update_brightness("sensor.outdoor_lux", 5000.0)
        assert len(configured_engine._outdoor_sensors["sensor.outdoor_lux"]) == 1

    def test_batch_update(self, configured_engine):
        count = configured_engine.update_brightness_batch([
            {"entity_id": "sensor.outdoor_lux", "lux": 5000},
            {"entity_id": "sensor.wohnzimmer_lux", "lux": 200},
        ])
        assert count == 2

    def test_outdoor_brightness(self, configured_engine):
        for i in range(5):
            configured_engine.update_brightness("sensor.outdoor_lux", 5000.0 + i * 100)
        outdoor = configured_engine.get_outdoor_brightness()
        assert outdoor > 0
        assert outdoor == pytest.approx(5200.0, rel=0.1)

    def test_empty_outdoor(self, engine):
        assert engine.get_outdoor_brightness() == 0.0


class TestCloudResilience:
    def test_stable_reading(self, configured_engine):
        # Set baseline
        for _ in range(5):
            configured_engine.update_brightness("sensor.outdoor_lux", 5000.0)
        baseline = configured_engine.get_outdoor_brightness()

        # Small fluctuation (< hysteresis)
        configured_engine.update_brightness("sensor.outdoor_lux", 4900.0)
        filtered = configured_engine.get_outdoor_brightness()
        # Should still return stable value (within hysteresis)
        assert abs(filtered - baseline) < baseline * _CLOUD_HYSTERESIS_PCT / 100 + 1

    def test_significant_change(self, configured_engine):
        # Set baseline
        for _ in range(10):
            configured_engine.update_brightness("sensor.outdoor_lux", 5000.0)
        configured_engine.get_outdoor_brightness()

        # Large change (cloud cover)
        for _ in range(10):
            configured_engine.update_brightness("sensor.outdoor_lux", 1000.0)
        new_val = configured_engine.get_outdoor_brightness()
        # Should eventually update to new value
        assert new_val < 4000


class TestZoneBrightness:
    def test_zone_needs_light(self, configured_engine):
        configured_engine.update_brightness("sensor.outdoor_lux", 10000.0)
        configured_engine.update_brightness("sensor.wohnzimmer_lux", 50.0)
        zb = configured_engine.get_zone_brightness("wohnbereich")
        assert zb.needs_light is True
        assert zb.threshold_met is False
        assert zb.suggested_dimming_pct > 0

    def test_zone_enough_light(self, configured_engine):
        configured_engine.update_brightness("sensor.outdoor_lux", 10000.0)
        configured_engine.update_brightness("sensor.wohnzimmer_lux", 350.0)
        zb = configured_engine.get_zone_brightness("wohnbereich")
        assert zb.needs_light is False
        assert zb.threshold_met is True
        assert zb.suggested_dimming_pct == 0

    def test_illumination_ratio(self, configured_engine):
        configured_engine.update_brightness("sensor.outdoor_lux", 10000.0)
        configured_engine.update_brightness("sensor.wohnzimmer_lux", 5000.0)
        zb = configured_engine.get_zone_brightness("wohnbereich")
        assert zb.illumination_ratio == pytest.approx(0.5, abs=0.1)
        assert zb.illumination_pct == pytest.approx(50.0, abs=10)

    def test_zone_configure(self, engine):
        engine.configure_zone("z1", name="Test Zone", target_lux=500, min_lux=200)
        assert engine._zone_targets["z1"] == 500
        assert engine._zone_mins["z1"] == 200
        assert engine._zone_names["z1"] == "Test Zone"

    def test_empty_zone(self, engine):
        zb = engine.get_zone_brightness("nonexistent")
        assert zb.avg_indoor_lux == 0.0
        assert zb.needs_light is True  # no light = needs light


class TestMoodScenes:
    def test_get_scenes(self, engine):
        scenes = engine.get_scenes()
        assert len(scenes) == len(_MOOD_SCENES)
        ids = [s["scene_id"] for s in scenes]
        assert "relax" in ids
        assert "focus" in ids

    def test_suggest_scene_day(self, engine):
        engine.update_sun(45, 180)
        engine.register_sensor("sensor.out", location="outdoor")
        for _ in range(5):
            engine.update_brightness("sensor.out", 50000.0)
        scene = engine.suggest_scene(hour=14)
        assert scene is not None
        assert scene.scene_id == "off"  # bright day => no need for lights

    def test_suggest_scene_evening(self, engine):
        engine.update_sun(-9, 270)  # nautical dusk
        engine.register_sensor("sensor.out", location="outdoor")
        for _ in range(5):
            engine.update_brightness("sensor.out", 50.0)
        scene = engine.suggest_scene(hour=21)
        assert scene is not None
        assert scene.scene_id in ("relax", "cozy", "night_light", "dim")

    def test_suggest_scene_morning(self, engine):
        engine.update_sun(2, 90)  # sunrise
        scene = engine.suggest_scene(hour=7)
        assert scene is not None

    def test_set_active_scene(self, engine):
        assert engine.set_active_scene("relax") is True
        assert engine._active_scene == "relax"

    def test_set_invalid_scene(self, engine):
        assert engine.set_active_scene("nonexistent") is False

    def test_set_zone_scene(self, engine):
        assert engine.set_active_scene("focus", zone_id="z1") is True
        assert engine._zone_scenes["z1"] == "focus"


class TestDashboard:
    def test_empty_dashboard(self, engine):
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, LightDashboard)
        assert dashboard.global_outdoor_lux == 0.0
        assert dashboard.sun.elevation == 0.0

    def test_dashboard_with_data(self, configured_engine):
        configured_engine.update_sun(30, 180)
        configured_engine.update_brightness("sensor.outdoor_lux", 8000.0)
        configured_engine.update_brightness("sensor.wohnzimmer_lux", 200.0)
        configured_engine.update_brightness("sensor.kueche_lux", 300.0)

        dashboard = configured_engine.get_dashboard()
        assert dashboard.sun.phase == "day"
        assert dashboard.global_outdoor_lux > 0
        assert len(dashboard.zones) >= 2  # wohnbereich, kueche (+ garten from outdoor sensor)
        assert dashboard.suggested_scene is not None

    def test_dashboard_scenes(self, engine):
        dashboard = engine.get_dashboard()
        assert len(dashboard.scenes) == len(_MOOD_SCENES)

    def test_dashboard_cloud_filter(self, configured_engine):
        # Initially stable
        for _ in range(5):
            configured_engine.update_brightness("sensor.outdoor_lux", 5000.0)
        configured_engine.get_outdoor_brightness()
        dashboard = configured_engine.get_dashboard()
        assert dashboard.cloud_filter_active is False


class TestEdgeCases:
    def test_zero_outdoor(self, configured_engine):
        configured_engine.update_brightness("sensor.outdoor_lux", 0.0)
        configured_engine.update_brightness("sensor.wohnzimmer_lux", 100.0)
        zb = configured_engine.get_zone_brightness("wohnbereich")
        assert zb.illumination_ratio == 0.0

    def test_scene_wrapping_hours(self, engine):
        # Night light wraps midnight (22-6)
        engine.update_sun(-20, 0)
        scene = engine.suggest_scene(hour=2)
        assert scene is not None
