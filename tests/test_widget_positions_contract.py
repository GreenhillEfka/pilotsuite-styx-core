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

    event_count_before_bulk = len(app.widget_position_events)
    bulk = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "humidity-wohn", "x": 30, "y": 40},
                1,
                {"widget_id": 42, "x": 7, "y": 8},
                {"widget_id": "broken", "x": -1, "y": 0},
            ]
        },
    )
    assert bulk.status_code == 200
    assert bulk.get_json()["saved_count"] == 1
    assert bulk.get_json()["errors"] == [
        {"widget_id": "unknown", "error": "Invalid position payload"},
        {"widget_id": "unknown", "error": "Invalid widget_id"},
        {"widget_id": "broken", "error": "Position values must be positive"},
    ]
    bulk_position = client.get("/api/v1/widgets/positions/humidity-wohn").get_json()["position"]
    assert app.widget_position_events[event_count_before_bulk:] == [
        (
            "widget_position_update",
            {"widget_id": "humidity-wohn", "position": bulk_position},
        )
    ]

    invalid_history = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "history-broken", "x": 1, "y": 2, "history": {}},
    )
    assert invalid_history.status_code == 400
    assert invalid_history.get_json() == {"error": "Invalid history"}

    invalid_redo_stack = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "redo-broken", "x": 3, "y": 4, "redo_stack": {}},
            ]
        },
    )
    assert invalid_redo_stack.status_code == 200
    assert invalid_redo_stack.get_json()["saved_count"] == 0
    assert invalid_redo_stack.get_json()["errors"] == [
        {"widget_id": "redo-broken", "error": "Invalid redo_stack"}
    ]

    invalid_history_entry = client.post(
        "/api/v1/widgets/positions",
        json={
            "widget_id": "history-entry-broken",
            "x": 2,
            "y": 3,
            "history": [{"width": 1, "height": 1}],
        },
    )
    assert invalid_history_entry.status_code == 400
    assert invalid_history_entry.get_json() == {"error": "Invalid history entry"}

    invalid_redo_entry = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {
                    "widget_id": "redo-entry-broken",
                    "x": 3,
                    "y": 4,
                    "redo_stack": [{"x": 7, "height": 2}],
                },
            ]
        },
    )
    assert invalid_redo_entry.status_code == 200
    assert invalid_redo_entry.get_json()["saved_count"] == 0
    assert invalid_redo_entry.get_json()["errors"] == [
        {"widget_id": "redo-entry-broken", "error": "Invalid redo_stack entry"}
    ]

    valid_history_shape = client.post(
        "/api/v1/widgets/positions",
        json={
            "widget_id": "history-ok",
            "x": 5,
            "y": 6,
            "history": [{"x": 1, "y": 2, "timestamp": "2026-04-08T08:00:00+00:00"}],
            "redo_stack": [{"x": 7, "y": 8, "width": 2, "height": 3}],
        },
    )
    assert valid_history_shape.status_code == 200
    assert valid_history_shape.get_json()["position"]["history"] == [
        {"x": 1, "y": 2, "timestamp": "2026-04-08T08:00:00+00:00"}
    ]
    assert valid_history_shape.get_json()["position"]["redo_stack"] == [
        {"x": 7, "y": 8, "width": 2, "height": 3}
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
        ({"widget_id": 7, "x": 1, "y": 2}, "Invalid widget_id"),
        ({"widget_id": "temp", "y": 2}, "Missing required field: x"),
        ({"widget_id": "temp", "x": 1, "y": 2, "history": {}}, "Invalid history"),
        ({"widget_id": "temp", "x": 1, "y": 2, "history": [{}]}, "Invalid history entry"),
        ({"widget_id": "temp", "x": 1, "y": 2, "redo_stack": {}}, "Invalid redo_stack"),
        ({"widget_id": "temp", "x": 1, "y": 2, "redo_stack": [{}]}, "Invalid redo_stack entry"),
        ({"widget_id": "temp", "x": "abc", "y": 2}, "Invalid position values"),
        ({"widget_id": "temp", "x": -1, "y": 2}, "Position values must be positive"),
    ],
)
def test_widget_positions_contract_covers_validation_and_not_found_paths(client, payload, error):
    response = client.post("/api/v1/widgets/positions", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": error}

    invalid_shape = client.post("/api/v1/widgets/positions", json=[{"widget_id": "temp"}])
    assert invalid_shape.status_code == 400
    assert invalid_shape.get_json() == {"error": "Invalid position payload"}

    bulk_missing = client.post("/api/v1/widgets/positions/bulk", json={})
    assert bulk_missing.status_code == 400
    assert bulk_missing.get_json() == {"error": "No positions provided"}

    bulk_invalid = client.post("/api/v1/widgets/positions/bulk", json={"positions": "oops"})
    assert bulk_invalid.status_code == 400
    assert bulk_invalid.get_json() == {"error": "Invalid positions payload"}

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


def test_widget_positions_contract_ignores_missing_persisted_last_update_in_root_aggregation(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {"x": 4, "y": 2, "last_update": "2026-04-08T06:22:00+00:00"},
                "clock": {"x": 8, "y": 1},
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
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
            },
        },
        "total": 2,
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_history_entry_as_unavailable(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"width": 1, "height": 1}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "No history available"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["x"] == 4
    assert fetched.get_json()["position"]["history"] == [{"width": 1, "height": 1}]


def test_widget_positions_contract_treats_invalid_persisted_current_position_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/history", json={"reason": "legacy"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "y": 2,
        "width": 3,
        "height": 2,
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_current_position_as_not_found_for_undo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "y": 2,
        "width": 3,
        "height": 2,
        "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_current_position_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "y": 2,
        "width": 3,
        "height": 2,
        "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_history_container_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": {},
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/history", json={"reason": "legacy"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": {},
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_redo_container_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": {},
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/history", json={"reason": "legacy"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
        "redo_stack": {},
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_history_container_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": {},
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 9, "y": 8, "width": 5, "height": 4},
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": {},
        "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_redo_container_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": {},
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 9, "y": 8, "width": 5, "height": 4},
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
        "redo_stack": {},
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_reports_invalid_persisted_history_container_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": {},
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "weather", "x": 9, "y": 8, "width": 5, "height": 4},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json()["saved_count"] == 0
    assert response.get_json()["errors"] == [
        {"widget_id": "weather", "error": "Widget position not found"}
    ]

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": {},
        "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_reports_invalid_persisted_redo_container_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": {},
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "weather", "x": 9, "y": 8, "width": 5, "height": 4},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json()["saved_count"] == 0
    assert response.get_json()["errors"] == [
        {"widget_id": "weather", "error": "Widget position not found"}
    ]

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
        "redo_stack": {},
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_redo_entry_as_unavailable(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "height": 1}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "No redo available"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["x"] == 4
    assert fetched.get_json()["position"]["redo_stack"] == [{"x": 8, "height": 1}]


def test_widget_positions_contract_treats_invalid_persisted_redo_container_as_not_found_for_undo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": {},
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
        "redo_stack": {},
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_treats_invalid_persisted_history_container_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": {},
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-08T06:22:00+00:00",
                }
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

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == {
        "widget_id": "weather",
        "x": 4,
        "y": 2,
        "width": 3,
        "height": 2,
        "history": {},
        "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
        "last_update": "2026-04-08T06:22:00+00:00",
    }
