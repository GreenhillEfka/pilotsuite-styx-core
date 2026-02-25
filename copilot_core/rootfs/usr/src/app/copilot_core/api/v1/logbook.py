"""
Logbook API - PilotSuite v7.29.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

logbook_bp = Blueprint("logbook", __name__, url_prefix="/api/v1/logbook")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None


@logbook_bp.route("", methods=["GET"])
@require_token
def get_logbook():
    """Get logbook entries."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        limit = int(request.args.get("limit", 20))
        from datetime import datetime, timedelta
        start_time = datetime.now() - timedelta(hours=24)
        
        logbook = hass.get_domain("logbook")
        if not logbook:
            return jsonify({"error": "Logbook not available"}), 503
        
        entries = logbook.get_events(start_time, None)
        entries = entries[:limit]
        
        return jsonify({
            "ok": True,
            "entries": [
                {"name": e.get("name"), "message": e.get("message"), "when": e.get("when")}
                for e in entries
            ],
            "count": len(entries),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
