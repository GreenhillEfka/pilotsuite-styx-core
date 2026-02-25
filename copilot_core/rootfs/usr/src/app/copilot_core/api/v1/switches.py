"""
Switches API - PilotSuite v7.15.0

API for controlling switches.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

switches_bp = Blueprint("switches", __name__, url_prefix="/api/v1/switches")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@switches_bp.route("", methods=["GET"])
@require_token
def list_switches():
    """List all switch entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        switches = [s for s in hass.states.async_all() if s.domain == "switch"]
        return jsonify({
            "ok": True,
            "switches": [
                {
                    "entity_id": sw.entity_id,
                    "state": sw.state,
                    "friendly_name": sw.attributes.get("friendly_name"),
                }
                for sw in switches
            ],
            "count": len(switches),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@switches_bp.route("/<switch_id>/turn_on", methods=["POST"])
@require_token
def turn_on_switch(switch_id):
    """Turn on a switch."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("switch", "turn_on", {"entity_id": switch_id})
        return jsonify({"ok": True, "entity_id": switch_id, "state": "on"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@switches_bp.route("/<switch_id>/turn_off", methods=["POST"])
@require_token
def turn_off_switch(switch_id):
    """Turn off a switch."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("switch", "turn_off", {"entity_id": switch_id})
        return jsonify({"ok": True, "entity_id": switch_id, "state": "off"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@switches_bp.route("/<switch_id>/toggle", methods=["POST"])
@require_token
def toggle_switch(switch_id):
    """Toggle a switch."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("switch", "toggle", {"entity_id": switch_id})
        return jsonify({"ok": True, "entity_id": switch_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
