"""Contract tests for request-replayed voice context cache isolation (CORE-STRUCT-102A)."""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402
from copilot_core.voice.context_builder import VoiceContextBuilder  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


def test_context_builder_does_not_cache_replayed_user_preferences_between_requests():
    builder = VoiceContextBuilder()

    first = builder.build_context(
        zone_name="wohnzimmer",
        user_preferences={"preferred_language": "EN", "tts_voice": "warm"},
    )
    second = builder.build_context(
        zone_name="wohnzimmer",
        user_preferences={"preferred_language": "DE", "tts_voice": "calm"},
    )

    assert first is not second
    assert first.language_preference == "en"
    assert second.language_preference == "de"
    assert second.user_preferences == {"preferred_language": "DE", "tts_voice": "calm"}


def test_context_builder_does_not_cache_replayed_active_devices_between_requests():
    builder = VoiceContextBuilder()

    first = builder.build_context(
        zone_name="wohnzimmer",
        active_devices=[
            {
                "device_name": "wohnzimmer_lampe",
                "device_type": "light",
                "state": "on",
                "attributes": {"brightness": 200},
            }
        ],
    )
    second = builder.build_context(
        zone_name="wohnzimmer",
        active_devices=[],
    )

    assert len(first.active_devices) == 1
    assert first.active_devices[0].device_name == "wohnzimmer_lampe"
    assert second.active_devices == []


def test_voice_intent_does_not_leak_replayed_context_across_same_zone_requests(monkeypatch):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    app = _make_app()
    client = app.test_client()

    first_response = client.post(
        "/api/v1/voice/intent",
        json={
            "text": "Status",
            "context": {
                "zone": {"zone_name": "Wohnzimmer"},
                "user_preferences": {"preferred_language": "EN", "tts_voice": "warm"},
                "active_devices": [
                    {
                        "device_name": "wohnzimmer_lampe",
                        "device_type": "light",
                        "state": "on",
                        "attributes": {"brightness": 200},
                    }
                ],
            },
        },
    )

    second_response = client.post(
        "/api/v1/voice/intent",
        json={
            "text": "Status",
            "context": {
                "zone": {"zone_name": "Wohnzimmer"},
                "user_preferences": {"preferred_language": "DE"},
                "active_devices": [],
            },
        },
    )

    assert first_response.status_code == 200, first_response.get_data(as_text=True)
    assert second_response.status_code == 200, second_response.get_data(as_text=True)

    first_context = first_response.get_json()["context"]
    second_context = second_response.get_json()["context"]

    assert first_context["language_preference"] == "en"
    assert len(first_context["active_devices"]) == 1
    assert second_context["language_preference"] == "de"
    assert second_context["user_preferences"] == {"preferred_language": "DE"}
    assert second_context["active_devices"] == []
