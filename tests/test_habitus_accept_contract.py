"""Contract coverage for habitus proposal acceptance → HA output handoff."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1.habitus import bp as habitus_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.register_blueprint(habitus_bp, url_prefix="/api/v1")
    return app.test_client()


def test_accept_zone_proposal_returns_normalized_ha_output(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/zone-proposals/accept",
        headers=headers,
        json={
            "proposal_id": "prop-accept-001",
            "zone_id": "zone:living",
            "zone_type": "living",
            "module_override": {
                "output_adapter": "homeassistant",
                "direct_execution_enabled": False,
                "approval_required": True,
            },
            "proposal": {
                "proposal_id": "prop-accept-001",
                "zone_id": "zone:living",
                "zone_type": "living",
                "module_id": "light",
                "title": "Wohnzimmerlicht vorschlagen",
                "summary": "Licht soll vorbereitet werden",
                "confidence": 0.82,
                "action": {
                    "domain": "light",
                    "service": "turn_on",
                    "entity_id": "light.wohnzimmer",
                    "state": "on",
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["action_intent"]["contract"] == "ActionIntentV1"
    assert body["ha_output"]["adapter"]["contract_version"] == "ha.output.v1"
    assert body["ha_output"]["action_intent"]["proposal_id"] == "prop-accept-001"
    assert body["ha_output"]["action_intent"]["action_type"] == "light.turn_on"
    assert body["ha_output"]["action_intent"]["source"] == "proposal.accepted"
    assert body["ha_output"]["action_intent"]["execution_state"] == body["action_intent"]["execution_state"]
    assert body["ha_output"]["action_intent"]["blocked_reasons"] == body["action_intent"]["blocked_reasons"]
    assert body["ha_output"]["module_command"]["target"]["entity_id"] == "light.wohnzimmer"
    assert body["ha_output"]["module_command"]["payload"]["expected_state"] == "on"
    assert body["ha_output"]["module_command"]["command_mode"] == "suggest"
    assert body["ha_output"]["module_command"]["metadata"]["decision_source"] == body["policy_gate"]["decision_source"]
    assert body["action_closure"]["metadata"]["rule_a"] == "light.wohnzimmer:on"
    assert body["action_closure"]["metadata"]["rule_b"] == "light.wohnzimmer:on"
