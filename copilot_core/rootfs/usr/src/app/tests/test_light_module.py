"""Tests for Adaptive Light Module Service (v1.0.0).

Tests cover:
- Zone profile CRUD
- Circadian color temperature curve
- Circadian brightness factor
- Brightness ratio adjustment
- Presence-based evaluation
- Mode handling (auto, manual, circadian, presence_only)
- Persistence (save/load)
- REST API endpoints
- Global config management
"""

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from copilot_core.light_module.service import (
    LightEvaluation,
    LightModuleService,
    ZoneLightProfile,
    ZoneLightState,
    brightness_ratio_adjustment,
    circadian_brightness_factor,
    circadian_color_temp,
)


# ---- Fixtures --------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory for light module persistence."""
    return str(tmp_path)


@pytest.fixture
def service(tmp_data_dir):
    """Create a LightModuleService with a temporary data directory."""
    return LightModuleService(data_dir=tmp_data_dir)


@pytest.fixture
def configured_service(service):
    """Service with a pre-configured zone profile."""
    service.upsert_zone_profile("zone:wohnbereich", {
        "enabled": True,
        "lights": ["light.wohnzimmer_decke", "light.wohnzimmer_stehlampe"],
        "motion_sensor": "binary_sensor.wohnzimmer_motion",
        "brightness_sensor": "sensor.wohnzimmer_helligkeit",
        "outdoor_brightness_sensor": "sensor.outdoor_lux",
        "min_brightness_pct": 10,
        "max_brightness_pct": 100,
        "color_temp_min_k": 2200,
        "color_temp_max_k": 5500,
        "presence_timeout_s": 300,
        "mode": "auto",
    })
    return service


# ---- Circadian Color Temperature Tests -------------------------------------


class TestCircadianColorTemp:

    def test_noon_is_coolest(self):
        """At noon (12:00), color temp should be at or near max (coolest)."""
        temp = circadian_color_temp(12.0, min_k=2200, max_k=5500)
        assert temp == 5500

    def test_midnight_is_warmest(self):
        """At midnight (0:00), color temp should be at or near min (warmest)."""
        temp = circadian_color_temp(0.0, min_k=2200, max_k=5500)
        assert temp == 2200

    def test_midnight_24_is_warmest(self):
        """Hour 24.0 should match midnight (warmest)."""
        temp = circadian_color_temp(24.0, min_k=2200, max_k=5500)
        assert temp == 2200

    def test_morning_intermediate(self):
        """At 6:00 AM, color temp should be intermediate."""
        temp = circadian_color_temp(6.0, min_k=2200, max_k=5500)
        assert 2200 < temp < 5500

    def test_evening_intermediate(self):
        """At 18:00, color temp should be intermediate."""
        temp = circadian_color_temp(18.0, min_k=2200, max_k=5500)
        assert 2200 < temp < 5500

    def test_symmetric_around_noon(self):
        """8 AM and 4 PM should have same color temp (symmetric)."""
        temp_8 = circadian_color_temp(8.0, min_k=2200, max_k=5500)
        temp_16 = circadian_color_temp(16.0, min_k=2200, max_k=5500)
        assert temp_8 == temp_16

    def test_monotonic_morning(self):
        """Color temp should increase from midnight to noon."""
        temps = [circadian_color_temp(h, min_k=2200, max_k=5500) for h in range(0, 13)]
        for i in range(len(temps) - 1):
            assert temps[i] <= temps[i + 1]

    def test_custom_range(self):
        """Custom min/max should be respected."""
        temp = circadian_color_temp(12.0, min_k=2700, max_k=5000)
        assert temp == 5000
        temp = circadian_color_temp(0.0, min_k=2700, max_k=5000)
        assert temp == 2700

    def test_returns_int(self):
        """Should return integer Kelvin value."""
        assert isinstance(circadian_color_temp(15.5), int)


# ---- Circadian Brightness Factor Tests ------------------------------------


