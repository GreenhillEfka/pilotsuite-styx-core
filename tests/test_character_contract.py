from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import character as module  # noqa: E402


class FakeCharacterService:
    def __init__(self) -> None:
        self.mode = "companion"
        self.raise_on: str | None = None

    def to_dict(self):
        if self.raise_on == "to_dict":
            raise RuntimeError("current exploded")
        return {
            "current_mode": self.mode,
            "preset": {
                "name": self.mode,
                "display_name": self.mode.title(),
                "description": f"{self.mode} mode",
                "icon": "🎭",
            },
        }

    def get_available_modes(self):
        if self.raise_on == "get_available_modes":
            raise RuntimeError("modes exploded")
        return [
            {"mode": "assistant", "display_name": "Assistent", "description": "Neutral", "icon": "🤖"},
            {"mode": "companion", "display_name": "Begleiter", "description": "Warm", "icon": "🦞"},
        ]

    def set_mode(self, mode):
        if self.raise_on == "set_mode":
            raise RuntimeError("set mode exploded")
        self.mode = mode.value

    def apply_mood_weights(self, base_mood):
        if self.raise_on == "apply_mood_weights":
            raise RuntimeError("mood exploded")
        return {key: value * 2 for key, value in base_mood.items()}


def _build_client(monkeypatch, *, authorized: bool = True, service=None):
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"character_service": service}
    app.register_blueprint(module.bp)
    return app.test_client()


def test_character_contract_covers_all_routes(monkeypatch) -> None:
    service = FakeCharacterService()
    client = _build_client(monkeypatch, service=service)

    response = client.get("/api/v1/character/current")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "current_mode": "companion",
        "preset": {
            "name": "companion",
            "display_name": "Companion",
            "description": "companion mode",
            "icon": "🎭",
        },
    }

    response = client.get("/api/v1/character/modes")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "modes": [
            {"mode": "assistant", "display_name": "Assistent", "description": "Neutral", "icon": "🤖"},
            {"mode": "companion", "display_name": "Begleiter", "description": "Warm", "icon": "🦞"},
        ],
    }

    response = client.post("/api/v1/character/mode", json={"mode": "assistant"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "current_mode": "assistant",
        "preset": {
            "name": "assistant",
            "display_name": "Assistant",
            "description": "assistant mode",
            "icon": "🎭",
        },
    }

    response = client.post("/api/v1/character/mood", json={"mood": {"relax": 0.5, "focus": 1.0}})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "weighted_mood": {"relax": 1.0, "focus": 2.0},
    }


def test_character_contract_hardens_uninitialized_validation_and_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch, service=None)

    response = client.get("/api/v1/character/current")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "character_service not initialized"}

    response = client.get("/api/v1/character/modes")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "character_service not initialized"}

    response = client.post("/api/v1/character/mode", json={"mode": "assistant"})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "character_service not initialized"}

    response = client.post("/api/v1/character/mood", json={"mood": {"relax": 1.0}})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "character_service not initialized"}

    service = FakeCharacterService()
    client = _build_client(monkeypatch, service=service)

    response = client.post("/api/v1/character/mode", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/character/mode", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mode must be a non-empty string"}

    response = client.post("/api/v1/character/mode", json={"mode": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mode must be a non-empty string"}

    response = client.post("/api/v1/character/mode", json={"mode": "unknown"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "unknown mode: unknown"}

    response = client.post("/api/v1/character/mood", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/character/mood", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mood dict required"}

    response = client.post("/api/v1/character/mood", json={"mood": []})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mood dict required"}

    response = client.post("/api/v1/character/mood", json={"mood": {"relax": "high"}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mood values must be numeric"}

    service.raise_on = "to_dict"
    response = client.get("/api/v1/character/current")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "current exploded"}

    service.raise_on = "get_available_modes"
    response = client.get("/api/v1/character/modes")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "modes exploded"}

    service.raise_on = "set_mode"
    response = client.post("/api/v1/character/mode", json={"mode": "assistant"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "set mode exploded"}

    service.raise_on = "apply_mood_weights"
    response = client.post("/api/v1/character/mood", json={"mood": {"relax": 1.0}})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "mood exploded"}


def test_character_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, service=FakeCharacterService())

    response = client.get("/api/v1/character/current")
    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}
