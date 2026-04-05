from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
MODULE_PATH = CORE_APP_ROOT / "copilot_core" / "api" / "v1" / "module_health.py"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

spec = importlib.util.spec_from_file_location("ps_module_health_contract_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeModuleRegistry:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.states: object = {
            "mood_engine": "active",
            "habitus_miner": "learning",
        }

    def get_all_states(self):
        if self.raise_on == "get_all_states":
            raise RuntimeError("module registry exploded")
        return self.states


class FakeIntegrationBus:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.stats: object = {
            "events_published": 7,
            "events_delivered": 11,
            "errors": 0,
            "dead_letter_count": 0,
            "total_subscribers": 3,
            "event_types_active": ["neuron.evaluated"],
        }

    def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("integration bus exploded")
        return self.stats


class FakeHebbianLearning:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.stats: object = {
            "tracked_synapses": 2,
            "updates_applied": 5,
        }
        self.weights: object = {
            "context.presence->state.energy": 0.61,
            "state.energy->mood.focus": 0.42,
        }
        self.drift: object = {
            "context.presence->state.energy": 0.11,
        }

    def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("learning stats exploded")
        return self.stats

    def get_all_weights(self):
        if self.raise_on == "get_all_weights":
            raise RuntimeError("learning weights exploded")
        return self.weights

    def get_weight_drift(self):
        if self.raise_on == "get_weight_drift":
            raise RuntimeError("learning drift exploded")
        return self.drift


@dataclass
class FakeProposal:
    from_neuron: str
    to_neuron: str
    proposed_weight: float
    reason: str
    confidence: float


class FakeCrossModuleAnalyzer:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.patterns: object = [
            {
                "pattern_id": "context.presence~state.energy",
                "module_a": "context.presence",
                "module_b": "state.energy",
                "correlation": 0.91,
                "co_occurrence_count": 6,
                "description": "presence and energy move together",
                "discovered_at_ms": 1712400000123,
            }
        ]
        self.stats: object = {
            "snapshots_collected": 12,
            "window_size": 100,
            "patterns_discovered": 1,
            "min_correlation": 0.6,
        }
        self.proposals: object = [
            FakeProposal(
                from_neuron="context.presence",
                to_neuron="state.energy",
                proposed_weight=0.273,
                reason="presence and energy move together",
                confidence=0.91,
            )
        ]

    def get_patterns(self):
        if self.raise_on == "get_patterns":
            raise RuntimeError("patterns exploded")
        return self.patterns

    def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("pattern stats exploded")
        return self.stats

    def suggest_new_connections(self):
        if self.raise_on == "suggest_new_connections":
            raise RuntimeError("proposals exploded")
        return self.proposals


class FakeFeedbackLoop:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.stats: object = {
            "adjustments_applied": 4,
            "accept_delta": 0.05,
            "reject_delta": -0.08,
        }

    def get_stats(self):
        if self.raise_on == "get_stats":
            raise RuntimeError("feedback exploded")
        return self.stats


def _build_client(
    *,
    module_registry=None,
    integration_bus=None,
    hebbian_learning=None,
    cross_module_analyzer=None,
    feedback_loop=None,
):
    module.init_module_health_api(
        module_registry=module_registry,
        integration_bus=integration_bus,
        hebbian_learning=hebbian_learning,
        cross_module_analyzer=cross_module_analyzer,
        feedback_loop=feedback_loop,
    )
    app = Flask(__name__)
    app.register_blueprint(module.module_health_bp)
    return app.test_client()


