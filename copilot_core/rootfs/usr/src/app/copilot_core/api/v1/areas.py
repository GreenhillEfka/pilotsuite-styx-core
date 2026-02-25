"""
Areas API - PilotSuite v7.34
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

areas_bp = Blueprint("areas", __name__, url_prefix="/api/v1/areas")

def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None

@areas_bp.route("", methods=["GET"])
@require_token
def list_areas():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    from homeassistant.helpers import area_registry as ar
    reg = ar.async_get(hass)
    areas = reg.areas
    return jsonify({"ok": True, "areas": [{"id": a.id, "name": a.name} for a in areas.values()], "count": len(areas)})
