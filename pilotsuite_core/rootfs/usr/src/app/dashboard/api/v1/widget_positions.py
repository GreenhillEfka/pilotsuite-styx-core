from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import threading
from typing import Any

from flask import Blueprint, current_app, jsonify, request

widget_positions_bp = Blueprint(
    "widget_positions_v1",
    __name__,
    url_prefix="/api/v1/widgets/positions",
)

_STORE_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _positions_file() -> Path:
    configured = current_app.config.get("WIDGET_POSITIONS_FILE")
    if configured:
        return Path(configured)

    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "widget_positions.json"
    )


def _state() -> dict[str, Any]:
    state = current_app.extensions.setdefault(
        "widget_positions_state",
        {"loaded": False, "positions": {}},
    )
    if not state["loaded"]:
        positions_file = _positions_file()
        try:
            if positions_file.exists():
                state["positions"] = json.loads(positions_file.read_text())
        except Exception:
            state["positions"] = {}
        state["loaded"] = True
    return state


def _persist() -> None:
    positions_file = _positions_file()
    positions_file.parent.mkdir(parents=True, exist_ok=True)
    positions_file.write_text(
        json.dumps(_state()["positions"], indent=2, sort_keys=True)
    )


def _emit(event: str, payload: dict[str, Any]) -> None:
    sink = current_app.config.get("WIDGET_POSITIONS_EVENT_SINK")
    if callable(sink):
        sink(event, payload)

    socketio = current_app.extensions.get("socketio")
    if socketio is not None:
        socketio.emit(event, payload)


def _positions() -> dict[str, dict[str, Any]]:
    return _state()["positions"]


def _coerce_position(data: dict[str, Any], *, require_widget_id: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    widget_id = data.get("widget_id")
    if require_widget_id and not widget_id:
        return None, "Missing required field: widget_id"

    for field in ("x", "y"):
        if field not in data:
            return None, f"Missing required field: {field}"

    try:
        x = int(data["x"])
        y = int(data["y"])
        width = int(data.get("width", 1))
        height = int(data.get("height", 1))
    except (TypeError, ValueError):
        return None, "Invalid position values"

    if x < 0 or y < 0 or width < 1 or height < 1:
        return None, "Position values must be positive"

    return {
        "widget_id": widget_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "zone_id": data.get("zone_id", "global"),
        "snap_to_grid": bool(data.get("snap_to_grid", True)),
        "history": deepcopy(data.get("history", [])),
        "redo_stack": deepcopy(data.get("redo_stack", [])),
        "last_update": _utc_now(),
    }, None


@widget_positions_bp.get("")
def get_all_positions():
    with _STORE_LOCK:
        positions = deepcopy(_positions())

    return jsonify(
        {
            "positions": positions,
            "total": len(positions),
            "last_update": max(
                (entry.get("last_update") for entry in positions.values()),
                default=None,
            ),
        }
    )


@widget_positions_bp.post("")
def save_position():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    position, error = _coerce_position(data)
    if error:
        return jsonify({"error": error}), 400

    widget_id = position["widget_id"]

    with _STORE_LOCK:
        existing = _positions().get(widget_id)
        if existing:
            position["history"] = deepcopy(existing.get("history", []))
            position["redo_stack"] = []
        _positions()[widget_id] = position
        _persist()

    payload = {"widget_id": widget_id, "position": deepcopy(position)}
    _emit("widget_position_update", payload)

    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "position": deepcopy(position),
            "timestamp": _utc_now(),
        }
    )


@widget_positions_bp.get("/<widget_id>")
def get_widget_position(widget_id: str):
    with _STORE_LOCK:
        position = deepcopy(_positions().get(widget_id))

    if not position:
        return jsonify({"error": "Widget position not found"}), 404

    return jsonify({"widget_id": widget_id, "position": position})


@widget_positions_bp.delete("/<widget_id>")
def delete_widget_position(widget_id: str):
    with _STORE_LOCK:
        if widget_id not in _positions():
            return jsonify({"error": "Widget position not found"}), 404
        del _positions()[widget_id]
        _persist()

    _emit("widget_position_deleted", {"widget_id": widget_id})
    return jsonify({"success": True, "widget_id": widget_id, "timestamp": _utc_now()})


