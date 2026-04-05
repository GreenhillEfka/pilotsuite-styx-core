from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import neurons as module  # noqa: E402


class FakeConfig:
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        decay_rate: float = 0.2,
        smoothing_factor: float = 0.3,
        weights: dict[str, float] | None = None,
        enabled: bool = True,
    ) -> None:
        self.threshold = threshold
        self.decay_rate = decay_rate
        self.smoothing_factor = smoothing_factor
        self.weights = dict(weights or {"energy": 0.4})
        self.enabled = enabled

    def to_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "decay_rate": self.decay_rate,
            "smoothing_factor": self.smoothing_factor,
            "weights": dict(self.weights),
            "enabled": self.enabled,
        }


class FakeNeuron:
    def __init__(self, neuron_id: str, *, neuron_type: str = "context") -> None:
        self.neuron_id = neuron_id
        self.name = neuron_id.split(".")[-1]
        self.type = neuron_type
        self.state = {"value": 0.73}
        self.config = FakeConfig()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "state": dict(self.state),
            "config": self.config.to_dict(),
        }


class FakeResult:
    def __init__(self) -> None:
        self.timestamp = "2026-04-04T16:20:00Z"
        self.context_values = {"presence": 0.9}
        self.state_values = {"energy": 0.7}
        self.mood_values = {"focus": 0.8}
        self.dominant_mood = "focus"
        self.mood_confidence = 0.88
        self.suggestions = [{"id": "sg-1", "title": "Open window"}]
        self.neuron_states = {"context.presence": {"value": 0.9}}


class FakeManager:
    def __init__(self) -> None:
        self.neurons = {
            "context.presence": FakeNeuron("context.presence"),
            "mood.focus": FakeNeuron("mood.focus", neuron_type="mood"),
        }
        self._ha_states: dict[str, object] = {}
        self._last_result = FakeResult()
        self.updated_states_calls: list[dict[str, object]] = []
        self.context_calls: list[dict[str, object]] = []
        self.configure_calls: list[tuple[dict[str, object], dict[str, object]]] = []
        self.evaluate_calls = 0
        self.persisted_neuron_ids: list[str] = []
        self.persist_all_calls = 0
        self.raise_on_summary: Exception | None = None

    def get_neuron_summary(self) -> dict[str, object]:
        if self.raise_on_summary is not None:
            raise self.raise_on_summary
        return {
            "context": ["context.presence"],
            "state": [],
            "mood": ["mood.focus"],
            "total_count": len(self.neurons),
        }

    def get_neuron(self, neuron_id: str):
        return self.neurons.get(neuron_id)

    def update_states(self, states: dict[str, object]) -> None:
        self.updated_states_calls.append(dict(states))
        self._ha_states.update(states)

    def set_context(self, context: dict[str, object]) -> None:
        self.context_calls.append(dict(context))

    def evaluate(self) -> FakeResult:
        self.evaluate_calls += 1
        self._last_result = FakeResult()
        return self._last_result

    def configure_from_ha(self, states: dict[str, object], config: dict[str, object]) -> None:
        self.configure_calls.append((dict(states), dict(config)))

    def get_mood_summary(self) -> dict[str, object]:
        return {
            "mood": "focus",
            "confidence": 0.88,
            "mood_values": {"focus": 0.8},
            "timestamp": self._last_result.timestamp,
        }

    def to_dict(self) -> dict[str, object]:
        return {"configured": True, "neuron_count": len(self.neurons)}

    def persist_neuron_config(self, neuron_id: str) -> None:
        self.persisted_neuron_ids.append(neuron_id)

    def persist_all_neuron_configs(self) -> None:
        self.persist_all_calls += 1


class FakeMoodHistoryStore:
    def __init__(self) -> None:
        self.recent_calls: list[int] = []
        self.trend_calls: list[int] = []
        self.raise_on_recent: Exception | None = None

    def get_recent(self, *, hours: int) -> list[dict[str, object]]:
        if self.raise_on_recent is not None:
            raise self.raise_on_recent
        self.recent_calls.append(hours)
        return [
            {"mood": "focus", "confidence": 0.8},
            {"mood": "relax", "confidence": 0.6},
        ]

    def get_trend(self, *, hours: int) -> dict[str, object]:
        self.trend_calls.append(hours)
        return {
            "count": 2,
            "distribution": {"focus": 1, "relax": 1},
            "dominant_mood": "focus",
            "avg_confidence": 0.7,
            "period_hours": hours,
        }


