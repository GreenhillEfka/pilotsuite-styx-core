"""Tests for status-query context rendering on voice endpoints (Slice 401)."""
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


def _status_request(path: str, client):
    return client.post(
        path,
        json={
            "text": "Status",
            "zone": "wohnzimmer",
            "context": {
                "active_devices": [
                    {"device_name": "Leselampe", "device_type": "light", "state": "on"},
                    {"device_name": "Heizung", "device_type": "climate", "state": "heat"},
                ]
            },
        },
    )


class TestStatusQueryContextRendering:
    def test_voice_intent_status_query_renders_zone_name_and_active_device_names(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = _status_request("/api/v1/voice/intent", client)

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        tts_text = response.get_json()["response"]["tts_text"]
        assert "Zone: wohnzimmer." in tts_text
        assert "Aktive Geräte: Leselampe, Heizung." in tts_text
        assert "ZoneContext(" not in tts_text

    def test_ha_assist_status_query_renders_zone_name_and_active_device_names(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = _status_request("/api/v1/voice/ha/assist", client)

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["source"] == "ha_assist"
        tts_text = payload["response"]["tts_text"]
        assert "Zone: wohnzimmer." in tts_text
        assert "Aktive Geräte: Leselampe, Heizung." in tts_text
        assert "ZoneContext(" not in tts_text
