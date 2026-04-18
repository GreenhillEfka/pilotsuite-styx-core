"""Contract tests for POST /api/v1/voice/command (VFM-002 / CORE-VFM-002-A)."""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.api.v1 import voice as voice_api  # noqa: E402
from copilot_core.voice import runtime_access as voice_runtime_access  # noqa: E402
from copilot_core.voice.dialog_state import DialogStateMachine  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(voice_api.bp)
    return app


def _isolated_dialog_machine(tmp_path):
    machine = DialogStateMachine(data_dir=str(tmp_path / "dialog-data"))
    machine.reset()
    return machine


def test_voice_command_executes_safe_high_confidence_light_command(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-safe-1",
            "utterance": "Mach das Licht an",
            "confidence": 0.95,
            "zone_id": "Wohnzimmer",
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "executed"
    assert payload["action"] == "light.turn_on"
    assert payload["session_state"]["dialog_state"] == "ACTIVE"
    assert payload["session_state"]["session_id"] == "sess-safe-1"
    assert payload["context"]["zone_name"] == "wohnzimmer"
    assert payload["response"]["actions"][0]["domain"] == "light"


def test_voice_command_requires_clarification_for_medium_confidence_ambiguous_request(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-clarify-1",
            "utterance": "Mach es an",
            "confidence": 0.70,
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "clarification_required"
    assert payload["action"] is None
    assert payload["session_state"]["dialog_state"] == "CLARIFYING"
    assert payload["session_state"]["slot_values"]["_clarification"] == payload["message"]
    assert "genauer" in payload["message"].lower() or "was genau" in payload["message"].lower()


def test_voice_command_requires_confirmation_for_high_confidence_unsafe_request(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-confirm-1",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "confirmation_required"
    assert payload["confirmation_token"]
    assert payload["session_state"]["dialog_state"] == "CONFIRMING"
    assert payload["session_state"]["slot_values"]["_confirmation_token"] == payload["confirmation_token"]
    assert payload["session_state"]["pending_action_label"] == "lock.unlock"
    assert payload["session_state"]["pending_action_payload"]["domain"] == "lock"
    assert "bestätig" in payload["message"].lower()


def test_voice_command_rejects_low_confidence_unknown_request(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-reject-1",
            "utterance": "blorpy zarg",
            "confidence": 0.20,
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "rejected"
    assert payload["action"] is None
    assert payload["session_state"]["dialog_state"] == "IDLE"
    assert "nicht verstanden" in payload["message"].lower()


def test_voice_command_requires_utterance(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()
    response = client.post(
        "/api/v1/voice/command",
        json={"confidence": 0.8},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "utterance" in payload["message"].lower()


def test_voice_command_confirm_executes_persisted_pending_action(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    pending = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-confirm-follow-through",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    ).get_json()

    response = client.post(
        "/api/v1/voice/command/confirm",
        json={
            "session_id": "sess-confirm-follow-through",
            "confirmation_token": pending["confirmation_token"],
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "executed"
    assert payload["action"] == "lock.unlock"
    assert payload["session_state"]["dialog_state"] == "IDLE"
    assert payload["response"]["actions"][0]["domain"] == "lock"
    assert payload["response"]["actions"][0]["service"] == "unlock"
    assert "bestätigt" in payload["message"].lower()


def test_voice_command_reject_clears_persisted_pending_action(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    pending = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-reject-follow-through",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    ).get_json()

    response = client.post(
        "/api/v1/voice/command/reject",
        json={
            "session_id": "sess-reject-follow-through",
            "confirmation_token": pending["confirmation_token"],
        },
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "rejected"
    assert payload["action"] == "lock.unlock"
    assert payload["session_state"]["dialog_state"] == "IDLE"
    assert payload["session_state"]["confirmation_token"] is None
    assert "verwerfe" in payload["message"].lower()


def test_voice_command_confirm_rejects_mismatched_confirmation_token(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-confirm-invalid-token",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    )

    response = client.post(
        "/api/v1/voice/command/confirm",
        json={
            "session_id": "sess-confirm-invalid-token",
            "confirmation_token": "wrong-token",
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "pending confirmation" in payload["message"].lower()


def test_voice_command_state_returns_pending_confirmation_projection(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-command-state-pending",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    )

    response = client.get(
        "/api/v1/voice/command/state",
        query_string={"session_id": "sess-command-state-pending"},
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["session_id"] == "sess-command-state-pending"
    assert payload["state"]["last_status"] == "confirmation_required"
    assert payload["state"]["pending_confirmation"] is True
    assert payload["state"]["pending_action_label"] == "lock.unlock"
    assert isinstance(payload["state"]["confirmation_expires_at"], str)
    assert payload["state"]["confirmation_expires_at"].endswith("Z")


def test_voice_command_state_returns_idle_shape_for_other_session(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-command-state-active",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    )

    response = client.get(
        "/api/v1/voice/command/state",
        query_string={"session_id": "different-session"},
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["state"] == {
        "last_status": "idle",
        "pending_confirmation": False,
        "pending_action_label": None,
        "confirmation_expires_at": None,
    }


def test_voice_command_state_keeps_last_status_after_confirmation_follow_through(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    machine = _isolated_dialog_machine(tmp_path)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: machine)

    app = _make_app()
    client = app.test_client()

    pending = client.post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-command-state-confirmed",
            "utterance": "Garage öffnen",
            "confidence": 0.93,
        },
    ).get_json()

    client.post(
        "/api/v1/voice/command/confirm",
        json={
            "session_id": "sess-command-state-confirmed",
            "confirmation_token": pending["confirmation_token"],
        },
    )

    response = client.get(
        "/api/v1/voice/command/state",
        query_string={"session_id": "sess-command-state-confirmed"},
    )

    assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
    payload = response.get_json()
    assert payload["state"] == {
        "last_status": "executed",
        "pending_confirmation": False,
        "pending_action_label": None,
        "confirmation_expires_at": None,
    }


def test_voice_command_state_requires_session_id(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)
    monkeypatch.setattr(voice_api, "_get_dialog_machine", lambda: _isolated_dialog_machine(tmp_path))

    app = _make_app()
    client = app.test_client()

    response = client.get("/api/v1/voice/command/state")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "session_id" in payload["message"]


def test_voice_command_prefers_injected_runtime_seam(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_api, "_validate_token", lambda request: True)

    class _DummyHandler:
        mood_engine = None
        habitus_service = None

    class _DummyContext:
        def to_dict(self):
            return {"zone_name": "wohnzimmer"}

    class _DummyContextBuilder:
        def build_context(self, **kwargs):
            return _DummyContext()

    class _DummyIntent:
        intent_type = type("IntentTypeValue", (), {"value": "light_on"})()
        confidence = 0.95
        slots = {}
        language = "de"

        def __init__(self, raw_text):
            self.raw_text = raw_text

        def to_dict(self):
            return {
                "intent_type": "light_on",
                "confidence": self.confidence,
                "slots": self.slots,
                "language": self.language,
                "raw_text": self.raw_text,
            }

    class _DummyResponse:
        text = "Licht ist an"
        tts_text = "Licht ist an"
        requires_confirmation = False
        actions = [{"domain": "light", "service": "turn_on", "data": {}}]
        metadata = {}

        def to_dict(self):
            return {
                "text": self.text,
                "tts_text": self.tts_text,
                "requires_confirmation": self.requires_confirmation,
                "actions": self.actions,
                "metadata": self.metadata,
            }

    class _InjectedRouter:
        def route(self, **kwargs):
            return {
                "decision": type(
                    "Decision",
                    (),
                    {
                        "status": "executed",
                        "action": "light.turn_on",
                        "message": "Licht ist an",
                        "confirmation_token": None,
                        "action_payload": None,
                        "session_state": {
                            "state": "ACTIVE",
                            "session_id": kwargs.get("session_id"),
                            "user_id": kwargs.get("user_id"),
                            "zone_id": kwargs.get("zone_id"),
                        },
                    },
                )(),
                "intent": _DummyIntent(kwargs.get("utterance")),
                "normalized_intent": type("NormalizedIntent", (), {"value": "light_on"})(),
                "effective_confidence": 0.95,
                "response": _DummyResponse(),
            }

    machine = _isolated_dialog_machine(tmp_path)

    class _InjectedRuntime:
        def get_intent_handler(self):
            return _DummyHandler()

        def get_context_builder(self):
            return _DummyContextBuilder()

        def get_command_router(self):
            return _InjectedRouter()

        def get_dialog_machine(self):
            return machine

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("fallback voice runtime construction should not run")

    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_intent_handler", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_context_builder", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_command_router", _should_not_be_called)
    monkeypatch.setattr(voice_runtime_access.VoiceRuntimeAccess, "get_dialog_machine", _should_not_be_called)

    app = Flask(__name__)
    voice_runtime_access.init_voice_runtime(app, runtime=_InjectedRuntime())
    app.register_blueprint(voice_api.bp)

    response = app.test_client().post(
        "/api/v1/voice/command",
        json={
            "session_id": "sess-runtime-seam",
            "utterance": "Mach das Licht an",
            "confidence": 0.95,
            "zone_id": "Wohnzimmer",
        },
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["status"] == "executed"
    assert payload["action"] == "light.turn_on"
    assert payload["session_state"]["session_id"] == "sess-runtime-seam"
    assert payload["response"]["actions"][0]["domain"] == "light"