def test_module_health_contract_covers_dashboard_learning_and_patterns(monkeypatch) -> None:
    registry = FakeModuleRegistry()
    bus = FakeIntegrationBus()
    learning = FakeHebbianLearning()
    analyzer = FakeCrossModuleAnalyzer()
    feedback = FakeFeedbackLoop()
    client = _build_client(
        module_registry=registry,
        integration_bus=bus,
        hebbian_learning=learning,
        cross_module_analyzer=analyzer,
        feedback_loop=feedback,
    )
    monkeypatch.setattr(module.time, "time", lambda: 1712400000.123)

    response = client.get("/api/v1/modules/health/dashboard")
    assert response.status_code == 200
    assert response.get_json() == {
        "timestamp_ms": 1712400000123,
        "modules": registry.states,
        "bus": bus.stats,
        "learning": {
            "tracked_synapses": 2,
            "updates_applied": 5,
            "weight_drift": learning.drift,
        },
        "cross_module": {
            "snapshots_collected": 12,
            "window_size": 100,
            "patterns_discovered": 1,
            "min_correlation": 0.6,
            "patterns": analyzer.patterns,
        },
        "feedback": feedback.stats,
    }

    response = client.get("/api/v1/modules/health/learning")
    assert response.status_code == 200
    assert response.get_json() == {
        "stats": learning.stats,
        "weights": learning.weights,
        "drift": learning.drift,
        "timestamp_ms": 1712400000123,
    }

    response = client.get("/api/v1/modules/health/patterns")
    assert response.status_code == 200
    assert response.get_json() == {
        "patterns": analyzer.patterns,
        "proposed_synapses": [
            {
                "from_neuron": "context.presence",
                "to_neuron": "state.energy",
                "proposed_weight": 0.273,
                "reason": "presence and energy move together",
                "confidence": 0.91,
            }
        ],
        "stats": analyzer.stats,
        "timestamp_ms": 1712400000123,
    }


def test_module_health_contract_hardens_uninitialized_invalid_payloads_and_runtime_errors(monkeypatch) -> None:
    client = _build_client()
    monkeypatch.setattr(module.time, "time", lambda: 1712400000.123)

    response = client.get("/api/v1/modules/health/dashboard")
    assert response.status_code == 200
    assert response.get_json() == {
        "timestamp_ms": 1712400000123,
        "modules": {},
        "bus": None,
        "learning": None,
        "cross_module": None,
        "feedback": None,
    }

    response = client.get("/api/v1/modules/health/learning")
    assert response.status_code == 503
    assert response.get_json() == {"error": "HebbianLearning not initialized"}

    response = client.get("/api/v1/modules/health/patterns")
    assert response.status_code == 503
    assert response.get_json() == {"error": "CrossModuleAnalyzer not initialized"}

    registry = FakeModuleRegistry()
    bus = FakeIntegrationBus()
    learning = FakeHebbianLearning()
    analyzer = FakeCrossModuleAnalyzer()
    feedback = FakeFeedbackLoop()
    client = _build_client(
        module_registry=registry,
        integration_bus=bus,
        hebbian_learning=learning,
        cross_module_analyzer=analyzer,
        feedback_loop=feedback,
    )

    registry.raise_on = "get_all_states"
    response = client.get("/api/v1/modules/health/dashboard")
    assert response.status_code == 500
    assert response.get_json() == {"error": "module registry exploded"}

    registry.raise_on = None
    learning.stats = "broken"
    response = client.get("/api/v1/modules/health/dashboard")
    assert response.status_code == 500
    assert response.get_json() == {"error": "HebbianLearning stats must be an object"}

    learning.stats = {
        "tracked_synapses": 2,
        "updates_applied": 5,
    }
    learning.raise_on = "get_all_weights"
    response = client.get("/api/v1/modules/health/learning")
    assert response.status_code == 500
    assert response.get_json() == {"error": "learning weights exploded"}

    learning.raise_on = None
    analyzer.patterns = "broken"
    response = client.get("/api/v1/modules/health/patterns")
    assert response.status_code == 500
    assert response.get_json() == {"error": "CrossModuleAnalyzer patterns must be a list"}

    analyzer.patterns = [
        {
            "pattern_id": "context.presence~state.energy",
            "module_a": "context.presence",
            "module_b": "state.energy",
            "correlation": 0.91,
            "co_occurrence_count": 6,
            "description": "presence and energy move together",
            "discovered_at_ms": 1712400000123,
        }
    ]
    analyzer.proposals = [{"from_neuron": "context.presence"}]
    response = client.get("/api/v1/modules/health/patterns")
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "Proposed synapse must expose from_neuron, to_neuron, proposed_weight, reason, confidence"
    }