class FakeMetrics:
    def to_dict(self) -> dict[str, object]:
        return {
            "fire_rate": 0.9,
            "confidence": 0.82,
            "avg_value": 0.71,
            "trend": "up",
            "last_fire_time": "2026-04-04T16:19:00Z",
        }


class FakeGraphNode:
    def __init__(self, neuron_id: str, *, neuron_type: str = "context", layer: int = 1, value: float = 0.731) -> None:
        self.neuron_id = neuron_id
        self.name = neuron_id.split(".")[-1]
        self.neuron_type = neuron_type
        self.layer = layer
        self.active = True
        self.value = value
        self.metrics = FakeMetrics()


class FakeGraph:
    def __init__(self) -> None:
        self.nodes = {
            "context.presence": FakeGraphNode("context.presence"),
            "mood.focus": FakeGraphNode("mood.focus", neuron_type="mood", layer=3, value=0.944),
        }
        self.raise_on_stats: Exception | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [{"id": node_id} for node_id in self.nodes],
            "edges": [{"from": "context.presence", "to": "mood.focus"}],
            "metadata": {"total_nodes": len(self.nodes)},
        }

    def get_node(self, neuron_id: str):
        return self.nodes.get(neuron_id)

    def get_incoming_edges(self, neuron_id: str) -> list[dict[str, object]]:
        return [] if neuron_id == "context.presence" else [{"from": "context.presence", "to": neuron_id}]

    def get_outgoing_edges(self, neuron_id: str) -> list[dict[str, object]]:
        return [{"from": neuron_id, "to": "mood.focus"}] if neuron_id == "context.presence" else []

    def get_stats(self) -> dict[str, object]:
        if self.raise_on_stats is not None:
            raise self.raise_on_stats
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": len(self.nodes),
            "total_edges": 1,
            "avg_fire_rate": 0.9,
            "avg_confidence": 0.82,
            "layers": {"1": 1, "3": 1},
        }


def _build_client(
    monkeypatch,
    *,
    auth_ok: bool = True,
    manager: FakeManager | None = None,
    graph: FakeGraph | None = None,
    mood_store: FakeMoodHistoryStore | None = None,
    connections_result: dict[str, object] | None = None,
    connections_error: Exception | None = None,
    path_result: list[dict[str, object]] | None = None,
    path_error: Exception | None = None,
):
    manager = manager or FakeManager()
    graph = graph or FakeGraph()
    mood_store = mood_store or FakeMoodHistoryStore()
    path_calls: list[tuple[str, str, int]] = []

    monkeypatch.setattr(module, "_validate_token", lambda _request: auth_ok)
    monkeypatch.setattr(module, "require_admin_token", lambda request: request.headers.get("X-Admin") == "1")
    monkeypatch.setattr(module, "get_neuron_manager", lambda: manager)
    monkeypatch.setattr(module, "get_mood_history_store", lambda: mood_store)
    monkeypatch.setattr(module.neuron_graph_module, "get_neuron_graph", lambda: graph)

    def _connections(node_id: str | None = None):
        if connections_error is not None:
            raise connections_error
        return connections_result or {
            "node_id": node_id,
            "node_name": "Presence",
            "incoming": [],
            "outgoing": [{"to": "mood.focus"}],
            "total_connections": 1,
        }

    def _paths(from_id: str, to_id: str, max_depth: int):
        path_calls.append((from_id, to_id, max_depth))
        if path_error is not None:
            raise path_error
        return path_result or [
            {
                "path": [from_id, to_id],
                "length": 1,
                "nodes": [from_id, to_id],
            }
        ]

    monkeypatch.setattr(module, "get_neuron_connections", _connections)
    monkeypatch.setattr(module, "find_paths", _paths)

    app = Flask(__name__)
    app.register_blueprint(module.bp, url_prefix="/api/v1/neurons")
    return app.test_client(), manager, graph, mood_store, path_calls


def test_neurons_requires_auth(monkeypatch) -> None:
    client, *_ = _build_client(monkeypatch, auth_ok=False)

    response = client.get("/api/v1/neurons")

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }


