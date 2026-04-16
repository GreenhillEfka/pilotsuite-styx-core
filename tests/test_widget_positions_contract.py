from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilotsuite_core" / "rootfs" / "usr" / "src" / "app"))

from main import create_app
from dashboard.api.v1 import widget_positions as widget_positions_api


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
        ({"widget_id": "temp", "x": 1, "y": 2, "zone_id": {"id": "wohn"}}, "Invalid zone_id"),
        ({"widget_id": "temp", "x": 1, "y": 2, "snap_to_grid": {"enabled": True}}, "Invalid snap_to_grid"),
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

    bulk_invalid_zone_id = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "temp", "x": 1, "y": 2, "zone_id": {"id": "wohn"}},
            ]
        },
    )
    assert bulk_invalid_zone_id.status_code == 200
    assert bulk_invalid_zone_id.get_json()["saved_count"] == 0
    assert bulk_invalid_zone_id.get_json()["errors"] == [
        {"widget_id": "temp", "error": "Invalid zone_id"}
    ]

    bulk_invalid_snap_to_grid = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "temp", "x": 1, "y": 2, "snap_to_grid": {"enabled": True}},
            ]
        },
    )
    assert bulk_invalid_snap_to_grid.status_code == 200
    assert bulk_invalid_snap_to_grid.get_json()["saved_count"] == 0
    assert bulk_invalid_snap_to_grid.get_json()["errors"] == [
        {"widget_id": "temp", "error": "Invalid snap_to_grid"}
    ]

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
                "width": 1,
                "height": 1,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
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
                "width": 1,
                "height": 1,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-08T06:22:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 1,
                "height": 1,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
            },
        },
        "total": 2,
        "last_update": "2026-04-08T06:22:00+00:00",
    }


def test_widget_positions_contract_excludes_invalid_persisted_last_update_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": {"at": "2026-04-09T01:10:00+00:00"},
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_excludes_invalid_persisted_zone_id_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "snap_to_grid": True,
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "zone_id": "kitchen",
                    "snap_to_grid": True,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "kitchen",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_excludes_invalid_persisted_snap_to_grid_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "snap_to_grid": False,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": False,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_normalizes_numeric_string_history_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [
                        {
                            "x": "1",
                            "y": "0",
                            "width": "3",
                            "height": "2",
                            "timestamp": "2026-04-09T01:08:00+00:00",
                        }
                    ],
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [
                    {
                        "x": 1,
                        "y": 0,
                        "width": 3,
                        "height": 2,
                        "timestamp": "2026-04-09T01:08:00+00:00",
                    }
                ],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [
                {
                    "x": 1,
                    "y": 0,
                    "width": 3,
                    "height": 2,
                    "timestamp": "2026-04-09T01:08:00+00:00",
                }
            ],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_normalizes_numeric_string_redo_stack_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [
                        {
                            "x": "9",
                            "y": "5",
                            "width": "4",
                            "height": "2",
                            "timestamp": "2026-04-09T01:09:00+00:00",
                        }
                    ],
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                                "zone_id": "global",
                                "snap_to_grid": True,
"history": [],
"redo_stack": [
                    {
                        "x": 9,
                        "y": 5,
                        "width": 4,
                        "height": 2,
                        "timestamp": "2026-04-09T01:09:00+00:00",
                    }
                ],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                                "zone_id": "global",
                                "snap_to_grid": True,
"history": [],
"redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
                        "zone_id": "global",
                        "snap_to_grid": True,
"history": [],
"redo_stack": [
                {
                    "x": 9,
                    "y": 5,
                    "width": 4,
                    "height": 2,
                    "timestamp": "2026-04-09T01:09:00+00:00",
                }
            ],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_normalizes_numeric_string_current_position_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": "4",
                    "y": "2",
                    "width": "3",
                    "height": "2",
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_defaults_missing_current_position_size_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 1,
                "height": 1,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 1,
            "height": 1,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_defaults_missing_current_position_zone_id_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "zone_id": "kitchen",
                    "snap_to_grid": True,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "kitchen",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }




def test_widget_positions_contract_defaults_missing_current_position_snap_to_grid_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "snap_to_grid": False,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": False,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_defaults_missing_history_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }


def test_widget_positions_contract_defaults_missing_redo_stack_from_read_truth(tmp_path):
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
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                "redo_stack": [],
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        },
        "total": 2,
        "last_update": "2026-04-09T01:10:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json() == {
        "widget_id": "weather",
        "position": {
            "widget_id": "weather",
            "x": 4,
            "y": 2,
            "width": 3,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
            "redo_stack": [],
            "last_update": "2026-04-09T01:10:00+00:00",
        },
    }

    fetched_clock = client.get("/api/v1/widgets/positions/clock")
    assert fetched_clock.status_code == 200
    assert fetched_clock.get_json() == {
        "widget_id": "clock",
        "position": {
            "widget_id": "clock",
            "x": 8,
            "y": 1,
            "width": 2,
            "height": 2,
            "zone_id": "global",
            "snap_to_grid": True,
            "history": [],
            "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
            "last_update": "2026-04-09T01:05:00+00:00",
        },
    }



def test_widget_positions_contract_excludes_invalid_persisted_history_entry_from_read_truth(tmp_path):
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
                    "last_update": "2026-04-09T01:11:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_excludes_invalid_persisted_current_position_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-09T01:09:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


@pytest.mark.parametrize(
    ("persisted_entry", "other_entry"),
    [
        (
            {"y": 2, "width": 3, "height": 2, "last_update": "2026-04-09T01:10:00+00:00"},
            {"x": 8, "y": 1, "width": 2, "height": 2, "last_update": "2026-04-09T01:05:00+00:00"},
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "history": {},
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                "redo_stack": {},
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {"x": 4, "y": 2, "width": 3, "height": 2, "last_update": 1700000000},
            {"x": 8, "y": 1, "width": 2, "height": 2, "last_update": "2026-04-09T01:05:00+00:00"},
        ),
        (
            {"x": 4, "y": 2, "width": 3, "height": 2, "zone_id": 17, "last_update": "2026-04-09T01:10:00+00:00"},
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "snap_to_grid": "yes",
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "snap_to_grid": True,
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "widget_id": "clock",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
    ],
    ids=[
        "current-position",
        "history-container",
        "redo-container",
        "last-update",
        "zone-id",
        "snap-to-grid",
        "widget-id-drift",
    ],
)
def test_widget_positions_contract_treats_read_excluded_persisted_entries_as_not_found_for_delete(
    tmp_path, persisted_entry, other_entry
):
    persisted_file = tmp_path / "widget_positions.json"
    initial_payload = {
        "weather": persisted_entry,
        "clock": other_entry,
    }
    persisted_file.write_text(json.dumps(initial_payload))

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    listed_before = client.get("/api/v1/widgets/positions")
    assert listed_before.status_code == 200
    assert "weather" not in listed_before.get_json()["positions"]

    fetched_before = client.get("/api/v1/widgets/positions/weather")
    assert fetched_before.status_code == 404
    assert fetched_before.get_json() == {"error": "Widget position not found"}

    response = client.delete("/api/v1/widgets/positions/weather")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}
    assert events == []
    assert json.loads(persisted_file.read_text()) == initial_payload

    listed_after = client.get("/api/v1/widgets/positions")
    assert listed_after.status_code == 200
    assert listed_after.get_json() == listed_before.get_json()


