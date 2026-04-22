"""Mood API Contract Tests — CORE-HARDEN-211"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.mood import bp as mood_bp
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────

_AUTH_TOKEN = "test-token-mood"

def _with_auth():
    return patch("copilot_core.api.v1.mood._validate_token", return_value=True)

def _auth_headers():
    return {"Authorization": f"Bearer {_AUTH_TOKEN}"}

def _make_app():
    app = Flask(__name__)
    app.register_blueprint(mood_bp)
    return app


# ── MoodScore dataclass matching copilot_core.mood.scoring.MoodScore ────────

class MockMoodScore:
    def __init__(self, **kwargs):
        self.overall = kwargs.get("overall", 0.6)
        self.energy = kwargs.get("energy", 0.5)
        self.comfort = kwargs.get("comfort", 0.7)
        self.productivity = kwargs.get("productivity", 0.6)
        self.trend = kwargs.get("trend", "stable")

    def to_dict(self):
        return {
            "overall": self.overall,
            "energy": self.energy,
            "comfort": self.comfort,
            "productivity": self.productivity,
            "trend": self.trend,
        }

def _mock_scorer():
    scorer = MagicMock()
    scorer.score_from_events.return_value = MockMoodScore()
    return scorer

# Sentinel so to_dict() returns a real dict, not a MagicMock
_MOCK_MOOD_SCORE = MockMoodScore()


def _mock_scorer_with_score(**kwargs):
    scorer = MagicMock()
    scorer.score_from_events.return_value = MockMoodScore(**kwargs)
    return scorer

def _mock_orchestrator(zone_name="wohnzimmer", mood="focused"):
    mock = MagicMock()
    mock.orchestrate_zone.return_value = MagicMock(to_dict=lambda: {"mood": mood, "actions_executed": 0})
    mock.force_mood.return_value = True
    mock.get_zone_status.return_value = {"zone_name": zone_name, "mood_score": 0.7, "mood": mood}
    mock.get_all_zones_status.return_value = [
        {"zone_name": "wohnzimmer", "mood_score": 0.7},
        {"zone_name": "schlafzimmer", "mood_score": 0.4},
    ]
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Mood root — GET /mood/
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodRoot:
    """GET /mood/ — returns zone mood data."""

    def test_get_mood_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.get("/mood/", headers=_auth_headers())
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_mood_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.get("/mood/", headers=_auth_headers())
                    data = r.get_json()
                    assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_mood_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.api.v1.mood._scorer", _mock_scorer()):
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                client = app.test_client()
                r = client.get("/mood/")
                assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Score — POST /mood/score
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodScore:
    """POST /mood/score — compute mood from events."""

    def test_post_score_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.post("/mood/score", headers=_auth_headers(), json={})
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_score_with_events_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.post(
                        "/mood/score",
                        headers=_auth_headers(),
                        json={"events": [{"type": "presence", "state": "home"}]},
                    )
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_score_returns_mood_key(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.post("/mood/score", headers=_auth_headers(), json={})
                    data = r.get_json()
                    assert "mood" in data, f"'mood' key missing from response: {data}"

    def test_post_score_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.api.v1.mood._scorer", _mock_scorer()):
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                client = app.test_client()
                r = client.post("/mood/score", json={})
                assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# State — GET /mood/state
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodState:
    """GET /mood/state — mood with presence/weather context."""

    def test_get_state_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.get("/mood/state", headers=_auth_headers())
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_state_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._scorer") as mock_scorer:
                mock_scorer.return_value.score_from_events.return_value = _MOCK_MOOD_SCORE
                with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                    client = app.test_client()
                    r = client.get("/mood/state", headers=_auth_headers())
                    data = r.get_json()
                    assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_state_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.api.v1.mood._scorer", _mock_scorer()):
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                client = app.test_client()
                r = client.get("/mood/state")
                assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zone orchestrate — POST /mood/zones/<zone_name>/orchestrate
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodZoneOrchestrate:
    """POST /mood/zones/<zone_name>/orchestrate."""

    def test_post_orchestrate_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                    client = app.test_client()
                    r = client.post("/mood/zones/wohnzimmer/orchestrate", headers=_auth_headers(), json={})
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_orchestrate_with_sensor_data_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                    client = app.test_client()
                    r = client.post(
                        "/mood/zones/wohnzimmer/orchestrate",
                        headers=_auth_headers(),
                        json={"sensor_data": {"light.living_room": "on"}, "dry_run": True},
                    )
                    assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_orchestrate_invalid_zone_name_returns_400(self):
        """Names matching zone_name pattern are accepted; invalid patterns return 400."""
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
                with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                    client = app.test_client()
                    # space in name — fails ^[_a-zA-Z0-9-]+$
                    r = client.post("/mood/zones/bad%20name/orchestrate", headers=_auth_headers(), json={})
                    assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_orchestrate_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.api.v1.mood._event_store_if_available", return_value=None):
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.post("/mood/zones/wohnzimmer/orchestrate", json={})
                assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zone force_mood — POST /mood/zones/<zone_name>/force_mood
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodZoneForceMood:
    """POST /mood/zones/<zone_name>/force_mood."""

    def test_post_force_mood_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.post(
                    "/mood/zones/wohnzimmer/force_mood",
                    headers=_auth_headers(),
                    json={"mood": "relaxed"},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_force_mood_with_duration_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.post(
                    "/mood/zones/wohnzimmer/force_mood",
                    headers=_auth_headers(),
                    json={"mood": "relaxed", "duration_minutes": 60},
                )
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_force_mood_missing_mood_returns_400(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.post("/mood/zones/wohnzimmer/force_mood", headers=_auth_headers(), json={})
                assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_force_mood_invalid_duration_returns_400(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.post(
                    "/mood/zones/wohnzimmer/force_mood",
                    headers=_auth_headers(),
                    json={"mood": "relaxed", "duration_minutes": 9999},
                )
                assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_force_mood_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
            client = app.test_client()
            r = client.post("/mood/zones/wohnzimmer/force_mood", json={"mood": "relaxed"})
            assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zone status — GET /mood/zones/<zone_name>/status
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodZoneStatus:
    """GET /mood/zones/<zone_name>/status."""

    def test_get_zone_status_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/zones/wohnzimmer/status", headers=_auth_headers())
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_zone_status_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/zones/wohnzimmer/status", headers=_auth_headers())
                data = r.get_json()
                assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_zone_status_not_found_returns_404(self):
        app = _make_app()
        mock = MagicMock()
        mock.get_zone_status.return_value = None
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=mock):
                client = app.test_client()
                r = client.get("/mood/zones/unknown/status", headers=_auth_headers())
                assert r.status_code == 404, f"expected 404, got {r.status_code} / {r.get_json()}"

    def test_get_zone_status_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
            client = app.test_client()
            r = client.get("/mood/zones/wohnzimmer/status")
            assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# All zones status — GET /mood/zones/status
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodAllZonesStatus:
    """GET /mood/zones/status."""

    def test_get_all_zones_status_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/zones/status", headers=_auth_headers())
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_all_zones_status_returns_zones_list(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/zones/status", headers=_auth_headers())
                data = r.get_json()
                assert "zones" in data, f"'zones' key missing from response: {data}"

    def test_get_all_zones_status_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
            client = app.test_client()
            r = client.get("/mood/zones/status")
            assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Aggregated — GET /mood/aggregated
# ─────────────────────────────────────────────────────────────────────────────

class TestMoodAggregated:
    """GET /mood/aggregated."""

    def test_get_aggregated_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/aggregated", headers=_auth_headers())
                assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_aggregated_returns_overall_score(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
                client = app.test_client()
                r = client.get("/mood/aggregated", headers=_auth_headers())
                data = r.get_json()
                agg = data.get("aggregated", {})
                assert "overall_score" in agg, f"'overall_score' missing from aggregated: {agg}"

    def test_get_aggregated_requires_auth(self):
        app = _make_app()
        with patch("copilot_core.mood.orchestrator.MoodOrchestrator", return_value=_mock_orchestrator()):
            client = app.test_client()
            r = client.get("/mood/aggregated")
            assert r.status_code == 401, f"expected 401, got {r.status_code}"
