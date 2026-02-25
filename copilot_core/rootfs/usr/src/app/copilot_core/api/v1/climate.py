"""
Climate API - PilotSuite v7.15.0

API for controlling climate devices.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

climate_bp = Blueprint("climate", __name__, url_prefix="/api/v1/climate")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@climate_bp.route("", methods=["GET"])
@require_token
def list_climate_devices():
    """List all climate entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        climate = [s for s in hass.states.async_all() if s.domain == "climate"]
        return jsonify({
            "ok": True,
            "climate_devices": [
                {
                    "entity_id": c.entity_id,
                    "state": c.state,
                    "temperature": c.attributes.get("current_temperature"),
                    "target_temperature": c.attributes.get("temperature"),
                    "hvac_mode": c.attributes.get("hvac_mode"),
                    "friendly_name": c.attributes.get("friendly_name"),
                }
                for c in climate
            ],
            "count": len(climate),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@climate_bp.route("/<device_id>/set_temperature", methods=["POST"])
@require_token
def set_temperature(device_id):
    """Set target temperature."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    temperature = data.get("temperature")
    
    if not temperature:
        return jsonify({"error": "temperature required"}), 400
    
    try:
        hass.services.call("climate", "set_temperature", {
            "entity_id": device_id,
            "temperature": temperature
        })
        return jsonify({"ok": True, "entity_id": device_id, "temperature": temperature})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@climate_bp.route("/<device_id>/set_hvac_mode", methods=["POST"])
@require_token
def set_hvac_mode(device_id):
    """Set HVAC mode (heat, cool, auto, off)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    mode = data.get("mode")
    
    if not mode:
        return jsonify({"error": "mode required (heat, cool, auto, off)"}), 400
    
    try:
        hass.services.call("climate", "set_hvac_mode", {
            "entity_id": device_id,
            "hvac_mode": mode
        })
        return jsonify({"ok": True, "entity_id": device_id, "mode": mode})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
