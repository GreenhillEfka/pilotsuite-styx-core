"""
Cover/Blinds API - PilotSuite v7.18.0

API for controlling covers (blinds, curtains, garage doors).
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

covers_bp = Blueprint("covers", __name__, url_prefix="/api/v1/covers")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@covers_bp.route("", methods=["GET"])
@require_token
def list_covers():
    """List all cover entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        covers = [s for s in hass.states.async_all() if s.domain == "cover"]
        return jsonify({
            "ok": True,
            "covers": [
                {
                    "entity_id": c.entity_id,
                    "state": c.state,
                    "current_position": c.attributes.get("current_position"),
                    "friendly_name": c.attributes.get("friendly_name"),
                }
                for c in covers
            ],
            "count": len(covers),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@covers_bp.route("/<cover_id>/open", methods=["POST"])
@require_token
def open_cover(cover_id):
    """Open a cover."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("cover", "open_cover", {"entity_id": cover_id})
        return jsonify({"ok": True, "entity_id": cover_id, "state": "opening"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@covers_bp.route("/<cover_id>/close", methods=["POST"])
@require_token
def close_cover(cover_id):
    """Close a cover."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("cover", "close_cover", {"entity_id": cover_id})
        return jsonify({"ok": True, "entity_id": cover_id, "state": "closing"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@covers_bp.route("/<cover_id>/stop", methods=["POST"])
@require_token
def stop_cover(cover_id):
    """Stop a cover."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("cover", "stop_cover", {"entity_id": cover_id})
        return jsonify({"ok": True, "entity_id": cover_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@covers_bp.route("/<cover_id>/set_position", methods=["POST"])
@require_token
def set_cover_position(cover_id):
    """Set cover position (0-100)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    position = data.get("position")
    
    if position is None:
        return jsonify({"error": "position required (0-100)"}), 400
    
    try:
        hass.services.call("cover", "set_cover_position", {
            "entity_id": cover_id,
            "position": position
        })
        return jsonify({"ok": True, "entity_id": cover_id, "position": position})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
