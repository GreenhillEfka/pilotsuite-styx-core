"""Tests for HA Assist bridge on POST /api/v1/voice/ha/assist (Slice 399)."""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402
from copilot_core.voice.dialog_state import DialogStateMachine  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


def _isolated_dialog_machine(tmp_path):
    machine = DialogStateMachine(data_dir=str(tmp_path / "dialog-data"))
    machine.reset()
    return machine


class TestHAAssistBridge:
    """Slice 399: HA Assist bridge endpoint."""

    def test_ha_assist_accepts_text_field(self, monkeypatch):
        """HA Assist sends 'text' field — endpoint accepts and processes it."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={
                "text": "Mach das Licht an",
                "language": "de",
                "zone": "wohnzimmer",
            },
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["status"] == "ok"
        assert "intent" in payload
        assert "response" in payload
        assert "context" in payload
        assert payload.get("source") == "ha_assist"

    def test_ha_assist_accepts_sentence_field(self, monkeypatch):
        """HA Assist may send 'sentence' field as alias for 'text'."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={
                "sentence": "Licht einschalten",
                "zone": "schlafzimmer",
            },
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["status"] == "ok"
        assert payload.get("source") == "ha_assist"

    def test_ha_assist_rejects_empty_request(self, monkeypatch):
        """Missing both 'text' and 'sentence' returns 400."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={},
        )

        assert response.status_code == 400
        payload = response.get_json()
        assert "text" in payload["message"].lower() or "sentence" in payload["message"].lower()

    def test_ha_assist_with_context_replay(self, monkeypatch):
        """HA Assist with context replay works like process_intent()."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={
                "text": "Nochmal",
                "context": {
                    "zone_name": "wohnzimmer",
                    "active_devices": [
                        {"device_name": "lampe", "device_type": "light", "state": "on", "attributes": {}}
                    ],
                    "user_preferences": {"tts_voice": "warm"},
                },
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        ctx = payload["context"]
        assert ctx["zone_name"] == "wohnzimmer"
        assert len(ctx["active_devices"]) == 1
        assert ctx["active_devices"][0]["device_name"] == "lampe"
        assert ctx["user_preferences"]["tts_voice"] == "warm"

    def test_ha_assist_zone_canonicalization(self, monkeypatch):
        """HA Assist zone names are canonicalized to lowercase."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={
                "text": "Status",
                "zone": "Wohnzimmer",
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        # zone_name canonicalized in context
        assert payload["context"]["zone_name"] == "wohnzimmer"

    def test_ha_assist_replays_nested_context_zone_name_without_top_level_zone(self, monkeypatch):
        """Nested replayed context.zone.zone_name is used when top-level zone is absent."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
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

    def test_ha_assist_prefers_explicit_zone_name_over_nested_replayed_zone_name(self, monkeypatch):
        """Explicit replayed context.zone_name stays authoritative over nested zone.zone_name."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
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

    def test_language_preference_from_user_preferences_propagates_to_response(self, monkeypatch):
        """preferred_language in user_preferences overrides response.language."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/voice/ha/assist",
            json={
                "text": "Status",
                "context": {
                    "zone_name": "wohnzimmer",
                    "user_preferences": {"preferred_language": "en"},
                },
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        # context.language_preference should reflect the preferred_language
        assert payload["context"]["language_preference"] == "en"
        # response.language should honor context.language_preference
        assert payload["response"]["language"] == "en"

    def test_command_state_surface_exposes_ha_bridge_field_projection(self, monkeypatch, tmp_path):
        """The HA bridge can bind to a thin command-state surface without slot introspection."""
        monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
        machine = _isolated_dialog_machine(tmp_path)
        monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)
        app = _make_app()
        client = app.test_client()

        client.post(
            "/api/v1/voice/command",
            json={
                "session_id": "sess-ha-bridge-state",
                "utterance": "Garage öffnen",
                "confidence": 0.93,
            },
        )

        response = client.get(
            "/api/v1/voice/command/state",
            query_string={"session_id": "sess-ha-bridge-state"},
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()
        assert payload["status"] == "ok"
        assert set(payload["state"].keys()) == {
            "last_status",
            "pending_confirmation",
            "pending_action_label",
            "confirmation_expires_at",
        }
        assert payload["state"]["last_status"] == "confirmation_required"
        assert payload["state"]["pending_confirmation"] is True
        assert payload["state"]["pending_action_label"] == "lock.unlock"
