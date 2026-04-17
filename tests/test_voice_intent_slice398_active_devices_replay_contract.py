"""Tests for active_devices replay on POST /api/v1/voice/intent (Slice 398)."""
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


class TestActiveDevicesReplay:
    """Slice 398: active_devices replay on double zone-name seam."""

    def test_active_devices_replay_preserves_device_list(self, monkeypatch):
        """active_devices from body context are preserved verbatim in response context."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/intent",
            json={
                "text": "Licht an",
                "context": {
                    "zone_name": "Wohnzimmer",
                    "zone": {"zone_name": "wohnzimmer"},
                    "active_devices": [
                        {
                            "device_name": "wohnzimmer_lampe",
                            "device_type": "light",
                            "state": "on",
                            "attributes": {"brightness": 200},
                        }
                    ],
                    "user_preferences": {"tts_voice": "warm"},
                },
            },
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        ctx = payload["context"]

        # active_devices are preserved verbatim
        active_devices = ctx["active_devices"]
        assert len(active_devices) == 1
        assert active_devices[0]["device_name"] == "wohnzimmer_lampe"
        assert active_devices[0]["device_type"] == "light"
        assert active_devices[0]["state"] == "on"
        assert active_devices[0]["attributes"]["brightness"] == 200

        # user_preferences still works alongside active_devices
        assert ctx["user_preferences"]["tts_voice"] == "warm"

        # zone_name is canonical (lowercase)
        assert ctx["zone_name"] == "wohnzimmer"

    def test_active_devices_replay_empty_list(self, monkeypatch):
        """Empty active_devices list is preserved as empty list."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/intent",
            json={
                "text": "Licht aus",
                "context": {
                    "zone_name": "schlafzimmer",
                    "active_devices": [],
                },
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        ctx = payload["context"]
        assert ctx["active_devices"] == []
        assert ctx["zone_name"] == "schlafzimmer"

    def test_active_devices_without_body_context_uses_built_context(self, monkeypatch):
        """When no context in body, active_devices are built from services (empty in test)."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/intent",
            json={"text": "Status"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        ctx = payload["context"]
        assert "active_devices" in ctx
        assert isinstance(ctx["active_devices"], list)
