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
from copilot_core.api.v1 import autonomy as module  # noqa: E402


BASE_PATH = "/api/v1/autonomy"


class FakeZoneAutomation:
    def __init__(self) -> None:
        self.raise_on_mode = False

    def get_automation_mode(self, zone_id: str) -> str:
        if self.raise_on_mode:
            raise RuntimeError("zone mode exploded")
        return "autonomy" if zone_id == "wohnbereich" else "learning"


class FakeBehavioralLog:
    def __init__(self) -> None:
        self.raise_on_history = False
        self.raise_on_stats = False
        self.last_top_k: int | None = None

    def get_zone_history(self, zone_id: str, top_k: int = 20):
        if self.raise_on_history:
            raise RuntimeError("history exploded")
        self.last_top_k = top_k
        return [
            {
                "zone_id": zone_id,
                "action": "turn_on",
                "status": "executed",
            }
        ]

    def get_stats(self):
        if self.raise_on_stats:
            raise RuntimeError("log exploded")
        return {"doc_count": 3}


class FakeMoodOverrideResult:
    def __init__(self, mood: str, payload: dict[str, object]) -> None:
        self.mood = mood
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return {
            "mood": self.mood,
            "brightness_pct": self.payload.get("brightness_pct"),
            "overridden": True,
        }


class FakeMoodMapper:
    def __init__(self) -> None:
        self.raise_on_get = False
        self.raise_on_set = False
        self.override_calls: list[tuple[str, dict[str, object]]] = []

    def get_all_actions(self):
        if self.raise_on_get:
            raise RuntimeError("mood actions exploded")
        return {
            "relax": {"mood": "relax", "brightness_pct": 50, "overridden": False},
        }

    def set_override(self, mood: str, payload: dict[str, object]):
        if self.raise_on_set:
            raise RuntimeError("mood override exploded")
        self.override_calls.append((mood, payload))
        return FakeMoodOverrideResult(mood, payload)


class FakeExecutor:
    def __init__(self) -> None:
        self.raise_on_dashboard = False
        self._zone_automation = FakeZoneAutomation()
        self._behavioral_log = FakeBehavioralLog()
        self._mood_mapper = FakeMoodMapper()
        self._stats = {
            "total_events": 10,
            "executed": 5,
            "suggested": 3,
            "skipped": 2,
            "errors": 0,
        }

    def get_dashboard(self):
        if self.raise_on_dashboard:
            raise RuntimeError("dashboard exploded")
        return {
            "zones": [{"zone_id": "wohnbereich", "automation_mode": "autonomy"}],
            "stats": {"total_events": 10, "executed": 5},
            "log": {"doc_count": 3},
            "rate_limit_seconds": 30,
        }

    def _get_mood_mapper(self):
        return self._mood_mapper


class FakeModuleRegistry:
    def __init__(self) -> None:
        self.raise_on_get = False
        self.raise_on_set = False
        self.set_zone_state_result = True
        self.zone_states = {"wohnbereich": {"licht": "active", "musik": "learning"}}

    def get_zone_states(self, zone_id: str):
        if self.raise_on_get:
            raise RuntimeError("zone states exploded")
        return dict(self.zone_states.get(zone_id, {}))

    def set_zone_state(self, zone_id: str, module_id: str, state: str) -> bool:
        if self.raise_on_set:
            raise RuntimeError("set zone state exploded")
        if not self.set_zone_state_result:
            return False
        self.zone_states.setdefault(zone_id, {})[module_id] = state
        return True


def _build_client(monkeypatch, *, authorized: bool = True, executor=None, registry=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module.init_autonomy_api(executor, registry)
    app = Flask(__name__)
    app.register_blueprint(module.autonomy_bp)
    return app.test_client()


def test_autonomy_contract_covers_all_routes(monkeypatch) -> None:
    executor = FakeExecutor()
    registry = FakeModuleRegistry()
    client = _build_client(monkeypatch, executor=executor, registry=registry)

    response = client.get(f"{BASE_PATH}/dashboard")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zones": [{"zone_id": "wohnbereich", "automation_mode": "autonomy"}],
        "stats": {"total_events": 10, "executed": 5},
        "log": {"doc_count": 3},
        "rate_limit_seconds": 30,
    }

    response = client.get(f"{BASE_PATH}/zones/wohnbereich")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "wohnbereich",
        "automation_mode": "autonomy",
        "module_states": {"licht": "active", "musik": "learning"},
    }

    response = client.post(
        f"{BASE_PATH}/zones/wohnbereich/module",
        json={"module_id": "licht", "state": "off"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "wohnbereich",
        "module_id": "licht",
        "state": "off",
    }
    assert registry.zone_states["wohnbereich"]["licht"] == "off"

    response = client.get(f"{BASE_PATH}/zones/wohnbereich/history?limit=5")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "zone_id": "wohnbereich",
        "history": [
            {
                "zone_id": "wohnbereich",
                "action": "turn_on",
                "status": "executed",
            }
        ],
    }
    assert executor._behavioral_log.last_top_k == 5

    response = client.get(f"{BASE_PATH}/mood-actions")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "actions": {
            "relax": {"mood": "relax", "brightness_pct": 50, "overridden": False},
        },
    }

    response = client.post(
        f"{BASE_PATH}/mood-actions/relax/override",
        json={"brightness_pct": 70},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "mood": "relax",
        "brightness_pct": 70,
        "overridden": True,
    }
    assert executor._mood_mapper.override_calls == [("relax", {"brightness_pct": 70})]

    response = client.get(f"{BASE_PATH}/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "total_events": 10,
        "executed": 5,
        "suggested": 3,
        "skipped": 2,
        "errors": 0,
        "log": {"doc_count": 3},
    }


def test_autonomy_contract_hardens_validation_and_runtime_edges(monkeypatch) -> None:
    executor = FakeExecutor()
    registry = FakeModuleRegistry()
    client = _build_client(monkeypatch, executor=executor, registry=registry)

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module", json={"module_id": 7, "state": "off"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "module_id must be a non-empty string"}

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module", json={"module_id": "licht", "state": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "state must be a non-empty string"}

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module", json={"module_id": "  ", "state": "off"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "module_id must be a non-empty string"}

    response = client.post(f"{BASE_PATH}/zones/wohnbereich/module", json={"module_id": "licht", "state": "  "})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "state must be a non-empty string"}

    registry.set_zone_state_result = False
    response = client.post(
        f"{BASE_PATH}/zones/wohnbereich/module",
        json={"module_id": "licht", "state": "invalid"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid state: invalid"}
    registry.set_zone_state_result = True

    response = client.get(f"{BASE_PATH}/zones/wohnbereich/history?limit=abc")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid 'limit' parameter. Must be a positive integer.",
    }

    response = client.get(f"{BASE_PATH}/zones/wohnbereich/history?limit=0")
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Invalid 'limit' parameter. Must be a positive integer.",
    }

    response = client.post(
        f"{BASE_PATH}/mood-actions/relax/override",
        data="",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post(f"{BASE_PATH}/mood-actions/relax/override", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Request body required"}

    no_registry_client = _build_client(monkeypatch, executor=executor, registry=None)
    response = no_registry_client.post(
        f"{BASE_PATH}/zones/wohnbereich/module",
        json={"module_id": "licht", "state": "off"},
    )
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "ModuleRegistry not available"}

    client = _build_client(monkeypatch, executor=executor, registry=registry)

    no_executor_client = _build_client(monkeypatch, executor=None, registry=registry)
    response = no_executor_client.get(f"{BASE_PATH}/dashboard")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "AutonomyExecutor not available"}

    response = no_executor_client.post(
        f"{BASE_PATH}/mood-actions/relax/override",
        json={"brightness_pct": 70},
    )
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "AutonomyExecutor not available"}

    client = _build_client(monkeypatch, executor=executor, registry=registry)

    executor.raise_on_dashboard = True
    response = client.get(f"{BASE_PATH}/dashboard")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "dashboard exploded"}
    executor.raise_on_dashboard = False

    executor._zone_automation.raise_on_mode = True
    response = client.get(f"{BASE_PATH}/zones/wohnbereich")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone mode exploded"}
    executor._zone_automation.raise_on_mode = False

    registry.raise_on_get = True
    response = client.get(f"{BASE_PATH}/zones/wohnbereich")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "zone states exploded"}
    registry.raise_on_get = False

    registry.raise_on_set = True
    response = client.post(
        f"{BASE_PATH}/zones/wohnbereich/module",
        json={"module_id": "licht", "state": "off"},
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "set zone state exploded"}
    registry.raise_on_set = False

    executor._behavioral_log.raise_on_history = True
    response = client.get(f"{BASE_PATH}/zones/wohnbereich/history")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "history exploded"}
    executor._behavioral_log.raise_on_history = False

    executor._mood_mapper.raise_on_get = True
    response = client.get(f"{BASE_PATH}/mood-actions")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "mood actions exploded"}
    executor._mood_mapper.raise_on_get = False

    executor._mood_mapper.raise_on_set = True
    response = client.post(
        f"{BASE_PATH}/mood-actions/relax/override",
        json={"brightness_pct": 70},
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "mood override exploded"}
    executor._mood_mapper.raise_on_set = False

    executor._behavioral_log.raise_on_stats = True
    response = client.get(f"{BASE_PATH}/stats")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "log exploded"}


def test_autonomy_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, executor=FakeExecutor(), registry=FakeModuleRegistry())

    response = client.get(f"{BASE_PATH}/dashboard")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
