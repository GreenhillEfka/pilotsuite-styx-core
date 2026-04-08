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


def _sanitize_loaded_positions(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}

    sanitized: dict[str, dict[str, Any]] = {}
    for widget_id, entry in raw.items():
        if not isinstance(widget_id, str) or not isinstance(entry, dict):
            continue

        normalized = deepcopy(entry)
        normalized.setdefault("widget_id", widget_id)
        sanitized[widget_id] = normalized

    return sanitized


def _state() -> dict[str, Any]:
    state = current_app.extensions.setdefault(
        "widget_positions_state",
        {"loaded": False, "positions": {}},
    )
    if not state["loaded"]:
        positions_file = _positions_file()
        try:
            if positions_file.exists():
                state["positions"] = _sanitize_loaded_positions(
                    json.loads(positions_file.read_text())
                )
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


def _latest_position_update(positions: dict[str, dict[str, Any]]) -> str | None:
    return max(
        (
            last_update
            for entry in positions.values()
            if isinstance(entry, dict)
            for last_update in [entry.get("last_update")]
            if isinstance(last_update, str)
        ),
        default=None,
    )


def _error_widget_id(data: Any) -> str:
    if not isinstance(data, dict):
        return "unknown"

    widget_id = data.get("widget_id")
    if isinstance(widget_id, str) and widget_id:
        return widget_id

    return "unknown"


def _coerce_stack_entry(entry: Any, *, field: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(entry, dict):
        return None, f"Invalid {field} entry"

    for required_field in ("x", "y"):
        if required_field not in entry:
            return None, f"Invalid {field} entry"

    try:
        x = int(entry["x"])
        y = int(entry["y"])
        width = int(entry["width"]) if "width" in entry else None
        height = int(entry["height"]) if "height" in entry else None
    except (TypeError, ValueError):
        return None, f"Invalid {field} entry"

    if x < 0 or y < 0:
        return None, f"Invalid {field} entry"
    if width is not None and width < 1:
        return None, f"Invalid {field} entry"
    if height is not None and height < 1:
        return None, f"Invalid {field} entry"

    normalized = deepcopy(entry)
    normalized["x"] = x
    normalized["y"] = y
    if width is not None:
        normalized["width"] = width
    if height is not None:
        normalized["height"] = height

    return normalized, None


def _coerce_stack_entries(values: Any, *, field: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(values, list):
        return None, f"Invalid {field}"

    normalized_entries: list[dict[str, Any]] = []
    for entry in values:
        normalized_entry, error = _coerce_stack_entry(entry, field=field)
        if error:
            return None, error
        normalized_entries.append(normalized_entry)

    return normalized_entries, None


def _pop_runtime_stack_entry(current: dict[str, Any], *, field: str) -> dict[str, Any] | None:
    stack = current.get(field, [])
    if not isinstance(stack, list) or not stack:
        return None

    normalized_entry, error = _coerce_stack_entry(stack[-1], field=field)
    if error:
        return None

    stack.pop()
    current[field] = stack
    return normalized_entry


def _runtime_current_position(current: Any) -> dict[str, Any] | None:
    normalized_entry, error = _coerce_stack_entry(current, field="position")
    if error:
        return None

    return normalized_entry


def _coerce_position(data: Any, *, require_widget_id: bool = True) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(data, dict):
        return None, "Invalid position payload"

    widget_id = data.get("widget_id")
    if require_widget_id and not widget_id:
        return None, "Missing required field: widget_id"
    if widget_id is not None and not isinstance(widget_id, str):
        return None, "Invalid widget_id"

    history = []
    if "history" in data:
        history, error = _coerce_stack_entries(data["history"], field="history")
        if error:
            return None, error

    redo_stack = []
    if "redo_stack" in data:
        redo_stack, error = _coerce_stack_entries(data["redo_stack"], field="redo_stack")
        if error:
            return None, error

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
        "history": history,
        "redo_stack": redo_stack,
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
            "last_update": _latest_position_update(positions),
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
            if "redo_stack" in existing and not isinstance(existing.get("redo_stack"), list):
                return jsonify({"error": "Widget position not found"}), 404
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

    raw_positions = data["positions"]
    if not isinstance(raw_positions, list):
        return jsonify({"error": "Invalid positions payload"}), 400

    saved_count = 0
    errors: list[dict[str, str]] = []
    emitted_updates: list[dict[str, Any]] = []

    with _STORE_LOCK:
        for raw_position in raw_positions:
            position, error = _coerce_position(raw_position)
            widget_id = _error_widget_id(raw_position)
            if error:
                errors.append({"widget_id": widget_id, "error": error})
                continue

            existing = _positions().get(widget_id)
            if existing:
                if "redo_stack" in existing and not isinstance(existing.get("redo_stack"), list):
                    errors.append({"widget_id": widget_id, "error": "Widget position not found"})
                    continue
                position["history"] = deepcopy(existing.get("history", []))
                position["redo_stack"] = []
            _positions()[widget_id] = position
            emitted_updates.append({"widget_id": widget_id, "position": deepcopy(position)})
            saved_count += 1

        _persist()
        total_positions = len(_positions())

    for payload in emitted_updates:
        _emit("widget_position_update", payload)

    return jsonify(
        {
            "success": True,
            "saved_count": saved_count,
            "errors": errors,
            "total_positions": total_positions,
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

        current_position, error = _coerce_stack_entry(current, field="history")
        if error:
            return jsonify({"error": "Widget position not found"}), 404

        history = current.get("history")
        if history is None:
            history = []
        elif not isinstance(history, list):
            return jsonify({"error": "Widget position not found"}), 404

        if "redo_stack" in current and not isinstance(current.get("redo_stack"), list):
            return jsonify({"error": "Widget position not found"}), 404

        history.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
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

        current_position = _runtime_current_position(current)
        if current_position is None:
            return jsonify({"error": "Widget position not found"}), 404

        redo_stack = current.get("redo_stack")
        if redo_stack is None:
            redo_stack = []
            current["redo_stack"] = redo_stack
        elif not isinstance(redo_stack, list):
            return jsonify({"error": "Widget position not found"}), 404

        previous = _pop_runtime_stack_entry(current, field="history")
        if previous is None:
            return jsonify({"error": "No history available"}), 404

        redo_stack.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
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

        current_position = _runtime_current_position(current)
        if current_position is None:
            return jsonify({"error": "Widget position not found"}), 404

        history = current.get("history")
        if history is None:
            history = []
            current["history"] = history
        elif not isinstance(history, list):
            return jsonify({"error": "Widget position not found"}), 404

        next_position = _pop_runtime_stack_entry(current, field="redo_stack")
        if next_position is None:
            return jsonify({"error": "No redo available"}), 404

        history.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
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
