"""
Persons API - PilotSuite v7.31.0
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

persons_bp = Blueprint("persons", __name__, url_prefix="/api/v1/persons")

def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None

@persons_bp.route("", methods=["GET"])
@require_token
def list_persons():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    persons = [s for s in hass.states.async_all() if s.domain == "person"]
    return jsonify({"ok": True, "persons": [{"entity_id": p.entity_id, "state": p.state} for p in persons], "count": len(persons)})
