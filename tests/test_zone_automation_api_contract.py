"""Zone Automation API Contract Tests — CORE-HARDEN-210"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import zone_automation
from unittest.mock import patch, MagicMock
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(zone_automation.zone_automation_bp)
    return app


def _make_mock_controller():
    """Populate all controller methods with real dict returns."""
    mock = MagicMock()
    mock.is_initialized.return_value = True
    mock.get_dashboard.return_value = {"zones": 1, "automations": 0}
    mock.get_zone_state.return_value = {"zone_id": "wohnzimmer", "mode": "auto", "entities": []}
    mock.set_presence.return_value = {"actions": []}
    mock.on_presence_detected.return_value = [
        {"action": "light.turn_on", "entity": "light.wohnzimmer"},
        {"action": "music.play", "entity": "media_player.wohnzimmer"},
    ]
    mock.on_presence_cleared.return_value = [
        {"action": "light.turn_off", "entity": "light.wohnzimmer"},
        {"action": "music.stop", "entity": "media_player.wohnzimmer"},
    ]
    mock.set_brightness.return_value = {"ok": True}
    mock.set_mood.return_value = {"ok": True}
    mock.set_override.return_value = {"ok": True}
    mock.set_zone_config.return_value.to_dict.return_value = {"light": {"enabled": True}}
    mock.get_zone_entities.return_value = []
    # add_entity returns an Assignment dataclass (serialized via asdict)
    from dataclasses import dataclass
    @dataclass
    class MockAssignment:
        zone_id: str = "wohnzimmer"
        entity_id: str = "light.wohnzimmer"
        role: str = "light"
        tags: list = None
        display_name: str = ""
    mock.add_entity.return_value = MockAssignment()
    mock.remove_entity.return_value = True
    # set_zone_config returns a ZoneConfig with to_dict()
    mock.set_zone_config.return_value.to_dict.return_value = {"light": {"enabled": True}}
    mock.remove_entity_from_zone.return_value = {"ok": True}
    mock.get_zone_mode.return_value = "auto"  # get_automation_mode is called
    mock.get_automation_mode.return_value = "auto"
    mock.set_zone_mode.return_value = {"ok": True}
    mock.get_tags.return_value = []
    mock.get_roles.return_value = []
    mock.get_mood_profiles.return_value = []
    mock.get_module_schemas.return_value = []
    mock.ensure_zones.return_value = {"created": 0}
    mock.import_config.return_value = {"ok": True, "imported": 0}
    mock.search_entities.return_value = []
    # roles / tags require list of dicts
    mock.get_role_definitions.return_value = []
    mock.get_tag_definitions.return_value = []
    # import_config: checks zone_ids field in request body
    # (mock handles this via request.get_json)
    return mock


def _with_auth():
    return patch.object(security, 'validate_token', return_value=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard — optional_token
# ─────────────────────────────────────────────────────────────────────────────


class TestZoneAutomationDashboard:
    """GET /api/v1/zone-automation/dashboard — no auth required."""

    def test_get_dashboard_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/dashboard")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_dashboard_returns_ok_flag(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/dashboard")
            data = r.get_json()
            assert data.get("ok") is True

    def test_get_dashboard_works_without_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/dashboard")
            assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Zone state — optional_token (get_zone_state), require_token (get_zone)
# Note: get_zone_state uses @optional_token; get_zone uses @require_token
# ─────────────────────────────────────────────────────────────────────────────


class TestZoneAutomationZoneState:
    """GET /api/v1/zone-automation/zones/<zone_id>."""

    def test_get_zone_state_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/zones/wohnzimmer")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_zone_state_returns_zone_id(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/zones/wohnzimmer")
            data = r.get_json()
            assert "zone_id" in data or "ok" in data


class TestZoneAutomationPresence:
    """POST /api/v1/zone-automation/zones/<zone_id>/presence."""

    def test_post_presence_detected_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/presence",
                    json={"detected": True},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_presence_cleared_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/presence",
                    json={"detected": False},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_presence_returns_actions(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/presence",
                    json={"detected": True},
                )
                data = r.get_json()
                assert "actions" in data
                actions = {a["action"] for a in data["actions"]}
                assert "light.turn_on" in actions
                assert "music.play" in actions

    def test_post_presence_cleared_returns_light_and_music(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/presence",
                    json={"detected": False},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"
                data = r.get_json()
                actions = {a["action"] for a in data["actions"]}
                assert "light.turn_off" in actions
                assert "music.stop" in actions

    def test_post_presence_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/presence",
                json={"detected": True},
            )
            assert r.status_code in (401, 403)

    def test_post_presence_controller_not_init_returns_503(self):
        app = _make_app()
        with _with_auth():
            with patch.object(zone_automation, '_controller', None):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/presence",
                    json={"detected": True},
                )
                assert r.status_code == 503, f"expected 503, got {r.status_code}"


class TestZoneAutomationBrightness:
    """POST /api/v1/zone-automation/zones/<zone_id>/brightness."""

    def test_post_brightness_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/brightness",
                    json={"brightness": 75},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_brightness_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/brightness",
                json={"brightness": 75},
            )
            assert r.status_code in (401, 403)


class TestZoneAutomationMood:
    """POST /api/v1/zone-automation/zones/<zone_id>/mood."""

    def test_post_mood_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/mood",
                    json={"mood": "focused"},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_mood_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/mood",
                json={"mood": "focused"},
            )
            assert r.status_code in (401, 403)


class TestZoneAutomationOverride:
    """POST /api/v1/zone-automation/zones/<zone_id>/override."""

    def test_post_override_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/override",
                    json={"override": True},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_override_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/override",
                json={"override": True},
            )
            assert r.status_code in (401, 403)


class TestZoneAutomationZoneEntities:
    """Zone entity management endpoints."""

    def test_get_zone_entities_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.get("/api/v1/zone-automation/zones/wohnzimmer/entities")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_zone_entity_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/entities",
                    json={"entity_id": "light.wohnzimmer"},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_delete_zone_entity_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.delete(
                    "/api/v1/zone-automation/zones/wohnzimmer/entities/light.wohnzimmer",
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_zone_entity_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/entities",
                json={"entity_id": "light.wohnzimmer"},
            )
            assert r.status_code in (401, 403)


class TestZoneAutomationZoneMode:
    """GET/POST /api/v1/zone-automation/zones/<zone_id>/mode."""

    def test_get_zone_mode_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.get("/api/v1/zone-automation/zones/wohnzimmer/mode")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_zone_mode_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/mode",
                    json={"mode": "auto"},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_zone_mode_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/zones/wohnzimmer/mode")
            assert r.status_code in (401, 403)


class TestZoneAutomationConfig:
    """POST /api/v1/zone-automation/zones/<zone_id>/config."""

    def test_post_zone_config_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/zones/wohnzimmer/config",
                    json={"light_level": 80, "music_volume": 40},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_zone_config_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/zones/wohnzimmer/config",
                json={"light_level": 80},
            )
            assert r.status_code in (401, 403)


class TestZoneAutomationTagsRoles:
    """GET tags/roles — optional_token, no auth needed."""

    def test_get_tags_returns_200_no_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/tags")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_roles_returns_200_no_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/roles")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_mood_profiles_returns_200_no_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.get("/api/v1/zone-automation/mood-profiles")
            assert r.status_code == 200, f"expected 200, got {r.status_code}"


class TestZoneAutomationImport:
    """POST /api/v1/zone-automation/import."""

    def test_post_import_returns_200(self):
        app = _make_app()
        mock = _make_mock_controller()
        mock.import_from_example_config.return_value = 5
        with _with_auth():
            with patch.object(zone_automation, '_controller', mock):
                client = app.test_client()
                r = client.post(
                    "/api/v1/zone-automation/import",
                    json={"source": "example"},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_import_requires_auth(self):
        app = _make_app()
        mock = _make_mock_controller()
        with patch.object(zone_automation, '_controller', mock):
            client = app.test_client()
            r = client.post(
                "/api/v1/zone-automation/import",
                json={"zones": []},
            )
            assert r.status_code in (401, 403)