@pytest.mark.parametrize(
    ("persisted_entry", "other_entry"),
    [
        (
            {"width": 3, "height": 2, "last_update": "2026-04-09T01:10:00+00:00"},
            {"x": 8, "y": 1, "width": 2, "height": 2, "last_update": "2026-04-09T01:05:00+00:00"},
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "history": {},
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                "redo_stack": {},
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {"x": 4, "y": 2, "width": 3, "height": 2, "last_update": 1700000000},
            {"x": 8, "y": 1, "width": 2, "height": 2, "last_update": "2026-04-09T01:05:00+00:00"},
        ),
        (
            {"x": 4, "y": 2, "width": 3, "height": 2, "zone_id": 17, "last_update": "2026-04-09T01:10:00+00:00"},
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "snap_to_grid": "yes",
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "snap_to_grid": True,
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
        (
            {
                "widget_id": "clock",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "last_update": "2026-04-09T01:10:00+00:00",
            },
            {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "last_update": "2026-04-09T01:05:00+00:00",
            },
        ),
    ],
    ids=[
        "current-position",
        "history-container",
        "redo-container",
        "last-update",
        "zone-id",
        "snap-to-grid",
        "widget-id-drift",
    ],
)
def test_widget_positions_contract_reset_only_clears_public_read_snapshot(
    tmp_path, persisted_entry, other_entry
):
    persisted_file = tmp_path / "widget_positions.json"
    hidden_payload = {
        "weather": persisted_entry,
        "clock": other_entry,
    }
    persisted_file.write_text(json.dumps(hidden_payload))

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()
    expected_hidden_entry = dict(persisted_entry)
    expected_hidden_entry.setdefault("widget_id", "weather")

    listed_before = client.get("/api/v1/widgets/positions")
    assert listed_before.status_code == 200
    assert set(listed_before.get_json()["positions"].keys()) == {"clock"}

    response = client.post("/api/v1/widgets/positions/reset")
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert response.get_json()["message"] == "All widget positions reset"
    assert events == [("widget_positions_reset", {})]
    assert json.loads(persisted_file.read_text()) == {"weather": expected_hidden_entry}

    hidden_after = client.get("/api/v1/widgets/positions/weather")
    assert hidden_after.status_code == 404
    assert hidden_after.get_json() == {"error": "Widget position not found"}

    listed_after = client.get("/api/v1/widgets/positions")
    assert listed_after.status_code == 200
    assert listed_after.get_json() == {"positions": {}, "total": 0, "last_update": None}


def test_widget_positions_contract_reset_treats_publicly_empty_snapshot_as_noop(tmp_path, monkeypatch):
    local_timestamp = "2026-04-10T00:14:01+00:00"
    server_owned_timestamp = "2026-04-10T00:14:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    hidden_payload = {
        "weather": {
            "y": 2,
            "width": 3,
            "height": 2,
            "last_update": "2026-04-10T00:14:00+00:00",
        }
    }
    persisted_file.write_text(json.dumps(hidden_payload))

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    listed_before = client.get("/api/v1/widgets/positions")
    assert listed_before.status_code == 200
    assert listed_before.get_json() == {"positions": {}, "total": 0, "last_update": None}

    response = client.post("/api/v1/widgets/positions/reset")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "No widget positions to reset",
        "timestamp": None,
    }
    assert response.get_json()["timestamp"] != local_timestamp
    assert response.get_json()["timestamp"] != server_owned_timestamp
    assert events == []
    assert json.loads(persisted_file.read_text()) == hidden_payload

    listed_after = client.get("/api/v1/widgets/positions")
    assert listed_after.status_code == 200
    assert listed_after.get_json() == listed_before.get_json()


def test_widget_positions_contract_repeated_reset_after_public_clear_becomes_noop(tmp_path, monkeypatch):
    mutation_timestamps = iter(
        [
            "2026-04-10T00:20:01+00:00",
            "2026-04-10T00:20:02+00:00",
        ]
    )
    server_owned_calls: list[str] = []

    def fake_server_owned_last_update() -> str:
        timestamp = next(mutation_timestamps)
        server_owned_calls.append(timestamp)
        return timestamp

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        fake_server_owned_last_update,
    )

    persisted_file = tmp_path / "widget_positions.json"
    initial_payload = {
        "weather": {
            "y": 2,
            "width": 3,
            "height": 2,
            "last_update": "2026-04-10T00:20:00+00:00",
        },
        "clock": {
            "x": 8,
            "y": 1,
            "width": 2,
            "height": 2,
            "last_update": "2026-04-10T00:19:00+00:00",
        },
    }
    persisted_file.write_text(json.dumps(initial_payload))

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    listed_before = client.get("/api/v1/widgets/positions")
    assert listed_before.status_code == 200
    assert listed_before.get_json()["positions"].keys() == {"clock"}

    first_reset = client.post("/api/v1/widgets/positions/reset")
    assert first_reset.status_code == 200
    assert first_reset.get_json() == {
        "success": True,
        "message": "All widget positions reset",
        "timestamp": "2026-04-10T00:20:01+00:00",
    }
    assert server_owned_calls == ["2026-04-10T00:20:01+00:00"]
    assert events == [("widget_positions_reset", {})]
    assert json.loads(persisted_file.read_text()) == {
        "weather": {
            "widget_id": "weather",
            "y": 2,
            "width": 3,
            "height": 2,
            "last_update": "2026-04-10T00:20:00+00:00",
        }
    }

    second_reset = client.post("/api/v1/widgets/positions/reset")
    assert second_reset.status_code == 200
    assert second_reset.get_json() == {
        "success": True,
        "message": "No widget positions to reset",
        "timestamp": None,
    }
    assert server_owned_calls == ["2026-04-10T00:20:01+00:00"]
    assert events == [("widget_positions_reset", {})]
    assert json.loads(persisted_file.read_text()) == {
        "weather": {
            "widget_id": "weather",
            "y": 2,
            "width": 3,
            "height": 2,
            "last_update": "2026-04-10T00:20:00+00:00",
        }
    }

    listed_after = client.get("/api/v1/widgets/positions")
    assert listed_after.status_code == 200
    assert listed_after.get_json() == {"positions": {}, "total": 0, "last_update": None}


