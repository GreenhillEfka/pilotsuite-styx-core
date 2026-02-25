"""
Alerts API - PilotSuite v7.22.0

API for HA alerts (persistent notifications).
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/v1/alerts")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@alerts_bp.route("", methods=["GET"])
@require_token
def list_alerts():
    """List all persistent notifications."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        notifications = hass.states.async_all("persistent_notification")
        return jsonify({
            "ok": True,
            "alerts": [
                {
                    "entity_id": n.entity_id,
                    "title": n.attributes.get("title"),
                    "message": n.attributes.get("message"),
                    "notification_id": n.attributes.get("notification_id"),
                }
                for n in notifications
            ],
            "count": len(notifications),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/create", methods=["POST"])
@require_token
def create_alert():
    """Create a persistent notification."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    title = data.get("title", "PilotSuite Alert")
    message = data.get("message")
    
    if not message:
        return jsonify({"error": "message required"}), 400
    
    try:
        hass.services.call("persistent_notification", "create", {
            "title": title,
            "message": message,
        })
        return jsonify({
            "ok": True,
            "title": title,
            "message": message,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/dismiss", methods=["POST"])
@require_token
def dismiss_alert():
    """Dismiss a persistent notification."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    notification_id = data.get("notification_id")
    
    if not notification_id:
        return jsonify({"error": "notification_id required"}), 400
    
    try:
        hass.services.call("persistent_notification", "dismiss", {
            "notification_id": notification_id,
        })
        return jsonify({"ok": True, "message": "Alert dismissed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
