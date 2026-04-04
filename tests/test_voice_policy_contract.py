"""Contract coverage for voice control proposal → policy-gated action handoff."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
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


def test_parse_voice_control_returns_clarification_needed_for_low_confidence_dialog_turn(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht",
            "session_id": "voice-api-clarify",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "clarification_needed"
    assert body["proposal"] is None
    assert body["voice_command"]["intent_type"] == "unknown"
    assert body["voice_response"]["action_taken"]["intent"] == "clarification_required"
    assert body["dialog"]["session_id"] == "voice-api-clarify"
    assert body["dialog"]["status"] == "awaiting_clarification"
    assert body["dialog"]["pending_command"]["raw_text"] == "Licht"
    assert body["dialog_session"]["session_id"] == "voice-api-clarify"
    assert body["dialog_session"]["status"] == "awaiting_clarification"


def test_parse_voice_control_materializes_proposal_after_clarification_turn(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht",
            "session_id": "voice-api-continue",
        },
    )
    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "clarification_needed"

    response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "im Schlafzimmer an",
            "session_id": "voice-api-continue",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "proposal_ready"
    assert body["proposal"]["contract"] == "VoiceControlProposalV1"
    assert body["proposal"]["raw_text"] == "Licht im Schlafzimmer an"
    assert body["voice_command"]["intent_type"] == "turn_on"
    assert body["voice_command"]["zone_id"] == "zone_bedroom"
    assert body["proposal"]["action_preview"]["target"]["entity_id"] == "light.bedroom"
    assert body["dialog"]["status"] == "active"
    assert body["dialog"]["pending_command"] is None
    assert body["dialog_session"]["session_id"] == "voice-api-continue"
    assert body["dialog_session"]["status"] == "active"
    assert body["dialog_session"]["pending_command"] is None


def test_continue_voice_control_materializes_proposal_after_clarification_turn(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-api-explicit-continue"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht",
            "session_id": session_id,
        },
    )
    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "clarification_needed"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "im Schlafzimmer an",
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "proposal_ready"
    assert body["proposal"]["raw_text"] == "Licht im Schlafzimmer an"
    assert body["voice_command"]["intent_type"] == "turn_on"
    assert body["voice_command"]["zone_id"] == "zone_bedroom"
    assert body["dialog_session"]["session_id"] == session_id
    assert body["dialog_session"]["status"] == "active"


def test_continue_voice_control_requires_existing_session_id(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={"text": "im Schlafzimmer an"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error"
    assert body["message"] == "Missing 'session_id' in request body"


def test_continue_voice_control_returns_404_for_unknown_session(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "im Schlafzimmer an",
            "session_id": "voice-api-missing-session",
        },
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["status"] == "error"
    assert "voice-api-missing-session" in body["message"]


def test_get_voice_control_session_returns_clarification_state(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    parse_response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht",
            "session_id": "voice-api-session-state",
        },
    )

    assert parse_response.status_code == 200
    assert parse_response.get_json()["dialog_phase"] == "clarification_needed"

    response = client.get(
        "/api/v1/voice/control/session/voice-api-session-state",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["session"]["session_id"] == "voice-api-session-state"
    assert body["session"]["status"] == "awaiting_clarification"
    assert body["session"]["pending_command"]["raw_text"] == "Licht"
    assert body["session"]["clarification_prompt"]


def test_get_voice_control_session_returns_resolved_state_after_continuation(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-api-session-continue"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "Licht", "session_id": session_id},
    )
    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "clarification_needed"

    second = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "im Schlafzimmer an", "session_id": session_id},
    )
    assert second.status_code == 200
    assert second.get_json()["dialog_phase"] == "proposal_ready"

    response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["session"]["status"] == "active"
    assert body["session"]["pending_command"] is None
    assert body["session"]["last_command"]["intent_type"] == "turn_on"
    assert body["session"]["current_zone_id"] == "zone_bedroom"


def test_voice_control_session_readback_preserves_clarify_continue_follow_up_history(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-api-session-readback-history"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "Licht", "session_id": session_id},
    )
    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "clarification_needed"

    second = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={"text": "im Schlafzimmer an", "session_id": session_id},
    )
    assert second.status_code == 200
    assert second.get_json()["dialog_phase"] == "proposal_ready"

    third = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": {
                "kind": "proposal",
                "proposal_id": "proposal:voice:readback",
                "zone_id": "zone_bedroom",
                "summary": "Schlafzimmer-Vorschlag prüfen.",
                "status": "open",
            },
        },
    )

    assert third.status_code == 200
    body = third.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["dialog_session"]["session_id"] == session_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["last_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["dialog_session"]["last_response"]["action_taken"]["target_id"] == "proposal:voice:readback"
    assert body["dialog_session"]["last_response"]["action_taken"]["status"] == "open"
    assert len(body["dialog_session"]["history"]) == 3
    assert [entry["status"] for entry in body["dialog_session"]["history"]] == [
        "awaiting_clarification",
        "active",
        "resolved",
    ]
    assert [entry["raw_text"] for entry in body["dialog_session"]["history"]] == [
        "Licht",
        "im Schlafzimmer an",
        "mach weiter",
    ]
    assert body["dialog_session"]["history"][-1]["response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["dialog_session"]["history"][-1]["response"]["action_taken"]["target_id"] == "proposal:voice:readback"

    session_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )

    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert session_body["status"] == "ok"
    assert session_body["session"]["session_id"] == session_id
    assert session_body["session"]["status"] == "resolved"
    assert session_body["session"]["current_zone_id"] == "zone_bedroom"
    assert session_body["session"]["last_command"]["raw_text"] == "mach weiter"
    assert session_body["session"]["last_response"] == body["dialog_session"]["last_response"]
    assert session_body["session"]["history"] == body["dialog_session"]["history"]


def test_parse_voice_control_carries_zone_context_across_successive_turns(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-api-zone-carryover"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "Licht im Wohnzimmer an", "session_id": session_id},
    )

    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["dialog_phase"] == "proposal_ready"
    assert first_body["voice_command"]["zone_id"] == "zone_living_room"

    second = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "heller", "session_id": session_id},
    )

    assert second.status_code == 200
    body = second.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "proposal_ready"
    assert body["voice_command"]["intent_type"] == "brighten"
    assert body["voice_command"]["zone_id"] == "zone_living_room"
    assert body["proposal"]["zone_id"] == "zone_living_room"
    assert body["proposal"]["action_preview"]["target"]["entity_id"] == "light.living_room"
    assert body["dialog"]["current_zone_id"] == "zone_living_room"
    assert body["dialog"]["last_command"]["zone_id"] == "zone_living_room"


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


@pytest.mark.parametrize(
    ("text", "follow_up_target", "expected_target_kind", "expected_target_id", "expected_zone_id"),
    [
        (
            "mach weiter",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:123",
                "zone_id": "zone_living_room",
                "summary": "Heiz-Vorschlag prüfen.",
            },
            "proposal",
            "proposal:voice:123",
            "zone_living_room",
        ),
        (
            "wie steht es damit",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:456",
                "zone_id": "zone_kitchen",
                "summary": "Letzten Fehlerlauf prüfen.",
            },
            "action_closure",
            "closure:voice:456",
            "zone_kitchen",
        ),
    ],
)
def test_parse_voice_control_returns_follow_up_dialog_phase(
    monkeypatch,
    text: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
    expected_zone_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": text,
            "session_id": f"voice-follow-up-{expected_target_kind}",
            "follow_up_target": follow_up_target,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["proposal"] is None
    assert body["policy_preview"] is None
    assert body["voice_response"]["requires_confirmation"] is False
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == expected_target_kind
    assert body["voice_response"]["action_taken"]["target_id"] == expected_target_id
    assert body["dialog"]["status"] == "resolved"
    assert body["dialog"]["current_zone_id"] == expected_zone_id
    assert body["dialog"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["current_zone_id"] == expected_zone_id


@pytest.mark.parametrize(
    ("session_suffix", "follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:resume",
                "zone_id": "zone_living_room",
                "summary": "Heiz-Vorschlag prüfen.",
                "status": "open",
            },
            "proposal",
            "proposal:voice:resume",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:resume",
                "zone_id": "zone_kitchen",
                "summary": "Letzten Fehlerlauf prüfen.",
                "status": "open",
            },
            "action_closure",
            "closure:voice:resume",
        ),
    ],
)
def test_continue_voice_control_resumes_open_follow_up_session(
    monkeypatch,
    session_suffix: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-resume-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["dialog_phase"] == "follow_up"
    assert first_body["dialog_session"]["status"] == "resolved"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "wie steht es damit",
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == expected_target_kind
    assert body["voice_response"]["action_taken"]["target_id"] == expected_target_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["active_follow_up"]["status"] == "open"


@pytest.mark.parametrize(
    ("resume_phrase", "expected_history_text"),
    [
        ("continue", "continue"),
        ("continue with", "continue with"),
        ("follow up", "follow up"),
        ("what about that", "what about that"),
        ("still open", "still open"),
        ("go on", "go on"),
        ("check on it", "check on it"),
        ("how's that going", "how's that going"),
        ("hows that going", "hows that going"),
        ("how's it going", "how's it going"),
        ("hows it going", "hows it going"),
    ],
)
@pytest.mark.parametrize(
    ("target_kind", "follow_up_target", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:en-resume",
                "zone_id": "zone_living_room",
                "summary": "Review the living room proposal.",
                "status": "open",
            },
            "proposal:voice:en-resume",
        ),
        (
            "action_closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:en-resume",
                "zone_id": "zone_kitchen",
                "summary": "Review the kitchen closure.",
                "status": "open",
            },
            "closure:voice:en-resume",
        ),
    ],
)
def test_continue_voice_control_accepts_explicit_english_follow_up_resume_phrases(
    monkeypatch,
    resume_phrase: str,
    expected_history_text: str,
    target_kind: str,
    follow_up_target: dict[str, str],
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-en-resume-{target_kind}-{resume_phrase.replace(' ', '-')}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "continue",
            "language": "en",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": resume_phrase,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == target_kind
    assert body["voice_response"]["action_taken"]["target_id"] == expected_target_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["language"] == "en"
    assert body["dialog_session"]["active_follow_up"]["status"] == "open"
    assert body["dialog_session"]["history"][-1]["raw_text"] == expected_history_text

    session_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert session_body["session"]["language"] == "en"
    assert session_body["session"]["last_command"]["raw_text"] == expected_history_text
    assert session_body["session"]["active_follow_up"]["target_kind"] == target_kind
    assert session_body["session"]["active_follow_up"]["target_id"] == expected_target_id


@pytest.mark.parametrize(
    ("resume_phrase", "expected_history_text"),
    [
        ("mach weiter", "mach weiter"),
        ("weiter damit", "weiter damit"),
        ("mach damit weiter", "mach damit weiter"),
        ("wie stehts damit", "wie stehts damit"),
        ("was ist damit", "was ist damit"),
        ("noch offen", "noch offen"),
    ],
)
def test_continue_voice_control_accepts_explicit_german_follow_up_resume_phrases(
    monkeypatch,
    resume_phrase: str,
    expected_history_text: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-de-resume-{resume_phrase.replace(' ', '-')}"
    follow_up_target = {
        "kind": "proposal",
        "proposal_id": "proposal:voice:de-resume",
        "zone_id": "zone_living_room",
        "summary": "Wohnzimmervorschlag prüfen.",
        "status": "open",
    }

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "language": "de",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": resume_phrase,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == "proposal"
    assert body["voice_response"]["action_taken"]["target_id"] == follow_up_target["proposal_id"]
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["language"] == "de"
    assert body["dialog_session"]["active_follow_up"]["status"] == "open"
    assert body["dialog_session"]["history"][-1]["raw_text"] == expected_history_text

    session_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert session_body["session"]["language"] == "de"
    assert session_body["session"]["last_command"]["raw_text"] == expected_history_text
    assert session_body["session"]["active_follow_up"]["target_kind"] == "proposal"
    assert session_body["session"]["active_follow_up"]["target_id"] == follow_up_target["proposal_id"]


@pytest.mark.parametrize(
    "resume_phrase",
    [
        "wie stehts damit",
        "was ist damit",
        "noch offen",
    ],
)
@pytest.mark.parametrize(
    ("session_suffix", "open_follow_up_target", "terminal_follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:de-terminal-readback-contracted",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmervorschlag prüfen.",
                "status": "open",
            },
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:de-terminal-readback-contracted",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmervorschlag prüfen.",
                "status": "settled",
            },
            "proposal",
            "proposal:voice:de-terminal-readback-contracted",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:de-terminal-readback-contracted",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "open",
            },
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:de-terminal-readback-contracted",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "settled",
            },
            "action_closure",
            "closure:voice:de-terminal-readback-contracted",
        ),
    ],
)
def test_continue_voice_control_keeps_german_terminal_follow_up_conflict_readback_stable_for_natural_resume_phrases(
    monkeypatch,
    resume_phrase: str,
    session_suffix: str,
    open_follow_up_target: dict[str, str],
    terminal_follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-de-terminal-readback-contracted-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": open_follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": resume_phrase,
            "session_id": session_id,
            "follow_up_target": terminal_follow_up_target,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "settled"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_after["active_follow_up"]["target_id"] == expected_target_id
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]


@pytest.mark.parametrize(
    ("session_language", "resume_phrase", "expected_history_text"),
    [
        ("de", "continue", "continue"),
        ("en", "mach weiter", "mach weiter"),
    ],
)
def test_continue_voice_control_accepts_cross_language_follow_up_resume_phrases(
    monkeypatch,
    session_language: str,
    resume_phrase: str,
    expected_history_text: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-cross-language-{session_language}-{resume_phrase.replace(' ', '-')}"
    follow_up_target = {
        "kind": "proposal",
        "proposal_id": f"proposal:{session_id}",
        "zone_id": "zone_living_room",
        "summary": "Review the living room proposal.",
        "status": "open",
    }
    initial_text = "mach weiter" if session_language == "de" else "continue"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": initial_text,
            "language": session_language,
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": resume_phrase,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == "proposal"
    assert body["voice_response"]["action_taken"]["target_id"] == follow_up_target["proposal_id"]
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["language"] == session_language
    assert body["dialog_session"]["active_follow_up"]["status"] == "open"
    assert body["dialog_session"]["history"][-1]["raw_text"] == expected_history_text

    session_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert session_body["session"]["language"] == session_language
    assert session_body["session"]["last_command"]["raw_text"] == expected_history_text
    assert session_body["session"]["active_follow_up"]["target_kind"] == "proposal"
    assert session_body["session"]["active_follow_up"]["target_id"] == follow_up_target["proposal_id"]


@pytest.mark.parametrize(
    ("session_suffix", "follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:en-readback-conflict",
                "zone_id": "zone_living_room",
                "summary": "Review the living room proposal.",
                "status": "open",
            },
            "proposal",
            "proposal:voice:en-readback-conflict",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:en-readback-conflict",
                "zone_id": "zone_kitchen",
                "summary": "Review the kitchen closure.",
                "status": "open",
            },
            "action_closure",
            "closure:voice:en-readback-conflict",
        ),
    ],
)
def test_continue_voice_control_rejects_english_non_follow_up_resume_text_and_keeps_readback_stable(
    monkeypatch,
    session_suffix: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-en-readback-conflict-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "continue",
            "language": "en",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "turn on bedroom light",
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "open"
    assert body["dialog_session"]["language"] == "en"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["language"] == "en"
    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_after["active_follow_up"]["target_id"] == expected_target_id
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]


@pytest.mark.parametrize(
    ("session_suffix", "open_follow_up_target", "terminal_follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:en-terminal-readback",
                "zone_id": "zone_living_room",
                "summary": "Review the living room proposal.",
                "status": "open",
            },
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:en-terminal-readback",
                "zone_id": "zone_living_room",
                "summary": "Review the living room proposal.",
                "status": "settled",
            },
            "proposal",
            "proposal:voice:en-terminal-readback",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:en-terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Review the kitchen closure.",
                "status": "open",
            },
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:en-terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Review the kitchen closure.",
                "status": "settled",
            },
            "action_closure",
            "closure:voice:en-terminal-readback",
        ),
    ],
)
@pytest.mark.parametrize(
    "resume_phrase",
    [
        "follow up",
        "continue with",
        "what about that",
        "still open",
        "check on it",
        "how's that going",
        "hows that going",
        "how's it going",
        "hows it going",
    ],
)
def test_continue_voice_control_surfaces_english_terminal_follow_up_status_without_mutating_session_readback(
    monkeypatch,
    resume_phrase: str,
    session_suffix: str,
    open_follow_up_target: dict[str, str],
    terminal_follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-en-terminal-readback-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "continue",
            "language": "en",
            "session_id": session_id,
            "follow_up_target": open_follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": resume_phrase,
            "session_id": session_id,
            "follow_up_target": terminal_follow_up_target,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["language"] == "en"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "settled"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["language"] == "en"
    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_after["active_follow_up"]["target_id"] == expected_target_id
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]



def test_continue_voice_control_rejects_non_follow_up_resume_text(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-follow-up-new-command"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": {
                "kind": "proposal",
                "proposal_id": "proposal:voice:strict-resume",
                "zone_id": "zone_living_room",
                "summary": "Heiz-Vorschlag prüfen.",
                "status": "open",
            },
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "Licht im Schlafzimmer an",
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == "proposal"
    assert body["follow_up_target"]["target_id"] == "proposal:voice:strict-resume"
    assert body["follow_up_target"]["status"] == "open"
    assert body["dialog_session"]["session_id"] == session_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["current_zone_id"] == "zone_living_room"
    assert "proposal:voice:strict-resume" in body["message"]


@pytest.mark.parametrize(
    ("session_suffix", "follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:readback-conflict",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmervorschlag prüfen.",
                "status": "open",
            },
            "proposal",
            "proposal:voice:readback-conflict",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:readback-conflict",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "open",
            },
            "action_closure",
            "closure:voice:readback-conflict",
        ),
    ],
)
def test_continue_voice_control_keeps_readback_stable_on_non_follow_up_resume_conflict(
    monkeypatch,
    session_suffix: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-readback-conflict-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "Licht im Schlafzimmer an",
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "open"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_after["active_follow_up"]["target_id"] == expected_target_id
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]


def test_continue_voice_control_keeps_full_clarify_continue_follow_up_readback_stable_on_resume_conflict(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-follow-up-full-readback-conflict"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={"text": "Licht", "session_id": session_id},
    )
    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "clarification_needed"

    second = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={"text": "im Schlafzimmer an", "session_id": session_id},
    )
    assert second.status_code == 200
    assert second.get_json()["dialog_phase"] == "proposal_ready"

    third = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": {
                "kind": "proposal",
                "proposal_id": "proposal:voice:full-readback-conflict",
                "zone_id": "zone_bedroom",
                "summary": "Schlafzimmer-Vorschlag prüfen.",
                "status": "open",
            },
        },
    )
    assert third.status_code == 200
    assert third.get_json()["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]
    assert [entry["status"] for entry in session_before["history"]] == [
        "awaiting_clarification",
        "active",
        "resolved",
    ]
    assert [entry["raw_text"] for entry in session_before["history"]] == [
        "Licht",
        "im Schlafzimmer an",
        "mach weiter",
    ]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "Licht im Wohnzimmer an",
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == "proposal"
    assert body["follow_up_target"]["target_id"] == "proposal:voice:full-readback-conflict"
    assert body["follow_up_target"]["status"] == "open"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]
    assert [entry["status"] for entry in body["dialog_session"]["history"]] == [
        "awaiting_clarification",
        "active",
        "resolved",
    ]
    assert [entry["raw_text"] for entry in body["dialog_session"]["history"]] == [
        "Licht",
        "im Schlafzimmer an",
        "mach weiter",
    ]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == "proposal"
    assert session_after["active_follow_up"]["target_id"] == "proposal:voice:full-readback-conflict"
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]



def test_continue_voice_control_rejects_closed_follow_up_target(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = "voice-follow-up-closed"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht im Wohnzimmer an",
            "session_id": session_id,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "proposal_ready"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": {
                "kind": "action_closure",
                "closure_id": "closure:voice:closed",
                "zone_id": "zone_living_room",
                "status": "settled",
            },
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == "action_closure"
    assert body["follow_up_target"]["target_id"] == "closure:voice:closed"
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["session_id"] == session_id
    assert "closure:voice:closed" in body["message"]


@pytest.mark.parametrize(
    ("session_suffix", "follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:closed-readback",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmervorschlag prüfen.",
                "status": "settled",
            },
            "proposal",
            "proposal:voice:closed-readback",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:closed-readback",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmerabschluss prüfen.",
                "status": "settled",
            },
            "action_closure",
            "closure:voice:closed-readback",
        ),
    ],
)
def test_continue_voice_control_keeps_active_session_readback_stable_on_closed_follow_up_conflict(
    monkeypatch,
    session_suffix: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-closed-readback-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "Licht im Wohnzimmer an",
            "session_id": session_id,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "proposal_ready"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "settled"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]


@pytest.mark.parametrize(
    ("session_suffix", "open_follow_up_target", "terminal_follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:terminal",
                "zone_id": "zone_kitchen",
                "summary": "Küchenvorschlag prüfen.",
                "status": "open",
            },
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:terminal",
                "zone_id": "zone_kitchen",
                "summary": "Küchenvorschlag prüfen.",
                "status": "settled",
            },
            "proposal",
            "proposal:voice:terminal",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:terminal",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "open",
            },
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:terminal",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "settled",
            },
            "action_closure",
            "closure:voice:terminal",
        ),
    ],
)
def test_continue_voice_control_surfaces_terminal_follow_up_state_in_resume_conflict(
    monkeypatch,
    session_suffix: str,
    open_follow_up_target: dict[str, str],
    terminal_follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-terminal-state-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": open_follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": terminal_follow_up_target,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["session_id"] == session_id
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["current_zone_id"] == "zone_kitchen"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "settled"
    assert expected_target_id in body["message"]


@pytest.mark.parametrize(
    ("session_suffix", "open_follow_up_target", "terminal_follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Küchenvorschlag prüfen.",
                "status": "open",
            },
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Küchenvorschlag prüfen.",
                "status": "settled",
            },
            "proposal",
            "proposal:voice:terminal-readback",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "open",
            },
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:terminal-readback",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "settled",
            },
            "action_closure",
            "closure:voice:terminal-readback",
        ),
    ],
)
def test_continue_voice_control_keeps_last_response_and_history_stable_on_resume_conflict(
    monkeypatch,
    session_suffix: str,
    open_follow_up_target: dict[str, str],
    terminal_follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-terminal-readback-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": open_follow_up_target,
        },
    )

    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["dialog_phase"] == "follow_up"

    session_before_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_before_response.status_code == 200
    session_before = session_before_response.get_json()["session"]

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": terminal_follow_up_target,
        },
    )

    assert response.status_code == 409
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dialog_phase"] == "resume_conflict"
    assert body["follow_up_target"]["target_kind"] == expected_target_kind
    assert body["follow_up_target"]["target_id"] == expected_target_id
    assert body["follow_up_target"]["status"] == "settled"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "settled"
    assert body["dialog_session"]["last_response"] == session_before["last_response"]
    assert body["dialog_session"]["history"] == session_before["history"]

    session_after_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )
    assert session_after_response.status_code == 200
    session_after = session_after_response.get_json()["session"]

    assert session_after["active_follow_up"] == session_before["active_follow_up"]
    assert session_after["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_after["active_follow_up"]["target_id"] == expected_target_id
    assert session_after["active_follow_up"]["status"] == "open"
    assert session_after["last_response"] == session_before["last_response"]
    assert session_after["history"] == session_before["history"]


@pytest.mark.parametrize(
    ("session_suffix", "follow_up_target", "expected_target_kind", "expected_target_id"),
    [
        (
            "proposal",
            {
                "kind": "proposal",
                "proposal_id": "proposal:voice:resume-status",
                "zone_id": "zone_living_room",
                "summary": "Wohnzimmervorschlag prüfen.",
                "status": "open",
            },
            "proposal",
            "proposal:voice:resume-status",
        ),
        (
            "action-closure",
            {
                "kind": "action_closure",
                "closure_id": "closure:voice:resume-status",
                "zone_id": "zone_kitchen",
                "summary": "Küchenabschluss prüfen.",
                "status": "open",
            },
            "action_closure",
            "closure:voice:resume-status",
        ),
    ],
)
def test_continue_voice_control_normalizes_explicit_follow_up_status_on_successful_resume(
    monkeypatch,
    session_suffix: str,
    follow_up_target: dict[str, str],
    expected_target_kind: str,
    expected_target_id: str,
) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    session_id = f"voice-follow-up-success-status-{session_suffix}"

    first = client.post(
        "/api/v1/voice/control/parse",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": follow_up_target,
        },
    )

    assert first.status_code == 200
    assert first.get_json()["dialog_phase"] == "follow_up"

    resume_follow_up_target = dict(follow_up_target)
    resume_follow_up_target["status"] = "Needs Review"

    response = client.post(
        "/api/v1/voice/control/continue",
        headers=headers,
        json={
            "text": "mach weiter",
            "session_id": session_id,
            "follow_up_target": resume_follow_up_target,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["dialog_phase"] == "follow_up"
    assert body["voice_response"]["action_taken"]["intent"] == "dialog_follow_up"
    assert body["voice_response"]["action_taken"]["target_kind"] == expected_target_kind
    assert body["voice_response"]["action_taken"]["target_id"] == expected_target_id
    assert body["voice_response"]["action_taken"]["status"] == "needs_review"
    assert body["dialog_session"]["status"] == "resolved"
    assert body["dialog_session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert body["dialog_session"]["active_follow_up"]["target_id"] == expected_target_id
    assert body["dialog_session"]["active_follow_up"]["status"] == "needs_review"

    session_response = client.get(
        f"/api/v1/voice/control/session/{session_id}",
        headers=headers,
    )

    assert session_response.status_code == 200
    session_body = session_response.get_json()
    assert session_body["session"]["active_follow_up"]["target_kind"] == expected_target_kind
    assert session_body["session"]["active_follow_up"]["target_id"] == expected_target_id
    assert session_body["session"]["active_follow_up"]["status"] == "needs_review"


def test_get_voice_control_session_returns_404_for_unknown_session(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get(
        "/api/v1/voice/control/session/does-not-exist",
        headers=headers,
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["status"] == "error"
    assert "does-not-exist" in body["message"]