class TestCircadianBrightnessFactor:

    def test_midday_full(self):
        """During the day (8-17), factor should be 1.0."""
        assert circadian_brightness_factor(12.0) == 1.0
        assert circadian_brightness_factor(8.0) == 1.0
        assert circadian_brightness_factor(17.0) == 1.0

    def test_night_minimum(self):
        """During deep night (22-06), factor should be 0.3."""
        assert circadian_brightness_factor(0.0) == 0.3
        assert circadian_brightness_factor(3.0) == 0.3
        assert circadian_brightness_factor(23.0) == 0.3

    def test_evening_ramp_down(self):
        """Between 17 and 22, factor ramps from 1.0 to 0.3."""
        f19 = circadian_brightness_factor(19.0)
        assert 0.3 < f19 < 1.0
        # 19:00 is 2h into 5h ramp => 0.72
        assert abs(f19 - 0.72) < 0.01

    def test_morning_ramp_up(self):
        """Between 6 and 8, factor ramps from 0.3 to 1.0."""
        f7 = circadian_brightness_factor(7.0)
        assert 0.3 < f7 < 1.0
        # 7:00 is 1h into 2h ramp => 0.65
        assert abs(f7 - 0.65) < 0.01

    def test_range_always_valid(self):
        """Factor should always be between 0 and 1."""
        for h in [i * 0.5 for i in range(48)]:
            f = circadian_brightness_factor(h)
            assert 0.0 <= f <= 1.0


# ---- Brightness Ratio Adjustment Tests ------------------------------------


class TestBrightnessRatioAdjustment:

    def test_dark_outside_full_brightness(self):
        """When it is dark outside, target should be max brightness."""
        pct = brightness_ratio_adjustment(
            outdoor_lux=50.0, indoor_lux=100.0,
            min_brightness_pct=10, max_brightness_pct=100,
        )
        assert pct == 100

    def test_bright_outside_with_natural_light(self):
        """When very bright outside and natural light reaches indoors, use min."""
        pct = brightness_ratio_adjustment(
            outdoor_lux=15000.0, indoor_lux=6000.0,
            min_brightness_pct=10, max_brightness_pct=100,
        )
        assert pct == 10

    def test_intermediate(self):
        """Mid-range outdoor should give intermediate brightness."""
        pct = brightness_ratio_adjustment(
            outdoor_lux=1000.0, indoor_lux=200.0,
            min_brightness_pct=10, max_brightness_pct=100,
        )
        assert 10 < pct < 100

    def test_zero_outdoor(self):
        """Zero outdoor lux should give max brightness."""
        pct = brightness_ratio_adjustment(
            outdoor_lux=0.0, indoor_lux=50.0,
            min_brightness_pct=10, max_brightness_pct=100,
        )
        assert pct == 100

    def test_respects_min_max(self):
        """Result should always be within min/max range."""
        for outdoor in [0, 50, 500, 5000, 50000]:
            for indoor in [0, 100, 500]:
                pct = brightness_ratio_adjustment(
                    outdoor_lux=float(outdoor), indoor_lux=float(indoor),
                    min_brightness_pct=20, max_brightness_pct=80,
                )
                assert 20 <= pct <= 80


# ---- Zone Light Profile Tests ----------------------------------------------


class TestZoneLightProfile:

    def test_from_dict(self):
        """Create profile from dict."""
        data = {
            "zone_id": "zone:test",
            "enabled": True,
            "lights": ["light.a", "light.b"],
            "mode": "auto",
        }
        profile = ZoneLightProfile.from_dict(data)
        assert profile.zone_id == "zone:test"
        assert profile.lights == ["light.a", "light.b"]
        assert profile.mode == "auto"

    def test_from_dict_ignores_unknown(self):
        """Unknown keys should be silently ignored."""
        data = {
            "zone_id": "zone:test",
            "unknown_field": "ignored",
        }
        profile = ZoneLightProfile.from_dict(data)
        assert profile.zone_id == "zone:test"
        assert not hasattr(profile, "unknown_field")

    def test_to_dict_roundtrip(self):
        """to_dict -> from_dict should preserve values."""
        orig = ZoneLightProfile(
            zone_id="zone:wohn",
            lights=["light.a"],
            mode="circadian",
            min_brightness_pct=15,
        )
        d = orig.to_dict()
        restored = ZoneLightProfile.from_dict(d)
        assert restored.zone_id == orig.zone_id
        assert restored.lights == orig.lights
        assert restored.mode == orig.mode
        assert restored.min_brightness_pct == orig.min_brightness_pct


