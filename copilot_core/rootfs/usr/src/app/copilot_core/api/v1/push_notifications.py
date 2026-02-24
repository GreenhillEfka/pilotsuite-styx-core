"""Push Notification API - PilotSuite v7.12.0

API endpoints for sending push notifications.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

push_notifications_bp = Blueprint("push_notifications", __name__, url_prefix="/api/v1/notifications")


def _get_push_service():
    """Get push notification service instance."""
    try:
        from copilot_core.push_notifications import get_push_notification_service
        return get_push_notification_service()
    except Exception as e:
        logger.error(f"Failed to get push service: {e}")
        return None


@push_notifications_bp.route("/send", methods=["POST"])
@require_token
def send_notification():
    """Send a push notification.
    
    Request body:
    {
        "title": "Title",
        "message": "Message",
        "priority": "normal|high|critical",
        "channel": "all|mobile|telegram|email"
    }
    """
    service = _get_push_service()
    if not service:
        return jsonify({"error": "Push service not available"}), 503
    
    data = request.get_json() or {}
    title = data.get("title")
    message = data.get("message")
    
    if not title or not message:
        return jsonify({"error": title or not message "title and message required"}), 400
    
    priority = data.get("priority", "normal")
    channel = data.get("channel", "all")
    
    try:
        results = service.notify(title, message, priority, channel)
        return jsonify({
            "ok": True,
            "results": results,
        })
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return jsonify({"error": str(e)}), 500


@push_notifications_bp.route("/channels", methods=["GET"])
@require_token
def get_channels():
    """Get list of enabled notification channels."""
    service = _get_push_service()
    if not service:
        return jsonify({"error": "Push service not available"}), 503
    
    channels = service.get_enabled_channels()
    
    return jsonify({
        "ok": True,
        "channels": channels,
    })


@push_notifications_bp.route("/test", methods=["POST"])
@require_token
def test_notification():
    """Send a test notification."""
    service = _get_push_service()
    if not service:
        return jsonify({"error": "Push service not available"}), 503
    
    try:
        results = service.notify(
            title="PilotSuite Test",
            message="Push notifications are working! ✅",
            priority="normal",
            channel="all",
        )
        return jsonify({
            "ok": True,
            "message": "Test notification sent",
            "results": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
