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


def _server_owned_last_update() -> str:
    return _utc_now()


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


def _validated_history_entries(history: Any) -> list[dict[str, Any]] | None:
    if history is None:
        return []

    normalized_history, error = _coerce_stack_entries(history, field="history")
    if error:
        return None

    return normalized_history


def _overwrite_source_history(existing: dict[str, Any]) -> list[dict[str, Any]] | None:
    return _validated_history_entries(existing.get("history"))


def _validated_redo_stack_entries(redo_stack: Any) -> list[dict[str, Any]] | None:
    if redo_stack is None:
        return []

    normalized_redo_stack, error = _coerce_stack_entries(redo_stack, field="redo_stack")
    if error:
        return None

    return normalized_redo_stack


def _overwrite_target_redo_stack(existing: dict[str, Any]) -> list[dict[str, Any]] | None:
    return _validated_redo_stack_entries(existing.get("redo_stack"))


def _overwrite_current_position(existing: dict[str, Any]) -> dict[str, Any] | None:
    return _runtime_current_position(existing)


def _read_current_position(existing: dict[str, Any]) -> dict[str, Any] | None:
    position = _runtime_current_position(existing)
    if position is None:
        return None

    position.setdefault("width", 1)
    position.setdefault("height", 1)
    position.setdefault("zone_id", "global")
    position.setdefault("snap_to_grid", True)
    return position


def _overwrite_widget_id_matches(existing: dict[str, Any], widget_id: str) -> bool:
    persisted_widget_id = existing.get("widget_id")
    return isinstance(persisted_widget_id, str) and persisted_widget_id == widget_id


def _read_history_is_valid(existing: dict[str, Any]) -> bool:
    return _validated_history_entries(existing.get("history")) is not None


def _read_redo_stack_entries(existing: dict[str, Any]) -> list[dict[str, Any]] | None:
    redo_stack = _validated_redo_stack_entries(existing.get("redo_stack"))
    if redo_stack is None:
        return None

    if "redo_stack" not in existing:
        return []

    return redo_stack


def _read_redo_stack_is_valid(existing: dict[str, Any]) -> bool:
    return _read_redo_stack_entries(existing) is not None



def _read_last_update_is_valid(existing: dict[str, Any]) -> bool:
    last_update = existing.get("last_update")
    return last_update is None or isinstance(last_update, str)


def _read_zone_id_is_valid(existing: dict[str, Any]) -> bool:
    zone_id = existing.get("zone_id")
    return zone_id is None or isinstance(zone_id, str)


def _read_snap_to_grid_is_valid(existing: dict[str, Any]) -> bool:
    snap_to_grid = existing.get("snap_to_grid")
    return snap_to_grid is None or isinstance(snap_to_grid, bool)


def _read_position_if_widget_id_matches(existing: Any, widget_id: str) -> dict[str, Any] | None:
    if not isinstance(existing, dict):
        return None
    if not _overwrite_widget_id_matches(existing, widget_id):
        return None
    if not _read_history_is_valid(existing):
        return None
    if not _read_redo_stack_is_valid(existing):
        return None
    if not _read_last_update_is_valid(existing):
        return None
    if not _read_zone_id_is_valid(existing):
        return None
    if not _read_snap_to_grid_is_valid(existing):
        return None

    position = _read_current_position(existing)
    if position is None:
        return None

    history = _validated_history_entries(existing.get("history"))
    if history is None:
        return None
    position["history"] = history

    redo_stack = _read_redo_stack_entries(existing)
    if redo_stack is None:
        return None
    position["redo_stack"] = redo_stack

    return position


def _read_positions_snapshot() -> dict[str, dict[str, Any]]:
    positions: dict[str, dict[str, Any]] = {}
    for widget_id, existing in _positions().items():
        readable_position = _read_position_if_widget_id_matches(existing, widget_id)
        if readable_position is None:
            continue
        positions[widget_id] = readable_position
    return positions


def _saved_position_payload(widget_id: str) -> dict[str, Any] | None:
    position = _read_position_if_widget_id_matches(_positions().get(widget_id), widget_id)
    if position is None:
        return None

    return {"widget_id": widget_id, "position": position}


def _saved_payload_timestamp(saved_payload: dict[str, Any] | None) -> str | None:
    if not isinstance(saved_payload, dict):
        return None

    position = saved_payload.get("position")
    if not isinstance(position, dict):
        return None

    last_update = position.get("last_update")
    if not isinstance(last_update, str):
        return None

    return last_update


def _saved_payloads_timestamp(saved_payloads: list[dict[str, Any]]) -> str | None:
    return max(
        (
            timestamp
            for saved_payload in saved_payloads
            for timestamp in [_saved_payload_timestamp(saved_payload)]
            if isinstance(timestamp, str)
        ),
        default=None,
    )


