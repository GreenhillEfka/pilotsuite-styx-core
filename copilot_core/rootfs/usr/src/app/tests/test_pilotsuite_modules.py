"""Tests for PilotSuite Hub Modules: Licht, Helligkeit, Heiz, Bewegung, Praesenz (v1.0.0)."""

import pytest
from datetime import datetime, timedelta, timezone

from copilot_core.hub.licht_module import (
    LichtModuleEngine,
    LightEntity,
    ZoneLightState,
    LichtDashboard,
    _get_time_profile,
)
from copilot_core.hub.helligkeit_module import (
    HelligkeitModuleEngine,
    HelligkeitSensor,
    ZoneHelligkeit,
    HelligkeitDashboard,
)
from copilot_core.hub.heiz_module import (
    HeizModuleEngine,
    TemperatureSensor,
    HeatingEntity,
    ZoneClimate,
    HeizDashboard,
    _compute_comfort_index,
)
from copilot_core.hub.bewegung_module import (
    BewegungModuleEngine,
    MotionSensor,
    ZoneMotion,
    BewegungDashboard,
)
from copilot_core.hub.praesenz_module import (
    PraesenzModuleEngine,
    PresenceSource,
    ZonePresence,
    PraesenzDashboard,
)


# ═══════════════════════════════════════════════════════════════════════════
# LichtModuleEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestLichtModuleEngineInstantiation:
    def test_create_engine(self):
        engine = LichtModuleEngine()
        assert engine is not None

    def test_empty_engine_has_no_lights(self):
        engine = LichtModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.total_lights == 0
        assert dashboard.lights_on == 0


