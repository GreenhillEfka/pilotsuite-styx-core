from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app


@pytest.fixture()
def app(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    application = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions.json"),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    application.widget_position_events = events
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_widget_positions_contract_covers_crud_history_redo_reset_and_events(app, client):
    empty = client.get("/api/v1/widgets/positions")
    assert empty.status_code == 200
    assert empty.get_json()["total"] == 0

    created = client.post(
        "/api/v1/widgets/positions",
        json={
            "widget_id": "temp-wohn",
            "x": 1,
            "y": 2,
            "width": 3,
            "height": 4,
            "zone_id": "wohn",
        },
    )
    assert created.status_code == 200
    assert created.get_json()["position"]["zone_id"] == "wohn"
    assert app.widget_position_events[-1][0] == "widget_position_update"

    fetched = client.get("/api/v1/widgets/positions/temp-wohn")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["x"] == 1

    history = client.post(
        "/api/v1/widgets/positions/temp-wohn/history",
        json={"reason": "before move"},
    )
    assert history.status_code == 200
    assert history.get_json()["history_length"] == 1

    moved = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "temp-wohn", "x": 10, "y": 20, "width": 5, "height": 6},
    )
    assert moved.status_code == 200
    assert moved.get_json()["position"]["x"] == 10

    undone = client.post("/api/v1/widgets/positions/temp-wohn/undo")
    assert undone.status_code == 200
    assert undone.get_json()["position"]["x"] == 1
    assert app.widget_position_events[-1] == (
        "widget_position_update",
        {
            "widget_id": "temp-wohn",
            "position": undone.get_json()["position"],
            "action": "undo",
        },
    )

    redone = client.post("/api/v1/widgets/positions/temp-wohn/redo")
    assert redone.status_code == 200
    assert redone.get_json()["position"]["x"] == 10
    assert app.widget_position_events[-1] == (
        "widget_position_update",
        {
            "widget_id": "temp-wohn",
            "position": redone.get_json()["position"],
            "action": "redo",
        },
    )

    bulk = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "humidity-wohn", "x": 30, "y": 40},
                {"widget_id": "broken", "x": -1, "y": 0},
            ]
        },
    )
    assert bulk.status_code == 200
    assert bulk.get_json()["saved_count"] == 1
    assert bulk.get_json()["errors"] == [
        {"widget_id": "broken", "error": "Position values must be positive"}
    ]

    deleted = client.delete("/api/v1/widgets/positions/humidity-wohn")
    assert deleted.status_code == 200
    assert app.widget_position_events[-1] == (
        "widget_position_deleted",
        {"widget_id": "humidity-wohn"},
    )

    reset = client.post("/api/v1/widgets/positions/reset")
    assert reset.status_code == 200
    assert client.get("/api/v1/widgets/positions").get_json()["total"] == 0
    assert app.widget_position_events[-1] == ("widget_positions_reset", {})


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (None, "No data provided"),
        ({"x": 1, "y": 2}, "Missing required field: widget_id"),
        ({"widget_id": "temp", "y": 2}, "Missing required field: x"),
        ({"widget_id": "temp", "x": "abc", "y": 2}, "Invalid position values"),
        ({"widget_id": "temp", "x": -1, "y": 2}, "Position values must be positive"),
    ],
)
def test_widget_positions_contract_covers_validation_and_not_found_paths(client, payload, error):
    response = client.post("/api/v1/widgets/positions", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": error}

    bulk_missing = client.post("/api/v1/widgets/positions/bulk", json={})
    assert bulk_missing.status_code == 400
    assert bulk_missing.get_json() == {"error": "No positions provided"}

    missing_get = client.get("/api/v1/widgets/positions/missing")
    assert missing_get.status_code == 404
    assert missing_get.get_json() == {"error": "Widget position not found"}

    missing_delete = client.delete("/api/v1/widgets/positions/missing")
    assert missing_delete.status_code == 404
    assert missing_delete.get_json() == {"error": "Widget position not found"}

    missing_history = client.post("/api/v1/widgets/positions/missing/history", json={"ok": True})
    assert missing_history.status_code == 404
    assert missing_history.get_json() == {"error": "Widget position not found"}

    missing_undo = client.post("/api/v1/widgets/positions/missing/undo")
    assert missing_undo.status_code == 404
    assert missing_undo.get_json() == {"error": "Widget position not found"}

    missing_redo = client.post("/api/v1/widgets/positions/missing/redo")
    assert missing_redo.status_code == 404
    assert missing_redo.get_json() == {"error": "Widget position not found"}

    client.post("/api/v1/widgets/positions", json={"widget_id": "temp", "x": 0, "y": 0})

    no_history = client.post("/api/v1/widgets/positions/temp/undo")
    assert no_history.status_code == 404
    assert no_history.get_json() == {"error": "No history available"}

    no_redo = client.post("/api/v1/widgets/positions/temp/redo")
    assert no_redo.status_code == 404
    assert no_redo.get_json() == {"error": "No redo available"}


def test_widget_positions_contract_ignores_non_mapping_persisted_entries(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {"x": 4, "y": 2, "last_update": "2026-04-08T06:22:00+00:00"},
                "broken": ["not", "a", "mapping"],
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
        }
    )
    client = app.test_client()

    response = client.get("/api/v1/widgets/positions")
    assert response.status_code == 200
    assert response.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "last_update": "2026-04-08T06:22:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-08T06:22:00+00:00",
    }

    missing = client.get("/api/v1/widgets/positions/broken")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "Widget position not found"}
