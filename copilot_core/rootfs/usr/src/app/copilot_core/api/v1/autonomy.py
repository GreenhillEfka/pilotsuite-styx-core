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


# ── Dashboard ───────────────────────────────────────────────────────────

@autonomy_bp.route("/dashboard", methods=["GET"])
@require_token
def get_dashboard():
    """GET /api/v1/autonomy/dashboard — Status aller Zonen + Module + Stats."""
    if not _executor:
        return jsonify({"error": "AutonomyExecutor not available"}), 503
    return jsonify(_executor.get_dashboard())


# ── Zone Status ─────────────────────────────────────────────────────────

@autonomy_bp.route("/zones/<zone_id>", methods=["GET"])
@require_token
def get_zone_status(zone_id: str):
    """GET /api/v1/autonomy/zones/<zone_id> — Zone mode + per-module states."""
    result = {"zone_id": zone_id}
    if _executor and _executor._zone_automation:
        result["automation_mode"] = _executor._zone_automation.get_automation_mode(zone_id)
    if _module_registry:
        result["module_states"] = _module_registry.get_zone_states(zone_id)
    return jsonify(result)


@autonomy_bp.route("/zones/<zone_id>/module", methods=["POST"])
@require_token
def set_zone_module_state(zone_id: str):
    """POST /api/v1/autonomy/zones/<zone_id>/module — Per-zone module state setzen.

    Body: {"module_id": "licht", "state": "active"}
    """
    if not _module_registry:
        return jsonify({"error": "ModuleRegistry not available"}), 503

    body = request.get_json(silent=True) or {}
    module_id = body.get("module_id", "")
    state = body.get("state", "")

    if not module_id or not state:
        return jsonify({"error": "module_id and state required"}), 400

    ok = _module_registry.set_zone_state(zone_id, module_id, state)
    if not ok:
        return jsonify({"error": f"Invalid state: {state}"}), 400

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
        return jsonify({"error": "BehavioralLog not available"}), 503

    top_k = request.args.get("limit", 20, type=int)
    history = _executor._behavioral_log.get_zone_history(zone_id, top_k=top_k)
    return jsonify({"zone_id": zone_id, "history": history})


# ── Mood Actions ────────────────────────────────────────────────────────

@autonomy_bp.route("/mood-actions", methods=["GET"])
@require_token
def get_mood_actions():
    """GET /api/v1/autonomy/mood-actions — Aktuelle Mood-Action-Tabelle."""
    if not _executor:
        return jsonify({"error": "AutonomyExecutor not available"}), 503

    mapper = _executor._get_mood_mapper()
    return jsonify(mapper.get_all_actions())


@autonomy_bp.route("/mood-actions/<mood>/override", methods=["POST"])
@require_token
def set_mood_override(mood: str):
    """POST /api/v1/autonomy/mood-actions/<mood>/override — Override mood actions."""
    if not _executor:
        return jsonify({"error": "AutonomyExecutor not available"}), 503

    body = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"error": "Request body required"}), 400

    mapper = _executor._get_mood_mapper()
    result = mapper.set_override(mood, body)
    return jsonify(result.to_dict())


# ── Stats ───────────────────────────────────────────────────────────────

@autonomy_bp.route("/stats", methods=["GET"])
@require_token
def get_stats():
    """GET /api/v1/autonomy/stats — Execution statistics."""
    if not _executor:
        return jsonify({"error": "AutonomyExecutor not available"}), 503

    stats = dict(_executor._stats)
    if _executor._behavioral_log:
        stats["log"] = _executor._behavioral_log.get_stats()
    return jsonify(stats)