# ---- Service CRUD Tests ----------------------------------------------------


class TestServiceCRUD:

    def test_upsert_create(self, service):
        """Creating a new zone profile."""
        result = service.upsert_zone_profile("zone:test", {
            "lights": ["light.a"],
            "mode": "auto",
        })
        assert result["zone_id"] == "zone:test"
        assert result["lights"] == ["light.a"]
        assert result["mode"] == "auto"

    def test_upsert_update(self, service):
        """Updating an existing zone profile."""
        service.upsert_zone_profile("zone:test", {"lights": ["light.a"]})
        updated = service.upsert_zone_profile("zone:test", {
            "lights": ["light.a", "light.b"],
            "mode": "circadian",
        })
        assert updated["lights"] == ["light.a", "light.b"]
        assert updated["mode"] == "circadian"
        assert updated["zone_id"] == "zone:test"

    def test_get_zone_profiles(self, service):
        """List all zone profiles."""
        service.upsert_zone_profile("zone:a", {"lights": ["light.a"]})
        service.upsert_zone_profile("zone:b", {"lights": ["light.b"]})
        profiles = service.get_zone_profiles()
        assert len(profiles) == 2

    def test_get_zone_profile_missing(self, service):
        """Getting a non-existent profile returns None."""
        assert service.get_zone_profile("zone:nope") is None

    def test_delete_existing(self, service):
        """Deleting an existing profile returns True."""
        service.upsert_zone_profile("zone:test", {})
        assert service.delete_zone_profile("zone:test") is True
        assert service.get_zone_profile("zone:test") is None

    def test_delete_missing(self, service):
        """Deleting a non-existent profile returns False."""
        assert service.delete_zone_profile("zone:nope") is False


# ---- Service Evaluation Tests -----------------------------------------------