def test_widget_positions_contract_excludes_invalid_persisted_history_container_from_read_truth(tmp_path):
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
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_excludes_invalid_persisted_redo_container_from_read_truth(tmp_path):
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
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                                "zone_id": "global",
                                "snap_to_grid": True,
"history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_excludes_invalid_persisted_redo_entry_from_read_truth(tmp_path):
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
                    "redo_stack": [{"x": 8, "height": 1}],
                    "last_update": "2026-04-09T01:10:00+00:00",
                },
                "clock": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                    "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 8,
                "y": 1,
                "width": 2,
                "height": 2,
                                "zone_id": "global",
                                "snap_to_grid": True,
"history": [{"x": 7, "y": 1, "width": 2, "height": 2}],
                "redo_stack": [{"x": 6, "y": 1, "width": 2, "height": 2}],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_history_entry_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "height": 2}],
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_redo_entry_as_not_found_for_history(tmp_path):
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

    response = client.post("/api/v1/widgets/positions/weather/history", json={"reason": "legacy"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_persisted_widget_id_drift_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_last_update_as_not_found_for_history(tmp_path):
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
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": {"at": "2026-04-09T10:20:00+00:00"},
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_zone_id_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_snap_to_grid_as_not_found_for_history(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_current_position_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_excludes_persisted_widget_id_drift_from_read_truth(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T01:00:00+00:00",
                },
                "clock": {
                    "x": 7,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-09T01:05:00+00:00",
                },
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

    listed = client.get("/api/v1/widgets/positions")
    assert listed.status_code == 200
    assert listed.get_json() == {
        "positions": {
            "clock": {
                "widget_id": "clock",
                "x": 7,
                "y": 1,
                "width": 2,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-09T01:05:00+00:00",
            }
        },
        "total": 1,
        "last_update": "2026-04-09T01:05:00+00:00",
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_persisted_widget_id_drift_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T01:00:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_redo_entry_as_not_found_for_overwrite_save(tmp_path):
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

    response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 9, "y": 8, "width": 5, "height": 4},
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "Widget position not found"}

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_reports_invalid_persisted_current_position_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_reports_persisted_widget_id_drift_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T01:00:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_reports_invalid_persisted_redo_entry_for_bulk_overwrite_save(tmp_path):
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_treats_invalid_persisted_history_entry_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "height": 2}],
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_last_update_as_not_found_for_overwrite_save(tmp_path):
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
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": {"at": "2026-04-09T10:20:00+00:00"},
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_zone_id_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_snap_to_grid_as_not_found_for_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_reports_invalid_persisted_history_entry_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "height": 2}],
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_reports_invalid_persisted_last_update_for_bulk_overwrite_save(tmp_path):
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
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": {"at": "2026-04-09T10:20:00+00:00"},
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_reports_invalid_persisted_zone_id_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_reports_invalid_persisted_snap_to_grid_for_bulk_overwrite_save(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_persisted_widget_id_drift_as_not_found_for_undo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_persisted_widget_id_drift_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "climate",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_last_update_as_not_found_for_undo(tmp_path):
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
                    "last_update": {"at": "2026-04-09T10:20:00+00:00"},
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_last_update_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": {"at": "2026-04-09T10:20:00+00:00"},
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_defaults_missing_current_position_zone_id_for_undo(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

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
                    "last_update": "2026-04-09T10:20:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 200
    assert response.get_json()["position"]["zone_id"] == "global"
    assert events[-1][0] == "widget_position_update"
    assert events[-1][1]["position"]["zone_id"] == "global"

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["zone_id"] == "global"



def test_widget_positions_contract_defaults_missing_current_position_zone_id_for_redo(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 200
    assert response.get_json()["position"]["zone_id"] == "global"
    assert events[-1][0] == "widget_position_update"
    assert events[-1][1]["position"]["zone_id"] == "global"

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["zone_id"] == "global"



def test_widget_positions_contract_treats_invalid_persisted_zone_id_as_not_found_for_undo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_zone_id_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "zone_id": {"id": "wohn"},
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_defaults_missing_current_position_snap_to_grid_for_undo(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

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
                    "last_update": "2026-04-09T10:20:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 200
    assert response.get_json()["position"]["snap_to_grid"] is True
    assert events[-1][0] == "widget_position_update"
    assert events[-1][1]["position"]["snap_to_grid"] is True

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["snap_to_grid"] is True



def test_widget_positions_contract_defaults_missing_current_position_snap_to_grid_for_redo(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 200
    assert response.get_json()["position"]["snap_to_grid"] is True
    assert events[-1][0] == "widget_position_update"
    assert events[-1][1]["position"]["snap_to_grid"] is True

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["snap_to_grid"] is True



def test_widget_positions_contract_treats_invalid_persisted_snap_to_grid_as_not_found_for_undo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



def test_widget_positions_contract_treats_invalid_persisted_snap_to_grid_as_not_found_for_redo(tmp_path):
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "snap_to_grid": {"enabled": True},
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": "2026-04-09T10:20:00+00:00",
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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}



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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


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
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_overwrites_client_supplied_root_last_update_for_single_overwrite(app, client):
    created = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 4, "y": 2},
    )
    assert created.status_code == 200

    client_supplied_last_update = "1999-12-31T23:59:59+00:00"
    overwritten = client.post(
        "/api/v1/widgets/positions",
        json={
            "widget_id": "weather",
            "x": 8,
            "y": 6,
            "last_update": client_supplied_last_update,
        },
    )
    assert overwritten.status_code == 200

    overwritten_json = overwritten.get_json()
    position = overwritten_json["position"]
    assert position["last_update"] != client_supplied_last_update
    assert app.widget_position_events[-1] == (
        "widget_position_update",
        {"widget_id": "weather", "position": position},
    )

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["last_update"] == position["last_update"]


def test_widget_positions_contract_overwrites_client_supplied_root_last_update_for_bulk_overwrite(app, client):
    created = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 4, "y": 2},
    )
    assert created.status_code == 200

    client_supplied_last_update = "1998-01-02T03:04:05+00:00"
    bulk = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {
                    "widget_id": "weather",
                    "x": 9,
                    "y": 7,
                    "last_update": client_supplied_last_update,
                }
            ]
        },
    )
    assert bulk.status_code == 200
    bulk_json = bulk.get_json()
    assert bulk_json["saved_count"] == 1
    assert bulk_json["errors"] == []

    saved_positions = bulk_json["saved_positions"]
    assert saved_positions == [app.widget_position_events[-1][1]]
    assert saved_positions[0]["position"]["last_update"] != client_supplied_last_update

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["last_update"] == saved_positions[0]["position"]["last_update"]