def _root_list_response_payload(positions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "positions": deepcopy(positions),
        "total": len(positions),
        "last_update": _latest_position_update(positions),
    }


def _detail_response_payload(widget_id: str, position: dict[str, Any]) -> dict[str, Any]:
    return {
        "widget_id": widget_id,
        "position": deepcopy(position),
    }


def _detail_not_found_payload() -> dict[str, Any]:
    return {"error": "Widget position not found"}


def _single_overwrite_not_found_payload() -> dict[str, Any]:
    return {"error": "Widget position not found"}


def _single_overwrite_request_error_payload(error: str) -> dict[str, str]:
    return {"error": error}


def _single_overwrite_success_payload(
    widget_id: str,
    position: dict[str, Any],
    timestamp: str | None,
) -> dict[str, Any]:
    return {
        "success": True,
        "widget_id": widget_id,
        "position": deepcopy(position),
        "timestamp": timestamp,
    }



def _single_overwrite_event_payload(saved_payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(saved_payload)


def _bulk_overwrite_success_payload(
    saved_count: int,
    saved_positions: list[dict[str, Any]],
    errors: list[dict[str, str]],
    total_positions: int,
    timestamp: str | None,
) -> dict[str, Any]:
    return {
        "success": True,
        "saved_count": saved_count,
        "saved_positions": deepcopy(saved_positions),
        "errors": deepcopy(errors),
        "total_positions": total_positions,
        "timestamp": timestamp,
    }


def _bulk_overwrite_event_payload(saved_payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(saved_payload)


def _bulk_overwrite_not_found_payload(widget_id: str) -> dict[str, str]:
    return {"widget_id": widget_id, "error": "Widget position not found"}


def _bulk_overwrite_validation_error_payload(widget_id: str, error: str) -> dict[str, str]:
    return {"widget_id": widget_id, "error": error}


def _bulk_overwrite_request_error_payload(error: str) -> dict[str, str]:
    return {"error": error}


def _history_request_error_payload(error: str) -> dict[str, str]:
    return {"error": error}


def _history_not_found_payload() -> dict[str, Any]:
    return {"error": "Widget position not found"}


def _history_success_payload(
    widget_id: str,
    history_length: int,
    timestamp: str | None,
) -> dict[str, Any]:
    return {
        "success": True,
        "widget_id": widget_id,
        "history_length": history_length,
        "timestamp": timestamp,
    }



def _undo_not_found_payload() -> dict[str, Any]:
    return {"error": "Widget position not found"}


def _undo_no_history_payload() -> dict[str, Any]:
    return {"error": "No history available"}


def _reset_noop_payload() -> dict[str, Any]:
    return {
        "success": True,
        "message": "No widget positions to reset",
        "timestamp": None,
    }


def _reset_success_payload(mutation_timestamp: str) -> dict[str, Any]:
    return {
        "success": True,
        "message": "All widget positions reset",
        "timestamp": mutation_timestamp,
    }


def _reset_event_payload() -> dict[str, Any]:
    return {}


def _delete_not_found_payload() -> dict[str, Any]:
    return {"error": "Widget position not found"}


def _delete_success_payload(widget_id: str, mutation_timestamp: str) -> dict[str, Any]:
    return {
        "success": True,
        "widget_id": widget_id,
        "timestamp": mutation_timestamp,
    }



def _delete_event_payload(widget_id: str) -> dict[str, Any]:
    return {"widget_id": widget_id}


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

    zone_id = data.get("zone_id", "global")
    if not isinstance(zone_id, str):
        return None, "Invalid zone_id"

    snap_to_grid = data.get("snap_to_grid", True)
    if not isinstance(snap_to_grid, bool):
        return None, "Invalid snap_to_grid"

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
        "zone_id": zone_id,
        "snap_to_grid": snap_to_grid,
        "history": history,
        "redo_stack": redo_stack,
        "last_update": _server_owned_last_update(),
    }, None


@widget_positions_bp.get("")
def get_all_positions():
    with _STORE_LOCK:
        positions = _read_positions_snapshot()

    return jsonify(_root_list_response_payload(positions))


@widget_positions_bp.post("")
def save_position():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(_single_overwrite_request_error_payload("No data provided")), 400

    position, error = _coerce_position(data)
    if error:
        return jsonify(_single_overwrite_request_error_payload(error)), 400

    widget_id = position["widget_id"]

    with _STORE_LOCK:
        existing = _positions().get(widget_id)
        if existing:
            if not _overwrite_widget_id_matches(existing, widget_id):
                return jsonify(_single_overwrite_not_found_payload()), 404
            if not _read_last_update_is_valid(existing):
                return jsonify(_single_overwrite_not_found_payload()), 404
            if not _read_zone_id_is_valid(existing):
                return jsonify(_single_overwrite_not_found_payload()), 404
            if not _read_snap_to_grid_is_valid(existing):
                return jsonify(_single_overwrite_not_found_payload()), 404
            if _overwrite_current_position(existing) is None:
                return jsonify(_single_overwrite_not_found_payload()), 404
            history = _overwrite_source_history(existing)
            if history is None:
                return jsonify(_single_overwrite_not_found_payload()), 404
            if _overwrite_target_redo_stack(existing) is None:
                return jsonify(_single_overwrite_not_found_payload()), 404
            position["history"] = history
            position["redo_stack"] = []
        _positions()[widget_id] = position
        _persist()
        saved_payload = _saved_position_payload(widget_id)

    if saved_payload is None:
        return jsonify(_single_overwrite_not_found_payload()), 404

    _emit("widget_position_update", _single_overwrite_event_payload(saved_payload))

    return jsonify(
        _single_overwrite_success_payload(
            widget_id,
            saved_payload["position"],
            _saved_payload_timestamp(saved_payload),
        )
    )


@widget_positions_bp.get("/<widget_id>")
def get_widget_position(widget_id: str):
    with _STORE_LOCK:
        position = _read_position_if_widget_id_matches(_positions().get(widget_id), widget_id)

    if not position:
        return jsonify(_detail_not_found_payload()), 404

    return jsonify(_detail_response_payload(widget_id, position))


@widget_positions_bp.delete("/<widget_id>")
def delete_widget_position(widget_id: str):
    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if _read_position_if_widget_id_matches(current, widget_id) is None:
            return jsonify(_delete_not_found_payload()), 404
        mutation_timestamp = _server_owned_last_update()
        del _positions()[widget_id]
        _persist()

    _emit("widget_position_deleted", _delete_event_payload(widget_id))
    return jsonify(_delete_success_payload(widget_id, mutation_timestamp))


@widget_positions_bp.post("/bulk")
def save_bulk_positions():
    data = request.get_json(silent=True)
    if not data or "positions" not in data:
        return jsonify(_bulk_overwrite_request_error_payload("No positions provided")), 400

    raw_positions = data["positions"]
    if not isinstance(raw_positions, list):
        return jsonify(_bulk_overwrite_request_error_payload("Invalid positions payload")), 400

    saved_count = 0
    errors: list[dict[str, str]] = []
    saved_widget_ids: list[str] = []

    with _STORE_LOCK:
        for raw_position in raw_positions:
            position, error = _coerce_position(raw_position)
            widget_id = _error_widget_id(raw_position)
            if error:
                errors.append(_bulk_overwrite_validation_error_payload(widget_id, error))
                continue

            existing = _positions().get(widget_id)
            if existing:
                if not _overwrite_widget_id_matches(existing, widget_id):
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                if not _read_last_update_is_valid(existing):
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                if not _read_zone_id_is_valid(existing):
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                if not _read_snap_to_grid_is_valid(existing):
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                if _overwrite_current_position(existing) is None:
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                history = _overwrite_source_history(existing)
                if history is None:
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                if _overwrite_target_redo_stack(existing) is None:
                    errors.append(_bulk_overwrite_not_found_payload(widget_id))
                    continue
                position["history"] = history
                position["redo_stack"] = []
            _positions()[widget_id] = position
            saved_widget_ids.append(widget_id)
            saved_count += 1

        _persist()
        total_positions = len(_positions())
        saved_positions = [
            payload
            for widget_id in saved_widget_ids
            for payload in [_saved_position_payload(widget_id)]
            if payload is not None
        ]

    for payload in saved_positions:
        _emit("widget_position_update", _bulk_overwrite_event_payload(payload))

    return jsonify(
        _bulk_overwrite_success_payload(
            saved_count,
            saved_positions,
            errors,
            total_positions,
            _saved_payloads_timestamp(saved_positions),
        )
    )


@widget_positions_bp.post("/<widget_id>/history")
def add_position_history(widget_id: str):
    data = request.get_json(silent=True)
    if not data:
        return jsonify(_history_request_error_payload("No data provided")), 400

    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify(_history_not_found_payload()), 404
        if not _overwrite_widget_id_matches(current, widget_id):
            return jsonify(_history_not_found_payload()), 404
        if not _read_last_update_is_valid(current):
            return jsonify(_history_not_found_payload()), 404
        if not _read_zone_id_is_valid(current):
            return jsonify(_history_not_found_payload()), 404
        if not _read_snap_to_grid_is_valid(current):
            return jsonify(_history_not_found_payload()), 404

        current_position, error = _coerce_stack_entry(current, field="history")
        if error:
            return jsonify(_history_not_found_payload()), 404

        history = _validated_history_entries(current.get("history"))
        if history is None:
            return jsonify(_history_not_found_payload()), 404

        if _validated_redo_stack_entries(current.get("redo_stack")) is None:
            return jsonify(_history_not_found_payload()), 404

        mutation_timestamp = _server_owned_last_update()
        history.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
                "timestamp": mutation_timestamp,
            }
        )
        current["history"] = history[-20:]
        current["redo_stack"] = []
        current["last_update"] = mutation_timestamp
        _persist()
        saved_payload = _saved_position_payload(widget_id)

    if saved_payload is None:
        return jsonify(_history_not_found_payload()), 404

    return jsonify(
        _history_success_payload(
            widget_id,
            len(saved_payload["position"]["history"]),
            saved_payload["position"]["last_update"],
        )
    )


