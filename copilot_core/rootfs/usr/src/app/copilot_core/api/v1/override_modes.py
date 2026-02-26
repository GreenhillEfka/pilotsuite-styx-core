"""Override Modes API -- House-wide and per-zone automation overrides.

Blueprint prefix: /api/v1/modes

Endpoints:
    GET  /api/v1/modes                     List all mode definitions + active modes
    GET  /api/v1/modes/active              List currently active modes
    POST /api/v1/modes/<mode_id>/activate  Activate a mode
    POST /api/v1/modes/<mode_id>/deactivate Deactivate a mode
    POST /api/v1/modes/<mode_id>/toggle    Toggle a mode on/off
    GET  /api/v1/modes/<mode_id>           Get mode definition
    GET  /api/v1/modes/consequences/<zone_id> Get merged consequences for a zone
    POST /api/v1/modes/custom              Create a custom mode
    DELETE /api/v1/modes/custom/<mode_id>  Delete a custom mode
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

override_modes_bp = Blueprint(
    "override_modes", __name__, url_prefix="/api/v1/modes"
)

_service: Optional[Any] = None


def init_override_modes_api(override_modes_service) -> None:
    """Wire OverrideModesService into the blueprint."""
    global _service
    _service = override_modes_service
    _LOGGER.info("Override Modes API initialized")


def _require_service():
    if _service is None:
        return None, (jsonify({
            "ok": False,
            "error": "OverrideModesService not initialized",
        }), 503)
    return _service, None


@override_modes_bp.route("", methods=["GET"])
@require_token
def get_status():
    """Get all mode definitions and active modes."""
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_status()
    except Exception as exc:
        _LOGGER.exception("Failed to get override modes status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


@override_modes_bp.route("/active", methods=["GET"])
@require_token
def get_active():
    """List currently active modes."""
    svc, err = _require_service()
    if err:
        return err

    try:
        modes = svc.get_active_modes()
    except Exception as exc:
        _LOGGER.exception("Failed to get active modes")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "active_modes": modes})


@override_modes_bp.route("/<mode_id>", methods=["GET"])
@require_token
def get_definition(mode_id: str):
    """Get a single mode definition."""
    svc, err = _require_service()
    if err:
        return err

    result = svc.get_definition(mode_id)
    if result is None:
        return jsonify({"ok": False, "error": f"Mode '{mode_id}' not found"}), 404

    return jsonify({"ok": True, "mode": result})


@override_modes_bp.route("/<mode_id>/activate", methods=["POST"])
@require_token
def activate_mode(mode_id: str):
    """Activate an override mode.

    Request body (all optional)::

        {
            "zone_ids": ["zone:wohnzimmer", "zone:kinderzimmer"],
            "timeout_s": 3600,
            "activated_by": "user"
        }
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    try:
        result = svc.activate_mode(
            mode_id=mode_id,
            zone_ids=data.get("zone_ids"),
            activated_by=str(data.get("activated_by", "user")),
            timeout_s=int(data.get("timeout_s", 0)),
        )
    except Exception as exc:
        _LOGGER.exception("Failed to activate mode %s", mode_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@override_modes_bp.route("/<mode_id>/deactivate", methods=["POST"])
@require_token
def deactivate_mode(mode_id: str):
    """Deactivate an override mode."""
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.deactivate_mode(mode_id)
    except Exception as exc:
        _LOGGER.exception("Failed to deactivate mode %s", mode_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@override_modes_bp.route("/<mode_id>/toggle", methods=["POST"])
@require_token
def toggle_mode(mode_id: str):
    """Toggle an override mode on/off."""
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    try:
        result = svc.toggle_mode(
            mode_id=mode_id,
            zone_ids=data.get("zone_ids"),
            activated_by=str(data.get("activated_by", "user")),
        )
    except Exception as exc:
        _LOGGER.exception("Failed to toggle mode %s", mode_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@override_modes_bp.route("/consequences/<zone_id>", methods=["GET"])
@require_token
def get_consequences(zone_id: str):
    """Get the merged consequences for a zone from all active modes."""
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_effective_consequences(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to get consequences for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, **result})


@override_modes_bp.route("/custom", methods=["POST"])
@require_token
def create_custom():
    """Create a custom override mode.

    Request body::

        {
            "mode_id": "movie_night",
            "name": "Filmabend",
            "description": "...",
            "priority": 60,
            "consequences": {
                "light_max_brightness_pct": 10,
                "music_mute": true
            }
        }
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    try:
        result = svc.create_custom_mode(data)
    except Exception as exc:
        _LOGGER.exception("Failed to create custom mode")
        return jsonify({"ok": False, "error": str(exc)}), 500

    status_code = 201 if result.get("ok") else 400
    return jsonify(result), status_code


@override_modes_bp.route("/custom/<mode_id>", methods=["DELETE"])
@require_token
def delete_custom(mode_id: str):
    """Delete a custom override mode."""
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.delete_custom_mode(mode_id)
    except Exception as exc:
        _LOGGER.exception("Failed to delete custom mode %s", mode_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code