def test_widget_positions_contract_single_overwrite_uses_saved_root_last_update_for_response_timestamp(tmp_path, monkeypatch):
    previous_last_update = "2026-04-09T10:20:00+00:00"
    local_timestamp = "2026-04-09T10:20:01+00:00"
    server_owned_timestamp = "2026-04-09T10:20:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": previous_last_update,
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
        json={"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
    )
    assert response.status_code == 200

    response_json = response.get_json()
    response_position = response_json["position"]
    assert response_json["timestamp"] == server_owned_timestamp
    assert response_json["timestamp"] != local_timestamp
    assert response_position["last_update"] == response_json["timestamp"]
    assert response_position["last_update"] != previous_last_update

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["last_update"] == response_json["timestamp"]



def test_widget_positions_contract_bulk_overwrite_uses_saved_root_last_update_for_response_timestamp(tmp_path, monkeypatch):
    previous_last_update = "2026-04-09T10:20:00+00:00"
    local_timestamp = "2026-04-09T10:20:01+00:00"
    server_owned_timestamp = "2026-04-09T10:20:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": previous_last_update,
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
                {"widget_id": "weather", "x": 9, "y": 7, "width": 3, "height": 2}
            ]
        },
    )
    assert response.status_code == 200

    response_json = response.get_json()
    assert response_json["saved_count"] == 1
    assert response_json["errors"] == []
    assert response_json["timestamp"] == server_owned_timestamp
    assert response_json["timestamp"] != local_timestamp
    assert response_json["saved_positions"][0]["position"]["last_update"] == response_json["timestamp"]
    assert response_json["saved_positions"][0]["position"]["last_update"] != previous_last_update

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"]["last_update"] == response_json["timestamp"]



def test_widget_positions_contract_history_uses_saved_root_last_update_for_mutation_timestamp(tmp_path, monkeypatch):
    previous_last_update = "2026-04-09T10:20:00+00:00"
    local_timestamp = "2026-04-09T10:20:01+00:00"
    server_owned_timestamp = "2026-04-09T10:20:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": previous_last_update,
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
    assert response.status_code == 200

    response_json = response.get_json()
    assert response_json["history_length"] == 1
    assert response_json["timestamp"] == server_owned_timestamp
    assert response_json["timestamp"] != previous_last_update

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    fetched_position = fetched.get_json()["position"]
    assert fetched_position["last_update"] == response_json["timestamp"]
    assert len(fetched_position["history"]) == response_json["history_length"]
    assert fetched_position["history"][-1]["timestamp"] == server_owned_timestamp
    assert fetched_position["history"][-1]["timestamp"] != local_timestamp


def test_widget_positions_contract_undo_uses_saved_root_last_update_for_mutation_timestamp(tmp_path, monkeypatch):
    previous_last_update = "2026-04-09T10:20:00+00:00"
    local_timestamp = "2026-04-09T10:20:01+00:00"
    server_owned_timestamp = "2026-04-09T10:20:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [
                        {"x": 1, "y": 0, "width": 3, "height": 2},
                        {"x": 2, "y": 1, "width": 3, "height": 2},
                    ],
                    "last_update": previous_last_update,
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
    assert response.status_code == 200

    response_json = response.get_json()
    assert response_json["history_remaining"] == 1
    assert response_json["timestamp"] == server_owned_timestamp
    assert response_json["timestamp"] != previous_last_update

    response_position = response_json["position"]
    assert response_position["last_update"] == server_owned_timestamp
    assert response_position["redo_stack"][-1]["timestamp"] == server_owned_timestamp
    assert response_position["redo_stack"][-1]["timestamp"] != local_timestamp

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    fetched_position = fetched.get_json()["position"]
    assert fetched_position["last_update"] == response_json["timestamp"]
    assert fetched_position["redo_stack"][-1]["timestamp"] == server_owned_timestamp



def test_widget_positions_contract_undo_uses_saved_snapshot_for_response_event_parity(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    previous_last_update = "2026-04-09T10:20:00+00:00"
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [
                        {"x": "1", "y": "0", "width": "3", "height": "2"},
                        {"x": 2, "y": 1, "width": 3, "height": 2},
                    ],
                    "last_update": previous_last_update,
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/undo")
    assert response.status_code == 200

    response_position = response.get_json()["position"]
    assert response_position["last_update"] != previous_last_update
    assert response_position["history"] == [
        {"x": 1, "y": 0, "width": 3, "height": 2}
    ]
    assert events[-1] == (
        "widget_position_update",
        {"widget_id": "weather", "position": response_position, "action": "undo"},
    )

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == response_position


def test_widget_positions_contract_redo_uses_saved_root_last_update_for_mutation_timestamp(tmp_path, monkeypatch):
    previous_last_update = "2026-04-09T10:20:00+00:00"
    local_timestamp = "2026-04-09T10:20:01+00:00"
    server_owned_timestamp = "2026-04-09T10:20:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [
                        {"x": 6, "y": 7, "width": 3, "height": 2},
                        {"x": 8, "y": 9, "width": 3, "height": 2},
                    ],
                    "last_update": previous_last_update,
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
    assert response.status_code == 200

    response_json = response.get_json()
    assert response_json["redo_remaining"] == 1
    assert response_json["timestamp"] == server_owned_timestamp
    assert response_json["timestamp"] != previous_last_update

    response_position = response_json["position"]
    assert response_position["last_update"] == server_owned_timestamp
    assert response_position["history"][-1]["timestamp"] == server_owned_timestamp
    assert response_position["history"][-1]["timestamp"] != local_timestamp

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    fetched_position = fetched.get_json()["position"]
    assert fetched_position["last_update"] == response_json["timestamp"]
    assert fetched_position["history"][-1]["timestamp"] == server_owned_timestamp



