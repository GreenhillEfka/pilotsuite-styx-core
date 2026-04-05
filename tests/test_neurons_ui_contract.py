from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from copilot_core.api.v1 import neurons_ui as module  # noqa: E402


BASE_PATH = "/api/v1/neurons"
FIXED_TS = "2026-04-05T00:30:00+00:00"


def _build_client():
    app = Flask(__name__)
    app.register_blueprint(module.neurons_ui_bp)
    return app.test_client()


def _expected_serialized(neurons: list[dict[str, object]], *, value: float) -> list[dict[str, object]]:
    return [
        {**neuron, "value": value, "firing": False, "last_update": FIXED_TS}
        for neuron in neurons
    ]


def test_neurons_ui_core_surface_contracts(monkeypatch) -> None:
    monkeypatch.setattr(module, "_utc_now_iso", lambda: FIXED_TS)
    client = _build_client()

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    assert response.get_json() == {
        "layers": {
            "context": {
                "name": "CONTEXT",
                "description": "Objektive Umgebungsdaten",
                "neurons": _expected_serialized(module.CONTEXT_NEURONS, value=0.5),
            },
            "state": {
                "name": "STATE",
                "description": "Geglättete Zustände",
                "neurons": _expected_serialized(module.STATE_NEURONS, value=0.6),
            },
            "mood": {
                "name": "MOOD",
                "description": "Aggregierte Stimmung",
                "neurons": _expected_serialized(module.MOOD_NEURONS, value=0.4),
            },
        },
        "total_neurons": 25,
    }

    response = client.get(f"{BASE_PATH}/context")
    assert response.status_code == 200
    assert response.get_json() == {
        "layer": "context",
        "neurons": _expected_serialized(module.CONTEXT_NEURONS, value=0.5),
    }

    response = client.get(f"{BASE_PATH}/state")
    assert response.status_code == 200
    assert response.get_json() == {
        "layer": "state",
        "neurons": _expected_serialized(module.STATE_NEURONS, value=0.6),
    }

    response = client.get(f"{BASE_PATH}/mood")
    assert response.status_code == 200
    assert response.get_json() == {
        "layer": "mood",
        "neurons": _expected_serialized(module.MOOD_NEURONS, value=0.4),
        "dimensions": [
            {"id": dimension["id"], "name": dimension["name"], "value": 0.5}
            for dimension in module.MOOD_DIMENSIONS
        ],
    }

    response = client.get(f"{BASE_PATH}/pipeline")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "events_last_hour": 150,
        "patterns_discovered": 5,
        "suggestions_generated": 3,
        "last_run": FIXED_TS,
        "avg_latency_ms": 45,
        "neuron_fire_rates": {
            "context": 12.5,
            "state": 8.3,
            "mood": 4.2,
        },
    }

    response = client.post(f"{BASE_PATH}/evaluate", json={"force": True})
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "Pipeline evaluation triggered",
        "timestamp": FIXED_TS,
    }

    response = client.get(f"{BASE_PATH}/history?hours=48")
    assert response.status_code == 200
    assert response.get_json() == {
        "hours": 48,
        "history": [
            {
                "timestamp": FIXED_TS,
                "dominant_mood": "relax",
                "confidence": 0.85,
                "dimensions": {
                    "comfort": 0.8,
                    "joy": 0.7,
                    "frugality": 0.5,
                    "energy": 0.6,
                    "focus": 0.4,
                },
            }
        ],
    }

    response = client.get(f"{BASE_PATH}/graph")
    assert response.status_code == 200
    assert response.get_json() == {
        "svg_url": "/api/v1/neurons/graph.svg",
        "nodes": 25,
        "edges": 45,
        "layout": "hierarchical",
    }


def test_neurons_ui_validation_and_query_hardening(monkeypatch) -> None:
    monkeypatch.setattr(module, "_utc_now_iso", lambda: FIXED_TS)
    client = _build_client()

    response = client.post(f"{BASE_PATH}/evaluate", data="{", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "Invalid JSON body"}

    response = client.post(f"{BASE_PATH}/evaluate", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "JSON body must be an object"}

    response = client.post(f"{BASE_PATH}/evaluate", json={"force": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "force must be a boolean"}

    response = client.get(f"{BASE_PATH}/history?hours=abc")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid 'hours' parameter. Must be a positive integer.",
    }

    response = client.get(f"{BASE_PATH}/history?hours=0")
    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "error": "Invalid 'hours' parameter. Must be a positive integer.",
    }

    response = client.get(f"{BASE_PATH}/history?hours=999")
    assert response.status_code == 200
    assert response.get_json()["hours"] == module.MAX_HISTORY_HOURS


def test_neurons_ui_runtime_errors_return_consistent_json(monkeypatch) -> None:
    client = _build_client()

    monkeypatch.setattr(module, "_serialize_neurons", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("serialize failed")))
    response = client.get(BASE_PATH)
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "serialize failed"}

    monkeypatch.setattr(module, "_build_mood_history", lambda: (_ for _ in ()).throw(RuntimeError("history failed")))
    response = client.get(f"{BASE_PATH}/history")
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "history failed"}
