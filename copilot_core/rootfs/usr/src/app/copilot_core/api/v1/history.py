"""
History API - PilotSuite v7.20.0

API for entity history.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__, url_prefix="/api/v1/history")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@history_bp.route("/entity/<entity_id>", methods=["GET"])
@require_token
def get_entity_history(entity_id):
    """Get history for a specific entity."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hours = int(request.args.get("hours", 24))
        
        # Use HA history API
        from datetime import datetime, timedelta
        start_time = datetime.now() - timedelta(hours=hours)
        
        history_list = hass.get_domain("history")
        if not history_list:
            return jsonify({"error": "History not available"}), 503
        
        # Get history for entity
        states = history_list.get_state_list(start_time, entity_id=entity_id)
        
        return jsonify({
            "ok": True,
            "entity_id": entity_id,
            "history": [
                {
                    "state": s.state,
                    "timestamp": s.last_changed.isoformat() if s.last_changed else None,
                }
                for s in states
            ],
            "count": len(states),
        })
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return jsonify({"error": str(e)}), 500


@history_bp.route("/recent", methods=["GET"])
@require_token
def get_recent_changes():
    """Get recently changed entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        limit = int(request.args.get("limit", 20))
        
        all_states = list(hass.states.async_all())
        
        # Sort by last_changed
        sorted_states = sorted(
            all_states,
            key=lambda s: s.last_changed or 0,
            reverse=True
        )[:limit]
        
        return jsonify({
            "ok": True,
            "entities": [
                {
                    "entity_id": s.entity_id,
                    "domain": s.domain,
                    "state": s.state,
                    "last_changed": s.last_changed.isoformat() if s.last_changed else None,
                }
                for s in sorted_states
            ],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
