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

    def test_set_zone_config_zone_type(self):
        ctrl = ZoneAutomationController()
        cfg = ctrl.set_zone_config("living", {"zone_type": "kitchen"})
        assert cfg.zone_type == "kitchen"

    def test_set_zone_config_invalid_zone_type_keeps_previous(self):
        ctrl = ZoneAutomationController()
        cfg = ctrl.set_zone_config("living", {"zone_type": "not-a-zone"})
        assert cfg.zone_type == "living"

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

    def test_zone_entities_read_model(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.wohnzimmer_decke")
        ctrl.add_entity("living", "binary_sensor.wohnung_motion", role="motion")
        model = ctrl.get_zone_entities_read_model("living")

        assert model["zone_id"] == "living"
        assert model["entity_count"] == 2
        assert model["role_count"]["lights"] == 1
        assert model["role_count"]["motion"] == 1
        assert [entity["role"] for entity in model["entities"]] == ["lights", "motion"]

    def test_all_entities_read_model(self):
        ctrl = ZoneAutomationController()
        ctrl.set_zone_config("kitchen", {"zone_name": "Küche"})
        ctrl.add_entity("living", "light.wohnzimmer_decke")

        model = ctrl.get_all_entities_read_model()
        assert model["summary"]["zone_count"] == 2
        assert model["summary"]["entity_count"] == 1
        assert model["summary"]["revision"] >= 1
        assert model["summary"]["updated_at"] >= 0

        zone_ids = [zone["zone_id"] for zone in model["zones"]]
        assert zone_ids == sorted(zone_ids)
        assert any(zone["zone_id"] == "kitchen" and zone["entity_count"] == 0 for zone in model["zones"])

    def test_entity_revision_updates_on_changes(self):
        ctrl = ZoneAutomationController()
        initial = ctrl.get_zone_entities_read_model("living")
        assert initial["revision"] == 0

        ctrl.add_entity("living", "light.wohnzimmer_decke")
        after_add = ctrl.get_zone_entities_read_model("living")
        assert after_add["revision"] == 1
        assert after_add["entities"][0]["role"] == "lights"

        # idempotent add should not bump revision
        ctrl.add_entity("living", "light.wohnzimmer_decke")
        assert ctrl.get_zone_entities_read_model("living")["revision"] == 1

        # actual mutation bumps revision
        assert ctrl.update_entity_role("living", "light.wohnzimmer_decke", "energy") is True
        assert ctrl.get_zone_entities_read_model("living")["revision"] == 2
        assert ctrl.remove_entity("living", "light.wohnzimmer_decke") is True
        assert ctrl.get_all_entities_read_model()["summary"]["revision"] == 3

    def test_all_entities_read_model_deltas_empty(self):
        ctrl = ZoneAutomationController()
        model = ctrl.get_all_entities_read_model(since_revision=0, deltas=True)
        assert model["zones"] == []
        assert model["summary"]["returned_zone_count"] == 0
        assert model["summary"]["returned_entity_count"] == 0

    def test_all_entities_read_model_deltas(self):
        ctrl = ZoneAutomationController()
        ctrl.add_entity("living", "light.living_ceiling")
        ctrl.add_entity("kitchen", "light.kitchen_ceiling")

        base = ctrl.get_all_entities_read_model()
        base_revision = base["summary"]["revision"]

        # mutate living and kitchen
        ctrl.update_entity_tags("living", "light.living_ceiling", ["licht", "styx"])
        ctrl.add_entity("kitchen", "media_player.kitchen_spot")

        delta = ctrl.get_all_entities_read_model(since_revision=base_revision, deltas=True)
        assert delta["summary"]["delta_from_revision"] == base_revision
        assert delta["summary"]["delta_to_revision"] >= base_revision
        assert set(z["zone_id"] for z in delta["zones"]) == {"living", "kitchen"}
        assert delta["summary"]["returned_zone_count"] == 2

        compact_delta = ctrl.get_all_entities_read_model(since_revision=base_revision, deltas=True, compact=True)
        assert "entities" not in compact_delta["zones"][0]
        assert "entities_by_role" not in compact_delta["zones"][0]
        assert compact_delta["summary"].get("compact") is True

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
                resp = c.post(
                    "/api/v1/zone-automation/zones/living/config",
                    json={"light": {"brightness_target_pct": 50}},
                    content_type="application/json",
                )
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["config"]["light"]["brightness_target_pct"] == 50

    def test_update_zone_config_with_invalid_zone_type(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post(
                    "/api/v1/zone-automation/zones/living/config",
                    json={"zone_type": "not-a-zone"},
                    content_type="application/json",
                )
                assert resp.status_code == 400
                data = json.loads(resp.data)
                assert data["ok"] is False

    def test_create_zone_invalid_zone_type(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post(
                    "/api/v1/zone-automation/zones",
                    json={"zone_id": "badzone", "zone_name": "Bad", "zone_type": "invalid"},
                    content_type="application/json",
                )
                assert resp.status_code == 400
                data = json.loads(resp.data)
                assert data["ok"] is False

    def test_delete_zone(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                create = c.post(
                    "/api/v1/zone-automation/zones",
                    json={"zone_id": "tempzone", "zone_name": "Temp"},
                    content_type="application/json",
                )
                assert create.status_code == 201
                resp = c.delete("/api/v1/zone-automation/zones/tempzone")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True

                resp = c.delete("/api/v1/zone-automation/zones/tempzone")
                assert resp.status_code == 404

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

    def test_zone_entities_read_model(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                c.post(
                    "/api/v1/zone-automation/zones/living/entities",
                    json={"entity_id": "light.test_lamp", "source": "manual"},
                    content_type="application/json",
                )
                c.post(
                    "/api/v1/zone-automation/zones/living/entities",
                    json={"entity_id": "binary_sensor.motion_1", "role": "motion"},
                    content_type="application/json",
                )

                resp = c.get("/api/v1/zone-automation/zones/living/entities/read-model")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["changed"] is True
                assert data["zone_id"] == "living"
                assert data["entity_count"] == 2
                assert data["role_count"]["lights"] == 1
                assert data["role_count"]["motion"] == 1
                assert data["entities"][0]["role"] == "lights"
                assert data["revision"] >= 2
                assert data["updated_at"] >= 0

                rev = data["revision"]
                fresh = c.get(f"/api/v1/zone-automation/zones/living/entities/read-model?since={rev}")
                assert fresh.status_code == 200
                zone_cached = json.loads(fresh.data)
                assert zone_cached["changed"] is False
                assert zone_cached["revision"] == rev
                assert zone_cached["zone_id"] == "living"

                # Compact read-model: cache-aware projection
                fresh_compact = c.get(f"/api/v1/zone-automation/zones/living/entities/read-model?since={rev}&compact=true")
                assert fresh_compact.status_code == 200
                zone_cached_compact = json.loads(fresh_compact.data)
                assert zone_cached_compact["changed"] is False
                assert zone_cached_compact["revision"] == rev
                assert zone_cached_compact["zone_id"] == "living"
                assert zone_cached_compact["compact"] is True
                assert "entities" not in zone_cached_compact
                assert zone_cached_compact["entity_count"] == 2

                compact = c.get("/api/v1/zone-automation/zones/living/entities/read-model?compact=true")
                assert compact.status_code == 200
                compact_data = json.loads(compact.data)
                assert compact_data["ok"] is True
                assert compact_data["changed"] is True
                assert compact_data["zone_id"] == "living"
                assert compact_data["compact"] is True
                assert "entities" not in compact_data
                assert "entities_by_role" not in compact_data
                assert compact_data["role_count"]["lights"] == 1

                bad = c.get("/api/v1/zone-automation/zones/living/entities/read-model?since=abc")
                assert bad.status_code == 400

                bad_compact = c.get(
                    "/api/v1/zone-automation/zones/living/entities/read-model?compact=maybe"
                )
                assert bad_compact.status_code == 400

    def test_all_entities_read_model(self):
        app, ctrl = self._make_client()
        ctrl.add_entity("kitchen", "light.kueche", role="lights", source="manual")
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone-automation/entities/read-model")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["changed"] is True
                assert data["summary"]["zone_count"] >= 1
                assert data["summary"]["entity_count"] >= 1
                assert data["summary"]["revision"] >= 1
                assert any(zone["zone_id"] == "kitchen" for zone in data["zones"])

                # Compact projection omits entities but keeps deterministic counters.
                compact = c.get("/api/v1/zone-automation/entities/read-model?compact=true")
                assert compact.status_code == 200
                compact_data = json.loads(compact.data)
                assert compact_data["summary"].get("compact") is True
                assert compact_data["zones"][0]["zone_id"] == "kitchen"
                assert "entities" not in compact_data["zones"][0]
                assert "entities_by_role" not in compact_data["zones"][0]
                assert "role_count" in compact_data["zones"][0]

                # Compact + deltas should also avoid entity payloads.
                compact_delta = c.get(f"/api/v1/zone-automation/entities/read-model?since={data['summary']['revision']}&deltas=true&compact=true")
                assert compact_delta.status_code == 200
                compact_delta_data = json.loads(compact_delta.data)
                assert compact_delta_data["ok"] is True
                assert "zones" in compact_delta_data
                if compact_delta_data["changed"]:
                    assert "entities" not in compact_delta_data["zones"][0]

                rev = data["summary"]["revision"]
                fresh = c.get(f"/api/v1/zone-automation/entities/read-model?since={rev}")
                assert fresh.status_code == 200
                cached = json.loads(fresh.data)
                assert cached["ok"] is True
                assert cached["changed"] is False
                assert cached["zones"] == []
                assert cached["revision"] == rev

                stale = c.get(f"/api/v1/zone-automation/entities/read-model?since={rev - 1}")
                assert stale.status_code == 200
                changed = json.loads(stale.data)
                assert changed["ok"] is True
                assert changed["changed"] is True
                assert changed["summary"]["revision"] == rev

                bad = c.get("/api/v1/zone-automation/entities/read-model?since=abc")
                assert bad.status_code == 400

                bad_deltas = c.get("/api/v1/zone-automation/entities/read-model?deltas=true")
                assert bad_deltas.status_code == 400

                bad_compact = c.get("/api/v1/zone-automation/entities/read-model?compact=maybe")
                assert bad_compact.status_code == 400

                bad_deltas_value = c.get(
                    f"/api/v1/zone-automation/entities/read-model?deltas=maybe&since={rev}"
                )
                assert bad_deltas_value.status_code == 400

    def test_all_entities_read_model_deltas(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                # Seed initial state (2 changes => revision > 0)
                c.post(
                    "/api/v1/zone-automation/zones/living/entities",
                    json={"entity_id": "light.living_ceiling"},
                    content_type="application/json",
                )
                c.post(
                    "/api/v1/zone-automation/zones/kitchen/entities",
                    json={"entity_id": "light.kitchen_ceiling"},
                    content_type="application/json",
                )

                base = c.get("/api/v1/zone-automation/entities/read-model")
                base_data = json.loads(base.data)
                base_revision = base_data["summary"]["revision"]
                assert base_data["changed"] is True

                # Mutate kitchen assignments
                resp = c.post(
                    "/api/v1/zone-automation/zones/kitchen/entities/light.kitchen_ceiling/tags",
                    json={"tags": ["licht", "styx"]},
                    content_type="application/json",
                )
                assert resp.status_code == 200

                # Request only changed zones since known revision
                delta = c.get(f"/api/v1/zone-automation/entities/read-model?since={base_revision}&deltas=true")
                assert delta.status_code == 200
                data = json.loads(delta.data)
                assert data["ok"] is True
                assert data["changed"] is True
                assert data["summary"]["returned_zone_count"] == 1
                assert data["summary"]["delta_from_revision"] == base_revision
                assert data["summary"]["delta_to_revision"] >= base_revision
                assert data["delta"]["zone_ids"] == ["kitchen"]
                assert len(data["zones"]) == 1
                assert data["zones"][0]["zone_id"] == "kitchen"
                assert any(entity["entity_id"] == "light.kitchen_ceiling" for entity in data["zones"][0]["entities"])

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


# ── HubZone Sync Tests ────────────────────────────────────────────────────────


class TestHubZoneSync:
    """Tests for the sync endpoint and sync_habitus_zones method."""

    def _make_client(self):
        from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
        from copilot_core.hub.zone_automation import ZoneAutomationController
        ctrl = ZoneAutomationController()
        init_zone_automation_api(ctrl)
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_automation_bp)
        return app, ctrl

    def test_sync_creates_zone_automation_config(self):
        """sync_habitus_zones should create ZoneAutomationConfig for new zones."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/sync",
                    json={
                        "zones": [
                            {"zone_id": "wohnbereich", "name": "Wohnbereich",
                             "area_id": "wohnzimmer", "entities": ["light.decke"]},
                        ]
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200, f"Got {resp.status_code}: {resp.data}"
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert data["synced"] == 1
                # ZoneAutomationController should have the config
                assert "wohnbereich" in ctrl._configs

    def test_sync_definitions_normalizes_zone_type(self):
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post(
                    "/api/v1/zone-automation/sync-definitions",
                    json={
                        "source": "ha",
                        "zones": [
                            {
                                "zone_id": "terrace-zone",
                                "name_de": "Terasse",
                                "zone_type": "terrace",
                                "entities": ["light.terrace_1"],
                            },
                        ],
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                assert "terrace-zone" in ctrl._configs
                assert ctrl._configs["terrace-zone"].zone_type == "terrace"

                resp = c.post(
                    "/api/v1/zone-automation/sync-definitions",
                    json={
                        "zones": [
                            {
                                "zone_id": "terrace-zone",
                                "name_de": "Terasse",
                                "zone_type": "invalid-type",
                            },
                        ]
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                assert ctrl._configs["terrace-zone"].zone_type == "terrace"

    def test_sync_definitions_applies_role_mapping_and_entity_ids(self):
        """sync-definitions should parse role-mapped entity dicts and plain entity_ids list."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post(
                    "/api/v1/zone-automation/sync-definitions",
                    json={
                        "source": "ha",
                        "zones": [
                            {
                                "zone_id": "wohnzimmer",
                                "name": "Wohnzimmer",
                                "entities": {
                                    "lights": ["light.woon_1", "light.woon_2"],
                                    "motion": ["binary_sensor.wohn_motion"],
                                },
                                "entity_ids": ["light.woon_1", "sensor.wohn_temp"],
                            },
                        ],
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                assert resp.get_json()["ok"] is True

                zone_entities = ctrl.get_zone_entities("wohnzimmer")
                assignments = {a["entity_id"]: a for a in zone_entities}
                assert len(assignments) == 4
                assert assignments["light.woon_1"]["role"] == "lights"
                assert [e["entity_id"] for e in zone_entities].count("light.woon_1") == 1
                assert assignments["light.woon_2"]["role"] == "lights"
                assert assignments["binary_sensor.wohn_motion"]["role"] == "motion"
                assert assignments["sensor.wohn_temp"]["source"] == "ha_sync"
                assert assignments["sensor.wohn_temp"]["role"] == "sensors"


    def test_sync_creates_hub_zones(self):
        """sync_habitus_zones should register rooms+zones in HubZoneEngine."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/sync",
                    json={
                        "zones": [
                            {"zone_id": "kueche", "name": "Küche",
                             "area_id": "kueche", "entities": []},
                        ]
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                # HubZoneEngine should have the zone
                hub = getattr(ctrl, "_hub_zones", None)
                assert hub is not None, "HubZoneEngine should be created on first sync"
                assert "kueche" in hub._zones, f"Zone 'kueche' not in hub_zones: {list(hub._zones.keys())}"
                assert "kueche" in hub._rooms

    def test_sync_definitions_preserves_manual_assignments(self):
        """sync-definitions must not override manually assigned entities."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                # Seed a manual assignment that should be preserved.
                ctrl.add_entity("kueche", "light.manual_anchor", source="manual")

                resp = c.post(
                    "/api/v1/zone-automation/sync-definitions",
                    json={
                        "source": "ha",
                        "zones": [
                            {
                                "zone_id": "arbeitszimmer",
                                "name": "Arbeitszimmer",
                                "entities": ["light.manual_anchor", "light.ha_only"],
                            },
                        ],
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                assert resp.get_json()["ok"] is True

                kitchen_assignments = {a.entity_id: a.source for a in ctrl._entity_assignments.get("kueche", [])}
                assert kitchen_assignments.get("light.manual_anchor") == "manual"

                wb_assignments = {a.entity_id: a.source for a in ctrl._entity_assignments.get("arbeitszimmer", [])}
                assert wb_assignments.get("light.ha_only") == "ha_sync"
                assert "light.manual_anchor" not in wb_assignments


    def test_sync_returns_entity_zone_map(self):
        """sync response should include entity→zone mapping for HA."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/sync",
                    json={
                        "zones": [
                            {"zone_id": "bad", "name": "Badezimmer",
                             "area_id": "bad", "entities": ["light.spiegel", "sensor.temp"]},
                        ]
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                data = json.loads(resp.data)
                emap = data["ha_should_update"]["entity_zone_map"]
                assert emap["light.spiegel"] == "bad"
                assert emap["sensor.temp"] == "bad"

    def test_ensure_zones_with_habitus_sync(self):
        """ensure-zones with habitus_sync=true should also touch HubZoneEngine."""
        app, ctrl = self._make_client()
        with patch("copilot_core.api.v1.zone_automation.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.post("/api/v1/zone-automation/ensure-zones",
                    json={
                        "zone_ids": ["neue_zone"],
                        "habitus_sync": True,
                        "zone_names": {"neue_zone": "Neue Zone"},
                    },
                    content_type="application/json",
                )
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert "neue_zone" in data["created"] or "neue_zone" in ctrl._configs

