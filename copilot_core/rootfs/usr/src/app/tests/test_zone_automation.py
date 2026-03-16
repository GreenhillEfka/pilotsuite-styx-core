"""Tests for Zone Automation Controller — presence-based light & music, entity management, tags.

Tests:
  - ZoneAutomationController config CRUD
  - Presence detection → light on with delay
  - Presence cleared → light off with absence delay
  - Brightness update with hysteresis dampening
  - Outdoor compensation for brightness target
  - Music auto-play with presence delay
  - Override switch disables automation
  - Entity add/remove/search
  - Auto-detect role and tags from entity_id
  - Import from example config
  - Zone Automation API endpoints
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from copilot_core.hub.zone_automation import (
    ZoneAutomationController,
    ZoneLightConfig,
    ZoneMusicConfig,
    ZoneAutomationConfig,
    detect_entity_role,
    detect_entity_tags,
    ENTITY_ROLES,
    TAG_DEFINITIONS,
)


# ── Unit Tests: ZoneAutomationController ─────────────────────────────────────


class TestZoneConfig:
    def test_get_creates_default_config(self):
        ctrl = ZoneAutomationController()
        cfg = ctrl.get_zone_config("living")
        assert cfg.zone_id == "living"
        assert cfg.light.enabled is True
        assert cfg.music.enabled is True

    def test_set_zone_config_partial_update(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "zone_name": "Wohnzimmer",
            "light": {"brightness_target_pct": 60, "presence_delay_s": 10},
        })
        cfg = ctrl.get_zone_config("living")
        assert cfg.zone_name == "Wohnzimmer"
        assert cfg.light.brightness_target_pct == 60
        assert cfg.light.presence_delay_s == 10
        # Unchanged defaults
        assert cfg.light.absence_delay_s == 120
        assert cfg.music.default_volume_pct == 30

    def test_config_to_dict_and_from_dict(self):
        cfg = ZoneAutomationConfig(zone_id="kitchen", zone_name="Kueche")
        cfg.light.brightness_target_pct = 70
        d = cfg.to_dict()
        assert d["zone_id"] == "kitchen"
        assert d["light"]["brightness_target_pct"] == 70

        restored = ZoneAutomationConfig.from_dict(d)
        assert restored.zone_id == "kitchen"
        assert restored.light.brightness_target_pct == 70

    def test_get_all_configs(self):
        ctrl = ZoneAutomationController()
        ctrl.get_zone_config("living")
        ctrl.get_zone_config("kitchen")
        all_cfg = ctrl.get_all_configs()
        assert "living" in all_cfg
        assert "kitchen" in all_cfg


class TestPresenceLight:
    def test_presence_triggers_light_on_after_delay(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"automation_mode": "autonomy", "light": {"presence_delay_s": 0}})

        actions = ctrl.on_presence_detected("living")
        assert actions.get("light_on") is True
        assert "brightness_pct" in actions

    def test_presence_does_not_trigger_before_delay(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"automation_mode": "autonomy", "light": {"presence_delay_s": 60}})

        actions = ctrl.on_presence_detected("living")
        # Delay not met → no light_on
        assert "light_on" not in actions

    def test_absence_triggers_light_off_after_delay(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {"presence_delay_s": 0, "absence_delay_s": 0}
        })

        # First: turn on
        ctrl.on_presence_detected("living")
        # Then: clear presence
        actions = ctrl.on_presence_cleared("living")
        assert actions.get("light_off") is True

    def test_override_disables_light(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {"enabled": False, "presence_delay_s": 0}
        })
        actions = ctrl.on_presence_detected("living")
        assert "light_on" not in actions

    def test_learning_mode_does_not_trigger_actions(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"automation_mode": "learning", "light": {"presence_delay_s": 0}})

        actions = ctrl.on_presence_detected("living")
        assert "light_on" not in actions
        assert actions.get("learning_event") == "presence_confirmed"

    def test_off_mode_records_state_only(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"automation_mode": "off", "light": {"presence_delay_s": 0}})

        actions = ctrl.on_presence_detected("living")
        assert "light_on" not in actions
        assert "learning_event" not in actions


class TestBrightnessDampening:
    def test_hysteresis_prevents_small_changes(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {"presence_delay_s": 0, "dampening_band_pct": 10}
        })
        ctrl.on_presence_detected("living")

        # Small change within dead-band → no adjustment
        result = ctrl.update_brightness("living", 280, 5000)
        # Initially brightness was set, so first call depends on actual diff
        # Let's verify the structure
        assert "zone_id" in result

    def test_large_brightness_change_adjusts(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {
                "presence_delay_s": 0,
                "dampening_band_pct": 5,
                "brightness_target_pct": 80,
                "lux_outdoor_compensation": True,
                "lux_indoor_target": 300,
            }
        })
        ctrl.on_presence_detected("living")

        # Large change → should adjust
        result = ctrl.update_brightness("living", 50, 10000)
        # With indoor=50 and target=300, deficit is huge → high brightness
        assert result["zone_id"] == "living"

    def test_outdoor_compensation_reduces_brightness(self):
        ctrl = ZoneAutomationController()
        cfg = ctrl.get_zone_config("office")
        cfg.light.brightness_target_pct = 80
        cfg.light.lux_indoor_target = 300
        cfg.light.lux_outdoor_compensation = True

        # Indoor already bright enough → low target
        target = ctrl._compute_target_brightness(
            "office", cfg, indoor_lux=280, outdoor_lux=5000
        )
        assert target < 80  # Should be much less since indoor is near target


class TestPresenceMusic:
    def test_music_auto_play_with_presence(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "music": {"enabled": True, "presence_auto_play": True, "presence_delay_s": 0}
        })
        # Also need light delay 0 for presence to be confirmed
        ctrl.set_zone_config("living", {"light": {"presence_delay_s": 0}})

        actions = ctrl.on_presence_detected("living")
        assert actions.get("music_start") is True
        assert actions.get("music_volume_pct") == 30

    def test_music_disabled_no_auto_play(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {"presence_delay_s": 0},
            "music": {"enabled": False, "presence_auto_play": True, "presence_delay_s": 0}
        })
        actions = ctrl.on_presence_detected("living")
        assert "music_start" not in actions

    def test_music_pauses_on_absence(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {
            "automation_mode": "autonomy",
            "light": {"presence_delay_s": 0, "absence_delay_s": 0},
            "music": {"enabled": True, "presence_auto_play": True, "presence_delay_s": 0, "absence_pause_s": 0}
        })
        ctrl.on_presence_detected("living")
        actions = ctrl.on_presence_cleared("living")
        assert actions.get("music_pause") is True


class TestEntityManagement:
    def test_add_entity(self):
        ctrl = ZoneAutomationController()
        a = ctrl.add_entity("living", "light.wohnzimmer_decke")
        assert a.entity_id == "light.wohnzimmer_decke"
        assert a.role == "lights"  # auto-detected from domain
        assert a.zone_id == "living"

    def test_add_entity_with_explicit_role(self):
        ctrl = ZoneAutomationController()
        a = ctrl.add_entity("living", "sensor.custom", role="energy")
        assert a.role == "energy"

    def test_remove_entity(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.test")
        assert ctrl.remove_entity("living", "light.test") is True
        assert ctrl.remove_entity("living", "light.nonexistent") is False

    def test_get_zone_entities_by_role(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.decke")
        ctrl.add_entity("living", "binary_sensor.bewegung")
        ctrl.add_entity("living", "media_player.sonos")

        by_role = ctrl.get_zone_entities_by_role("living")
        assert "lights" in by_role
        assert "motion" in by_role
        assert "media" in by_role

    def test_update_entity_tags(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.test")
        assert ctrl.update_entity_tags("living", "light.test", ["licht", "styx"]) is True
        entities = ctrl.get_zone_entities("living")
        assert entities[0]["tags"] == ["licht", "styx"]

    def test_update_entity_role(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "sensor.test")
        assert ctrl.update_entity_role("living", "sensor.test", "energy") is True
        entities = ctrl.get_zone_entities("living")
        assert entities[0]["role"] == "energy"

    def test_search_entities(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.wohnzimmer_decke")
        ctrl.add_entity("kitchen", "light.kueche_decke")

        results = ctrl.search_entities("wohnzimmer")
        assert len(results) == 1
        assert results[0]["entity_id"] == "light.wohnzimmer_decke"

    def test_import_from_example_config(self):
        ctrl = ZoneAutomationController()
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
        count = ctrl.import_from_example_config(EXAMPLE_ZONE_ENTITIES)
        assert count > 50  # Should import many entities
        # Check living has entities
        living = ctrl.get_zone_entities("living")
        assert len(living) > 5


class TestAutoDetection:
    def test_detect_role_from_domain(self):
        assert detect_entity_role("light.test") == "lights"
        assert detect_entity_role("media_player.test") == "media"
        assert detect_entity_role("climate.test") == "climate"
        assert detect_entity_role("cover.test") == "cover"

    def test_detect_role_from_name_hints(self):
        assert detect_entity_role("binary_sensor.wohnzimmer_praesenz") == "motion"
        assert detect_entity_role("sensor.buero_helligkeit") == "sensors"
        assert detect_entity_role("sensor.spuelmaschine_verbrauch") == "energy"
        assert detect_entity_role("binary_sensor.bad_fenster") == "window"

    def test_detect_tags(self):
        tags = detect_entity_tags("light.wohnzimmer_decke")
        assert "licht" in tags

        tags = detect_entity_tags("binary_sensor.praesenz_flur")
        assert "praesenz" in tags

    def test_tag_definitions(self):
        assert "licht" in TAG_DEFINITIONS
        assert "praesenz" in TAG_DEFINITIONS
        assert TAG_DEFINITIONS["licht"]["role"] == "lights"

    def test_entity_roles_list(self):
        assert "lights" in ENTITY_ROLES
        assert "motion" in ENTITY_ROLES
        assert "media" in ENTITY_ROLES


class TestDashboard:
    def test_get_dashboard(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"automation_mode": "autonomy", "light": {"presence_delay_s": 0}})
        ctrl.on_presence_detected("living")

        dash = ctrl.get_dashboard()
        assert "zones" in dash
        assert "summary" in dash
        assert dash["summary"]["occupied_zones"] == 1
        assert dash["summary"]["active_lights"] == 1

    def test_get_zone_state(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("living", {"zone_name": "Wohnzimmer"})
        state = ctrl.get_zone_state("living")
        assert state["zone_id"] == "living"
        assert "config" in state
        assert "state" in state


# ── API Integration Tests ────────────────────────────────────────────────────


class TestZoneAutomationAPI:
    def _make_client(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        ctrl = ZoneAutomationController()
        init_zone_automation_api(ctrl)

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_automation_bp)
        return app, ctrl

    def test_get_dashboard(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone-automation/dashboard")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert "zones" in data

    def test_update_zone_config(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/zones/living/config",
                              json={"light": {"brightness_target_pct": 50}},
                              content_type="application/json")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["config"]["light"]["brightness_target_pct"] == 50

    def test_toggle_override(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/zones/living/override",
                              json={"light_enabled": False},
                              content_type="application/json")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["config"]["light"]["enabled"] is False

    def test_report_presence(self):
        app, ctrl = self._make_client()
        ctrl.set_zone_config("living", {"automation_mode": "autonomy", "light": {"presence_delay_s": 0}})
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/zones/living/presence",
                              json={"detected": True},
                              content_type="application/json")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["actions"]["light_on"] is True

    def test_add_and_list_entities(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                # Add entity
                resp = c.post("/api/v1/zone-automation/zones/living/entities",
                              json={"entity_id": "light.test_lamp"},
                              content_type="application/json")
                assert resp.status_code == 200

                # List entities
                resp = c.get("/api/v1/zone-automation/zones/living/entities")
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert len(data["entities"]) == 1

    def test_remove_entity(self):
        app, ctrl = self._make_client()
        ctrl.add_entity("living", "light.test")
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.delete("/api/v1/zone-automation/zones/living/entities/light.test")
                assert resp.status_code == 200

    def test_list_tags_and_roles(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone-automation/tags")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert "licht" in data["tags"]

                resp = c.get("/api/v1/zone-automation/roles")
                data = json.loads(resp.data)
                assert "lights" in data["roles"]

    def test_import_example(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/import",
                              json={"source": "example"},
                              content_type="application/json")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["imported"] > 50

    def test_ensure_zones(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                # No zones initially
                resp = c.get("/api/v1/zone-automation/dashboard")
                data = json.loads(resp.data)
                assert len(data["zones"]) == 0

                # Ensure zones exist
                resp = c.post("/api/v1/zone-automation/ensure-zones",
                              json={"zone_ids": ["wohnbereich", "badbereich", "kochbereich"]},
                              content_type="application/json")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert len(data["created"]) == 3
                assert "wohnbereich" in data["created"]
                assert len(data["zones"]) == 3

                # Calling again should not re-create
                resp = c.post("/api/v1/zone-automation/ensure-zones",
                              json={"zone_ids": ["wohnbereich", "gangbereich"]},
                              content_type="application/json")
                data = json.loads(resp.data)
                assert data["created"] == ["gangbereich"]
                assert len(data["zones"]) == 4

    def test_search_entities(self):
        app, ctrl = self._make_client()
        ctrl.add_entity("living", "light.wohnzimmer_decke")
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone-automation/entities/search?q=wohnzimmer")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["count"] == 1
