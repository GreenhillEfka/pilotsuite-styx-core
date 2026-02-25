"""
Input Number API - PilotSuite v7.25.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

input_number_bp = Blueprint("input_number", __name__, url_prefix="/api/v1/input_number")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@input_number_bp.route("", methods=["GET"])
@require_token
def list_input_numbers():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        inputs = [s for s in hass.states.async_all() if s.domain == "input_number"]
        return jsonify({
            "ok": True,
            "inputs": [
                {"entity_id": i.entity_id, "state": i.state, "attributes": dict(i.attributes)}
                for i in inputs
            ],
            "count": len(inputs),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@input_number_bp.route("/<input_id>/set", methods=["POST"])
@require_token
def set_input_number(input_id):
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    value = data.get("value")
    
    if value is None:
        return jsonify({"error": "value required"}), 400
    
    try:
        hass.services.call("input_number", "set_value", {"entity_id": input_id, "value": float(value)})
        return jsonify({"ok": True, "entity_id": input_id, "value": value})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
