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

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("conflict_resolution", __name__, url_prefix="/api/v1/conflicts")
_LOGGER = logging.getLogger(__name__)


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
        return jsonify({"ok": False, "error": "conflict_resolver not initialized"}), 503
    return jsonify({"ok": True, **resolver.state.to_dict()})


@bp.route("/evaluate", methods=["POST"])
def evaluate():
    """Evaluate conflicts.

    If a UserPreferenceStore is wired, can auto-read moods/priorities.
    Otherwise expects JSON body: {user_moods, user_priorities}.
    """
    resolver = _get_resolver()
    if not resolver:
        return jsonify({"ok": False, "error": "conflict_resolver not initialized"}), 503

    data = request.get_json(silent=True) or {}

    # Option 1: explicit moods/priorities in body
    if "user_moods" in data and "user_priorities" in data:
        state = resolver.evaluate(data["user_moods"], data["user_priorities"])
        return jsonify({"ok": True, **state.to_dict()})

    # Option 2: auto-read from UserPreferenceStore
    active_ids = data.get("active_user_ids")
    try:
        state = resolver.evaluate_from_store(active_ids)
        return jsonify({"ok": True, **state.to_dict()})
    except Exception as exc:
        _LOGGER.exception("Conflict evaluation failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/strategy", methods=["POST"])
def set_strategy():
    """Set resolution strategy.

    JSON body: {strategy: "weighted"|"compromise"|"override", override_user?: str}
    """
    resolver = _get_resolver()
    if not resolver:
        return jsonify({"ok": False, "error": "conflict_resolver not initialized"}), 503

    data = request.get_json(silent=True) or {}
    strategy = data.get("strategy")
    if not strategy:
        return jsonify({"ok": False, "error": "strategy required"}), 400

    try:
        resolver.set_strategy(strategy, data.get("override_user"))
        return jsonify({"ok": True, "strategy": strategy})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
