"""
Lights API - PilotSuite v7.15.0

API for controlling lights.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

lights_bp = Blueprint("lights", __name__, url_prefix="/api/v1/lights")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@lights_bp.route("", methods=["GET"])
@require_token
def list_lights():
    """List all light entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        lights = [s for s in hass.states.async_all() if s.domain == "light"]
        return jsonify({
            "ok": True,
            "lights": [
                {
                    "entity_id": l.entity_id,
                    "state": l.state,
                    "brightness": l.attributes.get("brightness"),
                    "color_temp": l.attributes.get("color_temp"),
                    "rgb_color": l.attributes.get("rgb_color"),
                    "friendly_name": l.attributes.get("friendly_name"),
                }
                for l in lights
            ],
            "count": len(lights),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lights_bp.route("/<light_id>/turn_on", methods=["POST"])
@require_token
def turn_on_light(light_id):
    """Turn on a light."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    
    service_data = {}
    if "brightness" in data:
        service_data["brightness"] = data["brightness"]
    if "color_temp" in data:
        service_data["color_temp"] = data["color_temp"]
    if "rgb_color" in data:
        service_data["rgb_color"] = data["rgb_color"]
    
    try:
        hass.services.call("light", "turn_on", {"entity_id": light_id}, service_data)
        return jsonify({"ok": True, "entity_id": light_id, "state": "on"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lights_bp.route("/<light_id>/turn_off", methods=["POST"])
@require_token
def turn_off_light(light_id):
    """Turn off a light."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("light", "turn_off", {"entity_id": light_id})
        return jsonify({"ok": True, "entity_id": light_id, "state": "off"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lights_bp.route("/<light_id>/toggle", methods=["POST"])
@require_token
def toggle_light(light_id):
    """Toggle a light."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("light", "toggle", {"entity_id": light_id})
        return jsonify({"ok": True, "entity_id": light_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
