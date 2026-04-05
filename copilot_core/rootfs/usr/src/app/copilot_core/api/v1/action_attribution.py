"""Action Attribution API — Multi-source user attribution.

Endpoints:
  POST /api/v1/attribution/attribute   — Attribute an action to a user
  GET  /api/v1/attribution/history     — Get action history
  GET  /api/v1/attribution/user/:uid   — Get actions for a specific user
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("action_attribution", __name__, url_prefix="/api/v1/attribution")
_LOGGER = logging.getLogger(__name__)


def _service():
    return current_app.config.get("COPILOT_SERVICES", {}).get("action_attribution")


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _json_error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _require_service():
    svc = _service()
    if not svc:
        return None, _json_error("action_attribution not initialized", 503)
    return svc, None


def _require_json_object():
    data = request.get_json(silent=True)
    if data is None:
        return None, _json_error("JSON body required", 400)
    if not isinstance(data, dict):
        return None, _json_error("JSON object required", 400)
    return data, None


def _require_non_empty_string(value: Any, field_name: str):
    if not isinstance(value, str) or not value.strip():
        return None, _json_error(f"{field_name} must be a non-empty string", 400)
    return value.strip(), None


def _parse_limit(default: int = 100):
    raw_limit = request.args.get("limit")
    if raw_limit in (None, ""):
        return default, None

    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None, _json_error("limit must be a positive integer", 400)

    if limit <= 0:
        return None, _json_error("limit must be a positive integer", 400)

    return limit, None


def _parse_signals(payload: Any):
    if payload is None:
        return [], None
    if not isinstance(payload, list):
        return None, _json_error("signals must be a list", 400)

    from copilot_core.styx.action_attribution import AttributionSignal

    parsed_signals = []
    for index, signal in enumerate(payload):
        if not isinstance(signal, dict):
            return None, _json_error(f"signals[{index}] must be an object", 400)

        user_id = signal.get("user_id")
        if user_id is not None and (not isinstance(user_id, str) or not user_id.strip()):
            return None, _json_error(f"signals[{index}].user_id must be a non-empty string", 400)

        source_name = signal.get("source_name", "unknown")
        if not isinstance(source_name, str) or not source_name.strip():
            return None, _json_error(f"signals[{index}].source_name must be a non-empty string", 400)

        confidence = signal.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)):
            return None, _json_error(f"signals[{index}].confidence must be numeric", 400)

        metadata = signal.get("metadata", {})
        if not isinstance(metadata, dict):
            return None, _json_error(f"signals[{index}].metadata must be an object", 400)

        if not user_id:
            continue

        parsed_signals.append(
            AttributionSignal(
                source_name=source_name.strip(),
                user_id=user_id.strip(),
                confidence=float(confidence),
                metadata=metadata,
            )
        )

    return parsed_signals, None


def _serialize_timestamp(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_action(action: Any, *, include_user_id: bool = True) -> dict[str, Any]:
    payload = {
        "entity_id": action.entity_id,
        "action": action.action,
        "confidence": action.confidence,
        "timestamp": _serialize_timestamp(action.timestamp),
    }
    if include_user_id:
        payload["user_id"] = action.user_id
    return payload


@bp.route("/attribute", methods=["POST"])
def attribute():
    """Attribute an action to a user from pre-gathered signals."""
    svc, error_response = _require_service()
    if error_response:
        return error_response

    data, error_response = _require_json_object()
    if error_response:
        return error_response

    entity_id, error_response = _require_non_empty_string(data.get("entity_id"), "entity_id")
    if error_response:
        return error_response

    action, error_response = _require_non_empty_string(data.get("action"), "action")
    if error_response:
        return error_response

    parsed_signals, error_response = _parse_signals(data.get("signals", []))
    if error_response:
        return error_response

    try:
        result = svc.attribute_action(entity_id, action, parsed_signals)
    except Exception as exc:  # pragma: no cover - guarded by contract tests
        _LOGGER.exception("Action attribution failed")
        return _json_error(str(exc), 500)

    if result is None:
        return jsonify({"ok": False, "error": "no attribution possible"})

    return jsonify(
        {
            "ok": True,
            "attribution": {
                "user_id": result.user_id,
                "entity_id": result.entity_id,
                "action": result.action,
                "confidence": result.confidence,
                "sources": result.sources,
                "timestamp": _serialize_timestamp(result.timestamp),
            },
        }
    )


@bp.route("/history", methods=["GET"])
def history():
    """Get recent action history."""
    svc, error_response = _require_service()
    if error_response:
        return error_response

    limit, error_response = _parse_limit()
    if error_response:
        return error_response

    try:
        actions = svc.get_action_history(limit)
    except Exception as exc:  # pragma: no cover - guarded by contract tests
        _LOGGER.exception("Action attribution history failed")
        return _json_error(str(exc), 500)

    return jsonify({"ok": True, "actions": [_serialize_action(action) for action in actions]})


@bp.route("/user/<user_id>", methods=["GET"])
def user_actions(user_id):
    """Get actions for a specific user."""
    svc, error_response = _require_service()
    if error_response:
        return error_response

    limit, error_response = _parse_limit()
    if error_response:
        return error_response

    try:
        actions = svc.get_user_actions(user_id, limit)
    except Exception as exc:  # pragma: no cover - guarded by contract tests
        _LOGGER.exception("User action attribution history failed")
        return _json_error(str(exc), 500)

    return jsonify(
        {
            "ok": True,
            "user_id": user_id,
            "actions": [_serialize_action(action, include_user_id=False) for action in actions],
        }
    )