def test_widget_positions_contract_redo_uses_saved_snapshot_for_response_event_parity(tmp_path):
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    previous_last_update = "2026-04-09T10:20:00+00:00"
    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "redo_stack": [
                        {"x": "6", "y": "7", "width": "3", "height": "2"},
                        {"x": 8, "y": 9, "width": 3, "height": 2},
                    ],
                    "last_update": previous_last_update,
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/weather/redo")
    assert response.status_code == 200

    response_position = response.get_json()["position"]
    assert response_position["last_update"] != previous_last_update
    assert response_position["redo_stack"] == [
        {"x": 6, "y": 7, "width": 3, "height": 2}
    ]
    assert events[-1] == (
        "widget_position_update",
        {"widget_id": "weather", "position": response_position, "action": "redo"},
    )

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 200
    assert fetched.get_json()["position"] == response_position


def test_widget_positions_contract_delete_uses_server_owned_mutation_timestamp_for_response(tmp_path, monkeypatch):
    local_timestamp = "2026-04-10T00:10:01+00:00"
    server_owned_timestamp = "2026-04-10T00:10:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.delete("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "widget_id": "weather",
        "timestamp": server_owned_timestamp,
    }
    assert response.get_json()["timestamp"] != local_timestamp
    assert events[-1] == ("widget_position_deleted", {"widget_id": "weather"})

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_single_overwrite_request_error_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[str] = []

    def fake_single_overwrite_request_error_payload(error: str) -> dict[str, str]:
        helper_calls.append(error)
        return {
            "error": error,
            "contract": "single-overwrite-request-error-helper",
        }

    monkeypatch.setattr(
        widget_positions_api,
        "_single_overwrite_request_error_payload",
        fake_single_overwrite_request_error_payload,
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions.json"),
        }
    )
    client = app.test_client()

    missing_response = client.post("/api/v1/widgets/positions", json=None)
    assert missing_response.status_code == 400
    assert missing_response.get_json() == {
        "error": "No data provided",
        "contract": "single-overwrite-request-error-helper",
    }

    invalid_response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": 7, "x": 1, "y": 2},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.get_json() == {
        "error": "Invalid widget_id",
        "contract": "single-overwrite-request-error-helper",
    }

    assert helper_calls == [
        "No data provided",
        "Invalid widget_id",
    ]



def test_widget_positions_contract_history_request_error_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[str] = []

    def fake_history_request_error_payload(error: str) -> dict[str, str]:
        helper_calls.append(error)
        return {
            "error": error,
            "contract": "history-request-error-helper",
        }

    monkeypatch.setattr(
        widget_positions_api,
        "_history_request_error_payload",
        fake_history_request_error_payload,
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions.json"),
        }
    )
    client = app.test_client()

    missing_response = client.post("/api/v1/widgets/positions/weather/history", json=None)
    assert missing_response.status_code == 400
    assert missing_response.get_json() == {
        "error": "No data provided",
        "contract": "history-request-error-helper",
    }

    assert helper_calls == ["No data provided"]



def test_widget_positions_contract_history_not_found_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "Widget position not found",
        "contract": "history-not-found-helper",
    }
    helper_calls: list[str] = []

    def fake_history_not_found_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_history_not_found_payload",
        fake_history_not_found_payload,
    )

    mismatch_file = tmp_path / "widget_positions_history_mismatch.json"
    mismatch_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "other",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    mismatch_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(mismatch_file),
        }
    )
    mismatch_client = mismatch_app.test_client()

    mismatch_response = mismatch_client.post(
        "/api/v1/widgets/positions/weather/history",
        json={"reason": "legacy"},
    )
    assert mismatch_response.status_code == 404
    assert mismatch_response.get_json() == helper_payload

    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: "2026-04-10T00:10:01+00:00")
    monkeypatch.setattr(widget_positions_api, "_saved_position_payload", lambda widget_id: None)

    fallback_file = tmp_path / "widget_positions_history_saved_payload_missing.json"
    fallback_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "weather",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    fallback_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(fallback_file),
        }
    )
    fallback_client = fallback_app.test_client()

    fallback_response = fallback_client.post(
        "/api/v1/widgets/positions/weather/history",
        json={"reason": "legacy"},
    )
    assert fallback_response.status_code == 404
    assert fallback_response.get_json() == helper_payload

    assert helper_calls == ["called", "called"]



def test_widget_positions_contract_undo_not_found_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "Widget position not found",
        "contract": "undo-not-found-helper",
    }
    helper_calls: list[str] = []

    def fake_undo_not_found_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_undo_not_found_payload",
        fake_undo_not_found_payload,
    )

    mismatch_file = tmp_path / "widget_positions_undo_mismatch.json"
    mismatch_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "other",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    mismatch_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(mismatch_file),
        }
    )
    mismatch_client = mismatch_app.test_client()

    mismatch_response = mismatch_client.post("/api/v1/widgets/positions/weather/undo")
    assert mismatch_response.status_code == 404
    assert mismatch_response.get_json() == helper_payload

    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: "2026-04-10T00:10:01+00:00")
    monkeypatch.setattr(widget_positions_api, "_saved_position_payload", lambda widget_id: None)

    fallback_file = tmp_path / "widget_positions_undo_saved_payload_missing.json"
    fallback_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "weather",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    fallback_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(fallback_file),
        }
    )
    fallback_client = fallback_app.test_client()

    fallback_response = fallback_client.post("/api/v1/widgets/positions/weather/undo")
    assert fallback_response.status_code == 404
    assert fallback_response.get_json() == helper_payload

    assert helper_calls == ["called", "called"]



def test_widget_positions_contract_undo_no_history_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "No history available",
        "contract": "undo-no-history-helper",
    }
    helper_calls: list[str] = []

    def fake_undo_no_history_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_undo_no_history_payload",
        fake_undo_no_history_payload,
    )

    empty_history_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions_undo_no_history_empty.json"),
        }
    )
    empty_history_client = empty_history_app.test_client()

    created = empty_history_client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 4, "y": 2},
    )
    assert created.status_code == 200

    empty_history_response = empty_history_client.post("/api/v1/widgets/positions/weather/undo")
    assert empty_history_response.status_code == 404
    assert empty_history_response.get_json() == helper_payload

    invalid_history_file = tmp_path / "widget_positions_undo_no_history_invalid_entry.json"
    invalid_history_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "weather",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"width": 1, "height": 1}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    invalid_history_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(invalid_history_file),
        }
    )
    invalid_history_client = invalid_history_app.test_client()

    invalid_history_response = invalid_history_client.post("/api/v1/widgets/positions/weather/undo")
    assert invalid_history_response.status_code == 404
    assert invalid_history_response.get_json() == helper_payload

    assert helper_calls == ["called", "called"]



