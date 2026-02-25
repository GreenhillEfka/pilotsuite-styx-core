"""
Issues API - PilotSuite v7.35
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

issues_bp = Blueprint("issues", __name__, url_prefix="/api/v1/issues")

def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None

@issues_bp.route("", methods=["GET"])
@require_token
def list_issues():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    issues = [s for s in hass.states.async_all() if s.domain == "issue"]
    return jsonify({"ok": True, "issues": [{"entity_id": i.entity_id, "state": i.state} for i in issues], "count": len(issues)})
