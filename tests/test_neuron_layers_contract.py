from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import neuron_layers as module  # noqa: E402


@dataclass
class FakeState:
    active: bool


@dataclass
class FakeNeuron:
    value: float
    confidence: float
    state: FakeState


@dataclass
class FakeResult:
    timestamp: float
    dominant_mood: str
    mood_confidence: float


class FakeManager:
    def __init__(self) -> None:
        self._last_result = FakeResult(timestamp=1712345678.0, dominant_mood="active", mood_confidence=0.82)
        self._neurons = {
            "context.presence": FakeNeuron(0.9, 0.95, FakeState(True)),
            "context.time_of_day": FakeNeuron(0.6, 0.8, FakeState(True)),
            "context.weather": FakeNeuron(0.4, 0.7, FakeState(True)),
            "state.energy_level": FakeNeuron(0.75, 0.88, FakeState(True)),
            "state.stress_index": FakeNeuron(0.2, 0.9, FakeState(False)),
            "mood.active": FakeNeuron(0.8, 0.92, FakeState(True)),
            "mood.relax": FakeNeuron(0.1, 0.6, FakeState(False)),
        }

    def get_all_neurons(self):
        return dict(self._neurons)


class FakeBus:
    def get_stats(self):
        return {"events": 3, "errors": 0}


class ExplodingManager:
    def __init__(self, message: str) -> None:
        self._last_result = None
        self.message = message

    def get_all_neurons(self):
        raise RuntimeError(self.message)


def _build_client(monkeypatch, tmp_path, *, manager=None, bus=None):
    monkeypatch.setenv("SYNAPSE_CONFIG_PATH", str(tmp_path / "synapse_overrides.json"))
    module._synapse_overrides.clear()
    module.init_neuron_layers_api(manager, bus)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(module.neuron_layers_bp)
    return app.test_client()


def test_neuron_layers_contract_covers_all_routes(monkeypatch, tmp_path) -> None:
    client = _build_client(monkeypatch, tmp_path, manager=FakeManager(), bus=FakeBus())

    response = client.get("/api/v1/neurons/layers/visualization")
    assert response.status_code == 200
    assert response.get_json() == {
        "layers": [
            {
                "id": 0,
                "name": "Context",
                "neurons": [
                    {"id": "context.presence", "name": "presence", "value": 0.9, "active": True, "confidence": 0.95},
                    {"id": "context.time_of_day", "name": "time_of_day", "value": 0.6, "active": True, "confidence": 0.8},
                    {"id": "context.weather", "name": "weather", "value": 0.4, "active": True, "confidence": 0.7},
                ],
            },
            {
                "id": 1,
                "name": "State",
                "neurons": [
                    {"id": "state.energy_level", "name": "energy_level", "value": 0.75, "active": True, "confidence": 0.88},
                    {"id": "state.stress_index", "name": "stress_index", "value": 0.2, "active": False, "confidence": 0.9},
                ],
            },
            {
                "id": 2,
                "name": "Mood",
                "neurons": [
                    {"id": "mood.active", "name": "active", "value": 0.8, "active": True, "confidence": 0.92},
                    {"id": "mood.relax", "name": "relax", "value": 0.1, "active": False, "confidence": 0.6},
                ],
            },
        ],
        "connections": [
            {
                "from": from_id,
                "to": to_id,
                "weight": weight,
                "signal_strength": round(abs(weight) * (FakeManager()._neurons.get(from_id).value if FakeManager()._neurons.get(from_id) else 0.0), 3),
                "excitatory": weight > 0,
            }
            for from_id, to_id, weight in module.SYNAPSE_TOPOLOGY
        ],
        "pipeline_status": {
            "last_evaluation": 1712345678.0,
            "dominant_mood": "active",
            "mood_confidence": 0.82,
        },
        "bus_stats": {"events": 3, "errors": 0},
        "timestamp_ms": response.get_json()["timestamp_ms"],
    }

    response = client.get("/api/v1/neurons/layers/snapshot.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.content_type
    svg = response.data.decode()
    assert "<svg" in svg
    assert "PilotSuite Styx Neural Pipeline" in svg
    assert "presence" in svg

    response = client.get("/api/v1/neurons/layers/heatmap")
    assert response.status_code == 200
    heatmap = response.get_json()
    assert heatmap["labels"] == [
        "context.presence",
        "context.time_of_day",
        "context.weather",
        "mood.active",
        "mood.relax",
        "state.energy_level",
        "state.stress_index",
    ]
    assert heatmap["layer_boundaries"] == [3, 5, 7]
    assert len(heatmap["matrix"]) == len(heatmap["labels"])
    assert heatmap["timestamp_ms"] > 0

    response = client.get("/api/v1/neurons/layers/synapses")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "count": len(module.SYNAPSE_TOPOLOGY),
        "data": [
            {
                "from": from_id,
                "to": to_id,
                "default_weight": weight,
                "weight": weight,
                "overridden": False,
            }
            for from_id, to_id, weight in module.SYNAPSE_TOPOLOGY
        ],
    }

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": "state.energy_level", "weight": 0.55},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "from": "context.presence",
            "to": "state.energy_level",
            "weight": 0.55,
            "default_weight": 0.2,
        },
    }

    response = client.post(
        "/api/v1/neurons/layers/synapses/reset",
        json={"from": "context.presence", "to": "state.energy_level"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "from": "context.presence",
            "to": "state.energy_level",
            "reset": True,
        },
    }

    client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": "state.energy_level", "weight": 0.45},
    )
    client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "state.energy_level", "to": "mood.active", "weight": 0.7},
    )
    response = client.post("/api/v1/neurons/layers/synapses/reset", json={"all": True})
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "data": {"reset_count": 2}}