def test_widget_positions_contract_history_success_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "success": True,
        "widget_id": "weather",
        "history_length": 7,
        "timestamp": "2026-04-10T00:10:02+00:00",
        "meta": "history-success-response-helper",
    }
    helper_calls: list[tuple[str, int, str | None]] = []

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:10:02+00:00",
    )

    def fake_history_success_payload(
        widget_id: str,
        history_length: int,
        timestamp: str | None,
    ) -> dict[str, object]:
        helper_calls.append((widget_id, history_length, timestamp))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_history_success_payload",
        fake_history_success_payload,
    )

    persisted_file = tmp_path / "widget_positions_history_success.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "weather",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [],
                    "last_update": "2026-04-10T00:10:00+00:00",
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
        "/api/v1/widgets/positions/weather/history",
        json={"reason": "legacy"},
    )
    assert response.status_code == 200
    assert response.get_json() == helper_payload
    assert helper_calls == [
        (
            "weather",
            2,
            "2026-04-10T00:10:02+00:00",
        )
    ]



def test_widget_positions_contract_single_overwrite_not_found_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "Widget position not found",
        "contract": "single-overwrite-not-found-helper",
    }
    helper_calls: list[str] = []

    def fake_single_overwrite_not_found_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_single_overwrite_not_found_payload",
        fake_single_overwrite_not_found_payload,
    )

    mismatch_file = tmp_path / "widget_positions_mismatch.json"
    mismatch_file.write_text(
        json.dumps(
            {
                "weather": {
                    "widget_id": "other",
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                }
            }
        )
    )

    mismatch_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(mismatch_file),
        }
    )
    mismatch_client = mismatch_app.test_client()

    mismatch_response = mismatch_client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
    )
    assert mismatch_response.status_code == 404
    assert mismatch_response.get_json() == helper_payload

    invalid_last_update_file = tmp_path / "widget_positions_invalid_last_update.json"
    invalid_last_update_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [{"x": 1, "y": 0, "width": 3, "height": 2}],
                    "redo_stack": [{"x": 8, "y": 9, "width": 3, "height": 2}],
                    "last_update": {"at": "2026-04-10T00:09:01+00:00"},
                }
            }
        )
    )

    invalid_last_update_app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(invalid_last_update_file),
        }
    )
    invalid_last_update_client = invalid_last_update_app.test_client()

    invalid_last_update_response = invalid_last_update_client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
    )
    assert invalid_last_update_response.status_code == 404
    assert invalid_last_update_response.get_json() == helper_payload

    assert helper_calls == ["called", "called"]



def test_widget_positions_contract_single_overwrite_success_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "success": True,
        "widget_id": "weather",
        "position": {
            "contract": "single-overwrite-success-helper",
        },
        "timestamp": "2026-04-10T00:09:03+00:00",
        "meta": "single-overwrite-response-helper",
    }
    helper_calls: list[tuple[str, dict[str, object], str | None]] = []

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:09:03+00:00",
    )

    def fake_single_overwrite_success_payload(
        widget_id: str,
        position: dict[str, object],
        timestamp: str | None,
    ) -> dict[str, object]:
        helper_calls.append((widget_id, dict(position), timestamp))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_single_overwrite_success_payload",
        fake_single_overwrite_success_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
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
        json={"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
    )
    assert response.status_code == 200
    assert response.get_json() == helper_payload
    assert helper_calls == [
        (
            "weather",
            {
                "widget_id": "weather",
                "x": 8,
                "y": 6,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-10T00:09:03+00:00",
            },
            "2026-04-10T00:09:03+00:00",
        )
    ]



def test_widget_positions_contract_single_overwrite_success_event_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "widget_id": "weather",
        "position": {"contract": "single-overwrite-event-helper"},
        "meta": "single-overwrite-event-helper",
    }
    helper_calls: list[dict[str, object]] = []
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:09:04+00:00",
    )

    def fake_single_overwrite_event_payload(saved_payload: dict[str, object]) -> dict[str, object]:
        helper_calls.append(json.loads(json.dumps(saved_payload)))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_single_overwrite_event_payload",
        fake_single_overwrite_event_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post(
        "/api/v1/widgets/positions",
        json={"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
    )
    assert response.status_code == 200
    assert helper_calls == [
        {
            "widget_id": "weather",
            "position": {
                "widget_id": "weather",
                "x": 8,
                "y": 6,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-10T00:09:04+00:00",
            },
        }
    ]
    assert events == [("widget_position_update", helper_payload)]



def test_widget_positions_contract_bulk_overwrite_success_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "success": True,
        "saved_count": 7,
        "saved_positions": [{"contract": "bulk-overwrite-success-helper"}],
        "errors": [{"widget_id": "bad", "error": "bulk-helper-error"}],
        "total_positions": 11,
        "timestamp": "2026-04-10T00:09:04+00:00",
        "meta": "bulk-overwrite-response-helper",
    }
    helper_calls: list[
        tuple[int, list[dict[str, object]], list[dict[str, str]], int, str | None]
    ] = []

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:09:04+00:00",
    )

    def fake_bulk_overwrite_success_payload(
        saved_count: int,
        saved_positions: list[dict[str, object]],
        errors: list[dict[str, str]],
        total_positions: int,
        timestamp: str | None,
    ) -> dict[str, object]:
        helper_calls.append(
            (
                saved_count,
                [dict(payload) for payload in saved_positions],
                [dict(error) for error in errors],
                total_positions,
                timestamp,
            )
        )
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_bulk_overwrite_success_payload",
        fake_bulk_overwrite_success_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
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
                {"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
                {"widget_id": "unknown"},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json() == helper_payload
    assert helper_calls == [
        (
            1,
            [
                {
                    "widget_id": "weather",
                    "position": {
                        "widget_id": "weather",
                        "x": 8,
                        "y": 6,
                        "width": 3,
                        "height": 2,
                        "zone_id": "global",
                        "snap_to_grid": True,
                        "history": [],
                        "redo_stack": [],
                        "last_update": "2026-04-10T00:09:04+00:00",
                    },
                }
            ],
            [{"widget_id": "unknown", "error": "Missing required field: x"}],
            1,
            "2026-04-10T00:09:04+00:00",
        )
    ]



def test_widget_positions_contract_bulk_overwrite_success_event_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "widget_id": "weather",
        "position": {"contract": "bulk-overwrite-event-helper"},
        "meta": "bulk-overwrite-event-helper",
    }
    helper_calls: list[dict[str, object]] = []
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:09:05+00:00",
    )

    def fake_bulk_overwrite_event_payload(saved_payload: dict[str, object]) -> dict[str, object]:
        helper_calls.append(json.loads(json.dumps(saved_payload)))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_bulk_overwrite_event_payload",
        fake_bulk_overwrite_event_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
                {"widget_id": "unknown"},
            ]
        },
    )
    assert response.status_code == 200
    assert helper_calls == [
        {
            "widget_id": "weather",
            "position": {
                "widget_id": "weather",
                "x": 8,
                "y": 6,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-10T00:09:05+00:00",
            },
        }
    ]
    assert events == [("widget_position_update", helper_payload)]



