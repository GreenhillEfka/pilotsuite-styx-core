"""Contract coverage for canonical feedback / execution closure surface."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.action_closure import get_action_closure_store  # noqa: E402
from copilot_core.api.v1.action_closure import action_closure_bp  # noqa: E402
from copilot_core.api.v1.multizone import multizone_bp  # noqa: E402
from copilot_core.api.v1.predictive import predictive_bp  # noqa: E402
from copilot_core.api.v1.voice import bp as voice_bp  # noqa: E402
from copilot_core.predictive.automation_engine import (  # noqa: E402
    BehavioralPattern,
    PatternType,
    PredictionConfidence,
    PredictiveAutomationEngine,
)


def setup_function() -> None:
    get_action_closure_store().clear()


def _predictive_engine() -> PredictiveAutomationEngine:
    engine = PredictiveAutomationEngine()
    engine._patterns["pattern_action_closure"] = BehavioralPattern(
        pattern_id="pattern_action_closure",
        pattern_type=PatternType.TIME_BASED,
        zone_id="zone:living",
        module_id="light",
        entity_id="light.wohnzimmer",
        trigger_conditions={"hour": datetime.now(timezone.utc).hour, "hour_tolerance": 2},
        typical_action={
            "domain": "light",
            "service": "turn_on",
            "entity_id": "light.wohnzimmer",
            "state": "on",
        },
        occurrence_count=7,
        confidence=PredictionConfidence.HIGH,
    )
    return engine


def _client(monkeypatch, *, predictive_engine: PredictiveAutomationEngine | None = None):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    if predictive_engine is not None:
        app.config["COPILOT_SERVICES"] = {"predictive_engine": predictive_engine}
    app.register_blueprint(action_closure_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(predictive_bp)
    app.register_blueprint(multizone_bp)
    return app.test_client()


def test_voice_confirmation_seeds_shared_action_closure_and_feedback(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    parsed = client.post(
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
            },
        },
    )
    proposal_id = parsed.get_json()["proposal"]["proposal_id"]

    confirmed = client.post(
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
            },
        },
    )

    assert confirmed.status_code == 200
    body = confirmed.get_json()
    closure = body["action_closure"]
    assert closure["contract"] == "ActionClosureV1"
    assert closure["source"] == "voice.accepted"
    assert closure["state"] == "accepted"
    assert closure["action_id"] == body["action_intent"]["action_intent_id"]

    feedback = client.post(
        f"/api/v1/action-closures/{closure['closure_id']}/feedback",
        headers=headers,
        json={"feedback": "worked_well", "comment": "passt"},
    )

    assert feedback.status_code == 200
    feedback_body = feedback.get_json()["closure"]
    assert feedback_body["state"] == "feedback_received"
    assert feedback_body["latest_feedback"]["feedback"] == "worked_well"
    assert feedback_body["event_history"][-1]["event_type"] == "feedback"


def test_predictive_confirmation_records_execution_on_shared_closure(monkeypatch) -> None:
    engine = _predictive_engine()
    proposal = engine.generate_predictions({"presence_detected": True})[0]
    client = _client(monkeypatch, predictive_engine=engine)
    headers = {"Authorization": "Bearer test-token"}

    confirmed = client.post(
        "/api/v1/predictive/confirm",
        headers=headers,
        json={
            "proposal_id": proposal.proposal_id,
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "direct_execution_enabled": True,
                "approval_required": False,
            },
            "execute_now": True,
        },
    )

    assert confirmed.status_code == 200
    closure = confirmed.get_json()["action_closure"]
    execution = client.post(
        f"/api/v1/action-closures/{closure['closure_id']}/execution",
        headers=headers,
        json={
            "outcome": "executed",
            "runtime_source": "ha.adapter",
            "result": {"status": "ok"},
        },
    )

    assert execution.status_code == 200
    execution_body = execution.get_json()["closure"]
    assert execution_body["state"] == "executed"
    assert execution_body["execution"]["runtime_source"] == "ha.adapter"
    assert execution_body["execution"]["result"]["status"] == "ok"


def test_multizone_pending_actions_expose_shared_action_closure(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    created = client.post(
        "/api/v1/multizone/scenes",
        headers=headers,
        json={
            "name": "Arrival Scene",
            "description": "Shared closure contract",
            "proposal_handoff": {"contract": "ProposalIntentV1", "proposal_id": "proposal:arrival"},
            "action_handoff": {"contract": "ActionIntentV1", "action_id": "action:arrival"},
            "zone_actions": {
                "zone_living": [
                    {
                        "module_id": "light",
                        "target": {"entity_id": "light.living_room"},
                        "action_type": "light.turn_on",
                        "payload": {"brightness": 180},
                        "proposal_intent": {
                            "contract": "ProposalIntentV1",
                            "proposal_id": "proposal:arrival",
                            "zone_id": "zone_living",
                            "module_id": "light",
                            "source": "proposal.accepted",
                        },
                        "action_intent": {
                            "contract": "ActionIntentV1",
                            "action_id": "action:arrival",
                            "zone_id": "zone_living",
                            "module_id": "light",
                            "action_type": "light.turn_on",
                            "target": {"entity_id": "light.living_room"},
                            "payload": {"brightness": 180},
                            "source": "proposal.accepted",
                        },
                    }
                ]
            },
        },
    )
    scene_id = created.get_json()["scene_id"]

    activated = client.post(
        f"/api/v1/multizone/scenes/{scene_id}/activate",
        headers=headers,
        json={"runtime_source": "api.manual"},
    )

    assert activated.status_code == 200
    pending_action = activated.get_json()["pending_actions"][0]
    closure = pending_action["action_closure"]
    assert pending_action["action_closure_id"] == closure["closure_id"]
    assert closure["contract"] == "ActionClosureV1"
    assert closure["subject_type"] == "scene"
    assert closure["subject_id"] == scene_id

    executed = client.post(
        f"/api/v1/action-closures/{closure['closure_id']}/execution",
        headers=headers,
        json={"outcome": "executed", "runtime_source": "multizone.runtime"},
    )
    assert executed.status_code == 200

    listed = client.get(
        "/api/v1/action-closures?action_id=action:arrival",
        headers=headers,
    )
    assert listed.status_code == 200
    listed_body = listed.get_json()
    assert listed_body["count"] == 1
    assert listed_body["closures"][0]["execution"]["runtime_source"] == "multizone.runtime"