@widget_positions_bp.post("/<widget_id>/undo")
def undo_position(widget_id: str):
    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify(_undo_not_found_payload()), 404
        if not _overwrite_widget_id_matches(current, widget_id):
            return jsonify(_undo_not_found_payload()), 404

        current_position = _runtime_current_position(current)
        if current_position is None:
            return jsonify(_undo_not_found_payload()), 404
        if not _read_last_update_is_valid(current):
            return jsonify(_undo_not_found_payload()), 404
        if not _read_zone_id_is_valid(current):
            return jsonify(_undo_not_found_payload()), 404
        if not _read_snap_to_grid_is_valid(current):
            return jsonify(_undo_not_found_payload()), 404

        redo_stack = current.get("redo_stack")
        if redo_stack is None:
            redo_stack = []
            current["redo_stack"] = redo_stack
        elif not isinstance(redo_stack, list):
            return jsonify(_undo_not_found_payload()), 404

        previous = _pop_runtime_stack_entry(current, field="history")
        if previous is None:
            return jsonify(_undo_no_history_payload()), 404

        mutation_timestamp = _server_owned_last_update()
        redo_stack.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
                "timestamp": mutation_timestamp,
            }
        )
        current.update(
            {
                "x": previous["x"],
                "y": previous["y"],
                "width": previous.get("width", 1),
                "height": previous.get("height", 1),
                "last_update": mutation_timestamp,
            }
        )
        history_remaining = len(current.get("history", []))
        _persist()
        saved_payload = _saved_position_payload(widget_id)

    if saved_payload is None:
        return jsonify(_undo_not_found_payload()), 404

    _emit(
        "widget_position_update",
        {**deepcopy(saved_payload), "action": "undo"},
    )
    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "position": deepcopy(saved_payload["position"]),
            "history_remaining": history_remaining,
            "timestamp": saved_payload["position"]["last_update"],
        }
    )


