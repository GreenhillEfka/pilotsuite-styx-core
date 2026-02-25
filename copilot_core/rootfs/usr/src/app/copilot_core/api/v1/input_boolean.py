"""
Input Boolean API - PilotSuite v7.26.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

input_boolean_bp = Blueprint("input_boolean", __name__, url_prefix="/api/v1/input_boolean")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@input_boolean_bp.route("", methods=["GET"])
@require_token
def list_input_booleans():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        inputs = [s for s in hass.states.async_all() if s.domain == "input_boolean"]
        return jsonify({"ok": True, "inputs": [{"entity_id": i.entity_id, "state": i.state} for i in inputs], "count": len(inputs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@input_boolean_bp.route("/<input_id>/turn_on", methods=["POST"])
@require_token
def turn_on_input(input_id):
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("input_boolean", "turn_on", {"entity_id": input_id})
        return jsonify({"ok": True, "entity_id": input_id, "state": "on"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@input_boolean_bp.route("/<input_id>/turn_off", methods=["POST"])
@require_token
def turn_off_input(input_id):
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("input_boolean", "turn_off", {"entity_id": input_id})
        return jsonify({"ok": True, "entity_id": input_id, "state": "off"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
