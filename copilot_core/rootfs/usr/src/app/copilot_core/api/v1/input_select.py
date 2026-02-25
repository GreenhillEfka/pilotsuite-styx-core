"""
Input Select API - PilotSuite v7.17.0

API for input_select entities.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

input_select_bp = Blueprint("input_select", __name__, url_prefix="/api/v1/input_select")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@input_select_bp.route("", methods=["GET"])
@require_token
def list_input_selects():
    """List all input_select entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        selects = [s for s in hass.states.async_all() if s.domain == "input_select"]
        return jsonify({
            "ok": True,
            "input_selects": [
                {
                    "entity_id": s.entity_id,
                    "state": s.state,
                    "options": s.attributes.get("options", []),
                    "friendly_name": s.attributes.get("friendly_name"),
                }
                for s in selects
            ],
            "count": len(selects),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@input_select_bp.route("/<select_id>/select_option", methods=["POST"])
@require_token
def select_option(select_id):
    """Select an option."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    option = data.get("option")
    
    if not option:
        return jsonify({"error": "option required"}), 400
    
    try:
        hass.services.call("input_select", "select_option", {
            "entity_id": select_id,
            "option": option
        })
        return jsonify({"ok": True, "entity_id": select_id, "option": option})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
