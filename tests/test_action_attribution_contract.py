from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import action_attribution as module  # noqa: E402


class FakeActionAttributionService:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.last_attribute_call = None
        self.history = [
            SimpleNamespace(
                user_id="andreas",
                entity_id="light.kitchen",
                action="turn_on",
                confidence=0.9,
                timestamp=datetime(2026, 4, 5, 4, 10, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                user_id="maria",
                entity_id="switch.coffee",
                action="turn_off",
                confidence=0.6,
                timestamp=datetime(2026, 4, 5, 4, 11, tzinfo=timezone.utc),
            ),
        ]

    def attribute_action(self, entity_id, action, signals):
        if self.raise_on == "attribute_action":
            raise RuntimeError("attribute exploded")
        self.last_attribute_call = {
            "entity_id": entity_id,
            "action": action,
            "signals": signals,
        }
        if action == "impossible":
            return None
        return SimpleNamespace(
            user_id="andreas",
            entity_id=entity_id,
            action=action,
            confidence=0.85,
            sources={"presence": 0.55, "device_ownership": 0.3},
            timestamp=datetime(2026, 4, 5, 4, 12, tzinfo=timezone.utc),
        )

    def get_action_history(self, limit):
        if self.raise_on == "get_action_history":
            raise RuntimeError("history exploded")
        return self.history[:limit]

    def get_user_actions(self, user_id, limit):
        if self.raise_on == "get_user_actions":
            raise RuntimeError("user history exploded")
        return [entry for entry in self.history if entry.user_id == user_id][:limit]


def _build_client(monkeypatch, *, authorized: bool = True, service=None):
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"action_attribution": service}
    app.register_blueprint(module.bp)
    return app.test_client()


def test_action_attribution_contract_covers_all_routes(monkeypatch) -> None:
    service = FakeActionAttributionService()
    client = _build_client(monkeypatch, service=service)

    response = client.post(
        "/api/v1/attribution/attribute",
        json={
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "signals": [
                {
                    "source_name": "presence",
                    "user_id": "andreas",
                    "confidence": 0.55,
                    "metadata": {"room_match": 1.0},
                },
                {
                    "source_name": "device_ownership",
                    "user_id": "andreas",
                    "confidence": 0.3,
                },
                {
                    "source_name": "ignored_missing_user",
                    "confidence": 0.7,
                },
            ],
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "attribution": {
            "user_id": "andreas",
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "confidence": 0.85,
            "sources": {"presence": 0.55, "device_ownership": 0.3},
            "timestamp": "2026-04-05T04:12:00+00:00",
        },
    }
    assert service.last_attribute_call["entity_id"] == "light.kitchen"
    assert service.last_attribute_call["action"] == "turn_on"
    parsed_signals = service.last_attribute_call["signals"]
    assert len(parsed_signals) == 2
    assert parsed_signals[0].source_name == "presence"
    assert parsed_signals[0].user_id == "andreas"
    assert parsed_signals[0].confidence == 0.55
    assert parsed_signals[0].metadata == {"room_match": 1.0}

    response = client.get("/api/v1/attribution/history?limit=1")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "actions": [
            {
                "user_id": "andreas",
                "entity_id": "light.kitchen",
                "action": "turn_on",
                "confidence": 0.9,
                "timestamp": "2026-04-05T04:10:00+00:00",
            }
        ],
    }

    response = client.get("/api/v1/attribution/user/andreas?limit=1")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "user_id": "andreas",
        "actions": [
            {
                "entity_id": "light.kitchen",
                "action": "turn_on",
                "confidence": 0.9,
                "timestamp": "2026-04-05T04:10:00+00:00",
            }
        ],
    }


def test_action_attribution_contract_hardens_uninitialized_validation_no_result_and_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch, service=None)

    response = client.post("/api/v1/attribution/attribute", json={"entity_id": "light.kitchen", "action": "turn_on"})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "action_attribution not initialized"}

    response = client.get("/api/v1/attribution/history")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "action_attribution not initialized"}

    response = client.get("/api/v1/attribution/user/andreas")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "action_attribution not initialized"}

    service = FakeActionAttributionService()
    client = _build_client(monkeypatch, service=service)

    response = client.post("/api/v1/attribution/attribute", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/attribution/attribute")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body required"}

    response = client.post("/api/v1/attribution/attribute", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "entity_id must be a non-empty string"}

    response = client.post("/api/v1/attribution/attribute", json={"entity_id": "light.kitchen"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "action must be a non-empty string"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={"entity_id": "light.kitchen", "action": "turn_on", "signals": {}},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals must be a list"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={"entity_id": "light.kitchen", "action": "turn_on", "signals": ["bad"]},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals[0] must be an object"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "signals": [{"user_id": 7}],
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals[0].user_id must be a non-empty string"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "signals": [{"user_id": "andreas", "source_name": "", "confidence": 0.5}],
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals[0].source_name must be a non-empty string"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "signals": [{"user_id": "andreas", "confidence": "high"}],
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals[0].confidence must be numeric"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={
            "entity_id": "light.kitchen",
            "action": "turn_on",
            "signals": [{"user_id": "andreas", "metadata": []}],
        },
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "signals[0].metadata must be an object"}

    response = client.post(
        "/api/v1/attribution/attribute",
        json={"entity_id": "light.kitchen", "action": "impossible", "signals": []},
    )
    assert response.status_code == 200
    assert response.get_json() == {"ok": False, "error": "no attribution possible"}

    response = client.get("/api/v1/attribution/history?limit=abc")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    response = client.get("/api/v1/attribution/history?limit=0")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    response = client.get("/api/v1/attribution/user/andreas?limit=abc")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    response = client.get("/api/v1/attribution/user/andreas?limit=-1")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be a positive integer"}

    service.raise_on = "attribute_action"
    response = client.post(
        "/api/v1/attribution/attribute",
        json={"entity_id": "light.kitchen", "action": "turn_on", "signals": []},
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "attribute exploded"}

    service.raise_on = "get_action_history"
    response = client.get("/api/v1/attribution/history")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "history exploded"}

    service.raise_on = "get_user_actions"
    response = client.get("/api/v1/attribution/user/andreas")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "user history exploded"}


def test_action_attribution_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, service=FakeActionAttributionService())

    response = client.post(
        "/api/v1/attribution/attribute",
        json={"entity_id": "light.kitchen", "action": "turn_on", "signals": []},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}