class TestServiceEvaluation:

    def test_evaluate_no_profile(self, service):
        """Evaluating a zone with no profile returns no_profile."""
        result = service.evaluate("zone:missing")
        assert result.should_be_on is False
        assert result.reason == "no_profile"

    def test_evaluate_disabled_profile(self, service):
        """Evaluating a disabled profile returns profile_disabled."""
        service.upsert_zone_profile("zone:test", {"enabled": False})
        result = service.evaluate("zone:test")
        assert result.should_be_on is False
        assert result.reason == "profile_disabled"

    def test_evaluate_manual_mode(self, service):
        """Manual mode should return manual_mode."""
        service.upsert_zone_profile("zone:test", {"mode": "manual"})
        result = service.evaluate("zone:test")
        assert result.reason == "manual_mode"
        assert result.should_be_on is False

    def test_evaluate_no_presence_in_auto(self, configured_service):
        """In auto mode, no presence means lights off."""
        result = configured_service.evaluate("zone:wohnbereich")
        assert result.should_be_on is False
        assert result.reason == "no_presence"

    def test_evaluate_with_presence_dark(self, configured_service):
        """In auto mode with presence and dark outside -> lights on."""
        configured_service.update_presence("zone:wohnbereich", True)
        configured_service.update_brightness("zone:wohnbereich", indoor_lux=50.0, outdoor_lux=20.0)

        # Use a daytime hour for reasonable brightness
        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        result = configured_service.evaluate("zone:wohnbereich", now=noon)

        assert result.should_be_on is True
        assert result.brightness_pct > 0
        assert result.color_temp_k > 0

    def test_evaluate_with_presence_bright(self, configured_service):
        """With presence and bright outside, brightness should be lower."""
        configured_service.update_presence("zone:wohnbereich", True)
        configured_service.update_brightness(
            "zone:wohnbereich", indoor_lux=5000.0, outdoor_lux=20000.0
        )

        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        result = configured_service.evaluate("zone:wohnbereich", now=noon)

        assert result.should_be_on is True
        assert result.brightness_pct <= 20  # Low because lots of natural light

    def test_evaluate_circadian_mode(self, service):
        """Circadian mode computes brightness from time curve only."""
        service.upsert_zone_profile("zone:test", {
            "mode": "circadian",
            "min_brightness_pct": 10,
            "max_brightness_pct": 100,
        })

        # Noon -> full brightness
        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        result = service.evaluate("zone:test", now=noon)
        assert result.should_be_on is True
        assert result.brightness_pct == 100
        assert result.reason == "circadian"

        # Late night -> low brightness
        night = datetime(2026, 2, 26, 2, 0, tzinfo=timezone.utc)
        result = service.evaluate("zone:test", now=night)
        assert result.brightness_pct < 40

    def test_evaluate_circadian_color_temp_noon(self, configured_service):
        """At noon the color temp should be at max (coolest)."""
        configured_service.update_presence("zone:wohnbereich", True)
        configured_service.update_brightness("zone:wohnbereich", indoor_lux=50, outdoor_lux=20)

        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        result = configured_service.evaluate("zone:wohnbereich", now=noon)
        assert result.color_temp_k == 5500

    def test_evaluate_circadian_color_temp_midnight(self, configured_service):
        """At midnight the color temp should be at min (warmest)."""
        configured_service.update_presence("zone:wohnbereich", True)
        configured_service.update_brightness("zone:wohnbereich", indoor_lux=50, outdoor_lux=0)

        midnight = datetime(2026, 2, 26, 0, 0, tzinfo=timezone.utc)
        result = configured_service.evaluate("zone:wohnbereich", now=midnight)
        assert result.color_temp_k == 2200

    def test_evaluate_presence_only_mode(self, service):
        """presence_only mode should only turn on lights when presence detected."""
        service.upsert_zone_profile("zone:test", {"mode": "presence_only"})

        # No presence -> off
        result = service.evaluate("zone:test")
        assert result.should_be_on is False
        assert result.reason == "no_presence"

        # With presence -> on
        service.update_presence("zone:test", True)
        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        result = service.evaluate("zone:test", now=noon)
        assert result.should_be_on is True

    def test_presence_timeout(self, service):
        """After motion stops, lights stay on for timeout_s seconds."""
        service.upsert_zone_profile("zone:test", {
            "mode": "auto",
            "presence_timeout_s": 300,
        })

        # Motion detected, then stopped
        service.update_presence("zone:test", True)
        service.update_presence("zone:test", False)

        # Should still be "active" within timeout
        assert service._is_presence_active("zone:test") is True

    def test_presence_timeout_expired(self, service):
        """After timeout expires, presence is no longer active."""
        service.upsert_zone_profile("zone:test", {
            "mode": "auto",
            "presence_timeout_s": 5,
        })

        service.update_presence("zone:test", True)
        # Simulate time passing by setting last_motion_ts in the past
        state = service._states["zone:test"]
        state.presence_detected = False
        state.last_motion_ts = time.time() - 10  # 10 seconds ago

        assert service._is_presence_active("zone:test") is False

    def test_evaluate_all(self, service):
        """evaluate_all should return results for all configured zones."""
        service.upsert_zone_profile("zone:a", {"mode": "circadian"})
        service.upsert_zone_profile("zone:b", {"mode": "circadian"})

        results = service.evaluate_all()
        assert len(results) == 2
        zone_ids = {r["zone_id"] for r in results}
        assert "zone:a" in zone_ids
        assert "zone:b" in zone_ids

    def test_module_disabled(self, service):
        """When global module is disabled, all evaluations return module_disabled."""
        service.upsert_zone_profile("zone:test", {"mode": "auto"})
        service.update_global_config({"enabled": False})

        result = service.evaluate("zone:test")
        assert result.reason == "module_disabled"
        assert result.should_be_on is False


