"""
Webhooks API - PilotSuite v7.19.0

API for managing webhooks.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/v1/webhooks")


# In-memory webhook registry (in production, use persistent storage)
_webhook_registry = {}


@webhooks_bp.route("", methods=["GET"])
@require_token
def list_webhooks():
    """List all registered webhooks."""
    return jsonify({
        "ok": True,
        "webhooks": list(_webhook_registry.values()),
        "count": len(_webhook_registry),
    })


@webhooks_bp.route("/register", methods=["POST"])
@require_token
def register_webhook():
    """Register a new webhook."""
    data = request.get_json() or {}
    webhook_id = data.get("webhook_id")
    url = data.get("url")
    events = data.get("events", ["all"])
    
    if not webhook_id or not url:
        return jsonify({"error": "webhook_id and url required"}), 400
    
    _webhook_registry[webhook_id] = {
        "webhook_id": webhook_id,
        "url": url,
        "events": events,
        "enabled": True,
    }
    
    return jsonify({
        "ok": True,
        "webhook_id": webhook_id,
        "message": "Webhook registered",
    })


@webhooks_bp.route("/<webhook_id>/trigger", methods=["POST"])
@require_token
def trigger_webhook(webhook_id):
    """Trigger a webhook manually."""
    if webhook_id not in _webhook_registry:
        return jsonify({"error": "Webhook not found"}), 404
    
    webhook = _webhook_registry[webhook_id]
    data = request.get_json() or {}
    
    try:
        import requests
        resp = requests.post(webhook["url"], json=data, timeout=10)
        return jsonify({
            "ok": True,
            "webhook_id": webhook_id,
            "response_status": resp.status_code,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@webhooks_bp.route("/<webhook_id>/delete", methods=["POST"])
@require_token
def delete_webhook(webhook_id):
    """Delete a webhook."""
    if webhook_id not in _webhook_registry:
        return jsonify({"error": "Webhook not found"}), 404
    
    del _webhook_registry[webhook_id]
    
    return jsonify({
        "ok": True,
        "message": "Webhook deleted",
    })