def test_neurons_core_surface_contracts(monkeypatch) -> None:
    client, manager, _graph, mood_store, path_calls = _build_client(monkeypatch)

    response = client.get("/api/v1/neurons")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": manager.get_neuron_summary(),
    }

    response = client.get("/api/v1/neurons/context.presence")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": manager.neurons["context.presence"].to_dict(),
    }

    response = client.get("/api/v1/neurons/mood")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": manager.get_mood_summary(),
    }

    response = client.get("/api/v1/neurons/suggestions")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "suggestions": manager._last_result.suggestions,
            "mood": manager._last_result.dominant_mood,
            "timestamp": manager._last_result.timestamp,
        },
    }
    assert manager.evaluate_calls == 0

    response = client.get("/api/v1/neurons/graph")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "nodes": [{"id": "context.presence"}, {"id": "mood.focus"}],
            "edges": [{"from": "context.presence", "to": "mood.focus"}],
            "metadata": {"total_nodes": 2},
        },
    }

    response = client.get("/api/v1/neurons/presence/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "neuron_id": "context.presence",
            "name": "presence",
            "type": "context",
            "layer": 1,
            "active": True,
            "value": 0.731,
            "metrics": {
                "fire_rate": 0.9,
                "confidence": 0.82,
                "avg_value": 0.71,
                "trend": "up",
                "last_fire_time": "2026-04-04T16:19:00Z",
            },
            "connections": {"incoming": 0, "outgoing": 1},
        },
    }

    response = client.get("/api/v1/neurons/graph/stats")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "total_nodes": 2,
            "active_nodes": 2,
            "total_edges": 1,
            "avg_fire_rate": 0.9,
            "avg_confidence": 0.82,
            "layers": {"1": 1, "3": 1},
        },
    }

    response = client.get("/api/v1/neurons/connections?node_id=context.presence")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "node_id": "context.presence",
            "node_name": "Presence",
            "incoming": [],
            "outgoing": [{"to": "mood.focus"}],
            "total_connections": 1,
        },
    }

    response = client.get("/api/v1/neurons/paths?from=context.presence&to=mood.focus&max_depth=99")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "from": "context.presence",
            "to": "mood.focus",
            "paths": [{"path": ["context.presence", "mood.focus"], "length": 1, "nodes": ["context.presence", "mood.focus"]}],
            "path_count": 1,
            "max_depth": 10,
        },
    }
    assert path_calls == [("context.presence", "mood.focus", 10)]

    response = client.get("/api/v1/neurons/mood/history?hours=500")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "history": [
                {"mood": "focus", "confidence": 0.8},
                {"mood": "relax", "confidence": 0.6},
            ],
            "count": 2,
            "hours": 168,
        },
    }
    assert mood_store.recent_calls == [168]

    response = client.get("/api/v1/neurons/mood/trend?hours=0")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "count": 2,
            "distribution": {"focus": 1, "relax": 1},
            "dominant_mood": "focus",
            "avg_confidence": 0.7,
            "period_hours": 1,
        },
    }
    assert mood_store.trend_calls == [1]


def test_neurons_validation_and_lookup_error_paths(monkeypatch) -> None:
    client, *_ = _build_client(
        monkeypatch,
        connections_result={"error": "Neuron not found: missing.node"},
        path_error=ValueError("No path found between nodes"),
    )

    response = client.get("/api/v1/neurons/INVALID-ID")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid neuron_id format. Must be lowercase letters, underscores, or dots.",
    }

    response = client.get("/api/v1/neurons/context.missing")
    assert response.status_code == 404
    assert response.get_json() == {
        "success": False,
        "error": "Neuron not found: context.missing",
    }

    response = client.get("/api/v1/neurons/mood/history?hours=abc")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid 'hours' parameter. Must be a positive integer.",
    }

    response = client.get("/api/v1/neurons/mood/trend?hours=abc")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid 'hours' parameter. Must be a positive integer.",
    }

    response = client.get("/api/v1/neurons/connections?node_id=missing.node")
    assert response.status_code == 404
    assert response.get_json() == {
        "success": False,
        "error": "Neuron not found: missing.node",
    }

    response = client.get("/api/v1/neurons/paths")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Missing required parameters: 'from' and 'to'",
    }

    response = client.get("/api/v1/neurons/paths?from=context.presence&to=mood.focus&max_depth=abc")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid 'max_depth' parameter. Must be a positive integer.",
    }

    response = client.get("/api/v1/neurons/paths?from=context.presence&to=mood.focus")
    assert response.status_code == 404
    assert response.get_json() == {
        "success": False,
        "error": "No path found between nodes",
    }


