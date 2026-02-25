"""
Scripts API - PilotSuite v7.24.0

API for HA scripts.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

scripts_bp = Blueprint("scripts", __name__, url_prefix="/api/v1/scripts")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@scripts_bp.route("", methods=["GET"])
@require_token
def list_scripts():
    """List all script entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        scripts = [s for s in hass.states.async_all() if s.domain == "script"]
        return jsonify({
            "ok": True,
            "scripts": [
                {
                    "entity_id": s.entity_id,
                    "state": s.state,
                    "friendly_name": s.attributes.get("friendly_name"),
                }
                for s in scripts
            ],
            "count": len(scripts),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scripts_bp.route("/<script_id>/run", methods=["POST"])
@require_token
def run_script(script_id):
    """Run a script."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    
    try:
        hass.services.call("script", "turn_on", {
            "entity_id": script_id,
        })
        return jsonify({"ok": True, "script_id": script_id, "message": "Script started"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scripts_bp.route("/<script_id>/stop", methods=["POST"])
@require_token
def stop_script(script_id):
    """Stop a running script."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("script", "turn_off", {"entity_id": script_id})
        return jsonify({"ok": True, "script_id": script_id, "message": "Script stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
