from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402
from copilot_core.api.v1 import module_control as module  # noqa: E402
from copilot_core.module_registry import DEFAULT_STATE, ModuleRegistry  # noqa: E402


class ExplodingRegistry:
    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.zone_states: dict[str, dict[str, str]] = {}
        self.raise_on: str | None = None
        self.set_state_result = True
        self.set_zone_state_result = True

    def _maybe_raise(self, name: str, message: str) -> None:
        if self.raise_on == name:
            raise RuntimeError(message)

    def get_all_states(self):
        self._maybe_raise("get_all_states", "list exploded")
        return dict(self.states)

    def get_state(self, module_id: str) -> str:
        self._maybe_raise("get_state", "get exploded")
        return self.states.get(module_id, DEFAULT_STATE)

    def set_state(self, module_id: str, state: str) -> bool:
        self._maybe_raise("set_state", "set exploded")
        if not self.set_state_result:
            return False
        self.states[module_id] = state
        return True

    def delete_state(self, module_id: str) -> bool:
        self._maybe_raise("delete_state", "delete exploded")
        return self.states.pop(module_id, None) is not None

    def get_zone_states(self, zone_id: str):
        self._maybe_raise("get_zone_states", "zone list exploded")
        return dict(self.zone_states.get(zone_id, {}))

    def set_zone_state(self, zone_id: str, module_id: str, state: str) -> bool:
        self._maybe_raise("set_zone_state", "zone set exploded")
        if not self.set_zone_state_result:
            return False
        self.zone_states.setdefault(zone_id, {})[module_id] = state
        return True

    def delete_zone_state(self, zone_id: str, module_id: str) -> bool:
        self._maybe_raise("delete_zone_state", "zone delete exploded")
        zone = self.zone_states.get(zone_id, {})
        if module_id not in zone:
            return False
        del zone[module_id]
        if not zone:
            self.zone_states.pop(zone_id, None)
        return True


def _build_client(monkeypatch, *, authorized: bool = True, registry=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    if registry is None:
        registry = ExplodingRegistry()
    module.init_module_control_api(registry)
    app = Flask(__name__)
    app.register_blueprint(module.module_control_bp)
    return app.test_client()


def test_module_control_contract_covers_all_routes(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "module_states.db"
    os.environ["MODULE_STATES_DB"] = str(db_path)
    registry = ModuleRegistry(db_path=str(db_path))
    client = _build_client(monkeypatch, registry=registry)

    response = client.get("/api/v1/modules")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "modules": {}}

    response = client.get("/api/v1/modules/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "state": "active",
    }

    response = client.post("/api/v1/modules", json={"module_id": "mood_engine", "state": "LEARNING"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "state": "learning",
        "action": "created",
    }

    response = client.put("/api/v1/modules/mood_engine", json={"state": "off"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "state": "off",
        "previous": "learning",
        "action": "updated",
    }

    response = client.post("/api/v1/modules/mood_engine/configure", json={"state": "active"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "state": "active",
        "previous": "off",
    }

    response = client.get("/api/v1/modules")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "modules": {"mood_engine": "active"}}

    response = client.get("/api/v1/modules/zones/living")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "overrides": {},
    }

    response = client.get("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "module_id": "mood_engine",
        "state": "active",
        "global_state": "active",
        "override_state": None,
        "has_override": False,
    }

    response = client.put("/api/v1/modules/zones/living/mood_engine", json={"state": "off"})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "module_id": "mood_engine",
        "state": "off",
        "previous": "active",
        "previous_override": None,
        "action": "created",
    }

    response = client.get("/api/v1/modules/zones/living")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "overrides": {"mood_engine": "off"},
    }

    response = client.get("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "module_id": "mood_engine",
        "state": "off",
        "global_state": "active",
        "override_state": "off",
        "has_override": True,
    }

    response = client.delete("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "module_id": "mood_engine",
        "deleted_state": "off",
        "effective_state": "active",
    }

    response = client.get("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "living",
        "module_id": "mood_engine",
        "state": "active",
        "global_state": "active",
        "override_state": None,
        "has_override": False,
    }

    response = client.delete("/api/v1/modules/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "deleted_state": "active",
    }

    response = client.get("/api/v1/modules/mood_engine")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "module_id": "mood_engine",
        "state": "active",
    }

    response = client.get("/api/v1/modules")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "modules": {}}

    os.environ.pop("MODULE_STATES_DB", None)


def test_module_control_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    registry = ExplodingRegistry()
    client = _build_client(monkeypatch, registry=registry)

    response = client.post("/api/v1/modules")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/modules", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/modules", json={"module_id": 7, "state": "active"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "module_id must be a string"}

    response = client.post("/api/v1/modules", json={"module_id": "mood_engine", "state": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "state must be a string"}

    response = client.post("/api/v1/modules", json={"module_id": "mood_engine", "state": "invalid"})
    assert response.status_code == 422
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid state 'invalid'",
        "valid_states": ["active", "learning", "off"],
    }

    response = client.post("/api/v1/modules/mood_engine/configure", json={"state": "  "})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'state' in request body"}

    response = client.put("/api/v1/modules/mood_engine", json={"state": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "state must be a string"}

    response = client.delete("/api/v1/modules/missing")
    assert response.status_code == 404
    assert response.get_json() == {
        "ok": False,
        "error": "Module 'missing' has no explicit state to delete",
        "module_id": "missing",
    }

    response = client.put("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.put("/api/v1/modules/zones/living/mood_engine", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.put("/api/v1/modules/zones/living/mood_engine", json={"state": "invalid"})
    assert response.status_code == 422
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid state 'invalid'",
        "valid_states": ["active", "learning", "off"],
    }

    response = client.delete("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 404
    assert response.get_json() == {
        "ok": False,
        "error": "Zone module 'living/mood_engine' has no explicit state to delete",
        "zone_id": "living",
        "module_id": "mood_engine",
    }

    registry.raise_on = "get_all_states"
    response = client.get("/api/v1/modules")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "list exploded"}

    registry.raise_on = "get_state"
    response = client.get("/api/v1/modules/mood_engine")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "get exploded"}

    registry.raise_on = None
    registry.set_state_result = False
    response = client.post("/api/v1/modules", json={"module_id": "mood_engine", "state": "learning"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "Failed to persist module state"}

    registry.set_state_result = True
    registry.raise_on = "set_state"
    response = client.put("/api/v1/modules/mood_engine", json={"state": "learning"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "set exploded"}

    registry.raise_on = None
    registry.states["mood_engine"] = "learning"
    registry.raise_on = "delete_state"
    response = client.delete("/api/v1/modules/mood_engine")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "delete exploded"}

    registry.raise_on = "get_zone_states"
    response = client.get("/api/v1/modules/zones/living")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone list exploded"}

    registry.raise_on = None
    registry.set_zone_state_result = False
    response = client.put("/api/v1/modules/zones/living/mood_engine", json={"state": "learning"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "Failed to persist zone module state"}

    registry.set_zone_state_result = True
    registry.raise_on = "set_zone_state"
    response = client.put("/api/v1/modules/zones/living/mood_engine", json={"state": "learning"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone set exploded"}

    registry.raise_on = None
    registry.zone_states["living"] = {"mood_engine": "learning"}
    registry.raise_on = "delete_zone_state"
    response = client.delete("/api/v1/modules/zones/living/mood_engine")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone delete exploded"}


def test_module_control_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False)

    response = client.get("/api/v1/modules")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }

    response = client.get("/api/v1/modules/zones/living")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
