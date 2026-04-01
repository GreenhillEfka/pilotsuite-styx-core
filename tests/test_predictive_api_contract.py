"""Contract coverage for predictive proposal lifecycle → policy-gated action handoff."""

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


from copilot_core.api.v1.predictive import predictive_bp  # noqa: E402
from copilot_core.predictive.automation_engine import (  # noqa: E402
    BehavioralPattern,
    PatternType,
    PredictionConfidence,
    PredictiveAutomationEngine,
)


def _engine_with_pattern() -> PredictiveAutomationEngine:
    engine = PredictiveAutomationEngine()
    engine._patterns["pattern_predictive_api"] = BehavioralPattern(
        pattern_id="pattern_predictive_api",
        pattern_type=PatternType.TIME_BASED,
        zone_id="zone:living",
        module_id="light",
        entity_id="light.wohnzimmer",
        trigger_conditions={
            "hour": datetime.now(timezone.utc).hour,
            "hour_tolerance": 2,
        },
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


def _client(monkeypatch, engine: PredictiveAutomationEngine):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"predictive_engine": engine}
    app.register_blueprint(predictive_bp)
    return app.test_client()


def test_get_next_prediction_returns_canonical_predictive_contract(monkeypatch) -> None:
    engine = _engine_with_pattern()
    client = _client(monkeypatch, engine)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get(
        "/api/v1/predictive/next?max_predictions=1&presence_detected=true",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    prediction = body["prediction"]
    assert prediction["contract"] == "PredictiveProposalV1"
    assert prediction["policy_gate_required"] is True
    assert "pattern" in prediction["source_signals"]


def test_confirm_prediction_returns_policy_gated_action_contract(monkeypatch) -> None:
    engine = _engine_with_pattern()
    proposal = engine.generate_predictions({"presence_detected": True})[0]
    client = _client(monkeypatch, engine)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/predictive/confirm",
        headers=headers,
        json={
            "proposal_id": proposal.proposal_id,
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "direct_execution_enabled": False,
                "approval_required": True,
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["proposal_intent"]["contract"] == "ProposalIntentV1"
    assert body["action_intent"]["contract"] == "ActionIntentV1"
    assert body["action_intent"]["source"] == "predictive.accepted"
    assert body["ha_output"]["action_intent"]["source"] == "predictive.accepted"
    assert body["ha_output"]["action_intent"]["execution_state"] == body["action_intent"]["execution_state"]
    assert body["ha_output"]["module_command"]["target"]["entity_id"] == "light.wohnzimmer"
    assert body["ha_output"]["module_command"]["metadata"]["decision_source"] == body["policy_gate"]["decision_source"]


def test_reject_prediction_persists_feedback(monkeypatch) -> None:
    engine = _engine_with_pattern()
    proposal = engine.generate_predictions({})[0]
    client = _client(monkeypatch, engine)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/predictive/reject",
        headers=headers,
        json={
            "proposal_id": proposal.proposal_id,
            "feedback": "not_now",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["proposal"]["rejected"] is True
    assert body["proposal"]["feedback"] == "not_now"
