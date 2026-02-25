"""
Zones API - PilotSuite v7.25.0

API for HA zones.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

zones_bp = Blueprint("zones", __name__, url_prefix="/api/v1/zones")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@zones_bp.route("", methods=["GET"])
@require_token
def list_zones():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        zones = [s for s in hass.states.async_all() if s.domain == "zone"]
        return jsonify({
            "ok": True,
            "zones": [
                {
                    "entity_id": z.entity_id,
                    "state": z.state,
                    "attributes": dict(z.attributes),
                }
                for z in zones
            ],
            "count": len(zones),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
