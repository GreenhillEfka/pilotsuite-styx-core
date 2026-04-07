"""Character API — Styx Personality Management.

Endpoints:
  GET  /api/v1/character/current    — Current character preset
  GET  /api/v1/character/modes      — Available character modes
  POST /api/v1/character/mode       — Set character mode
  POST /api/v1/character/mood       — Apply mood weights via character
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("character", __name__, url_prefix="/api/v1/character")
_LOGGER = logging.getLogger(__name__)


def _service():
    return current_app.config.get("COPILOT_SERVICES", {}).get("character_service")


def _runtime_error(exc: Exception):
    _LOGGER.exception("Character API error: %s", exc)
    return jsonify({"ok": False, "error": str(exc)}), 500


def _require_service():
    svc = _service()
    if not svc:
        return None, (jsonify({"ok": False, "error": "character_service not initialized"}), 503)
    return svc, None


def _get_json_object() -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"ok": False, "error": "JSON object required"}), 400)
    return data, None


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/current", methods=["GET"])
def current_preset():
    """Get current character preset."""
    svc, error = _require_service()
    if error:
        return error

    try:
        return jsonify({"ok": True, **svc.to_dict()})
    except Exception as exc:  # pragma: no cover - exercised via contract harness
        return _runtime_error(exc)


@bp.route("/modes", methods=["GET"])
def list_modes():
    """List available character modes."""
    svc, error = _require_service()
    if error:
        return error

    try:
        return jsonify({"ok": True, "modes": svc.get_available_modes()})
    except Exception as exc:  # pragma: no cover - exercised via contract harness
        return _runtime_error(exc)


@bp.route("/mode", methods=["POST"])
def set_mode():
    """Set character mode."""
    svc, error = _require_service()
    if error:
        return error

    data, error = _get_json_object()
    if error:
        return error

    mode_str = data.get("mode")
    if not isinstance(mode_str, str) or not mode_str.strip():
        return jsonify({"ok": False, "error": "mode must be a non-empty string"}), 400

    from copilot_core.styx.character_models import CharacterMode

    try:
        mode = CharacterMode(mode_str)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": f"unknown mode: {mode_str}"}), 400

    try:
        svc.set_mode(mode)
        return jsonify({"ok": True, **svc.to_dict()})
    except Exception as exc:  # pragma: no cover - exercised via contract harness
        return _runtime_error(exc)


@bp.route("/mood", methods=["POST"])
def apply_mood():
    """Apply character mood weights to base mood scores."""
    svc, error = _require_service()
    if error:
        return error

    data, error = _get_json_object()
    if error:
        return error

    base_mood = data.get("mood")
    if not isinstance(base_mood, dict) or not base_mood:
        return jsonify({"ok": False, "error": "mood dict required"}), 400

    invalid_keys = [
        key for key, value in base_mood.items() if not isinstance(value, (int, float))
    ]
    if invalid_keys:
        return jsonify({"ok": False, "error": "mood values must be numeric"}), 400

    try:
        weighted = svc.apply_mood_weights(base_mood)
        return jsonify({"ok": True, "weighted_mood": weighted})
    except Exception as exc:  # pragma: no cover - exercised via contract harness
        return _runtime_error(exc)