def test_neurons_mutation_admin_and_batch_contracts(monkeypatch) -> None:
    client, manager, *_ = _build_client(monkeypatch)

    response = client.post("/api/v1/neurons/evaluate", json={"states": {"sensor.kitchen": {"state": "on"}}})
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for state overrides",
    }

    response = client.post(
        "/api/v1/neurons/evaluate",
        json={"states": {"sensor.kitchen": {"state": "on"}}, "context": {"zone": "kitchen"}},
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["dominant_mood"] == "focus"
    assert manager.updated_states_calls[-1] == {"sensor.kitchen": {"state": "on"}}
    assert manager.context_calls[-1] == {"zone": "kitchen"}

    response = client.post("/api/v1/neurons/update", json={"states": {"sensor.office": {"state": "off"}}})
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for state updates",
    }

    response = client.post("/api/v1/neurons/update", json={}, headers={"X-Admin": "1"})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "No JSON body provided",
    }

    response = client.post("/api/v1/neurons/update", json={"states": {}}, headers={"X-Admin": "1"})
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "No states provided",
    }

    response = client.post(
        "/api/v1/neurons/update",
        json={"states": {"sensor.office": {"state": "off"}}},
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"updated": 1, "total_states": 2},
    }

    response = client.post(
        "/api/v1/neurons/configure",
        json={"states": {"sensor.office": {"state": "off"}}, "config": {"mode": "demo"}},
    )
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for neuron configuration",
    }

    response = client.post(
        "/api/v1/neurons/configure",
        json={"states": {"sensor.office": {"state": "off"}}, "config": {"mode": "demo"}},
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"configured": True, "neuron_count": 2},
    }
    assert manager.configure_calls == [({"sensor.office": {"state": "off"}}, {"mode": "demo"})]

    response = client.patch("/api/v1/neurons/context.presence/config", json={"threshold": 0.75})
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for neuron configuration updates",
    }

    response = client.patch(
        "/api/v1/neurons/context.presence/config",
        json={"threshold": 1.5},
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid value: threshold must be between 0.0 and 1.0",
    }

    response = client.patch(
        "/api/v1/neurons/context.presence/config",
        json={"threshold": 0.75, "weights": {"energy": 0.9}, "enabled": False},
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "neuron_id": "context.presence",
            "changed": ["threshold", "weights", "enabled"],
            "config": {
                "threshold": 0.75,
                "decay_rate": 0.2,
                "smoothing_factor": 0.3,
                "weights": {"energy": 0.9},
                "enabled": False,
            },
        },
    }
    assert manager.persisted_neuron_ids[-1] == "context.presence"

    response = client.post("/api/v1/neurons/context.presence/enable")
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for neuron enable",
    }

    response = client.post("/api/v1/neurons/context.presence/enable", headers={"X-Admin": "1"})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"neuron_id": "context.presence", "enabled": True},
    }

    response = client.post("/api/v1/neurons/context.presence/disable", headers={"X-Admin": "1"})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"neuron_id": "context.presence", "enabled": False},
    }

    response = client.post(
        "/api/v1/neurons/batch-configure",
        json={"neurons": {"context.presence": {"enabled": True}}},
    )
    assert response.status_code == 403
    assert response.get_json() == {
        "success": False,
        "error": "Admin token required for neuron batch configuration",
    }

    response = client.post(
        "/api/v1/neurons/batch-configure",
        json={
            "neurons": {
                "context.presence": {"threshold": 2.0},
                "mood.focus": {"enabled": False, "weights": {"energy": 0.2}},
            }
        },
        headers={"X-Admin": "1"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": False,
        "data": {
            "updated": {
                "mood.focus": {
                    "threshold": 0.5,
                    "decay_rate": 0.2,
                    "smoothing_factor": 0.3,
                    "weights": {"energy": 0.2},
                    "enabled": False,
                }
            },
            "errors": {
                "context.presence": "threshold must be between 0.0 and 1.0",
            },
        },
    }
    assert manager.neurons["context.presence"].config.threshold == 0.75
    assert manager.persist_all_calls == 1


def test_neurons_runtime_errors_return_consistent_json(monkeypatch) -> None:
    manager = FakeManager()
    manager.raise_on_summary = RuntimeError("summary failed")
    mood_store = FakeMoodHistoryStore()
    mood_store.raise_on_recent = RuntimeError("history failed")
    graph = FakeGraph()
    graph.raise_on_stats = RuntimeError("graph stats failed")

    client, *_ = _build_client(
        monkeypatch,
        manager=manager,
        graph=graph,
        mood_store=mood_store,
        connections_error=RuntimeError("connections failed"),
    )

    response = client.get("/api/v1/neurons")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "summary failed"}

    response = client.get("/api/v1/neurons/mood/history")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "history failed"}

    response = client.get("/api/v1/neurons/graph/stats")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "graph stats failed"}

    response = client.get("/api/v1/neurons/connections")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "connections failed"}