# ---- Persistence Tests -----------------------------------------------------


class TestPersistence:

    def test_save_and_load(self, tmp_data_dir):
        """Profiles should survive save/load cycle."""
        svc1 = LightModuleService(data_dir=tmp_data_dir)
        svc1.upsert_zone_profile("zone:test", {
            "lights": ["light.a", "light.b"],
            "mode": "circadian",
            "min_brightness_pct": 15,
        })

        # Create a new service instance that loads from same dir
        svc2 = LightModuleService(data_dir=tmp_data_dir)
        profile = svc2.get_zone_profile("zone:test")
        assert profile is not None
        assert profile["lights"] == ["light.a", "light.b"]
        assert profile["mode"] == "circadian"
        assert profile["min_brightness_pct"] == 15

    def test_global_config_persists(self, tmp_data_dir):
        """Global config should persist across service restarts."""
        svc1 = LightModuleService(data_dir=tmp_data_dir)
        svc1.update_global_config({"enabled": False, "outdoor_lux_bright_threshold": 15000})

        svc2 = LightModuleService(data_dir=tmp_data_dir)
        config = svc2.get_global_config()
        assert config["enabled"] is False
        assert config["outdoor_lux_bright_threshold"] == 15000

    def test_empty_data_dir(self, tmp_data_dir):
        """Service should start fine with no existing data file."""
        svc = LightModuleService(data_dir=tmp_data_dir)
        assert svc.get_zone_profiles() == []


# ---- Global Config Tests ---------------------------------------------------


class TestGlobalConfig:

    def test_default_config(self, service):
        """Default config should have expected keys."""
        config = service.get_global_config()
        assert config["enabled"] is True
        assert config["circadian_enabled"] is True
        assert config["brightness_ratio_enabled"] is True
        assert config["presence_enabled"] is True

    def test_update_config_partial(self, service):
        """Partial update should only change specified keys."""
        service.update_global_config({"enabled": False})
        config = service.get_global_config()
        assert config["enabled"] is False
        assert config["circadian_enabled"] is True  # unchanged

    def test_unknown_config_key_ignored(self, service):
        """Unknown keys in config update should be ignored."""
        service.update_global_config({"unknown_key": 42})
        config = service.get_global_config()
        assert "unknown_key" not in config


# ---- Status Tests ----------------------------------------------------------


class TestStatus:

    def test_get_all_status_empty(self, service):
        """No zones configured -> empty status list."""
        assert service.get_all_status() == []

    def test_get_zone_status_missing(self, service):
        """Getting status for non-existent zone returns None."""
        assert service.get_zone_status("zone:nope") is None

    def test_get_zone_status_after_upsert(self, service):
        """After creating a profile, runtime state should exist."""
        service.upsert_zone_profile("zone:test", {"mode": "auto"})
        status = service.get_zone_status("zone:test")
        assert status is not None
        assert status["zone_id"] == "zone:test"
        assert status["mode"] == "auto"

    def test_status_updated_after_evaluate(self, service):
        """After evaluation, runtime state should reflect computed values."""
        service.upsert_zone_profile("zone:test", {"mode": "circadian"})
        noon = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
        service.evaluate("zone:test", now=noon)

        status = service.get_zone_status("zone:test")
        assert status is not None
        assert status["should_be_on"] is True
        assert status["brightness_pct"] > 0


# ---- API Blueprint Tests ---------------------------------------------------


@pytest.fixture
def app(service):
    """Create a Flask test app with the light module blueprint."""
    from flask import Flask
    from copilot_core.light_module.api import light_module_bp, init_light_module_api

    app = Flask(__name__)
    app.config["TESTING"] = True
    init_light_module_api(service)
    app.register_blueprint(light_module_bp)
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