def test_widget_positions_contract_bulk_overwrite_request_error_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[str] = []

    def fake_bulk_overwrite_request_error_payload(error: str) -> dict[str, str]:
        helper_calls.append(error)
        return {
            "error": error,
            "contract": "bulk-overwrite-request-error-helper",
        }

    monkeypatch.setattr(
        widget_positions_api,
        "_bulk_overwrite_request_error_payload",
        fake_bulk_overwrite_request_error_payload,
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions.json"),
        }
    )
    client = app.test_client()

    missing_response = client.post("/api/v1/widgets/positions/bulk", json={})
    assert missing_response.status_code == 400
    assert missing_response.get_json() == {
        "error": "No positions provided",
        "contract": "bulk-overwrite-request-error-helper",
    }

    invalid_response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={"positions": "oops"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.get_json() == {
        "error": "Invalid positions payload",
        "contract": "bulk-overwrite-request-error-helper",
    }

    assert helper_calls == [
        "No positions provided",
        "Invalid positions payload",
    ]



def test_widget_positions_contract_bulk_overwrite_validation_error_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[tuple[str, str]] = []

    def fake_bulk_overwrite_validation_error_payload(widget_id: str, error: str) -> dict[str, str]:
        helper_calls.append((widget_id, error))
        return {
            "widget_id": widget_id,
            "error": error,
            "contract": "bulk-overwrite-validation-helper",
        }

    monkeypatch.setattr(
        widget_positions_api,
        "_bulk_overwrite_validation_error_payload",
        fake_bulk_overwrite_validation_error_payload,
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(tmp_path / "widget_positions.json"),
        }
    )
    client = app.test_client()

    response = client.post(
        "/api/v1/widgets/positions/bulk",
        json={
            "positions": [
                {"widget_id": "weather"},
                {"widget_id": 7, "x": 1, "y": 2},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "saved_count": 0,
        "saved_positions": [],
        "errors": [
            {
                "widget_id": "weather",
                "error": "Missing required field: x",
                "contract": "bulk-overwrite-validation-helper",
            },
            {
                "widget_id": "unknown",
                "error": "Invalid widget_id",
                "contract": "bulk-overwrite-validation-helper",
            },
        ],
        "total_positions": 0,
        "timestamp": None,
    }
    assert helper_calls == [
        ("weather", "Missing required field: x"),
        ("unknown", "Invalid widget_id"),
    ]



def test_widget_positions_contract_bulk_overwrite_not_found_error_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[str] = []

    def fake_bulk_overwrite_not_found_payload(widget_id: str) -> dict[str, str]:
        helper_calls.append(widget_id)
        return {
            "widget_id": widget_id,
            "error": "Widget position not found",
            "contract": "bulk-overwrite-not-found-helper",
        }

    monkeypatch.setattr(
        widget_positions_api,
        "_bulk_overwrite_not_found_payload",
        fake_bulk_overwrite_not_found_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "history": [],
                    "redo_stack": [],
                    "last_update": {"at": "2026-04-10T00:09:01+00:00"},
                },
                "news": {
                    "widget_id": "other",
                    "x": 5,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                },
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
                {"widget_id": "weather", "x": 8, "y": 6, "width": 3, "height": 2},
                {"widget_id": "news", "x": 9, "y": 7, "width": 2, "height": 2},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "saved_count": 0,
        "saved_positions": [],
        "errors": [
            {
                "widget_id": "weather",
                "error": "Widget position not found",
                "contract": "bulk-overwrite-not-found-helper",
            },
            {
                "widget_id": "news",
                "error": "Widget position not found",
                "contract": "bulk-overwrite-not-found-helper",
            },
        ],
        "total_positions": 2,
        "timestamp": None,
    }
    assert helper_calls == ["weather", "news"]



def test_widget_positions_contract_root_list_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "positions": {
            "contract": "root-list-helper",
        },
        "total": 99,
        "last_update": "2026-04-10T00:08:59+00:00",
        "meta": "root-list-response-helper",
    }
    helper_calls: list[dict[str, dict[str, object]]] = []

    def fake_root_list_response_payload(
        positions: dict[str, dict[str, object]],
    ) -> dict[str, object]:
        helper_calls.append({widget_id: dict(position) for widget_id, position in positions.items()})
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_root_list_response_payload",
        fake_root_list_response_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                },
                "hidden": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": {"at": "2026-04-10T00:09:01+00:00"},
                },
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
    assert response.get_json() == helper_payload
    assert helper_calls == [
        {
            "weather": {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-10T00:09:00+00:00",
            }
        }
    ]


def test_widget_positions_contract_detail_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "widget_id": "weather",
        "position": {
            "contract": "detail-helper",
        },
        "meta": "detail-response-helper",
    }
    helper_calls: list[tuple[str, dict[str, object]]] = []

    def fake_detail_response_payload(widget_id: str, position: dict[str, object]) -> dict[str, object]:
        helper_calls.append((widget_id, dict(position)))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_detail_response_payload",
        fake_detail_response_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
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

    response = client.get("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert response.get_json() == helper_payload
    assert helper_calls == [
        (
            "weather",
            {
                "widget_id": "weather",
                "x": 4,
                "y": 2,
                "width": 3,
                "height": 2,
                "zone_id": "global",
                "snap_to_grid": True,
                "history": [],
                "redo_stack": [],
                "last_update": "2026-04-10T00:09:00+00:00",
            },
        )
    ]


def test_widget_positions_contract_detail_not_found_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "Widget position not found",
        "contract": "detail-not-found-helper",
    }
    helper_calls: list[str] = []

    def fake_detail_not_found_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_detail_not_found_payload",
        fake_detail_not_found_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:09:00+00:00",
                },
                "hidden": {
                    "x": 8,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": {"at": "2026-04-10T00:09:01+00:00"},
                },
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

    missing_response = client.get("/api/v1/widgets/positions/missing")
    assert missing_response.status_code == 404
    assert missing_response.get_json() == helper_payload

    hidden_response = client.get("/api/v1/widgets/positions/hidden")
    assert hidden_response.status_code == 404
    assert hidden_response.get_json() == helper_payload

    assert helper_calls == ["called", "called"]