@widget_positions_bp.post("/bulk")
def save_bulk_positions():
    data = request.get_json(silent=True)
    if not data or "positions" not in data:
        return jsonify({"error": "No positions provided"}), 400

    saved_count = 0
    errors: list[dict[str, str]] = []

    with _STORE_LOCK:
        for raw_position in data["positions"]:
            position, error = _coerce_position(raw_position)
            widget_id = raw_position.get("widget_id", "unknown")
            if error:
                errors.append({"widget_id": widget_id, "error": error})
                continue

            existing = _positions().get(widget_id)
            if existing:
                position["history"] = deepcopy(existing.get("history", []))
                position["redo_stack"] = []
            _positions()[widget_id] = position
            saved_count += 1

        _persist()

    return jsonify(
        {
            "success": True,
            "saved_count": saved_count,
            "errors": errors,
            "total_positions": len(_positions()),
            "timestamp": _utc_now(),
        }
    )


@widget_positions_bp.post("/<widget_id>/history")
def add_position_history(widget_id: str):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify({"error": "Widget position not found"}), 404

        history = current.setdefault("history", [])
        history.append(
            {
                "x": current["x"],
                "y": current["y"],
                "width": current.get("width", 1),
                "height": current.get("height", 1),
                "timestamp": _utc_now(),
            }
        )
        current["history"] = history[-20:]
        current["redo_stack"] = []
        current["last_update"] = _utc_now()
        _persist()
        history_length = len(current["history"])

    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "history_length": history_length,
            "timestamp": _utc_now(),
        }
    )


@widget_positions_bp.post("/<widget_id>/undo")
def undo_position(widget_id: str):
    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify({"error": "Widget position not found"}), 404

        history = current.get("history", [])
        if not history:
            return jsonify({"error": "No history available"}), 404

        previous = history.pop()
        redo_stack = current.setdefault("redo_stack", [])
        redo_stack.append(
            {
                "x": current["x"],
                "y": current["y"],
                "width": current.get("width", 1),
                "height": current.get("height", 1),
                "timestamp": _utc_now(),
            }
        )
        current.update(
            {
                "x": previous["x"],
                "y": previous["y"],
                "width": previous.get("width", 1),
                "height": previous.get("height", 1),
                "last_update": _utc_now(),
            }
        )
        snapshot = deepcopy(current)
        history_remaining = len(current.get("history", []))
        _persist()

    _emit(
        "widget_position_update",
        {"widget_id": widget_id, "position": snapshot, "action": "undo"},
    )
    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "position": snapshot,
            "history_remaining": history_remaining,
            "timestamp": _utc_now(),
        }
    )


@widget_positions_bp.post("/<widget_id>/redo")
def redo_position(widget_id: str):
    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify({"error": "Widget position not found"}), 404

        redo_stack = current.get("redo_stack", [])
        if not redo_stack:
            return jsonify({"error": "No redo available"}), 404

        next_position = redo_stack.pop()
        history = current.setdefault("history", [])
        history.append(
            {
                "x": current["x"],
                "y": current["y"],
                "width": current.get("width", 1),
                "height": current.get("height", 1),
                "timestamp": _utc_now(),
            }
        )
        current.update(
            {
                "x": next_position["x"],
                "y": next_position["y"],
                "width": next_position.get("width", 1),
                "height": next_position.get("height", 1),
                "last_update": _utc_now(),
            }
        )
        snapshot = deepcopy(current)
        redo_remaining = len(current.get("redo_stack", []))
        _persist()

    _emit(
        "widget_position_update",
        {"widget_id": widget_id, "position": snapshot, "action": "redo"},
    )
    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "position": snapshot,
            "redo_remaining": redo_remaining,
            "timestamp": _utc_now(),
        }
    )


@widget_positions_bp.post("/reset")
def reset_all_positions():
    with _STORE_LOCK:
        _positions().clear()
        _persist()

    _emit("widget_positions_reset", {})
    return jsonify(
        {
            "success": True,
            "message": "All widget positions reset",
            "timestamp": _utc_now(),
        }
    )
