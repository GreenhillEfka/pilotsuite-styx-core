"""
Repairs API - PilotSuite v7.30.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

repairs_bp = Blueprint("repairs", __name__, url_prefix="/api/v1/repairs")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None


@repairs_bp.route("", methods=["GET"])
@require_token
def list_repairs():
    """List all repair issues."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        repairs = [s for s in hass.states.async_all() if s.domain == "repair"]
        return jsonify({
            "ok": True,
            "repairs": [
                {"entity_id": r.entity_id, "state": r.state, "attributes": dict(r.attributes)}
                for r in repairs
            ],
            "count": len(repairs),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