@widget_positions_bp.post("/<widget_id>/redo")
def redo_position(widget_id: str):
    with _STORE_LOCK:
        current = _positions().get(widget_id)
        if not current:
            return jsonify({"error": "Widget position not found"}), 404
        if not _overwrite_widget_id_matches(current, widget_id):
            return jsonify({"error": "Widget position not found"}), 404

        current_position = _runtime_current_position(current)
        if current_position is None:
            return jsonify({"error": "Widget position not found"}), 404
        if not _read_last_update_is_valid(current):
            return jsonify({"error": "Widget position not found"}), 404
        if not _read_zone_id_is_valid(current):
            return jsonify({"error": "Widget position not found"}), 404
        if not _read_snap_to_grid_is_valid(current):
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

        mutation_timestamp = _server_owned_last_update()
        history.append(
            {
                "x": current_position["x"],
                "y": current_position["y"],
                "width": current_position.get("width", 1),
                "height": current_position.get("height", 1),
                "timestamp": mutation_timestamp,
            }
        )
        current.update(
            {
                "x": next_position["x"],
                "y": next_position["y"],
                "width": next_position.get("width", 1),
                "height": next_position.get("height", 1),
                "last_update": mutation_timestamp,
            }
        )
        redo_remaining = len(current.get("redo_stack", []))
        _persist()
        saved_payload = _saved_position_payload(widget_id)

    if saved_payload is None:
        return jsonify({"error": "Widget position not found"}), 404

    _emit(
        "widget_position_update",
        {**deepcopy(saved_payload), "action": "redo"},
    )
    return jsonify(
        {
            "success": True,
            "widget_id": widget_id,
            "position": deepcopy(saved_payload["position"]),
            "redo_remaining": redo_remaining,
            "timestamp": saved_payload["position"]["last_update"],
        }
    )


@widget_positions_bp.post("/reset")
def reset_all_positions():
    with _STORE_LOCK:
        readable_widget_ids = tuple(_read_positions_snapshot().keys())
        if not readable_widget_ids:
            return jsonify(_reset_noop_payload())

        mutation_timestamp = _server_owned_last_update()
        for widget_id in readable_widget_ids:
            _positions().pop(widget_id, None)
        _persist()

    _emit("widget_positions_reset", _reset_event_payload())
    return jsonify(_reset_success_payload(mutation_timestamp))