class TestLichtRegisterRemove:
    def test_register_light(self):
        engine = LichtModuleEngine()
        light = engine.register_light("light.living", "zone_living", "Wohnzimmer Decke")
        assert isinstance(light, LightEntity)
        assert light.entity_id == "light.living"
        assert light.zone_id == "zone_living"
        assert light.friendly_name == "Wohnzimmer Decke"

    def test_register_light_default_friendly_name(self):
        engine = LichtModuleEngine()
        light = engine.register_light("light.living", "zone_living")
        assert light.friendly_name == "light.living"

    def test_remove_light_existing(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        assert engine.remove_light("light.living") is True

    def test_remove_light_nonexistent(self):
        engine = LichtModuleEngine()
        assert engine.remove_light("light.nonexistent") is False

    def test_remove_light_decrements_count(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        engine.remove_light("light.living")
        assert engine.get_dashboard().total_lights == 0


class TestLichtConfigureZone:
    def test_configure_zone(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer", auto_enabled=True)
        state = engine.get_zone_state("zone_living")
        assert state.zone_name == "Wohnzimmer"
        assert state.auto_enabled is True

    def test_configure_zone_auto_disabled(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        engine.configure_zone("zone_living", auto_enabled=False)
        state = engine.get_zone_state("zone_living")
        assert state.auto_enabled is False

    def test_configure_zone_delays(self):
        engine = LichtModuleEngine()
        engine.configure_zone("zone_living", presence_delay_s=10, absence_delay_s=120)
        # No error; config is stored internally


class TestLichtUpdateState:
    def test_update_light_on(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        result = engine.update_light_state("light.living", is_on=True, brightness_pct=75, color_temp_k=3500)
        assert result is not None
        assert result.is_on is True
        assert result.brightness_pct == 75
        assert result.color_temp_k == 3500

    def test_update_light_off(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        engine.update_light_state("light.living", is_on=True, brightness_pct=100)
        result = engine.update_light_state("light.living", is_on=False)
        assert result.is_on is False

    def test_update_light_rgb(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        result = engine.update_light_state("light.living", is_on=True, rgb_color=(255, 0, 128))
        assert result.rgb_color == (255, 0, 128)

    def test_update_unknown_light_returns_none(self):
        engine = LichtModuleEngine()
        result = engine.update_light_state("light.nonexistent", is_on=True)
        assert result is None


class TestLichtOverride:
    def test_set_override(self):
        engine = LichtModuleEngine()
        engine.register_light("light.living", "zone_living")
        assert engine.set_override("light.living", True) is True
        state = engine.get_zone_state("zone_living")
        assert state.any_override is True

    def test_set_override_nonexistent(self):
        engine = LichtModuleEngine()
        assert engine.set_override("light.nonexistent") is False

    def test_clear_zone_overrides(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.register_light("light.b", "zone_living")
        engine.set_override("light.a")
        engine.set_override("light.b")
        count = engine.clear_zone_overrides("zone_living")
        assert count == 2
        state = engine.get_zone_state("zone_living")
        assert state.any_override is False

    def test_clear_overrides_empty_zone(self):
        engine = LichtModuleEngine()
        count = engine.clear_zone_overrides("zone_empty")
        assert count == 0


class TestLichtGetZoneState:
    def test_zone_state_counts(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.register_light("light.b", "zone_living")
        engine.update_light_state("light.a", is_on=True, brightness_pct=80)
        state = engine.get_zone_state("zone_living")
        assert state.lights_total == 2
        assert state.lights_on == 1

    def test_zone_state_avg_brightness(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.register_light("light.b", "zone_living")
        engine.update_light_state("light.a", is_on=True, brightness_pct=60)
        engine.update_light_state("light.b", is_on=True, brightness_pct=80)
        state = engine.get_zone_state("zone_living")
        assert state.avg_brightness_pct == 70.0

    def test_zone_state_no_lights_on_avg_zero(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        state = engine.get_zone_state("zone_living")
        assert state.avg_brightness_pct == 0.0

    def test_zone_state_empty_zone(self):
        engine = LichtModuleEngine()
        state = engine.get_zone_state("zone_empty")
        assert state.lights_total == 0
        assert state.lights_on == 0

    def test_zone_state_has_target_values(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        state = engine.get_zone_state("zone_living")
        assert state.target_brightness_pct > 0
        assert state.target_color_temp_k > 0


class TestLichtGetTargetForHour:
    def test_night_profile(self):
        engine = LichtModuleEngine()
        target = engine.get_target_for_hour(2)
        assert target["brightness_pct"] == 5
        assert target["color_temp_k"] == 2200

    def test_morning_profile(self):
        engine = LichtModuleEngine()
        target = engine.get_target_for_hour(7)
        assert target["brightness_pct"] == 60
        assert target["color_temp_k"] == 3500

    def test_day_profile(self):
        engine = LichtModuleEngine()
        target = engine.get_target_for_hour(12)
        assert target["brightness_pct"] == 100
        assert target["color_temp_k"] == 5000

    def test_evening_profile(self):
        engine = LichtModuleEngine()
        target = engine.get_target_for_hour(18)
        assert target["brightness_pct"] == 50
        assert target["color_temp_k"] == 2700

    def test_late_evening_profile(self):
        engine = LichtModuleEngine()
        target = engine.get_target_for_hour(21)
        assert target["brightness_pct"] == 30
        assert target["color_temp_k"] == 2500


class TestLichtDashboard:
    def test_dashboard_structure(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.register_light("light.b", "zone_kitchen")
        engine.update_light_state("light.a", is_on=True, brightness_pct=50)
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, LichtDashboard)
        assert isinstance(dashboard.zones, list)
        assert dashboard.total_lights == 2
        assert dashboard.lights_on == 1
        assert dashboard.overrides_active == 0
        assert len(dashboard.zones) == 2

    def test_dashboard_zone_dict_keys(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        dashboard = engine.get_dashboard()
        zone = dashboard.zones[0]
        expected_keys = {
            "zone_id", "zone_name", "lights_on", "lights_total",
            "avg_brightness_pct", "any_override", "auto_enabled",
            "target_brightness_pct", "target_color_temp_k",
        }
        assert set(zone.keys()) == expected_keys

    def test_dashboard_empty(self):
        engine = LichtModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.zones == []
        assert dashboard.total_lights == 0

    def test_dashboard_overrides_counted(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.register_light("light.b", "zone_living")
        engine.set_override("light.a")
        dashboard = engine.get_dashboard()
        assert dashboard.overrides_active == 1

    def test_dashboard_auto_mode_zones(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_a")
        engine.register_light("light.b", "zone_b")
        engine.configure_zone("zone_a", auto_enabled=True)
        engine.configure_zone("zone_b", auto_enabled=False)
        dashboard = engine.get_dashboard()
        assert dashboard.auto_mode_zones == 1


class TestLichtSummary:
    def test_summary_keys(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        summary = engine.get_summary()
        expected_keys = {"total_lights", "lights_on", "overrides_active", "auto_mode_zones", "zones"}
        assert set(summary.keys()) == expected_keys

    def test_summary_values_match_dashboard(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.update_light_state("light.a", is_on=True, brightness_pct=100)
        summary = engine.get_summary()
        assert summary["total_lights"] == 1
        assert summary["lights_on"] == 1


class TestLichtContextForLlm:
    def test_context_returns_string(self):
        engine = LichtModuleEngine()
        engine.register_light("light.a", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.update_light_state("light.a", is_on=True, brightness_pct=80)
        context = engine.get_context_for_llm()
        assert isinstance(context, str)
        assert "Lichtmodul" in context
        assert "Wohnzimmer" in context

    def test_context_empty_when_no_lights(self):
        engine = LichtModuleEngine()
        context = engine.get_context_for_llm()
        assert context == ""


# ═══════════════════════════════════════════════════════════════════════════
# HelligkeitModuleEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestHelligkeitInstantiation:
    def test_create_engine(self):
        engine = HelligkeitModuleEngine()
        assert engine is not None

    def test_empty_engine(self):
        engine = HelligkeitModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.total_sensors == 0


class TestHelligkeitRegisterRemove:
    def test_register_sensor(self):
        engine = HelligkeitModuleEngine()
        sensor = engine.register_sensor("sensor.lux_living", "zone_living", "indoor")
        assert isinstance(sensor, HelligkeitSensor)
        assert sensor.entity_id == "sensor.lux_living"
        assert sensor.zone_id == "zone_living"
        assert sensor.location == "indoor"

    def test_register_outdoor_sensor(self):
        engine = HelligkeitModuleEngine()
        sensor = engine.register_sensor("sensor.lux_outdoor", "zone_garden", "outdoor")
        assert sensor.location == "outdoor"

    def test_remove_sensor_existing(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.lux_living", "zone_living")
        assert engine.remove_sensor("sensor.lux_living") is True

    def test_remove_sensor_nonexistent(self):
        engine = HelligkeitModuleEngine()
        assert engine.remove_sensor("sensor.nonexistent") is False


class TestHelligkeitConfigureZone:
    def test_configure_zone(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.lux_living", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer", target_lux=500.0, min_lux=150.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.zone_name == "Wohnzimmer"
        assert state.target_lux == 500.0
        assert state.min_lux == 150.0

    def test_configure_zone_defaults(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.lux_living", "zone_living")
        state = engine.get_zone_brightness("zone_living")
        assert state.target_lux == 300.0
        assert state.min_lux == 100.0


class TestHelligkeitUpdateState:
    def test_update_reading(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.lux_living", "zone_living")
        result = engine.update_reading("sensor.lux_living", 450.0)
        assert result is not None
        assert result.last_lux == 450.0

    def test_update_reading_nonexistent(self):
        engine = HelligkeitModuleEngine()
        result = engine.update_reading("sensor.nonexistent", 100.0)
        assert result is None

    def test_update_batch(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living")
        engine.register_sensor("sensor.b", "zone_living")
        count = engine.update_batch({"sensor.a": 200.0, "sensor.b": 400.0, "sensor.c": 999.0})
        assert count == 2

    def test_outdoor_reading_updates_history(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.outdoor", "zone_garden", "outdoor")
        engine.update_reading("sensor.outdoor", 10000.0)
        assert engine.get_outdoor_brightness() == 10000.0


class TestHelligkeitGetZoneBrightness:
    def test_zone_brightness_indoor(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.register_sensor("sensor.b", "zone_living", "indoor")
        engine.update_reading("sensor.a", 200.0)
        engine.update_reading("sensor.b", 400.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.avg_indoor_lux == 300.0

    def test_zone_needs_light_when_below_min(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", min_lux=200.0)
        engine.update_reading("sensor.a", 50.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.needs_light is True

    def test_zone_no_light_needed_above_min(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", min_lux=100.0)
        engine.update_reading("sensor.a", 500.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.needs_light is False

    def test_deficit_pct_calculation(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", target_lux=400.0)
        engine.update_reading("sensor.a", 200.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.deficit_pct == 50.0

    def test_recommended_dimming_capped_at_100(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", target_lux=1000.0)
        engine.update_reading("sensor.a", 0.0)
        state = engine.get_zone_brightness("zone_living")
        assert state.recommended_dimming_pct == 100.0

    def test_empty_zone(self):
        engine = HelligkeitModuleEngine()
        state = engine.get_zone_brightness("zone_empty")
        assert state.avg_indoor_lux == 0.0


class TestHelligkeitOutdoorBrightness:
    def test_outdoor_hysteresis(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.outdoor", "zone_garden", "outdoor")
        # Set initial value
        engine.update_reading("sensor.outdoor", 10000.0)
        first = engine.get_outdoor_brightness()
        # Small change within 12% should not change the average
        engine.update_reading("sensor.outdoor", 10500.0)
        second = engine.get_outdoor_brightness()
        # The average shifted by ~2.5% which is within 12% hysteresis
        assert second == first

    def test_outdoor_no_history(self):
        engine = HelligkeitModuleEngine()
        assert engine.get_outdoor_brightness() == 0.0


class TestHelligkeitDashboard:
    def test_dashboard_structure(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.register_sensor("sensor.b", "zone_kitchen", "indoor")
        engine.update_reading("sensor.a", 200.0)
        engine.update_reading("sensor.b", 50.0)
        engine.configure_zone("zone_kitchen", min_lux=100.0)
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, HelligkeitDashboard)
        assert isinstance(dashboard.zones, list)
        assert dashboard.total_sensors == 2
        assert len(dashboard.zones) == 2

    def test_dashboard_zones_needing_light(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", min_lux=200.0)
        engine.update_reading("sensor.a", 50.0)
        dashboard = engine.get_dashboard()
        assert dashboard.zones_needing_light == 1

    def test_dashboard_zone_dict_keys(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        dashboard = engine.get_dashboard()
        zone = dashboard.zones[0]
        expected_keys = {
            "zone_id", "zone_name", "avg_indoor_lux", "avg_outdoor_lux",
            "target_lux", "min_lux", "needs_light", "deficit_pct",
            "recommended_dimming_pct",
        }
        assert set(zone.keys()) == expected_keys

    def test_dashboard_empty(self):
        engine = HelligkeitModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.zones == []
        assert dashboard.total_sensors == 0


class TestHelligkeitSummary:
    def test_summary_keys(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living")
        summary = engine.get_summary()
        expected_keys = {"total_sensors", "global_outdoor_lux", "zones_needing_light", "zones"}
        assert set(summary.keys()) == expected_keys


class TestHelligkeitContextForLlm:
    def test_context_returns_string(self):
        engine = HelligkeitModuleEngine()
        engine.register_sensor("sensor.a", "zone_living", "indoor")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.update_reading("sensor.a", 200.0)
        context = engine.get_context_for_llm()
        assert isinstance(context, str)
        assert "Helligkeitsmodul" in context
        assert "Wohnzimmer" in context

    def test_context_empty_when_no_sensors(self):
        engine = HelligkeitModuleEngine()
        context = engine.get_context_for_llm()
        assert context == ""


# ═══════════════════════════════════════════════════════════════════════════
# HeizModuleEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestHeizInstantiation:
    def test_create_engine(self):
        engine = HeizModuleEngine()
        assert engine is not None

    def test_empty_engine(self):
        engine = HeizModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.total_climate_entities == 0


class TestHeizRegisterRemove:
    def test_register_sensor(self):
        engine = HeizModuleEngine()
        sensor = engine.register_sensor("sensor.temp_living", "zone_living", "temperature")
        assert isinstance(sensor, TemperatureSensor)
        assert sensor.entity_id == "sensor.temp_living"
        assert sensor.sensor_type == "temperature"

    def test_register_humidity_sensor(self):
        engine = HeizModuleEngine()
        sensor = engine.register_sensor("sensor.hum_living", "zone_living", "humidity", unit="%")
        assert sensor.sensor_type == "humidity"
        assert sensor.unit == "%"

    def test_register_heater(self):
        engine = HeizModuleEngine()
        heater = engine.register_heater("climate.living", "zone_living", "Wohnzimmer Heizung")
        assert isinstance(heater, HeatingEntity)
        assert heater.entity_id == "climate.living"
        assert heater.friendly_name == "Wohnzimmer Heizung"

    def test_register_heater_default_name(self):
        engine = HeizModuleEngine()
        heater = engine.register_heater("climate.living", "zone_living")
        assert heater.friendly_name == "climate.living"


class TestHeizConfigureZone:
    def test_configure_zone(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer", target_temp=22.0, eco_temp=18.0)
        state = engine.get_zone_climate("zone_living")
        assert state.zone_name == "Wohnzimmer"
        assert state.target_temp == 22.0

    def test_eco_mode(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.configure_zone("zone_living", target_temp=22.0, eco_temp=18.0)
        engine.set_eco_mode("zone_living", True)
        state = engine.get_zone_climate("zone_living")
        assert state.eco_mode is True
        assert state.target_temp == 18.0

    def test_eco_mode_unconfigured_zone(self):
        engine = HeizModuleEngine()
        result = engine.set_eco_mode("zone_new", True)
        assert result is True


class TestHeizUpdateState:
    def test_update_sensor(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        result = engine.update_sensor("sensor.temp", 21.5)
        assert result is not None
        assert result.value == 21.5

    def test_update_sensor_nonexistent(self):
        engine = HeizModuleEngine()
        result = engine.update_sensor("sensor.nonexistent", 20.0)
        assert result is None

    def test_update_heater(self):
        engine = HeizModuleEngine()
        engine.register_heater("climate.living", "zone_living")
        result = engine.update_heater(
            "climate.living", hvac_mode="heat",
            target_temp=22.0, current_temp=19.5, is_heating=True,
        )
        assert result is not None
        assert result.hvac_mode == "heat"
        assert result.target_temp == 22.0
        assert result.is_heating is True

    def test_update_heater_partial(self):
        engine = HeizModuleEngine()
        engine.register_heater("climate.living", "zone_living")
        engine.update_heater("climate.living", hvac_mode="heat", target_temp=22.0)
        result = engine.update_heater("climate.living", is_heating=True)
        assert result.hvac_mode == "heat"
        assert result.is_heating is True

    def test_update_heater_nonexistent(self):
        engine = HeizModuleEngine()
        result = engine.update_heater("climate.nonexistent", hvac_mode="heat")
        assert result is None


class TestHeizGetZoneClimate:
    def test_zone_climate_basic(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.register_sensor("sensor.hum", "zone_living", "humidity")
        engine.update_sensor("sensor.temp", 21.0)
        engine.update_sensor("sensor.hum", 50.0)
        state = engine.get_zone_climate("zone_living")
        assert state.current_temp == 21.0
        assert state.humidity == 50.0

    def test_zone_climate_needs_heating(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.configure_zone("zone_living", target_temp=22.0)
        engine.update_sensor("sensor.temp", 18.0)
        state = engine.get_zone_climate("zone_living")
        assert state.needs_heating is True
        assert state.temp_delta < 0

    def test_zone_climate_no_heating_needed(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.configure_zone("zone_living", target_temp=20.0)
        engine.update_sensor("sensor.temp", 22.0)
        state = engine.get_zone_climate("zone_living")
        assert state.needs_heating is False
        assert state.temp_delta > 0

    def test_zone_climate_is_heating(self):
        engine = HeizModuleEngine()
        engine.register_heater("climate.living", "zone_living")
        engine.update_heater("climate.living", is_heating=True)
        state = engine.get_zone_climate("zone_living")
        assert state.is_heating is True

    def test_zone_climate_comfort_index(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.register_sensor("sensor.hum", "zone_living", "humidity")
        engine.update_sensor("sensor.temp", 21.0)
        engine.update_sensor("sensor.hum", 50.0)
        state = engine.get_zone_climate("zone_living")
        assert state.comfort_index == 100  # Perfect conditions

    def test_zone_climate_empty_zone(self):
        engine = HeizModuleEngine()
        state = engine.get_zone_climate("zone_empty")
        assert state.current_temp == 0.0
        assert state.humidity == 0.0


class TestComputeComfortIndex:
    def test_perfect_conditions(self):
        assert _compute_comfort_index(21.0, 50.0) == 100

    def test_cold_temperature(self):
        score = _compute_comfort_index(15.0, 50.0)
        assert score < 100
        assert score > 0

    def test_hot_temperature(self):
        score = _compute_comfort_index(28.0, 50.0)
        assert score < 100

    def test_low_humidity(self):
        score = _compute_comfort_index(21.0, 10.0)
        assert score < 100

    def test_high_humidity(self):
        score = _compute_comfort_index(21.0, 90.0)
        assert score < 100

    def test_score_clamped_0_100(self):
        score = _compute_comfort_index(0.0, 0.0)
        assert 0 <= score <= 100
        score = _compute_comfort_index(50.0, 100.0)
        assert 0 <= score <= 100


class TestHeizDashboard:
    def test_dashboard_structure(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.register_heater("climate.living", "zone_living")
        engine.update_sensor("sensor.temp", 21.0)
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, HeizDashboard)
        assert isinstance(dashboard.zones, list)
        assert dashboard.total_climate_entities == 2
        assert len(dashboard.zones) == 1

    def test_dashboard_zone_dict_keys(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.update_sensor("sensor.temp", 21.0)
        dashboard = engine.get_dashboard()
        zone = dashboard.zones[0]
        expected_keys = {
            "zone_id", "zone_name", "current_temp", "target_temp",
            "humidity", "is_heating", "eco_mode", "comfort_index",
            "needs_heating", "temp_delta",
        }
        assert set(zone.keys()) == expected_keys

    def test_dashboard_avg_temp(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp_a", "zone_a", "temperature")
        engine.register_sensor("sensor.temp_b", "zone_b", "temperature")
        engine.update_sensor("sensor.temp_a", 20.0)
        engine.update_sensor("sensor.temp_b", 22.0)
        dashboard = engine.get_dashboard()
        assert dashboard.avg_indoor_temp == 21.0

    def test_dashboard_zones_heating(self):
        engine = HeizModuleEngine()
        engine.register_heater("climate.a", "zone_a")
        engine.register_heater("climate.b", "zone_b")
        engine.update_heater("climate.a", is_heating=True)
        dashboard = engine.get_dashboard()
        assert dashboard.zones_heating == 1

    def test_dashboard_zones_eco(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_a", "temperature")
        engine.configure_zone("zone_a")
        engine.set_eco_mode("zone_a", True)
        dashboard = engine.get_dashboard()
        assert dashboard.zones_eco == 1

    def test_dashboard_empty(self):
        engine = HeizModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.zones == []
        assert dashboard.total_climate_entities == 0


class TestHeizSummary:
    def test_summary_keys(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        summary = engine.get_summary()
        expected_keys = {
            "total_climate_entities", "avg_indoor_temp", "avg_humidity",
            "zones_heating", "zones_eco", "zones",
        }
        assert set(summary.keys()) == expected_keys


class TestHeizContextForLlm:
    def test_context_returns_string(self):
        engine = HeizModuleEngine()
        engine.register_sensor("sensor.temp", "zone_living", "temperature")
        engine.register_sensor("sensor.hum", "zone_living", "humidity")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.update_sensor("sensor.temp", 21.0)
        engine.update_sensor("sensor.hum", 50.0)
        context = engine.get_context_for_llm()
        assert isinstance(context, str)
        assert "Heizmodul" in context
        assert "Wohnzimmer" in context

    def test_context_empty_when_no_entities(self):
        engine = HeizModuleEngine()
        context = engine.get_context_for_llm()
        assert context == ""


# ═══════════════════════════════════════════════════════════════════════════
# BewegungModuleEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestBewegungInstantiation:
    def test_create_engine(self):
        engine = BewegungModuleEngine()
        assert engine is not None

    def test_empty_engine(self):
        engine = BewegungModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.total_sensors == 0


class TestBewegungRegisterRemove:
    def test_register_sensor(self):
        engine = BewegungModuleEngine()
        sensor = engine.register_sensor("binary_sensor.motion_living", "zone_living", "Flur Sensor")
        assert isinstance(sensor, MotionSensor)
        assert sensor.entity_id == "binary_sensor.motion_living"
        assert sensor.zone_id == "zone_living"
        assert sensor.friendly_name == "Flur Sensor"

    def test_register_sensor_default_name(self):
        engine = BewegungModuleEngine()
        sensor = engine.register_sensor("binary_sensor.motion", "zone_living")
        assert sensor.friendly_name == "binary_sensor.motion"

    def test_remove_sensor_existing(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        assert engine.remove_sensor("binary_sensor.motion") is True

    def test_remove_sensor_nonexistent(self):
        engine = BewegungModuleEngine()
        assert engine.remove_sensor("nonexistent") is False


class TestBewegungConfigureZone:
    def test_configure_zone(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        state = engine.get_zone_motion("zone_living")
        assert state.zone_name == "Wohnzimmer"


class TestBewegungUpdateState:
    def test_trigger_motion(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        result = engine.trigger_motion("binary_sensor.motion")
        assert result is not None
        assert result.is_active is True
        assert result.trigger_count == 1
        assert result.last_triggered is not None

    def test_trigger_motion_increments_count(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        engine.trigger_motion("binary_sensor.motion")
        result = engine.trigger_motion("binary_sensor.motion")
        assert result.trigger_count == 3

    def test_trigger_motion_nonexistent(self):
        engine = BewegungModuleEngine()
        result = engine.trigger_motion("nonexistent")
        assert result is None

    def test_clear_motion(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        result = engine.clear_motion("binary_sensor.motion")
        assert result is not None
        assert result.is_active is False

    def test_clear_motion_nonexistent(self):
        engine = BewegungModuleEngine()
        result = engine.clear_motion("nonexistent")
        assert result is None


class TestBewegungGetZoneMotion:
    def test_zone_motion_active(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion_a", "zone_living")
        engine.register_sensor("binary_sensor.motion_b", "zone_living")
        engine.trigger_motion("binary_sensor.motion_a")
        state = engine.get_zone_motion("zone_living")
        assert state.sensors_active == 1
        assert state.sensors_total == 2

    def test_zone_motion_last_5min(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        state = engine.get_zone_motion("zone_living")
        assert state.motion_in_last_5min is True
        assert state.motion_in_last_30min is True

    def test_zone_motion_no_triggers(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        state = engine.get_zone_motion("zone_living")
        assert state.motion_in_last_5min is False
        assert state.motion_in_last_30min is False
        assert state.last_motion is None

    def test_zone_motion_daily_triggers(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        engine.trigger_motion("binary_sensor.motion")
        state = engine.get_zone_motion("zone_living")
        assert state.daily_triggers == 2

    def test_zone_motion_empty_zone(self):
        engine = BewegungModuleEngine()
        state = engine.get_zone_motion("zone_empty")
        assert state.sensors_total == 0
        assert state.sensors_active == 0


class TestBewegungDashboard:
    def test_dashboard_structure(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion_a", "zone_living")
        engine.register_sensor("binary_sensor.motion_b", "zone_kitchen")
        engine.trigger_motion("binary_sensor.motion_a")
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, BewegungDashboard)
        assert isinstance(dashboard.zones, list)
        assert dashboard.total_sensors == 2
        assert dashboard.sensors_active == 1
        assert len(dashboard.zones) == 2

    def test_dashboard_zone_dict_keys(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        dashboard = engine.get_dashboard()
        zone = dashboard.zones[0]
        expected_keys = {
            "zone_id", "zone_name", "sensors_active", "sensors_total",
            "last_motion", "motion_in_last_5min", "motion_in_last_30min",
            "daily_triggers",
        }
        assert set(zone.keys()) == expected_keys

    def test_dashboard_zones_with_motion(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion_a", "zone_living")
        engine.register_sensor("binary_sensor.motion_b", "zone_kitchen")
        engine.trigger_motion("binary_sensor.motion_a")
        dashboard = engine.get_dashboard()
        assert dashboard.zones_with_motion == 1

    def test_dashboard_last_global_motion(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.trigger_motion("binary_sensor.motion")
        dashboard = engine.get_dashboard()
        assert dashboard.last_global_motion is not None

    def test_dashboard_empty(self):
        engine = BewegungModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.zones == []
        assert dashboard.total_sensors == 0
        assert dashboard.last_global_motion is None


class TestBewegungSummary:
    def test_summary_keys(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        summary = engine.get_summary()
        expected_keys = {
            "total_sensors", "sensors_active", "last_global_motion",
            "zones_with_motion", "zones",
        }
        assert set(summary.keys()) == expected_keys


class TestBewegungContextForLlm:
    def test_context_returns_string(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.trigger_motion("binary_sensor.motion")
        context = engine.get_context_for_llm()
        assert isinstance(context, str)
        assert "Bewegungsmodul" in context
        assert "Wohnzimmer" in context

    def test_context_empty_when_no_sensors(self):
        engine = BewegungModuleEngine()
        context = engine.get_context_for_llm()
        assert context == ""

    def test_context_shows_active_status(self):
        engine = BewegungModuleEngine()
        engine.register_sensor("binary_sensor.motion", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.trigger_motion("binary_sensor.motion")
        context = engine.get_context_for_llm()
        assert "aktiv" in context


# ═══════════════════════════════════════════════════════════════════════════
# PraesenzModuleEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestPraesenzInstantiation:
    def test_create_engine(self):
        engine = PraesenzModuleEngine()
        assert engine is not None

    def test_empty_engine(self):
        engine = PraesenzModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.total_sources == 0


class TestPraesenzRegisterRemove:
    def test_register_source(self):
        engine = PraesenzModuleEngine()
        source = engine.register_source(
            "device_tracker.phone_alice", "zone_living",
            source_type="device_tracker", person_name="Alice",
        )
        assert isinstance(source, PresenceSource)
        assert source.entity_id == "device_tracker.phone_alice"
        assert source.zone_id == "zone_living"
        assert source.source_type == "device_tracker"
        assert source.person_name == "Alice"

    def test_register_source_defaults(self):
        engine = PraesenzModuleEngine()
        source = engine.register_source("binary_sensor.motion", "zone_living")
        assert source.source_type == "motion"
        assert source.person_name == ""

    def test_remove_source_existing(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living")
        assert engine.remove_source("device_tracker.phone") is True

    def test_remove_source_nonexistent(self):
        engine = PraesenzModuleEngine()
        assert engine.remove_source("nonexistent") is False


class TestPraesenzConfigureZone:
    def test_configure_zone(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        state = engine.get_zone_presence("zone_living")
        assert state.zone_name == "Wohnzimmer"


class TestPraesenzUpdateState:
    def test_update_presence_enter(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        result = engine.update_presence("device_tracker.phone", is_present=True)
        assert result is not None
        assert result.is_present is True

    def test_update_presence_leave(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.phone", is_present=True)
        result = engine.update_presence("device_tracker.phone", is_present=False)
        assert result.is_present is False

    def test_update_presence_nonexistent(self):
        engine = PraesenzModuleEngine()
        result = engine.update_presence("nonexistent", is_present=True)
        assert result is None

    def test_update_presence_with_person_name(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living")
        engine.update_presence("device_tracker.phone", is_present=True, person_name="Bob")
        state = engine.get_zone_presence("zone_living")
        assert "Bob" in state.persons

    def test_occupied_since_set_on_entry(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.phone", is_present=True)
        state = engine.get_zone_presence("zone_living")
        assert state.occupied_since is not None

    def test_occupied_since_cleared_when_empty(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.phone", is_present=True)
        engine.update_presence("device_tracker.phone", is_present=False)
        state = engine.get_zone_presence("zone_living")
        assert state.occupied_since is None


class TestPraesenzGetZonePresence:
    def test_zone_occupied(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.phone", is_present=True)
        state = engine.get_zone_presence("zone_living")
        assert state.is_occupied is True
        assert state.person_count == 1
        assert "Alice" in state.persons

    def test_zone_empty(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.phone", "zone_living", person_name="Alice")
        state = engine.get_zone_presence("zone_living")
        assert state.is_occupied is False
        assert state.person_count == 0

    def test_zone_multiple_persons(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.register_source("device_tracker.bob", "zone_living", person_name="Bob")
        engine.update_presence("device_tracker.alice", is_present=True)
        engine.update_presence("device_tracker.bob", is_present=True)
        state = engine.get_zone_presence("zone_living")
        assert state.is_occupied is True
        assert state.person_count == 2
        assert sorted(state.persons) == ["Alice", "Bob"]

    def test_zone_sources_count(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.register_source("binary_sensor.motion", "zone_living")
        engine.update_presence("device_tracker.alice", is_present=True)
        state = engine.get_zone_presence("zone_living")
        assert state.sources_active == 1
        assert state.sources_total == 2

    def test_zone_empty_zone(self):
        engine = PraesenzModuleEngine()
        state = engine.get_zone_presence("zone_empty")
        assert state.is_occupied is False
        assert state.sources_total == 0

    def test_zone_unique_persons(self):
        """Two sources for same person should count as one person."""
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice_phone", "zone_living", person_name="Alice")
        engine.register_source("device_tracker.alice_watch", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.alice_phone", is_present=True)
        engine.update_presence("device_tracker.alice_watch", is_present=True)
        state = engine.get_zone_presence("zone_living")
        assert state.person_count == 1


class TestPraesenzGetAllPersonsHome:
    def test_all_persons_home(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.register_source("device_tracker.bob", "zone_kitchen", person_name="Bob")
        engine.update_presence("device_tracker.alice", is_present=True)
        engine.update_presence("device_tracker.bob", is_present=True)
        persons = engine.get_all_persons_home()
        assert sorted(persons) == ["Alice", "Bob"]

    def test_no_persons_home(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        persons = engine.get_all_persons_home()
        assert persons == []


class TestPraesenzDashboard:
    def test_dashboard_structure(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.register_source("device_tracker.bob", "zone_kitchen", person_name="Bob")
        engine.update_presence("device_tracker.alice", is_present=True)
        dashboard = engine.get_dashboard()
        assert isinstance(dashboard, PraesenzDashboard)
        assert isinstance(dashboard.zones, list)
        assert dashboard.total_sources == 2
        assert dashboard.persons_home == 1
        assert dashboard.zones_occupied == 1
        assert dashboard.zones_empty == 1
        assert len(dashboard.zones) == 2

    def test_dashboard_zone_dict_keys(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.alice", is_present=True)
        dashboard = engine.get_dashboard()
        zone = dashboard.zones[0]
        expected_keys = {
            "zone_id", "zone_name", "is_occupied", "person_count",
            "persons", "last_entered", "last_left", "occupied_since",
            "sources_active", "sources_total",
        }
        assert set(zone.keys()) == expected_keys

    def test_dashboard_empty(self):
        engine = PraesenzModuleEngine()
        dashboard = engine.get_dashboard()
        assert dashboard.zones == []
        assert dashboard.total_sources == 0
        assert dashboard.persons_home == 0


class TestPraesenzSummary:
    def test_summary_keys(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        summary = engine.get_summary()
        expected_keys = {
            "total_sources", "persons_home", "persons",
            "zones_occupied", "zones_empty", "zones",
        }
        assert set(summary.keys()) == expected_keys

    def test_summary_persons_list(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.update_presence("device_tracker.alice", is_present=True)
        summary = engine.get_summary()
        assert "Alice" in summary["persons"]


class TestPraesenzContextForLlm:
    def test_context_returns_string(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.update_presence("device_tracker.alice", is_present=True)
        context = engine.get_context_for_llm()
        assert isinstance(context, str)
        assert "Praesenzmodul" in context
        assert "Wohnzimmer" in context
        assert "Alice" in context

    def test_context_empty_when_no_sources(self):
        engine = PraesenzModuleEngine()
        context = engine.get_context_for_llm()
        assert context == ""

    def test_context_shows_occupied_status(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        engine.update_presence("device_tracker.alice", is_present=True)
        context = engine.get_context_for_llm()
        assert "belegt" in context

    def test_context_shows_empty_status(self):
        engine = PraesenzModuleEngine()
        engine.register_source("device_tracker.alice", "zone_living", person_name="Alice")
        engine.configure_zone("zone_living", zone_name="Wohnzimmer")
        context = engine.get_context_for_llm()
        assert "leer" in context

    def test_context_shows_niemand_when_nobody_home(self):
        engine = PraesenzModuleEngine()
        engine.register_source("binary_sensor.motion", "zone_living")
        context = engine.get_context_for_llm()
        assert "niemand" in context


# ═══════════════════════════════════════════════════════════════════════════
# Time Profile Helper (Lichtmodul)
# ═══════════════════════════════════════════════════════════════════════════


class TestTimeProfile:
    def test_night_hours(self):
        for h in [0, 1, 2, 3, 4, 5, 22, 23]:
            brightness, temp = _get_time_profile(h)
            assert brightness == 5
            assert temp == 2200

    def test_morning_hours(self):
        for h in [6, 7, 8]:
            brightness, temp = _get_time_profile(h)
            assert brightness == 60
            assert temp == 3500

    def test_day_hours(self):
        for h in [9, 10, 11, 12, 13, 14, 15, 16]:
            brightness, temp = _get_time_profile(h)
            assert brightness == 100
            assert temp == 5000

    def test_evening_hours(self):
        for h in [17, 18, 19]:
            brightness, temp = _get_time_profile(h)
            assert brightness == 50
            assert temp == 2700

    def test_late_evening_hours(self):
        for h in [20, 21]:
            brightness, temp = _get_time_profile(h)
            assert brightness == 30
            assert temp == 2500
