"""
Bulk Operations API - PilotSuite v7.27.0

Bulk entity operations.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

bulk_bp = Blueprint("bulk", __name__, url_prefix="/api/v1/bulk")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@bulk_bp.route("/turn_on", methods=["POST"])
@require_token
def bulk_turn_on():
    """Turn on multiple entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    entities = data.get("entities", [])
    
    if not entities:
        return jsonify({"error": "entities array required"}), 400
    
    try:
        for entity in entities:
            domain = entity.split(".")[0]
            hass.services.call(domain, "turn_on", {"entity_id": entity})
        return jsonify({"ok": True, "affected": len(entities)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bulk_bp.route("/turn_off", methods=["POST"])
@require_token
def bulk_turn_off():
    """Turn off multiple entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    entities = data.get("entities", [])
    
    if not entities:
        return jsonify({"error": "entities array required"}), 400
    
    try:
        for entity in entities:
            domain = entity.split(".")[0]
            hass.services.call(domain, "turn_off", {"entity_id": entity})
        return jsonify({"ok": True, "affected": len(entities)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
