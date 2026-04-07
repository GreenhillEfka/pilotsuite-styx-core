"""
Notification Delivery API — Slice 68.

REST API for unified notification delivery with channel routing,
rate limiting, and delivery tracking.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from typing import Optional

from .delivery_contracts import (
    DeliveryMode,
    DeliveryStatus,
    NotificationChannel,
    NotificationPriority,
    NotificationType,
    NotificationV1,
)
from .delivery_engine import DeliveryEngine
from .delivery_store import get_notification_delivery_store


def create_delivery_blueprint(delivery_engine: DeliveryEngine):
    """Create Flask blueprint for notification delivery API."""
    bp = Blueprint("notification_delivery", __name__, url_prefix="/api/v1/notifications")
    
    @bp.route("/send", methods=["POST"])
    def send_notification():
        """
        Send a notification.
        
        Body:
        - type: notification type (alert, info, reminder, digest, action_required, system)
        - priority: low, normal, high, critical
        - channel: telegram, whatsapp, email, push, ha_notification, sms, slack, webhook
        - recipient_id: recipient identifier
        - user_id: user ID for preferences lookup
        - zone_id: optional zone ID
        - title: notification title
        - body: notification body
        - data: optional data dict
        - action_url: optional action URL
        - action_data: optional action data dict
        - scheduled_at: optional ISO-8601 timestamp
        - ttl_seconds: optional TTL
        - idempotency_key: optional idempotency key
        """
        import asyncio
        data = request.get_json() or {}
        
        # Validate required fields
        required = ["type", "priority", "channel", "recipient_id", "user_id", "title", "body"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Create notification
        notification = NotificationV1(
            notification_id=f"notif_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            type=NotificationType(data["type"]),
            priority=NotificationPriority(data["priority"]),
            channel=NotificationChannel(data["channel"]),
            recipient_id=data["recipient_id"],
            user_id=data["user_id"],
            zone_id=data.get("zone_id"),
            title=data["title"],
            body=data["body"],
            data=data.get("data", {}),
            action_url=data.get("action_url"),
            action_data=data.get("action_data", {}),
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            ttl_seconds=data.get("ttl_seconds"),
            idempotency_key=data.get("idempotency_key"),
        )
        
        # Save notification
        store = get_notification_delivery_store()
        store.save_notification(notification)
        
        # Deliver
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            delivery = loop.run_until_complete(delivery_engine.deliver(notification))
        finally:
            loop.close()
        
        return jsonify(delivery.to_dict()), 201 if delivery.status == DeliveryStatus.SENT else 202
    
    @bp.route("/deliveries", methods=["GET"])
    def list_deliveries():
        """
        List deliveries with filters.
        
        Query params:
        - user_id: filter by user
        - status: filter by status
        - channel: filter by channel
        - limit: max results (default 100)
        - offset: offset for pagination
        - since_revision: for delta polling
        """
        store = get_notification_delivery_store()
        
        user_id = request.args.get("user_id")
        status = request.args.get("status")
        channel = request.args.get("channel")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        since_revision = request.args.get("since_revision", type=int)
        
        if since_revision:
            # Delta response
            delta = store.get_delta(since_revision)
            return jsonify({
                "delta": delta.to_dict(),
            })
        
        if user_id:
            deliveries = store.get_deliveries_by_user(user_id, limit, offset)
        elif status:
            deliveries = store.get_deliveries_by_status(DeliveryStatus(status), limit)
        else:
            deliveries = store.get_pending_deliveries(limit)
        
        return jsonify({
            "deliveries": [d.to_dict() for d in deliveries],
            "total": len(deliveries),
            "revision": store._revision,
        })
    
    @bp.route("/deliveries/<delivery_id>", methods=["GET"])
    def get_delivery(delivery_id):
        """Get delivery by ID."""
        store = get_notification_delivery_store()
        delivery = store.get_delivery(delivery_id)
        
        if not delivery:
            return jsonify({"error": "Delivery not found"}), 404
        
        return jsonify(delivery.to_dict())
    
    @bp.route("/deliveries/<delivery_id>/delivered", methods=["PUT"])
    def mark_delivered(delivery_id):
        """Mark delivery as delivered."""
        store = get_notification_delivery_store()
        success = store.mark_delivered(delivery_id)
        
        if not success:
            return jsonify({"error": "Delivery not found"}), 404
        
        return jsonify({"status": "delivered", "delivery_id": delivery_id})
    
    @bp.route("/deliveries/<delivery_id>/read", methods=["PUT"])
    def mark_read(delivery_id):
        """Mark delivery as read."""
        store = get_notification_delivery_store()
        success = store.mark_read(delivery_id)
        
        if not success:
            return jsonify({"error": "Delivery not found"}), 404
        
        return jsonify({"status": "read", "delivery_id": delivery_id})
    
    @bp.route("/deliveries/<delivery_id>/acknowledged", methods=["PUT"])
    def mark_acknowledged(delivery_id):
        """Mark delivery as acknowledged."""
        store = get_notification_delivery_store()
        success = store.mark_acknowledged(delivery_id)
        
        if not success:
            return jsonify({"error": "Delivery not found"}), 404
        
        return jsonify({"status": "acknowledged", "delivery_id": delivery_id})
    
    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Get delivery summary."""
        store = get_notification_delivery_store()
        since_revision = request.args.get("since_revision", type=int)
        
        summary = store.get_summary(since_revision)
        
        return jsonify({
            "summary": summary.to_dict(),
        })
    
    @bp.route("/rate-limit", methods=["GET"])
    def get_rate_limit():
        """Get rate limit state for user/channel."""
        user_id = request.args.get("user_id")
        channel = request.args.get("channel")
        
        if not user_id or not channel:
            return jsonify({"error": "user_id and channel required"}), 400
        
        state = delivery_engine.get_rate_limit_state(user_id, NotificationChannel(channel))
        
        if not state:
            return jsonify({"rate_limit": None})
        
        return jsonify({
            "rate_limit": state.to_dict(),
        })
    
    @bp.route("/quiet-hours", methods=["GET"])
    def get_quiet_hours():
        """Get quiet hours state for user."""
        user_id = request.args.get("user_id")
        
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        
        state = delivery_engine.get_quiet_hours_state(user_id)
        
        return jsonify({
            "quiet_hours": state.to_dict(),
        })
    
    return bp
