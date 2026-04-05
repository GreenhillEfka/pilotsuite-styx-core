from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "neurons_visualization.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

spec = importlib.util.spec_from_file_location("ps_neurons_visualization_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 5, 10, 43, 0, tzinfo=timezone.utc)


class FakeState:
    def __init__(self, *, value: object = 0.8, trigger_count: object = 10, last_trigger: object = "2026-04-05T10:38:00+00:00") -> None:
        self.value = value
        self.trigger_count = trigger_count
        self.last_trigger = last_trigger

    def to_dict(self):
        return {
            "active": True,
            "value": self.value,
            "confidence": 0.91,
            "last_update": "2026-04-05T10:42:00+00:00",
            "last_trigger": self.last_trigger,
            "trigger_count": self.trigger_count,
        }


class FakeConfig:
    def __init__(self, *, entity_ids: object = None) -> None:
        self.entity_ids = ["binary_sensor.living_room_presence"] if entity_ids is None else entity_ids

    def to_dict(self):
        return {
            "threshold": 0.55,
            "decay_rate": 0.2,
            "smoothing_factor": 0.1,
            "entity_ids": self.entity_ids,
        }


class FakeNeuron:
    def __init__(
        self,
        key: str,
        *,
        name: str,
        neuron_type: str,
        is_active: bool,
        value: float,
        payload: object | None = None,
    ) -> None:
        self.key = key
        self.name = name
        self.neuron_type = SimpleNamespace(value=neuron_type)
        self.is_active = is_active
        self.state = FakeState(value=value)
        self.config = FakeConfig()
        self.payload = {
            "type": neuron_type,
            "active": is_active,
            "value": value,
        } if payload is None else payload
        self.raise_on: str | None = None

    def to_dict(self):
        if self.raise_on == "to_dict":
            raise RuntimeError(f"{self.key} exploded")
        return self.payload


@dataclass
class FakeLastResult:
    timestamp: object = "2026-04-05T10:42:30+00:00"
    dominant_mood: object = "focus"
    suggestions: object = None

    def __post_init__(self) -> None:
        if self.suggestions is None:
            self.suggestions = [
                {"id": "suggestion-1", "title": "Lights dimmen"},
                {"id": "suggestion-2", "title": "Musik leiser"},
            ]


class FakeManager:
    def __init__(self) -> None:
        self._context_neurons = {
            "context.presence": FakeNeuron(
                "context.presence",
                name="presence",
                neuron_type="context",
                is_active=True,
                value=0.8,
            )
        }
        self._state_neurons = {
            "state.energy": FakeNeuron(
                "state.energy",
                name="energy",
                neuron_type="state",
                is_active=False,
                value=0.45,
            )
        }
        self._mood_neurons = {
            "mood.focus": FakeNeuron(
                "mood.focus",
                name="focus",
                neuron_type="mood",
                is_active=True,
                value=0.92,
            )
        }
        self._last_result = FakeLastResult()
        self._evaluation_count = 9
        self._ha_states = {
            "binary_sensor.living_room_presence": "on",
            "sensor.energy_level": 0.45,
        }
        self.summary_payload: object = {
            "context": {"presence": 0.8},
            "state": {"energy": 0.45},
            "mood": {"focus": 0.92},
        }
        self.raise_on: str | None = None

    def get_neuron_summary(self):
        if self.raise_on == "get_neuron_summary":
            raise RuntimeError("summary exploded")
        return self.summary_payload


def _build_client(monkeypatch, *, authorized: bool = True, manager: FakeManager | None = None):
    monkeypatch.setattr(module, "validate_token", lambda _request: authorized)
    monkeypatch.setattr(module, "get_neuron_manager", lambda: manager)
    monkeypatch.setattr(module, "datetime", FrozenDateTime)
    app = Flask(__name__)
    api_v1 = Blueprint("api_v1_test", __name__, url_prefix="/api/v1")
    api_v1.register_blueprint(module.bp)
    app.register_blueprint(api_v1)
    return app.test_client()


def test_neurons_visualization_contract_covers_state_fire_and_pipeline(monkeypatch) -> None:
    manager = FakeManager()
    client = _build_client(monkeypatch, manager=manager)

    response = client.get("/api/v1/neurons/state")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "timestamp": "2026-04-05T10:43:00+00:00",
            "total_neurons": 3,
            "active_count": 2,
            "neurons": {
                "context": [
                    {
                        "type": "context",
                        "active": True,
                        "value": 0.8,
                        "name": "context.presence",
                    }
                ],
                "state": [
                    {
                        "type": "state",
                        "active": False,
                        "value": 0.45,
                        "name": "state.energy",
                    }
                ],
                "mood": [
                    {
                        "type": "mood",
                        "active": True,
                        "value": 0.92,
                        "name": "mood.focus",
                    }
                ],
            },
            "summary": {
                "context_values": {"presence": 0.8},
                "state_values": {"energy": 0.45},
                "mood_values": {"focus": 0.92},
            },
        },
    }

    response = client.get("/api/v1/neurons/presence/fire")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "name": "presence",
            "type": "context",
            "firing": True,
            "state": {
                "active": True,
                "value": 0.8,
                "confidence": 0.91,
                "last_update": "2026-04-05T10:42:00+00:00",
                "last_trigger": "2026-04-05T10:38:00+00:00",
                "trigger_count": 10,
            },
            "config": {
                "threshold": 0.55,
                "decay_rate": 0.2,
                "smoothing_factor": 0.1,
                "entity_ids": ["binary_sensor.living_room_presence"],
            },
            "live_metrics": {
                "firing_rate": 2.0,
                "avg_value": 0.8,
                "trend": "increasing",
            },
        },
    }

    response = client.get("/api/v1/neurons/brain/pipeline")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "pipeline": {
                "stages": [
                    {
                        "name": "Context Evaluation",
                        "type": "input",
                        "neuron_count": 1,
                        "active_count": 1,
                        "status": "active",
                        "description": "Evaluates objective environmental factors",
                    },
                    {
                        "name": "State Smoothing",
                        "type": "processing",
                        "neuron_count": 1,
                        "active_count": 0,
                        "status": "active",
                        "description": "Applies EMA smoothing and inertia",
                    },
                    {
                        "name": "Mood Aggregation",
                        "type": "aggregation",
                        "neuron_count": 1,
                        "active_count": 1,
                        "status": "active",
                        "description": "Aggregates into mood values",
                    },
                    {
                        "name": "Suggestion Generation",
                        "type": "output",
                        "neuron_count": 0,
                        "active_count": 0,
                        "status": "active",
                        "description": "Generates actionable suggestions",
                    },
                ],
                "status": "active",
                "last_execution": "2026-04-05T10:42:30+00:00",
                "execution_count": 9,
            },
            "data_flow": {
                "input_rate": 2,
                "output_rate": 2,
                "avg_latency_ms": 8.0,
            },
            "connections": {
                "context_to_state": [
                    {"from": "context.presence", "to": "state_neurons", "weight": 0.5}
                ],
                "state_to_mood": [
                    {"from": "state.energy", "to": "mood_neurons", "weight": 0.7}
                ],
                "mood_to_suggestions": [
                    {"from": "mood.focus", "to": "suggestions", "weight": 1.0}
                ],
            },
            "current_state": {
                "context_active": 1,
                "state_active": 0,
                "mood_active": 1,
                "dominant_mood": "focus",
            },
        },
    }


