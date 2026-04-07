"""Conflict Resolution API endpoints.

Provides endpoints to manage multi-user preference conflict detection
and resolution strategies.

Endpoints:
  GET  /api/v1/conflicts/state       — Current conflict state
  POST /api/v1/conflicts/evaluate    — Evaluate conflicts (optional: active_user_ids)
  POST /api/v1/conflicts/strategy    — Set resolution strategy
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("conflict_resolution", __name__, url_prefix="/api/v1/conflicts")
_LOGGER = logging.getLogger(__name__)


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _json_object_from_request(*, allow_missing: bool = True) -> tuple[dict[str, Any], tuple[Any, int] | None]:
    data = request.get_json(silent=True)
    if data is None:
        return ({}, None) if allow_missing else ({}, _error("JSON object required", 400))
    if not isinstance(data, dict):
        return {}, _error("JSON object required", 400)
    return data, None


def _validate_mood_payload(user_moods: Any) -> tuple[dict[str, dict[str, float]] | None, tuple[Any, int] | None]:
    if not isinstance(user_moods, dict):
        return None, _error("user_moods must be an object", 400)

    normalized: dict[str, dict[str, float]] = {}
    for user_id, moods in user_moods.items():
        if not isinstance(user_id, str) or not user_id.strip():
            return None, _error("user_moods keys must be non-empty strings", 400)
        if not isinstance(moods, dict):
            return None, _error("each user_moods entry must be an object", 400)

        normalized_moods: dict[str, float] = {}
        for axis, value in moods.items():
            if not isinstance(axis, str) or not axis.strip():
                return None, _error("mood axis keys must be non-empty strings", 400)
            if not isinstance(value, (int, float)):
                return None, _error("mood values must be numeric", 400)
            normalized_moods[axis] = float(value)

        normalized[user_id.strip()] = normalized_moods

    return normalized, None


def _validate_priority_payload(user_priorities: Any) -> tuple[dict[str, float] | None, tuple[Any, int] | None]:
    if not isinstance(user_priorities, dict):
        return None, _error("user_priorities must be an object", 400)

    normalized: dict[str, float] = {}
    for user_id, priority in user_priorities.items():
        if not isinstance(user_id, str) or not user_id.strip():
            return None, _error("user_priorities keys must be non-empty strings", 400)
        if not isinstance(priority, (int, float)):
            return None, _error("user_priorities values must be numeric", 400)
        normalized[user_id.strip()] = float(priority)

    return normalized, None


def _validate_active_user_ids(value: Any) -> tuple[list[str] | None, tuple[Any, int] | None]:
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, _error("active_user_ids must be a list of non-empty strings", 400)

    normalized: list[str] = []
    for user_id in value:
        if not isinstance(user_id, str) or not user_id.strip():
            return None, _error("active_user_ids must be a list of non-empty strings", 400)
        normalized.append(user_id.strip())

    return normalized, None


def _validate_strategy_payload(data: dict[str, Any]) -> tuple[tuple[str, str | None] | None, tuple[Any, int] | None]:
    strategy = data.get("strategy")
    if not isinstance(strategy, str) or not strategy.strip():
        return None, _error("strategy required", 400)

    override_user = data.get("override_user")
    if override_user is not None:
        if not isinstance(override_user, str) or not override_user.strip():
            return None, _error("override_user must be a non-empty string", 400)
        override_user = override_user.strip()

    return (strategy.strip(), override_user), None


def _get_resolver():
    """Get ConflictResolver from app services."""
    services = current_app.config.get("COPILOT_SERVICES", {})
    return services.get("conflict_resolver")


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/state", methods=["GET"])
def get_state():
    """Return current conflict state."""
    resolver = _get_resolver()
    if not resolver:
        return _error("conflict_resolver not initialized", 503)

    try:
        return jsonify({"ok": True, **resolver.state.to_dict()})
    except Exception as exc:
        _LOGGER.exception("Conflict state read failed")
        return _error(str(exc), 500)


@bp.route("/evaluate", methods=["POST"])
def evaluate():
    """Evaluate conflicts.

    If a UserPreferenceStore is wired, can auto-read moods/priorities.
    Otherwise expects JSON body: {user_moods, user_priorities}.
    """
    resolver = _get_resolver()
    if not resolver:
        return _error("conflict_resolver not initialized", 503)

    data, error = _json_object_from_request()
    if error:
        return error

    has_user_moods = "user_moods" in data
    has_user_priorities = "user_priorities" in data

    if has_user_moods or has_user_priorities:
        if not (has_user_moods and has_user_priorities):
            return _error("user_moods and user_priorities must be provided together", 400)

        user_moods, error = _validate_mood_payload(data.get("user_moods"))
        if error:
            return error

        user_priorities, error = _validate_priority_payload(data.get("user_priorities"))
        if error:
            return error

        try:
            state = resolver.evaluate(user_moods, user_priorities)
            return jsonify({"ok": True, **state.to_dict()})
        except Exception as exc:
            _LOGGER.exception("Conflict evaluation failed")
            return _error(str(exc), 500)

    active_ids, error = _validate_active_user_ids(data.get("active_user_ids"))
    if error:
        return error

    try:
        state = resolver.evaluate_from_store(active_ids)
        return jsonify({"ok": True, **state.to_dict()})
    except Exception as exc:
        _LOGGER.exception("Conflict evaluation failed")
        return _error(str(exc), 500)


@bp.route("/strategy", methods=["POST"])
def set_strategy():
    """Set resolution strategy.

    JSON body: {strategy: "weighted"|"compromise"|"override", override_user?: str}
    """
    resolver = _get_resolver()
    if not resolver:
        return _error("conflict_resolver not initialized", 503)

    data, error = _json_object_from_request()
    if error:
        return error

    validated, error = _validate_strategy_payload(data)
    if error:
        return error

    strategy, override_user = validated

    try:
        resolver.set_strategy(strategy, override_user)
        response = {"ok": True, "strategy": strategy}
        if override_user is not None:
            response["override_user"] = override_user
        return jsonify(response)
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        _LOGGER.exception("Conflict strategy update failed")
        return _error(str(exc), 500)
