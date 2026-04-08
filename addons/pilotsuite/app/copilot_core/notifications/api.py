"""Notification API endpoints (v5.8.0)."""

from flask import Blueprint, jsonify, request

from ..api.security import require_api_key
from .engine import NotificationEngine, Priority

notifications_bp = Blueprint("notifications", __name__)

_engine: NotificationEngine | None = None


def init_notifications_api(engine: NotificationEngine) -> None:
    """Initialize with engine instance."""
    global _engine
    _engine = engine


@notifications_bp.route("/api/v1/notifications", methods=["GET"])
@require_api_key
def get_notifications():
    """Get notification history.

    Query params:
        limit: Max items (default 50)
        source: Filter by source module
    """
    if not _engine:
        return jsonify({"error": "Notification engine not initialized"}), 503

    limit = request.args.get("limit", 50, type=int)
    source = request.args.get("source")

    items = _engine.get_history(limit=limit, source=source)
    return jsonify({"ok": True, "count": len(items), "notifications": items})


@notifications_bp.route("/api/v1/notifications", methods=["POST"])
@require_api_key
def create_notification():
    """Submit a notification.

    Body: {"source", "title", "message", "priority"(1-4), "channel", "data"}
    """
    if not _engine:
        return jsonify({"error": "Notification engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    source = body.get("source", "api")
    title = body.get("title")
    message = body.get("message")

    if not title or not message:
        return jsonify({"ok": False, "error": "title and message required"}), 400

    priority = body.get("priority", 3)
    channel = body.get("channel", "default")
    data = body.get("data", {})

    notif = _engine.notify(
        source=source,
        title=title,
        message=message,
        priority=priority,
        channel=channel,
        data=data,
    )

    if notif is None:
        return jsonify({"ok": True, "status": "deduplicated_or_rate_limited"})

    return jsonify({
        "ok": True,
        "id": notif.id,
        "priority": notif.priority.name,
        "channel": notif.channel,
    }), 201


@notifications_bp.route("/api/v1/notifications/digest", methods=["GET"])
@require_api_key
def get_digest():
    """Get notification digest.

    Query params:
        hours: Look-back period (default 24)
    """
    if not _engine:
        return jsonify({"error": "Notification engine not initialized"}), 503

    hours = request.args.get("hours", 24.0, type=float)
    digest = _engine.get_digest(hours=hours)

    return jsonify({
        "ok": True,
        "period_start": digest.period_start,
        "period_end": digest.period_end,
        "count": digest.count,
        "by_source": digest.by_source,
        "by_priority": digest.by_priority,
        "items": digest.items,
    })


@notifications_bp.route("/api/v1/notifications/pending", methods=["GET"])
@require_api_key
def get_pending():
    """Flush and return pending notifications for delivery."""
    if not _engine:
        return jsonify({"error": "Notification engine not initialized"}), 503

    pending = _engine.flush_pending()
    return jsonify({
        "ok": True,
        "count": len(pending),
        "notifications": [
            {
                "id": n.id,
                "source": n.source,
                "title": n.title,
                "message": n.message,
                "priority": n.priority.name if isinstance(n.priority, Priority) else str(n.priority),
                "channel": n.channel,
                "data": n.data,
            }
            for n in pending
        ],
    })


@notifications_bp.route("/api/v1/notifications/stats", methods=["GET"])
@require_api_key
def get_stats():
    """Get notification engine statistics."""
    if not _engine:
        return jsonify({"error": "Notification engine not initialized"}), 503

    return jsonify({"ok": True, **_engine.get_stats()})
