"""Autonomy REST API — Dashboard, zone module control, behavioral history.

Blueprint prefix: /api/v1/autonomy
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

autonomy_bp = Blueprint("autonomy", __name__, url_prefix="/api/v1/autonomy")

_executor = None
_module_registry = None


def init_autonomy_api(executor=None, module_registry=None) -> None:
    """Wire executor and module registry into blueprint."""
    global _executor, _module_registry
    _executor = executor
    _module_registry = module_registry


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _json_body(*, allow_empty: bool = False):
    body = request.get_json(silent=True)
    if body is None:
        return None, _error("No JSON body provided", 400)
    if not isinstance(body, dict):
        return None, _error("JSON body must be an object", 400)
    if not allow_empty and not body:
        return None, _error("Request body required", 400)
    return body, None


def _parse_positive_int_arg(name: str, *, default: int):
    raw = request.args.get(name)
    if raw is None:
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, _error(f"Invalid '{name}' parameter. Must be a positive integer.", 400)
    if value <= 0:
        return None, _error(f"Invalid '{name}' parameter. Must be a positive integer.", 400)
    return value, None


# ── Dashboard ───────────────────────────────────────────────────────────

@autonomy_bp.route("/dashboard", methods=["GET"])
@require_token
def get_dashboard():
    """GET /api/v1/autonomy/dashboard — Status aller Zonen + Module + Stats."""
    if not _executor:
        return _error("AutonomyExecutor not available", 503)
    try:
        dashboard = _executor.get_dashboard()
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to build autonomy dashboard")
        return _error(str(exc), 500)
    return jsonify({"ok": True, **dashboard})


# ── Zone Status ─────────────────────────────────────────────────────────

@autonomy_bp.route("/zones/<zone_id>", methods=["GET"])
@require_token
def get_zone_status(zone_id: str):
    """GET /api/v1/autonomy/zones/<zone_id> — Zone mode + per-module states."""
    result = {"ok": True, "zone_id": zone_id}
    try:
        if _executor and _executor._zone_automation:
            result["automation_mode"] = _executor._zone_automation.get_automation_mode(zone_id)
        if _module_registry:
            result["module_states"] = _module_registry.get_zone_states(zone_id)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to build autonomy zone status for %s", zone_id)
        return _error(str(exc), 500)
    return jsonify(result)


@autonomy_bp.route("/zones/<zone_id>/module", methods=["POST"])
@require_token
def set_zone_module_state(zone_id: str):
    """POST /api/v1/autonomy/zones/<zone_id>/module — Per-zone module state setzen.

    Body: {"module_id": "licht", "state": "active"}
    """
    if not _module_registry:
        return _error("ModuleRegistry not available", 503)

    body, error_response = _json_body()
    if error_response:
        return error_response

    module_id = body.get("module_id")
    state = body.get("state")

    if not isinstance(module_id, str) or not module_id.strip():
        return _error("module_id must be a non-empty string", 400)
    if not isinstance(state, str) or not state.strip():
        return _error("state must be a non-empty string", 400)

    module_id = module_id.strip()
    state = state.strip()

    try:
        ok = _module_registry.set_zone_state(zone_id, module_id, state)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to set autonomy module state for zone %s", zone_id)
        return _error(str(exc), 500)

    if not ok:
        return _error(f"Invalid state: {state}", 400)

    return jsonify({
        "zone_id": zone_id,
        "module_id": module_id,
        "state": state,
        "ok": True,
    })


# ── Zone History ────────────────────────────────────────────────────────

@autonomy_bp.route("/zones/<zone_id>/history", methods=["GET"])
@require_token
def get_zone_history(zone_id: str):
    """GET /api/v1/autonomy/zones/<zone_id>/history — Behavioral log for zone."""
    if not _executor or not _executor._behavioral_log:
        return _error("BehavioralLog not available", 503)

    top_k, error_response = _parse_positive_int_arg("limit", default=20)
    if error_response:
        return error_response

    try:
        history = _executor._behavioral_log.get_zone_history(zone_id, top_k=top_k)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to fetch autonomy history for zone %s", zone_id)
        return _error(str(exc), 500)
    return jsonify({"ok": True, "zone_id": zone_id, "history": history})


# ── Mood Actions ────────────────────────────────────────────────────────

@autonomy_bp.route("/mood-actions", methods=["GET"])
@require_token
def get_mood_actions():
    """GET /api/v1/autonomy/mood-actions — Aktuelle Mood-Action-Tabelle."""
    if not _executor:
        return _error("AutonomyExecutor not available", 503)

    try:
        mapper = _executor._get_mood_mapper()
        actions = mapper.get_all_actions()
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to fetch autonomy mood actions")
        return _error(str(exc), 500)
    return jsonify({"ok": True, "actions": actions})


@autonomy_bp.route("/mood-actions/<mood>/override", methods=["POST"])
@require_token
def set_mood_override(mood: str):
    """POST /api/v1/autonomy/mood-actions/<mood>/override — Override mood actions."""
    if not _executor:
        return _error("AutonomyExecutor not available", 503)

    body, error_response = _json_body()
    if error_response:
        return error_response

    try:
        mapper = _executor._get_mood_mapper()
        result = mapper.set_override(mood, body)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to set autonomy mood override for %s", mood)
        return _error(str(exc), 500)
    return jsonify(result.to_dict())


# ── Stats ───────────────────────────────────────────────────────────────

@autonomy_bp.route("/stats", methods=["GET"])
@require_token
def get_stats():
    """GET /api/v1/autonomy/stats — Execution statistics."""
    if not _executor:
        return _error("AutonomyExecutor not available", 503)

    try:
        stats = dict(_executor._stats)
        if _executor._behavioral_log:
            stats["log"] = _executor._behavioral_log.get_stats()
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to build autonomy stats")
        return _error(str(exc), 500)
    return jsonify({"ok": True, **stats})