def test_neuron_layers_contract_hardens_request_and_runtime_errors(monkeypatch, tmp_path) -> None:
    client = _build_client(monkeypatch, tmp_path, manager=None)

    response = client.get("/api/v1/neurons/layers/visualization")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "NeuronManager not initialized"}

    response = client.get("/api/v1/neurons/layers/heatmap")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "NeuronManager not initialized"}

    response = client.get("/api/v1/neurons/layers/snapshot.svg")
    assert response.status_code == 200
    assert "NeuronManager not initialized" in response.data.decode()

    client = _build_client(monkeypatch, tmp_path, manager=ExplodingManager("layer load exploded"))

    response = client.get("/api/v1/neurons/layers/visualization")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "layer load exploded"}

    response = client.get("/api/v1/neurons/layers/heatmap")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "layer load exploded"}

    response = client.get("/api/v1/neurons/layers/snapshot.svg")
    assert response.status_code == 500
    assert "layer load exploded" in response.data.decode()

    response = client.post("/api/v1/neurons/layers/synapses/update")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/neurons/layers/synapses/update", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": 7, "to": "state.energy_level", "weight": 0.5},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "'from' must be a non-empty string"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": " ", "weight": 0.5},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "'to' must be a non-empty string"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": "state.energy_level", "weight": True},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "weight must be a number"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": "state.energy_level"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Missing 'weight' in request body"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "context.presence", "to": "state.energy_level", "weight": 5},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "weight must be between -1.0 and 1.0"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/update",
        json={"from": "x.y", "to": "a.b", "weight": 0.1},
    )
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "error": "Synapse x.y -> a.b not found"}

    response = client.post("/api/v1/neurons/layers/synapses/reset")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "No JSON body provided"}

    response = client.post("/api/v1/neurons/layers/synapses/reset", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON body must be an object"}

    response = client.post("/api/v1/neurons/layers/synapses/reset", json={"all": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "'all' must be a boolean"}

    response = client.post(
        "/api/v1/neurons/layers/synapses/reset",
        json={"from": 7, "to": "state.energy_level"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "'from' must be a non-empty string"}