class TestAPI:
    """Test REST API endpoints."""

    def test_list_zones_empty(self, client):
        resp = client.get("/api/v1/light-module/zones")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["zones"] == []
        assert data["count"] == 0

    def test_upsert_and_get_zone(self, client):
        # Create
        resp = client.post(
            "/api/v1/light-module/zones/zone:wohn",
            json={"lights": ["light.a"], "mode": "auto"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["zone"]["zone_id"] == "zone:wohn"

        # Get
        resp = client.get("/api/v1/light-module/zones/zone:wohn")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["zone"]["lights"] == ["light.a"]

    def test_get_zone_not_found(self, client):
        resp = client.get("/api/v1/light-module/zones/zone:missing")
        assert resp.status_code == 404

    def test_delete_zone(self, client):
        client.post("/api/v1/light-module/zones/zone:del", json={"mode": "auto"})
        resp = client.delete("/api/v1/light-module/zones/zone:del")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_delete_zone_not_found(self, client):
        resp = client.delete("/api/v1/light-module/zones/zone:nope")
        assert resp.status_code == 404

    def test_list_zones_with_data(self, client):
        client.post("/api/v1/light-module/zones/zone:a", json={"mode": "auto"})
        client.post("/api/v1/light-module/zones/zone:b", json={"mode": "circadian"})
        resp = client.get("/api/v1/light-module/zones")
        data = resp.get_json()
        assert data["count"] == 2

    def test_get_status_empty(self, client):
        resp = client.get("/api/v1/light-module/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_get_zone_status(self, client):
        client.post("/api/v1/light-module/zones/zone:s", json={"mode": "auto"})
        resp = client.get("/api/v1/light-module/status/zone:s")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["zone"]["zone_id"] == "zone:s"

    def test_get_zone_status_not_found(self, client):
        resp = client.get("/api/v1/light-module/status/zone:missing")
        assert resp.status_code == 404

    def test_evaluate_all(self, client):
        client.post("/api/v1/light-module/zones/zone:e1", json={"mode": "circadian"})
        resp = client.post("/api/v1/light-module/evaluate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["evaluations"]) == 1

    def test_evaluate_single(self, client):
        client.post("/api/v1/light-module/zones/zone:e2", json={"mode": "circadian"})
        resp = client.post("/api/v1/light-module/evaluate/zone:e2")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["zone_id"] == "zone:e2"
        assert "brightness_pct" in data
        assert "color_temp_k" in data

    def test_get_config(self, client):
        resp = client.get("/api/v1/light-module/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "config" in data
        assert data["config"]["enabled"] is True

    def test_update_config(self, client):
        resp = client.post(
            "/api/v1/light-module/config",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["config"]["enabled"] is False

    def test_update_presence(self, client):
        client.post("/api/v1/light-module/zones/zone:p", json={"mode": "auto"})
        resp = client.post(
            "/api/v1/light-module/presence/zone:p",
            json={"detected": True},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["detected"] is True

    def test_update_brightness(self, client):
        client.post("/api/v1/light-module/zones/zone:b", json={"mode": "auto"})
        resp = client.post(
            "/api/v1/light-module/brightness/zone:b",
            json={"indoor_lux": 250.0, "outdoor_lux": 8500.0},
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_apply_no_profile(self, client):
        resp = client.post("/api/v1/light-module/apply/zone:missing")
        assert resp.status_code == 404


# ---- Data Model Tests -------------------------------------------------------


class TestDataModels:

    def test_light_evaluation_to_dict(self):
        ev = LightEvaluation(
            brightness_pct=75,
            color_temp_k=4200,
            should_be_on=True,
            reason="brightness_ratio",
        )
        d = ev.to_dict()
        assert d["brightness_pct"] == 75
        assert d["color_temp_k"] == 4200
        assert d["should_be_on"] is True
        assert d["reason"] == "brightness_ratio"

    def test_zone_light_state_to_dict(self):
        state = ZoneLightState(zone_id="zone:test", brightness_pct=50, should_be_on=True)
        d = state.to_dict()
        assert d["zone_id"] == "zone:test"
        assert d["brightness_pct"] == 50
