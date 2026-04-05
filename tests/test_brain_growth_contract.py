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
from copilot_core.api.v1 import brain_growth as module  # noqa: E402
from copilot_core.brain_graph.brain_growth_read_model import SemanticTransferTrace  # noqa: E402


class FakeGraphService:
    def __init__(self) -> None:
        self.zone_stats = {
            "living_room": {"node_count": 3, "edge_count": 2},
            "hallway": {"node_count": 1, "edge_count": 0},
        }

    def get_graph_statistics(self):
        return {
            "total_nodes": 11,
            "total_edges": 7,
            "nodes_added_last_hour": 2,
            "edges_added_last_hour": 1,
            "growth_rate_nodes_per_hour": 2.5,
            "growth_rate_edges_per_hour": 1.25,
            "last_input_timestamp": "2026-04-05T03:40:00+00:00",
            "brain_freshness_score": 0.91,
        }

    def get_zone_graph_stats(self, zone_id: str):
        return self.zone_stats[zone_id]


class FakeNeuronManager:
    def get_module_contexts(self):
        return [{"module_id": "mood_engine"}, {"module_id": "light_engine"}]

    def get_zone_neuron_ids(self, zone_id: str):
        return {
            "context": [f"ctx-{zone_id}"],
            "state": [f"state-{zone_id}"],
            "mood": [f"mood-{zone_id}"],
        }


class FakeZoneTruth:
    def get_all_zones(self):
        return [
            {
                "zone_id": "living_room",
                "name": "Living Room",
                "enabled": True,
                "entities": ["light.living_room_main", "sensor.living_room_motion"],
            },
            {
                "zone_id": "hallway",
                "name": "Hallway",
                "enabled": False,
                "entities": ["light.hallway_main"],
            },
        ]


class ExplodingReadModel:
    def __init__(self, method_name: str, message: str) -> None:
        self.method_name = method_name
        self.message = message

    def _explode(self, current: str):
        if self.method_name == current:
            raise RuntimeError(self.message)

    def get_brain_growth_summary(self):
        self._explode("summary")

    def get_semantic_transfer_trace(self, _input_id: str):
        self._explode("trace")

    def get_zone_brain_links(self):
        self._explode("zone-links")

    def get_recent_activity(self, limit: int = 50):
        self._explode("activity")
        return []


def _build_read_model():
    read_model = module.build_brain_growth_read_model(
        graph_service=FakeGraphService(),
        neuron_manager=FakeNeuronManager(),
        zone_truth=FakeZoneTruth(),
        event_processor=None,
    )
    read_model.log_semantic_transfer(
        SemanticTransferTrace(
            input_id="input-1",
            input_type="event",
            input_timestamp="2026-04-05T03:35:00+00:00",
            graph_updates=[{"type": "node_added", "node_id": "node-1"}],
            neuron_updates=[{"neuron_id": "ctx-living_room", "change": "activated"}],
            module_context_updates=[{"module_id": "mood_engine", "change": "freshened"}],
            propagation_depth=2,
            confidence_score=0.88,
        )
    )
    read_model.log_semantic_transfer(
        SemanticTransferTrace(
            input_id="input-2",
            input_type="sensor_reading",
            input_timestamp="2026-04-05T03:39:00+00:00",
            graph_updates=[{"type": "edge_added", "edge_id": "edge-1"}],
            neuron_updates=[{"neuron_id": "state-living_room", "change": "updated"}],
            module_context_updates=[{"module_id": "light_engine", "change": "propagated"}],
            propagation_depth=1,
            confidence_score=0.77,
        )
    )
    return read_model


def _build_client(monkeypatch, *, authorized: bool = True, read_model=None):
    monkeypatch.setattr(security, "validate_token", lambda _request: authorized)
    module._read_model = read_model
    app = Flask(__name__)
    app.register_blueprint(module.brain_growth_bp)
    return app.test_client()


