from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "explain.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api import security  # noqa: E402

spec = importlib.util.spec_from_file_location("ps_explain_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeExplainEngine:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.return_invalid_for: str | None = None
        self.calls: list[tuple[str, dict[str, str | None]]] = []

    def explain_suggestion(self, subject_id: str, payload: dict[str, str | None]):
        self.calls.append((subject_id, dict(payload)))
        if self.raise_on == subject_id:
            raise RuntimeError(f"{subject_id} exploded")
        if self.return_invalid_for == subject_id:
            return [subject_id]
        return {
            "explanation": f"Because of {subject_id}",
            "confidence": 0.91,
            "source": payload,
            "type": "suggestion",
        }


def _build_client(monkeypatch, *, authorized: bool = True, engine=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module.init_explain_api(engine)

    app = Flask(__name__)
    app.register_blueprint(module.explain_bp)
    return app.test_client()


def test_explain_contract_covers_suggestion_and_pattern_surfaces(monkeypatch) -> None:
    engine = FakeExplainEngine()
    client = _build_client(monkeypatch, engine=engine)

    response = client.get(
        "/api/v1/explain/suggestion/s-17?source=sensor.window&target=light.kitchen&time_pattern=evening",
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "explanation": "Because of s-17",
        "confidence": 0.91,
        "source": {
            "source_entity": "sensor.window",
            "target_entity": "light.kitchen",
            "time_pattern": "evening",
        },
        "type": "suggestion",
    }

    response = client.get(
        "/api/v1/explain/pattern/p-42?antecedent=binary_sensor.motion&consequent=light.hallway",
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "explanation": "Because of p-42",
        "confidence": 0.91,
        "source": {
            "source_entity": "binary_sensor.motion",
            "target_entity": "light.hallway",
            "time_pattern": None,
        },
        "type": "pattern",
    }

    assert engine.calls == [
        (
            "s-17",
            {
                "source_entity": "sensor.window",
                "target_entity": "light.kitchen",
                "time_pattern": "evening",
            },
        ),
        (
            "p-42",
            {
                "source_entity": "binary_sensor.motion",
                "target_entity": "light.hallway",
                "time_pattern": None,
            },
        ),
    ]


def test_explain_contract_hardens_auth_uninitialized_and_runtime_paths(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, engine=FakeExplainEngine())

    response = client.get("/api/v1/explain/suggestion/s-17")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }

    response = client.get("/api/v1/explain/pattern/p-42")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }

    client = _build_client(monkeypatch, engine=None)

    response = client.get("/api/v1/explain/suggestion/s-17")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "ExplainabilityEngine not initialized"}

    response = client.get("/api/v1/explain/pattern/p-42")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "ExplainabilityEngine not initialized"}

    engine = FakeExplainEngine()
    engine.return_invalid_for = "s-invalid"
    client = _build_client(monkeypatch, engine=engine)

    response = client.get("/api/v1/explain/suggestion/s-invalid")
    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "error": "suggestion explanation result must be an object",
    }

    engine.raise_on = "p-broken"
    response = client.get("/api/v1/explain/pattern/p-broken")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "p-broken exploded"}
