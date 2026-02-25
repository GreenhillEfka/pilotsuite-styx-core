"""
Tags API - PilotSuite v7.32
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

tags_bp = Blueprint("tags", __name__, url_prefix="/api/v1/tags")

def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None

@tags_bp.route("", methods=["GET"])
@require_token
def list_tags():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    tags = [s for s in hass.states.async_all() if s.domain == "tag"]
    return jsonify({"ok": True, "tags": [{"entity_id": t.entity_id, "state": t.state} for t in tags], "count": len(tags)})