def test_neurons_visualization_contract_hardens_auth_uninitialized_and_runtime_errors(monkeypatch) -> None:
    manager = FakeManager()

    client = _build_client(monkeypatch, authorized=False, manager=manager)
    response = client.get("/api/v1/neurons/state")
    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }

    client = _build_client(monkeypatch, manager=None)
    response = client.get("/api/v1/neurons/state")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "NeuronManager not initialized"}

    response = client.get("/api/v1/neurons/context.presence/fire")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "NeuronManager not initialized"}

    response = client.get("/api/v1/neurons/brain/pipeline")
    assert response.status_code == 503
    assert response.get_json() == {"success": False, "error": "NeuronManager not initialized"}

    client = _build_client(monkeypatch, manager=manager)

    manager.summary_payload = "broken"
    response = client.get("/api/v1/neurons/state")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "Neuron summary must be an object"}

    manager.summary_payload = {
        "context": {"presence": 0.8},
        "state": {"energy": 0.45},
        "mood": {"focus": 0.92},
    }
    manager._context_neurons["context.presence"].payload = "broken"
    response = client.get("/api/v1/neurons/state")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "Neuron context.presence payload must be an object"}

    manager._context_neurons["context.presence"].payload = {
        "type": "context",
        "active": True,
        "value": 0.8,
    }
    response = client.get("/api/v1/neurons/missing/fire")
    assert response.status_code == 404
    assert response.get_json() == {"success": False, "error": "Neuron not found: missing"}

    manager._context_neurons["context.presence"].state.value = "bad"
    response = client.get("/api/v1/neurons/context.presence/fire")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "Neuron context.presence state value must be numeric",
    }

    manager._context_neurons["context.presence"].state.value = 0.8
    manager._last_result.suggestions = "broken"
    response = client.get("/api/v1/neurons/brain/pipeline")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "Pipeline suggestions must be a list"}

    manager._last_result.suggestions = [
        {"id": "suggestion-1", "title": "Lights dimmen"},
        {"id": "suggestion-2", "title": "Musik leiser"},
    ]
    manager._ha_states = "broken"
    response = client.get("/api/v1/neurons/brain/pipeline")
    assert response.status_code == 500
    assert response.get_json() == {
        "success": False,
        "error": "NeuronManager HA state cache must be an object",
    }
