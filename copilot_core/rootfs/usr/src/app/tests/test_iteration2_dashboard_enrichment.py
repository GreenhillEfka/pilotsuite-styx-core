"""Tests for Iteration 2: Dashboard enrichment, zone detail, cross-module links.

Tests:
  - Zone dashboard enrichment with example entities
  - Dashboard payload includes entity details
  - Suggestions API state management
  - Media play/pause/volume endpoints
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


# ── Zone Dashboard Enrichment ────────────────────────────────────

class TestZoneDashboardEnrichment:
    def test_zone_dashboard_enriches_with_example_entities(self):
        """Zone dashboard should enrich zones with example entity data."""
        from copilot_core.api.v1.zone_dashboard import zone_dashboard_bp

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_dashboard_bp)

        with patch("copilot_core.api.v1.zone_dashboard.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone/dashboard")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                zones = data.get("zones", [])
                if zones:
                    # At least some zones should have entity counts
                    z = zones[0]
                    assert "entity_counts" in z or "entity_count" in z or "entities_by_domain" in z

    def test_zone_dashboard_summary_endpoint(self):
        from copilot_core.api.v1.zone_dashboard import zone_dashboard_bp

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(zone_dashboard_bp)

        with patch("copilot_core.api.v1.zone_dashboard.require_token", lambda f: f):
            with app.test_client() as c:
                resp = c.get("/api/v1/zone/dashboard/summary")
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data["ok"] is True
                summary = data.get("summary", data)
                assert "total_zones" in summary
                assert "total_entities" in summary


# ── Suggestions State Management ─────────────────────────────────

class TestSuggestionsStateMgmt:
    def _make_client(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        from copilot_core.api.v1.suggestions import suggestions_bp, _suggestion_states
        _suggestion_states.clear()
        app.register_blueprint(suggestions_bp)
        return app

    def test_accept_then_list_excludes(self):
        with patch("copilot_core.api.v1.suggestions.require_token", lambda f: f):
            app = self._make_client()
            with app.test_client() as c:
                # Accept
                c.post("/api/v1/suggestions/accept", json={"id": "sug_morning_kitchen"})
                # List
                resp = c.get("/api/v1/suggestions")
                data = json.loads(resp.data)
                ids = [s["id"] for s in data["suggestions"]]
                assert "sug_morning_kitchen" not in ids

    def test_reject_then_list_excludes(self):
        with patch("copilot_core.api.v1.suggestions.require_token", lambda f: f):
            app = self._make_client()
            with app.test_client() as c:
                c.post("/api/v1/suggestions/reject", json={"id": "sug_tv_dimm"})
                resp = c.get("/api/v1/suggestions")
                data = json.loads(resp.data)
                ids = [s["id"] for s in data["suggestions"]]
                assert "sug_tv_dimm" not in ids

    def test_snooze_does_not_exclude(self):
        with patch("copilot_core.api.v1.suggestions.require_token", lambda f: f):
            app = self._make_client()
            with app.test_client() as c:
                c.post("/api/v1/suggestions/snooze", json={"id": "sug_nobody_home"})
                resp = c.get("/api/v1/suggestions")
                data = json.loads(resp.data)
                ids = [s["id"] for s in data["suggestions"]]
                # Snoozed items should still be in the list
                assert "sug_nobody_home" in ids


# ── Media Play/Pause/Volume ──────────────────────────────────────

class TestMediaPlayPauseVolume:
    @pytest.fixture
    def mock_mgr(self):
        mgr = MagicMock()
        mgr.get_all_assignments.return_value = {"living": ["media_player.sonos_wohnzimmer"]}
        mgr.play_zone.return_value = None
        mgr.pause_zone.return_value = None
        mgr.set_zone_volume.return_value = None
        return mgr

    @pytest.fixture
    def client(self, mock_mgr):
        from copilot_core.api.rate_limit import RateLimiter
        permissive = RateLimiter(default_limits={}, default_period=1)
        with patch("copilot_core.api.v1.media_zones.require_token", lambda f: f):
            with patch("copilot_core.api.rate_limit.get_rate_limiter", return_value=permissive):
                app = Flask(__name__)
                app.config["TESTING"] = True
                from copilot_core.api.v1.media_zones import media_zones_bp, init_media_zones_api
                init_media_zones_api(mock_mgr, MagicMock())
                app.register_blueprint(media_zones_bp, url_prefix="/api/v1")
                with app.test_client() as c:
                    yield c

    def test_play_zone(self, client, mock_mgr):
        resp = client.post("/api/v1/zones/living/play")
        assert resp.status_code == 200
        mock_mgr.play_zone.assert_called_once_with("living")

    def test_pause_zone(self, client, mock_mgr):
        resp = client.post("/api/v1/zones/living/pause")
        assert resp.status_code == 200
        mock_mgr.pause_zone.assert_called_once_with("living")

    def test_set_volume(self, client, mock_mgr):
        resp = client.post("/api/v1/zones/living/volume", json={"volume": 0.5})
        assert resp.status_code == 200
        mock_mgr.set_zone_volume.assert_called_once_with("living", 0.5)

    def test_set_volume_invalid(self, client):
        resp = client.post("/api/v1/zones/living/volume", json={"volume": 1.5})
        assert resp.status_code == 400

    def test_set_volume_missing(self, client):
        resp = client.post("/api/v1/zones/living/volume", json={})
        assert resp.status_code == 400


# ── Dashboard Payload Completeness ───────────────────────────────

class TestDashboardPayloadIteration2:
    def test_dashboard_zones_have_priority(self):
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
                    for z in zones:
                        assert "priority" in z
                        assert "roles" in z

    def test_dashboard_suggestions_have_pattern(self):
        from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api

        app = Flask(__name__)
        app.config["TESTING"] = True
        init_styx_dashboard_api({})
        app.register_blueprint(styx_dashboard_bp)

        with patch("copilot_core.api.v1.styx_dashboard.validate_token", return_value=True):
            with app.test_client() as c:
                resp = c.get("/api/v1/styx/dashboard")
                data = json.loads(resp.data)
                suggestions = data.get("suggestions", [])
                if suggestions:
                    for s in suggestions:
                        assert "pattern" in s
                        assert "confidence" in s
