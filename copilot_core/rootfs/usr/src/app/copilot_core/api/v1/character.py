"""Character API — Styx Personality Management.

Endpoints:
  GET  /api/v1/character/current    — Current character preset
  GET  /api/v1/character/modes      — Available character modes
  POST /api/v1/character/mode       — Set character mode
  POST /api/v1/character/mood       — Apply mood weights via character
"""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("character", __name__, url_prefix="/api/v1/character")
_LOGGER = logging.getLogger(__name__)


def _service():
    return current_app.config.get("COPILOT_SERVICES", {}).get("character_service")


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/current", methods=["GET"])
def current_preset():
    """Get current character preset."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "character_service not initialized"}), 503
    return jsonify({"ok": True, **svc.to_dict()})


@bp.route("/modes", methods=["GET"])
def list_modes():
    """List available character modes."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "character_service not initialized"}), 503
    return jsonify({"ok": True, "modes": svc.get_available_modes()})


@bp.route("/mode", methods=["POST"])
def set_mode():
    """Set character mode."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "character_service not initialized"}), 503

    data = request.get_json(silent=True) or {}
    mode_str = data.get("mode")
    if not mode_str:
        return jsonify({"ok": False, "error": "mode required"}), 400

    from copilot_core.styx.character_models import CharacterMode
    try:
        mode = CharacterMode(mode_str)
    except ValueError:
        return jsonify({"ok": False, "error": f"unknown mode: {mode_str}"}), 400

    svc.set_mode(mode)
    return jsonify({"ok": True, **svc.to_dict()})


@bp.route("/mood", methods=["POST"])
def apply_mood():
    """Apply character mood weights to base mood scores."""
    svc = _service()
    if not svc:
        return jsonify({"ok": False, "error": "character_service not initialized"}), 503

    data = request.get_json(silent=True) or {}
    base_mood = data.get("mood", {})
    if not base_mood:
        return jsonify({"ok": False, "error": "mood dict required"}), 400

    weighted = svc.apply_mood_weights(base_mood)
    return jsonify({"ok": True, "weighted_mood": weighted})
