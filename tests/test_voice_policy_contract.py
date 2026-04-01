"""Contract coverage for voice control proposal → policy-gated action handoff."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.voice import bp as voice_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app.test_client()


def test_parse_voice_control_returns_canonical_proposal_contract(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht im Wohnzimmer an",
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "enabled": True,
                "direct_execution_enabled": False,
                "approval_required": True,
                "autonomy_mode": "learning",
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["proposal"]["contract"] == "VoiceControlProposalV1"
    assert body["proposal"]["source"] == "voice.control"
    assert body["proposal"]["module_id"] == "light"
    assert body["proposal"]["action_preview"]["target"]["entity_id"] == "light.living_room"
    assert body["proposal"]["policy_gate_required"] is True
    assert body["policy_preview"]["execution_state"] == "awaiting_styx_instruction"
    assert body["policy_preview"]["needs_explicit_styx_instruction"] is True


def test_confirm_voice_control_returns_policy_gated_action_contract(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    parse_response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht im Wohnzimmer an",
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "enabled": True,
                "direct_execution_enabled": False,
                "approval_required": True,
                "autonomy_mode": "learning",
            },
        },
    )
    proposal_id = parse_response.get_json()["proposal"]["proposal_id"]

    response = client.post(
        "/api/v1/voice/control/confirm",
        headers=headers,
        json={
            "proposal_id": proposal_id,
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "enabled": True,
                "direct_execution_enabled": False,
                "approval_required": True,
                "autonomy_mode": "learning",
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["proposal_intent"]["contract"] == "ProposalIntentV1"
    assert body["action_intent"]["contract"] == "ActionIntentV1"
    assert body["action_intent"]["source"] == "voice.accepted"
    assert body["ha_output"]["action_intent"]["source"] == "voice.accepted"
    assert body["ha_output"]["action_intent"]["execution_state"] == body["action_intent"]["execution_state"]
    assert body["ha_output"]["module_command"]["target"]["entity_id"] == "light.living_room"
    assert body["ha_output"]["module_command"]["metadata"]["decision_source"] == body["policy_gate"]["decision_source"]


def test_confirm_voice_control_execute_now_preserves_runtime_payload(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    parse_response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Heizung auf 22 Grad",
            "zone_id": "zone_bedroom",
            "zone_type": "bedroom",
            "entity_id": "climate.bedroom",
            "module_override": {
                "output_adapter": "homeassistant",
                "enabled": True,
                "direct_execution_enabled": True,
                "approval_required": False,
                "autonomy_mode": "autonomous",
            },
        },
    )
    proposal_id = parse_response.get_json()["proposal"]["proposal_id"]

    response = client.post(
        "/api/v1/voice/control/confirm",
        headers=headers,
        json={
            "proposal_id": proposal_id,
            "zone_type": "bedroom",
            "execute_now": True,
            "module_override": {
                "output_adapter": "homeassistant",
                "enabled": True,
                "direct_execution_enabled": True,
                "approval_required": False,
                "autonomy_mode": "autonomous",
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["policy_gate"]["eligible_for_execution"] is True
    assert body["policy_gate"]["execution_state"] == "ready_for_execution"
    assert body["ha_output"]["action_intent"]["execution_state"] == "ready_for_execution"
    assert body["ha_output"]["module_command"]["target"]["entity_id"] == "climate.bedroom"
    assert body["ha_output"]["module_command"]["payload"]["temperature"] == 22
    assert body["ha_output"]["module_command"]["payload"]["expected_state"] == {"temperature": 22}
