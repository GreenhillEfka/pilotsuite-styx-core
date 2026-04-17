"""Tests for replayed language preference parity on voice endpoints (Slice 402)."""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


def _request(path: str, client, user_preferences: dict):
    return client.post(
        path,
        json={
            "text": "Status",
            "context": {
                "zone": {"zone_name": "Wohnzimmer"},
                "user_preferences": user_preferences,
            },
        },
    )


class TestReplayedLanguagePreferenceParity:
    def test_voice_intent_uses_preferred_language_when_language_key_is_absent(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = _request(
            "/api/v1/voice/intent",
            client,
            {"preferred_language": "EN", "tts_voice": "warm"},
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["context"]["language_preference"] == "en"
        assert payload["context"]["user_preferences"]["preferred_language"] == "EN"

    def test_ha_assist_uses_preferred_language_when_language_key_is_absent(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = _request(
            "/api/v1/voice/ha/assist",
            client,
            {"preferred_language": "EN", "tts_voice": "warm"},
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["source"] == "ha_assist"
        assert payload["context"]["language_preference"] == "en"
        assert payload["context"]["user_preferences"]["preferred_language"] == "EN"

    def test_explicit_language_still_wins_over_preferred_language(self, monkeypatch):
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = _request(
            "/api/v1/voice/intent",
            client,
            {"language": "de", "preferred_language": "EN"},
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["context"]["language_preference"] == "de"
