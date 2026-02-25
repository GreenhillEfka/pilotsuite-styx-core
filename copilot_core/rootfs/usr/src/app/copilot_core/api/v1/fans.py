"""
Fans API - PilotSuite v7.18.0

API for controlling fans.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

fans_bp = Blueprint("fans", __name__, url_prefix="/api/v1/fans")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@fans_bp.route("", methods=["GET"])
@require_token
def list_fans():
    """List all fan entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        fans = [s for s in hass.states.async_all() if s.domain == "fan"]
        return jsonify({
            "ok": True,
            "fans": [
                {
                    "entity_id": f.entity_id,
                    "state": f.state,
                    "percentage": f.attributes.get("percentage"),
                    "preset_mode": f.attributes.get("preset_mode"),
                    "friendly_name": f.attributes.get("friendly_name"),
                }
                for f in fans
            ],
            "count": len(fans),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@fans_bp.route("/<fan_id>/turn_on", methods=["POST"])
@require_token
def turn_on_fan(fan_id):
    """Turn on a fan."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    percentage = data.get("percentage", 100)
    
    try:
        hass.services.call("fan", "turn_on", {
            "entity_id": fan_id,
            "percentage": percentage
        })
        return jsonify({"ok": True, "entity_id": fan_id, "state": "on"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@fans_bp.route("/<fan_id>/turn_off", methods=["POST"])
@require_token
def turn_off_fan(fan_id):
    """Turn off a fan."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("fan", "turn_off", {"entity_id": fan_id})
        return jsonify({"ok": True, "entity_id": fan_id, "state": "off"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@fans_bp.route("/<fan_id>/set_percentage", methods=["POST"])
@require_token
def set_fan_percentage(fan_id):
    """Set fan percentage (0-100)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    percentage = data.get("percentage")
    
    if percentage is None:
        return jsonify({"error": "percentage required (0-100)"}), 400
    
    try:
        hass.services.call("fan", "set_percentage", {
            "entity_id": fan_id,
            "percentage": percentage
        })
        return jsonify({"ok": True, "entity_id": fan_id, "percentage": percentage})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