def test_widget_positions_contract_delete_success_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_calls: list[tuple[str, str]] = []
    helper_payload = {
        "success": True,
        "widget_id": "weather",
        "timestamp": "2026-04-10T00:10:03+00:00",
        "contract": "delete-success-helper",
    }

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        lambda: "2026-04-10T00:10:03+00:00",
    )

    def fake_delete_success_payload(widget_id: str, mutation_timestamp: str) -> dict[str, object]:
        helper_calls.append((widget_id, mutation_timestamp))
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_delete_success_payload",
        fake_delete_success_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:10:00+00:00",
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

    response = client.delete("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert response.get_json() == helper_payload
    assert helper_calls == [("weather", "2026-04-10T00:10:03+00:00")]


def test_widget_positions_contract_delete_success_event_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "widget_id": "weather",
        "contract": "delete-event-helper",
    }
    helper_calls: list[str] = []
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    def fake_delete_event_payload(widget_id: str) -> dict[str, str]:
        helper_calls.append(widget_id)
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_delete_event_payload",
        fake_delete_event_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:10:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.delete("/api/v1/widgets/positions/weather")
    assert response.status_code == 200
    assert helper_calls == ["weather"]
    assert events == [("widget_position_deleted", helper_payload)]



def test_widget_positions_contract_delete_not_found_response_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {
        "error": "Widget position not found",
        "contract": "delete-not-found-helper",
    }
    helper_calls: list[str] = []

    def fake_delete_not_found_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_delete_not_found_payload",
        fake_delete_not_found_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:10:00+00:00",
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

    first_delete = client.delete("/api/v1/widgets/positions/weather")
    assert first_delete.status_code == 200

    missing_delete = client.delete("/api/v1/widgets/positions/weather")
    assert missing_delete.status_code == 404
    assert missing_delete.get_json() == helper_payload

    unknown_delete = client.delete("/api/v1/widgets/positions/unknown")
    assert unknown_delete.status_code == 404
    assert unknown_delete.get_json() == helper_payload

    assert helper_calls == ["called", "called"]


def test_widget_positions_contract_repeated_delete_after_success_holds_not_found_truth(tmp_path, monkeypatch):
    mutation_timestamps = iter(
        [
            "2026-04-10T00:11:01+00:00",
            "2026-04-10T00:11:02+00:00",
        ]
    )
    server_owned_calls: list[str] = []

    def fake_server_owned_last_update() -> str:
        timestamp = next(mutation_timestamps)
        server_owned_calls.append(timestamp)
        return timestamp

    monkeypatch.setattr(
        widget_positions_api,
        "_server_owned_last_update",
        fake_server_owned_last_update,
    )

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:11:00+00:00",
                },
                "hidden": {
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-10T00:10:00+00:00",
                },
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    first_delete = client.delete("/api/v1/widgets/positions/weather")
    assert first_delete.status_code == 200
    assert first_delete.get_json() == {
        "success": True,
        "widget_id": "weather",
        "timestamp": "2026-04-10T00:11:01+00:00",
    }
    assert server_owned_calls == ["2026-04-10T00:11:01+00:00"]
    assert events == [("widget_position_deleted", {"widget_id": "weather"})]
    assert json.loads(persisted_file.read_text()) == {
        "hidden": {
            "widget_id": "hidden",
            "y": 1,
            "width": 2,
            "height": 2,
            "last_update": "2026-04-10T00:10:00+00:00",
        }
    }

    second_delete = client.delete("/api/v1/widgets/positions/weather")
    assert second_delete.status_code == 404
    assert second_delete.get_json() == {"error": "Widget position not found"}
    assert server_owned_calls == ["2026-04-10T00:11:01+00:00"]
    assert events == [("widget_position_deleted", {"widget_id": "weather"})]
    assert json.loads(persisted_file.read_text()) == {
        "hidden": {
            "widget_id": "hidden",
            "y": 1,
            "width": 2,
            "height": 2,
            "last_update": "2026-04-10T00:10:00+00:00",
        }
    }

    fetched = client.get("/api/v1/widgets/positions/weather")
    assert fetched.status_code == 404
    assert fetched.get_json() == {"error": "Widget position not found"}


def test_widget_positions_contract_reset_uses_server_owned_mutation_timestamp_for_response(tmp_path, monkeypatch):
    local_timestamp = "2026-04-10T00:12:01+00:00"
    server_owned_timestamp = "2026-04-10T00:12:02+00:00"
    monkeypatch.setattr(widget_positions_api, "_utc_now", lambda: local_timestamp)
    monkeypatch.setattr(widget_positions_api, "_server_owned_last_update", lambda: server_owned_timestamp)

    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:12:00+00:00",
                },
                "clock": {
                    "x": 1,
                    "y": 1,
                    "width": 2,
                    "height": 2,
                    "last_update": "2026-04-10T00:11:00+00:00",
                },
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/reset")
    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "message": "All widget positions reset",
        "timestamp": server_owned_timestamp,
    }
    assert response.get_json()["timestamp"] != local_timestamp
    assert events[-1] == ("widget_positions_reset", {})

    emptied = client.get("/api/v1/widgets/positions")
    assert emptied.status_code == 200
    assert emptied.get_json() == {"positions": {}, "total": 0, "last_update": None}


def test_widget_positions_contract_reset_success_event_uses_helper_payload(tmp_path, monkeypatch):
    helper_payload = {"contract": "reset-event-helper"}
    helper_calls: list[str] = []
    events: list[tuple[str, dict]] = []

    def sink(event: str, payload: dict) -> None:
        events.append((event, payload))

    def fake_reset_event_payload() -> dict[str, str]:
        helper_calls.append("called")
        return helper_payload

    monkeypatch.setattr(
        widget_positions_api,
        "_reset_event_payload",
        fake_reset_event_payload,
    )

    persisted_file = tmp_path / "widget_positions.json"
    persisted_file.write_text(
        json.dumps(
            {
                "weather": {
                    "x": 4,
                    "y": 2,
                    "width": 3,
                    "height": 2,
                    "last_update": "2026-04-10T00:12:00+00:00",
                }
            }
        )
    )

    app = create_app(
        {
            "TESTING": True,
            "WIDGET_POSITIONS_FILE": str(persisted_file),
            "WIDGET_POSITIONS_EVENT_SINK": sink,
        }
    )
    client = app.test_client()

    response = client.post("/api/v1/widgets/positions/reset")
    assert response.status_code == 200
    assert helper_calls == ["called"]
    assert events == [("widget_positions_reset", helper_payload)]
