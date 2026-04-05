from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402
from copilot_core.api.v1 import suggestions as module  # noqa: E402


class FakeSuggestionEngine:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.pending = [
            {
                "id": "sug-accept",
                "title": "Abendlicht optimieren",
                "confidence": 0.9,
                "category": "energy",
            },
            {
                "id": "sug-reject",
                "title": "Unpassende Kaffeemaschinen-Regel",
                "confidence": 0.4,
                "category": "repair",
            },
        ]
        self.dismissed: list[str] = []
        self.snoozed: list[tuple[str, int]] = []
        self.repairs = [
            {
                "id": "engine-repair-1",
                "title": "Engine Repair",
                "category": "energy",
                "confidence": 0.77,
                "description": "Engine-backed repair suggestion",
                "severity": "medium",
                "estimated_savings_eur": 12.5,
                "fix_type": "engine_fix",
            }
        ]

    def _maybe_raise(self, name: str, message: str) -> None:
        if self.raise_on == name:
            raise RuntimeError(message)

    def get_pending(self, limit: int = 20):
        self._maybe_raise("list", "list exploded")
        return self.pending[:limit]

    def get_suggestions(self, include_dismissed: bool = False, include_accepted: bool = False):
        self._maybe_raise("list", "list exploded")
        return list(self.pending)

    def propose_suggestion(self, suggestion_id: str):
        self._maybe_raise("propose_suggestion", "accept exploded")
        if suggestion_id != "sug-accept":
            return None
        return {
            "proposal_id": "proposal-123",
            "status": "proposed",
            "suggestion_id": suggestion_id,
        }

    def dismiss_suggestion(self, suggestion_id: str):
        self._maybe_raise("dismiss_suggestion", "reject exploded")
        if suggestion_id != "sug-reject":
            return None
        self.dismissed.append(suggestion_id)
        return {"id": suggestion_id, "dismissed": True}

    def snooze_suggestion(self, suggestion_id: str, minutes: int = 15):
        self._maybe_raise("snooze_suggestion", "snooze exploded")
        if suggestion_id != "sug-accept":
            return None
        self.snoozed.append((suggestion_id, minutes))
        return {"id": suggestion_id, "minutes": minutes}

    def get_repair_suggestions(self, limit: int = 10):
        self._maybe_raise("get_repair_suggestions", "repair list exploded")
        return self.repairs[:limit]


def _build_client(monkeypatch, *, authorized: bool = True, suggestion_engine=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module.init_suggestions_api(suggestion_engine=suggestion_engine)
    app = Flask(__name__)
    app.register_blueprint(module.suggestions_bp)
    return app.test_client()


def test_suggestions_contract_covers_all_routes(monkeypatch) -> None:
    engine = FakeSuggestionEngine()
    client = _build_client(monkeypatch, suggestion_engine=engine)

    response = client.get("/api/v1/suggestions")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "suggestions": engine.pending}

    response = client.get("/api/v1/suggestions/repairs")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "count": 7,
        "suggestions": engine.repairs + module._BUILTIN_REPAIR_SUGGESTIONS,
        "total_potential_savings_eur": 52.5,
        "categories": {
            "repair": 3,
            "energy": 3,
            "optimization": 1,
        },
    }

    response = client.post("/api/v1/suggestions/accept", json={"id": "sug-accept"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "id": "sug-accept",
        "status": "accepted",
        "proposal_id": "proposal-123",
        "proposal": {
            "proposal_id": "proposal-123",
            "status": "proposed",
            "suggestion_id": "sug-accept",
        },
    }

    response = client.post("/api/v1/suggestions/reject", json={"id": "sug-reject"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "id": "sug-reject",
        "status": "rejected",
    }
    assert engine.dismissed == ["sug-reject"]

    response = client.post("/api/v1/suggestions/snooze", json={"id": "sug-accept", "minutes": 30})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "id": "sug-accept",
        "status": "snoozed",
        "minutes": 30,
    }
    assert engine.snoozed == [("sug-accept", 30)]


def test_suggestions_contract_hardens_validation_not_found_runtime_and_state_reset(monkeypatch) -> None:
    engine = FakeSuggestionEngine()
    client = _build_client(monkeypatch, suggestion_engine=engine)

    response = client.post("/api/v1/suggestions/accept")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/suggestions/reject", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/suggestions/snooze", json={"id": "  "})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "'id' must be a non-empty string"}

    response = client.post("/api/v1/suggestions/snooze", json={"id": "sug-accept", "minutes": "15"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "minutes must be a positive integer"}

    response = client.post("/api/v1/suggestions/snooze", json={"id": "sug-accept", "minutes": 0})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "minutes must be a positive integer"}

    response = client.post("/api/v1/suggestions/accept", json={"id": "missing"})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Suggestion not found"}

    response = client.post("/api/v1/suggestions/reject", json={"id": "missing"})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Suggestion not found"}

    response = client.post("/api/v1/suggestions/snooze", json={"id": "missing", "minutes": 10})
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Suggestion not found"}

    engine.raise_on = "list"
    response = client.get("/api/v1/suggestions")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "list exploded"}

    engine.raise_on = "propose_suggestion"
    response = client.post("/api/v1/suggestions/accept", json={"id": "sug-accept"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "accept exploded"}

    engine.raise_on = "dismiss_suggestion"
    response = client.post("/api/v1/suggestions/reject", json={"id": "sug-reject"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "reject exploded"}

    engine.raise_on = "snooze_suggestion"
    response = client.post("/api/v1/suggestions/snooze", json={"id": "sug-accept", "minutes": 10})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "snooze exploded"}

    fallback_client = _build_client(monkeypatch, suggestion_engine=None)
    response = fallback_client.post("/api/v1/suggestions/reject", json={"id": "repair_missing_mode"})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "id": "repair_missing_mode", "status": "rejected"}

    response = fallback_client.get("/api/v1/suggestions/repairs")
    repair_ids = [item["id"] for item in response.get_json()["suggestions"]]
    assert "repair_missing_mode" not in repair_ids

    reset_client = _build_client(monkeypatch, suggestion_engine=None)
    response = reset_client.get("/api/v1/suggestions/repairs")
    repair_ids = [item["id"] for item in response.get_json()["suggestions"]]
    assert "repair_missing_mode" in repair_ids


def test_suggestions_contract_requires_authentication_for_mutations(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, suggestion_engine=FakeSuggestionEngine())

    response = client.get("/api/v1/suggestions")
    assert response.status_code == 200

    expected = {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }

    response = client.post("/api/v1/suggestions/accept", json={"id": "sug-accept"})
    assert response.status_code == 401
    assert response.get_json() == expected

    response = client.post("/api/v1/suggestions/reject", json={"id": "sug-reject"})
    assert response.status_code == 401
    assert response.get_json() == expected

    response = client.post("/api/v1/suggestions/snooze", json={"id": "sug-accept", "minutes": 15})
    assert response.status_code == 401
    assert response.get_json() == expected
