"""Tests for Iteration 1: Zones, Musikwolke, Suggestions dashboard integration.

Tests:
  - Styx dashboard returns zones, media, suggestions data
  - Suggestions API (accept, reject, snooze, list)
  - Media zones group/ungroup endpoints
  - Example config structure
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


# ── Example Config Tests ─────────────────────────────────────────

class TestExampleConfig:
    def test_example_config_structure(self):
        from copilot_core.example_config import get_example_config
        cfg = get_example_config()
        assert "zones" in cfg
        assert "sonos_players" in cfg
        assert "suggestions" in cfg
        assert "zone_display" in cfg
        assert cfg["total_zones"] == 10

    def test_zone_entities_has_all_zones(self):
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
        expected = {"living", "kitchen", "bath", "hallway", "bedroom",
                    "office", "room_mira", "room_paul", "terrace", "outside"}
        assert set(EXAMPLE_ZONE_ENTITIES.keys()) == expected

    def test_zone_entities_have_lights(self):
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
        for zone_id, roles in EXAMPLE_ZONE_ENTITIES.items():
            assert "lights" in roles, f"{zone_id} missing lights"
            assert len(roles["lights"]) > 0

    def test_sonos_players_map(self):
        from copilot_core.example_config import EXAMPLE_SONOS_PLAYERS
        assert "living" in EXAMPLE_SONOS_PLAYERS
        assert "primary" in EXAMPLE_SONOS_PLAYERS["living"]
        assert EXAMPLE_SONOS_PLAYERS["living"]["primary"] == "media_player.sonos_wohnzimmer"

    def test_example_suggestions_structure(self):
        from copilot_core.example_config import EXAMPLE_SUGGESTIONS
        assert len(EXAMPLE_SUGGESTIONS) >= 5
        for s in EXAMPLE_SUGGESTIONS:
            assert "id" in s
            assert "title" in s
            assert "confidence" in s
            assert 0 <= s["confidence"] <= 1

    def test_zone_display_metadata(self):
        from copilot_core.example_config import ZONE_DISPLAY
        assert len(ZONE_DISPLAY) == 10
        for zid, meta in ZONE_DISPLAY.items():
            assert "icon" in meta
            assert "color" in meta
            assert "name_de" in meta


# ── Suggestions API Tests ────────────────────────────────────────

def _make_suggestions_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    from copilot_core.api.v1.suggestions import suggestions_bp
    app.register_blueprint(suggestions_bp)
    return app


@pytest.fixture
def sug_client():
    import copilot_core.api.v1.suggestions as _sug_mod
    # Reset module-level state to prevent cross-test leaking
    old_engine = _sug_mod._suggestion_engine
    old_states = _sug_mod._suggestion_states.copy()
    _sug_mod._suggestion_engine = None
    _sug_mod._suggestion_states.clear()
    with patch("copilot_core.api.v1.suggestions.require_token", lambda f: f):
        app = _make_suggestions_app()
        with app.test_client() as c:
            yield c
    # Restore
    _sug_mod._suggestion_engine = old_engine
    _sug_mod._suggestion_states.clear()
    _sug_mod._suggestion_states.update(old_states)


class TestSuggestionsAPI:
    def test_list_suggestions(self, sug_client):
        resp = sug_client.get("/api/v1/suggestions")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0

    def test_accept_suggestion(self, sug_client):
        resp = sug_client.post(
            "/api/v1/suggestions/accept",
            json={"id": "sug_morning_kitchen"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["status"] == "accepted"

    def test_reject_suggestion(self, sug_client):
        resp = sug_client.post(
            "/api/v1/suggestions/reject",
            json={"id": "sug_tv_dimm"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["status"] == "rejected"

    def test_snooze_suggestion(self, sug_client):
        resp = sug_client.post(
            "/api/v1/suggestions/snooze",
            json={"id": "sug_nobody_home"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["status"] == "snoozed"

    def test_accept_missing_id(self, sug_client):
        resp = sug_client.post("/api/v1/suggestions/accept", json={})
        assert resp.status_code == 400

    def test_reject_missing_id(self, sug_client):
        resp = sug_client.post("/api/v1/suggestions/reject", json={})
        assert resp.status_code == 400

    def test_snooze_missing_id(self, sug_client):
        resp = sug_client.post("/api/v1/suggestions/snooze", json={})
        assert resp.status_code == 400

    def test_accepted_filtered_from_list(self, sug_client):
        # Accept a suggestion
        sug_client.post(
            "/api/v1/suggestions/accept",
            json={"id": "sug_solar_dishwasher"},
        )
        # List should not include it
        resp = sug_client.get("/api/v1/suggestions")
        data = json.loads(resp.data)
        ids = [s["id"] for s in data["suggestions"]]
        assert "sug_solar_dishwasher" not in ids


# ── Media Group/Ungroup API Tests ────────────────────────────────

def _make_media_app(mock_mgr):
    app = Flask(__name__)
    app.config["TESTING"] = True
    from copilot_core.api.v1.media_zones import media_zones_bp, init_media_zones_api
    init_media_zones_api(mock_mgr, MagicMock())
    app.register_blueprint(media_zones_bp, url_prefix="/api/v1")
    return app


@pytest.fixture
def mock_media_mgr():
    mgr = MagicMock()
    mgr.get_all_assignments.return_value = {
        "living": ["media_player.sonos_wohnzimmer"],
        "kitchen": ["media_player.sonos_kueche"],
    }
    mgr.group_zone_players.return_value = None
    mgr.ungroup_zone_players.return_value = None
    mgr.group_multi_zone.return_value = None
    return mgr


@pytest.fixture
def media_client(mock_media_mgr):
    from copilot_core.api.rate_limit import RateLimiter
    permissive = RateLimiter(default_limits={}, default_period=1)
    permissive._limits = {}  # no limits
    with patch("copilot_core.api.v1.media_zones.require_token", lambda f: f):
        with patch("copilot_core.api.rate_limit.get_rate_limiter", return_value=permissive):
            app = _make_media_app(mock_media_mgr)
            with app.test_client() as c:
                yield c


class TestMediaGroupUngroup:
    def test_group_zone(self, media_client, mock_media_mgr):
        resp = media_client.post(
            "/api/v1/zones/group",
            json={"zone_id": "living"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["action"] == "group"
        mock_media_mgr.group_zone_players.assert_called_once_with("living")

    def test_ungroup_zone(self, media_client, mock_media_mgr):
        resp = media_client.post(
            "/api/v1/zones/ungroup",
            json={"zone_id": "living"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["action"] == "ungroup"
        mock_media_mgr.ungroup_zone_players.assert_called_once_with("living")

    def test_group_missing_zone_id(self, media_client):
        resp = media_client.post(
            "/api/v1/zones/group",
            json={},
        )
        assert resp.status_code == 400

    def test_group_invalid_zone_id(self, media_client):
        resp = media_client.post(
            "/api/v1/zones/group",
            json={"zone_id": "invalid zone!!"},
        )
        assert resp.status_code == 400

    def test_group_all(self, media_client, mock_media_mgr):
        resp = media_client.post(
            "/api/v1/zones/group-all",
            json={},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["action"] == "group-all"
        mock_media_mgr.group_multi_zone.assert_called_once()

    def test_ungroup_all(self, media_client, mock_media_mgr):
        resp = media_client.post(
            "/api/v1/zones/ungroup-all",
            json={},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["action"] == "ungroup-all"

    def test_group_zone_error(self, media_client, mock_media_mgr):
        mock_media_mgr.group_zone_players.side_effect = RuntimeError("Sonos offline")
        resp = media_client.post(
            "/api/v1/zones/group",
            json={"zone_id": "living"},
        )
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert data["ok"] is False


# ── Styx Dashboard Zones/Media/Suggestions ───────────────────────

class TestDashboardPayload:
    def test_dashboard_includes_zones(self):
        from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api

        app = Flask(__name__)
        app.config["TESTING"] = True
        init_styx_dashboard_api({})
        app.register_blueprint(styx_dashboard_bp)

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                assert "zones" in data
                assert "media" in data
                assert "suggestions" in data

    def test_dashboard_zones_have_structure(self):
        from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api

        app = Flask(__name__)
        app.config["TESTING"] = True
        init_styx_dashboard_api({})
        app.register_blueprint(styx_dashboard_bp)

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                data = json.loads(resp.data)
                zones = data.get("zones", [])
                if zones:
                    z = zones[0]
                    assert "id" in z
                    assert "name_de" in z
                    assert "icon" in z
                    assert "color" in z
                    assert "entity_count" in z
                    assert "roles" in z

    def test_dashboard_suggestions_fallback(self):
        from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api

        app = Flask(__name__)
        app.config["TESTING"] = True
        init_styx_dashboard_api({})  # no suggestion_engine
        app.register_blueprint(styx_dashboard_bp)

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                data = json.loads(resp.data)
                suggestions = data.get("suggestions", [])
                assert len(suggestions) >= 5  # fallback to EXAMPLE_SUGGESTIONS
