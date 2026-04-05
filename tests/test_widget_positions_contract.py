from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.api.v1 import widget_positions as module  # noqa: E402


class FakeSocketIO:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, event_name: str, payload: dict[str, object]) -> None:
        self.events.append((event_name, payload))


def _build_client(monkeypatch):
    monkeypatch.setattr(module, "save_positions_to_file", lambda: None)
    monkeypatch.setattr(module, "load_positions_from_file", lambda: None)
    module.widget_positions_store.clear()

    app = Flask(__name__)
    app.socketio = FakeSocketIO()
    app.register_blueprint(module.widget_positions_bp)
    return app.test_client(), app.socketio


def test_widget_positions_contract_covers_crud_history_redo_reset_and_events(monkeypatch) -> None:
    client, socketio = _build_client(monkeypatch)

    response = client.get("/api/v1/widgets/positions")
    assert response.status_code == 200
    assert response.get_json() == {"positions": {}, "total": 0, "last_update": None}

    response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 2, "y": 1, "width": 3, "height": 2, "zone_id": "living"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["widget_id"] == "weather"
    assert payload["position"]["zone_id"] == "living"
    assert payload["position"]["history"] == []

    response = client.get("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert response.get_json()["position"]["width"] == 3

    response = client.post("/api/v1/widgets/positions/weather/history", json={"reason": "before-move"})
    assert response.status_code == 200
    assert response.get_json()["history_length"] == 1

    module.widget_positions_store["weather"]["x"] = 5
    module.widget_positions_store["weather"]["y"] = 7

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 200
    undo_payload = response.get_json()
    assert undo_payload["position"]["x"] == 2
    assert undo_payload["position"]["y"] == 1
    assert undo_payload["history_remaining"] == 0

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 200
    redo_payload = response.get_json()
    assert redo_payload["position"]["x"] == 5
    assert redo_payload["position"]["y"] == 7
    assert redo_payload["redo_remaining"] == 0

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "lights", "x": 0, "y": 0},
                {"widget_id": "climate", "x": 4, "y": 1, "width": 2, "height": 1},
            ]
        },
    )
    assert response.status_code == 200
    bulk_payload = response.get_json()
    assert bulk_payload["success"] is True
    assert bulk_payload["saved_count"] == 2
    assert bulk_payload["errors"] == []
    assert bulk_payload["total_positions"] == 3

    response = client.delete("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert response.get_json()["widget_id"] == "weather"

    response = client.post("/api/v1/widgets/positions/reset")
    assert response.status_code == 200
    assert response.get_json()["message"] == "All widget positions reset"
    assert module.widget_positions_store == {}

    event_names = [event_name for event_name, _payload in socketio.events]
    assert event_names == [
        "widget_position_update",
        "widget_position_update",
        "widget_position_update",
        "widget_position_deleted",
        "widget_positions_reset",
    ]


def test_widget_positions_contract_covers_validation_and_not_found_paths(monkeypatch) -> None:
    client, _socketio = _build_client(monkeypatch)

    response = client.post("/api/v1/widgets/positions")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.post("/api/v1/widgets/positions", json=[{"widget_id": "weather"}])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/widgets/positions", json={"x": 0, "y": 0})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing required field: widget_id"}

    response = client.post("/api/v1/widgets/positions", json={"widget_id": "weather", "x": "bad", "y": 0})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid position values"}

    response = client.post("/api/v1/widgets/positions", json={"widget_id": "   ", "x": 1, "y": 0})
    assert response.status_code == 400
    assert response.get_json() == {"error": "widget_id must not be blank"}

    response = client.post("/api/v1/widgets/positions", json={"widget_id": "weather", "x": 0, "y": 0, "history": "bad"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "history must be a list"}

    response = client.post("/api/v1/widgets/positions", json={"widget_id": "weather", "x": -1, "y": 0})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Position values must be positive"}

    response = client.post("/api/v1/widgets/positions/bulk")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.post("/api/v1/widgets/positions/bulk", json={})
    assert response.status_code == 400
    assert response.get_json() == {"error": "No positions provided"}

    response = client.post("/api/v1/widgets/positions/bulk", json={"positions": {"widget_id": "weather"}})
    assert response.status_code == 400
    assert response.get_json() == {"error": "'positions' must be a list"}

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                "bad-entry",
                {"widget_id": "weather", "x": 1, "y": 2},
                {"widget_id": "bad-values", "x": -1, "y": 0},
                {"widget_id": "bad-history", "x": 2, "y": 1, "history": "bad"},
            ]
        },
    )
    assert response.status_code == 200
    bulk_payload = response.get_json()
    assert bulk_payload["saved_count"] == 1
    assert bulk_payload["total_positions"] == 1
    assert bulk_payload["errors"] == [
        {"widget_id": "unknown", "error": "Position entry must be an object"},
        {"widget_id": "bad-values", "error": "Position values must be positive", "status": 400},
        {"widget_id": "bad-history", "error": "history must be a list", "status": 400},
    ]

    response = client.get("/api/v1/widgets/positions/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    response = client.delete("/api/v1/widgets/positions/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    response = client.post("/api/v1/widgets/positions/missing/history", json={"reason": "noop"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    response = client.post("/api/v1/widgets/positions/missing/undo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    response = client.post("/api/v1/widgets/positions/missing/redo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    client.post("/api/v1/widgets/positions", json={"widget_id": "weather", "x": 1, "y": 2})

    response = client.post("/api/v1/widgets/positions/weather/history")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "No history available"}

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "No redo available"}
