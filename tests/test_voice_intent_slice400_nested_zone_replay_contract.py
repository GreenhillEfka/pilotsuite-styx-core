"""Tests for nested context.zone.zone_name replay fallback on POST /api/v1/voice/intent (Slice 400)."""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


class TestNestedZoneReplayFallback:
    """Slice 400: nested zone replay fallback resolves canonical zone authority."""

    def test_voice_intent_uses_nested_context_zone_name_when_top_level_zone_missing(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/intent",
            json={
                "text": "Status",
                "context": {
                    "zone": {"zone_name": "Schlafzimmer"},
                    "active_devices": [],
                },
            },
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["context"]["zone_name"] == "schlafzimmer"
        assert payload["context"]["zone"]["zone_name"] == "schlafzimmer"

    def test_voice_intent_prefers_context_zone_name_over_nested_zone_name(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/intent",
            json={
                "text": "Status",
                "context": {
                    "zone_name": "Kueche",
                    "zone": {"zone_name": "Schlafzimmer"},
                },
            },
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["context"]["zone_name"] == "kueche"
        assert payload["context"]["zone"]["zone_name"] == "kueche"
