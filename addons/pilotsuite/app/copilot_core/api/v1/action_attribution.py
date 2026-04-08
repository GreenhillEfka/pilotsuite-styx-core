"""Action Attribution API — Multi-source user attribution.

Endpoints:
  POST /api/v1/attribution/attribute   — Attribute an action to a user
  GET  /api/v1/attribution/history     — Get action history
  GET  /api/v1/attribution/user/:uid   — Get actions for a specific user
"""
from __future__ import annotations

import logging

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


@bp.route("/attribute", methods=["POST"])
def attribute():
    """Attribute an action to a user from pre-gathered signals."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "action_attribution not initialized"}), 503

    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id")
    action = data.get("action")
    signals = data.get("signals", [])

    if not entity_id or not action:
        return jsonify({"ok": False, "error": "entity_id and action required"}), 400

    from copilot_core.styx.action_attribution import AttributionSignal
    parsed_signals = [
        AttributionSignal(
            source_name=s.get("source_name", "unknown"),
            user_id=s.get("user_id", ""),
            confidence=s.get("confidence", 0.0),
            metadata=s.get("metadata", {}),
        )
        for s in signals if s.get("user_id")
    ]

    result = svc.attribute_action(entity_id, action, parsed_signals)
    if result is None:
        return jsonify({"ok": False, "error": "no attribution possible"})

    return jsonify({"ok": True, "attribution": {
        "user_id": result.user_id,
        "entity_id": result.entity_id,
        "action": result.action,
        "confidence": result.confidence,
        "sources": result.sources,
    }})


@bp.route("/history", methods=["GET"])
def history():
    """Get recent action history."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "action_attribution not initialized"}), 503

    limit = request.args.get("limit", 100, type=int)
    actions = svc.get_action_history(limit)
    return jsonify({"ok": True, "actions": [
        {"user_id": a.user_id, "entity_id": a.entity_id, "action": a.action,
         "confidence": a.confidence, "timestamp": a.timestamp}
        for a in actions
    ]})


@bp.route("/user/<user_id>", methods=["GET"])
def user_actions(user_id):
    """Get actions for a specific user."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "action_attribution not initialized"}), 503

    limit = request.args.get("limit", 100, type=int)
    actions = svc.get_user_actions(user_id, limit)
    return jsonify({"ok": True, "user_id": user_id, "actions": [
        {"entity_id": a.entity_id, "action": a.action,
         "confidence": a.confidence, "timestamp": a.timestamp}
        for a in actions
    ]})