def test_brain_growth_contract_covers_all_routes(monkeypatch) -> None:
    client = _build_client(monkeypatch, read_model=_build_read_model())

    response = client.get("/api/v1/brain/growth/summary")
    assert response.status_code == 200
    assert response.get_json() == {
        "total_nodes": 11,
        "total_edges": 7,
        "nodes_added_last_hour": 2,
        "edges_added_last_hour": 1,
        "growth_rate_nodes_per_hour": 2.5,
        "growth_rate_edges_per_hour": 1.25,
        "last_input_timestamp": "2026-04-05T03:40:00+00:00",
        "brain_freshness_score": 0.91,
        "active_zone_count": 1,
        "module_context_count": 2,
    }

    response = client.get("/api/v1/brain/growth/trace/input-1")
    assert response.status_code == 200
    assert response.get_json() == {
        "input_id": "input-1",
        "input_type": "event",
        "input_timestamp": "2026-04-05T03:35:00+00:00",
        "graph_updates": [{"type": "node_added", "node_id": "node-1"}],
        "neuron_updates": [{"neuron_id": "ctx-living_room", "change": "activated"}],
        "module_context_updates": [{"module_id": "mood_engine", "change": "freshened"}],
        "propagation_depth": 2,
        "confidence_score": 0.88,
    }

    response = client.get("/api/v1/brain/growth/zone-links")
    assert response.status_code == 200
    assert response.get_json() == [
        {
            "zone_id": "living_room",
            "zone_name": "Living Room",
            "entity_count": 2,
            "brain_node_count": 3,
            "brain_edge_count": 2,
            "context_neuron_ids": ["ctx-living_room"],
            "state_neuron_ids": ["state-living_room"],
            "mood_neuron_ids": ["mood-living_room"],
            "last_activity_timestamp": None,
            "activity_score": 0.0,
        },
        {
            "zone_id": "hallway",
            "zone_name": "Hallway",
            "entity_count": 1,
            "brain_node_count": 1,
            "brain_edge_count": 0,
            "context_neuron_ids": ["ctx-hallway"],
            "state_neuron_ids": ["state-hallway"],
            "mood_neuron_ids": ["mood-hallway"],
            "last_activity_timestamp": None,
            "activity_score": 0.0,
        },
    ]

    response = client.get("/api/v1/brain/growth/activity?limit=1")
    assert response.status_code == 200
    assert response.get_json() == [
        {
            "input_id": "input-2",
            "input_type": "sensor_reading",
            "input_timestamp": "2026-04-05T03:39:00+00:00",
            "graph_updates": [{"type": "edge_added", "edge_id": "edge-1"}],
            "neuron_updates": [{"neuron_id": "state-living_room", "change": "updated"}],
            "module_context_updates": [{"module_id": "light_engine", "change": "propagated"}],
            "propagation_depth": 1,
            "confidence_score": 0.77,
        }
    ]


def test_brain_growth_contract_hardens_uninitialized_validation_not_found_and_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch, read_model=None)

    for path in [
        "/api/v1/brain/growth/summary",
        "/api/v1/brain/growth/trace/input-1",
        "/api/v1/brain/growth/zone-links",
        "/api/v1/brain/growth/activity",
    ]:
        response = client.get(path)
        assert response.status_code == 503
        assert response.get_json() == {"error": "Brain Growth API not initialized"}

    client = _build_client(monkeypatch, read_model=_build_read_model())

    response = client.get("/api/v1/brain/growth/trace/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "No trace found for input missing"}

    response = client.get("/api/v1/brain/growth/activity?limit=abc")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be a positive integer"}

    response = client.get("/api/v1/brain/growth/activity?limit=0")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be a positive integer"}

    module._read_model = ExplodingReadModel("summary", "summary exploded")
    response = client.get("/api/v1/brain/growth/summary")
    assert response.status_code == 500
    assert response.get_json() == {"error": "summary exploded"}

    module._read_model = ExplodingReadModel("trace", "trace exploded")
    response = client.get("/api/v1/brain/growth/trace/input-1")
    assert response.status_code == 500
    assert response.get_json() == {"error": "trace exploded"}

    module._read_model = ExplodingReadModel("zone-links", "zone links exploded")
    response = client.get("/api/v1/brain/growth/zone-links")
    assert response.status_code == 500
    assert response.get_json() == {"error": "zone links exploded"}

    module._read_model = ExplodingReadModel("activity", "activity exploded")
    response = client.get("/api/v1/brain/growth/activity?limit=5")
    assert response.status_code == 500
    assert response.get_json() == {"error": "activity exploded"}


def test_brain_growth_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, read_model=_build_read_model())

    response = client.get("/api/v1/brain/growth/summary")
    assert response.status_code == 401
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }
