from __future__ import annotations

import sys
from pathlib import Path

from flask import Blueprint, Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import debug as module  # noqa: E402


class FakeDebugState:
    def __init__(self, *, initial: bool = False) -> None:
        self.enabled = initial
        self.raise_on: str | None = None
        self.set_calls: list[bool] = []

    def get_debug(self) -> bool:
        if self.raise_on == "get":
            raise RuntimeError("debug status exploded")
        return self.enabled

    def set_debug(self, enabled: bool) -> None:
        if self.raise_on == "set":
            raise RuntimeError("debug set exploded")
        self.enabled = enabled
        self.set_calls.append(enabled)


def _build_client(monkeypatch, *, authorized: bool = True, state: FakeDebugState | None = None):
    state = state or FakeDebugState()
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)
    monkeypatch.setattr(module, "get_debug", state.get_debug)
    monkeypatch.setattr(module, "set_debug", state.set_debug)

    app = Flask(__name__)
    api_v1 = Blueprint("api_v1_test", __name__, url_prefix="/api/v1")
    api_v1.register_blueprint(module.bp)
    app.register_blueprint(api_v1)
    return app.test_client(), state


def test_debug_contract_covers_status_and_toggle_routes(monkeypatch) -> None:
    client, state = _build_client(monkeypatch, state=FakeDebugState(initial=False))

    response = client.get("/api/v1/debug")
    assert response.status_code == 200
    assert response.get_json() == {"debug_mode": False}

    response = client.post("/api/v1/debug", json={"enabled": True})
    assert response.status_code == 200
    assert response.get_json() == {"enabled": True}
    assert state.enabled is True
    assert state.set_calls == [True]

    response = client.get("/api/v1/debug")
    assert response.status_code == 200
    assert response.get_json() == {"debug_mode": True}


def test_debug_contract_hardens_auth_validation_and_runtime_errors(monkeypatch) -> None:
    client, _state = _build_client(monkeypatch, authorized=False)

    response = client.get("/api/v1/debug")
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }

    response = client.post("/api/v1/debug", json={"enabled": True})
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }

    client, state = _build_client(monkeypatch)

    response = client.post("/api/v1/debug")
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}

    response = client.post("/api/v1/debug", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}

    response = client.post("/api/v1/debug", json={})
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Invalid request. 'enabled' must be a boolean (true/false)."
    }

    response = client.post("/api/v1/debug", json={"enabled": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Invalid request. 'enabled' must be a boolean (true/false)."
    }

    state.raise_on = "get"
    response = client.get("/api/v1/debug")
    assert response.status_code == 500
    assert response.get_json() == {"error": "debug status exploded"}

    state.raise_on = "set"
    response = client.post("/api/v1/debug", json={"enabled": False})
    assert response.status_code == 500
    assert response.get_json() == {"error": "debug set exploded"}
