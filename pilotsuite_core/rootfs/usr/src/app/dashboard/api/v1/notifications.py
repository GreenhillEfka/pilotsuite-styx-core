from __future__ import annotations

from collections import Counter
from copy import deepcopy

from flask import Blueprint, jsonify, request


notifications_bp = Blueprint("notifications_v1", __name__, url_prefix="/api/v1/notifications")

_NOTIFICATIONS = [
    {
        "id": "notif_presence_hold_office",
        "title": "Presence Hold aktiv",
        "message": "Office bleibt bis 08:30 im Hold, obwohl aktuell niemand zuhause gemeldet ist.",
        "priority": "high",
        "type": "alert",
        "timestamp": "2026-04-08T04:40:00+00:00",
        "action_data": {
            "zone": "office",
            "hold_until": "2026-04-08T08:30:00+00:00",
        },
        "action_url": "/presence",
        "target_devices": [],
        "target_users": [],
        "read": False,
        "dismissed": False,
        "sent": True,
        "source": "presence",
        "tags": ["presence", "hold"],
    },
    {
        "id": "notif_widget_layout_reset",
        "title": "Dashboard-Layout angepasst",
        "message": "Widget-Positionen wurden nach dem letzten Reset neu sortiert.",
        "priority": "normal",
        "type": "info",
        "timestamp": "2026-04-08T04:28:00+00:00",
        "action_data": {
            "layout": "family_dashboard",
        },
        "action_url": "/dashboard",
        "target_devices": [],
        "target_users": [],
        "read": True,
        "dismissed": False,
        "sent": True,
        "source": "dashboard_layout",
        "tags": ["dashboard", "layout"],
    },
    {
        "id": "notif_zone_catalog_review",
        "title": "Zone-Katalog prüfen",
        "message": "Habitus-Zonen sind vollständig, aber Outdoor-Tags sollten erneut validiert werden.",
        "priority": "low",
        "type": "suggestion",
        "timestamp": "2026-04-08T04:12:00+00:00",
        "action_data": {
            "zone_type": "outside",
        },
        "action_url": "/zones",
        "target_devices": [],
        "target_users": [],
        "read": False,
        "dismissed": False,
        "sent": True,
        "source": "zone_truth",
        "tags": ["zones", "review"],
    },
]

_PENDING_NOTIFICATIONS = [
    {
        "id": "pending_presence_hold_office_push",
        "notification_id": "notif_presence_hold_office",
        "title": "Presence Hold aktiv",
        "message": "Push-Auslieferung an die Haushaltsgeräte steht noch aus.",
        "priority": "high",
        "type": "alert",
        "source": "presence",
        "queued_at": "2026-04-08T04:41:00+00:00",
        "scheduled_for": "2026-04-08T04:45:00+00:00",
        "channels": ["push", "telegram"],
        "retry_count": 1,
    },
    {
        "id": "pending_zone_catalog_review_digest",
        "notification_id": "notif_zone_catalog_review",
        "title": "Zone-Katalog prüfen",
        "message": "Der nächste Digest-Eintrag für die Zonenprüfung ist noch zur Auslieferung vorgemerkt.",
        "priority": "low",
        "type": "suggestion",
        "source": "zone_truth",
        "queued_at": "2026-04-08T04:18:00+00:00",
        "scheduled_for": "2026-04-08T05:00:00+00:00",
        "channels": ["digest"],
        "retry_count": 0,
    },
]


def _parse_limit(raw_limit: str) -> int:
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        raise ValueError("invalid_limit") from None
    if limit < 1 or limit > 100:
        raise ValueError("invalid_limit")
    return limit


def _notification_digest(notifications: list[dict]) -> dict:
    by_type = Counter(notification["type"] for notification in notifications)
    by_source = Counter(notification["source"] for notification in notifications)
    by_priority = Counter(notification["priority"] for notification in notifications)

    return {
        "period": "last_24h",
        "total": len(notifications),
        "unread": sum(1 for notification in notifications if not notification["read"]),
        "read": sum(1 for notification in notifications if notification["read"]),
        "dismissed": sum(1 for notification in notifications if notification["dismissed"]),
        "sent": sum(1 for notification in notifications if notification["sent"]),
        "by_type": dict(by_type),
        "by_source": dict(by_source),
        "by_priority": dict(by_priority),
        "latest_timestamp": max((notification["timestamp"] for notification in notifications), default=None),
    }


def _notification_stats(notifications: list[dict]) -> dict:
    return {
        "total_notifications": len(notifications),
        "unread_count": sum(1 for notification in notifications if not notification["read"]),
        "by_source": dict(Counter(notification["source"] for notification in notifications)),
        "by_priority": dict(Counter(notification["priority"] for notification in notifications)),
        "by_type": dict(Counter(notification["type"] for notification in notifications)),
    }


@notifications_bp.get("")
def get_notifications():
    unread_only = request.args.get("unread_only", "").strip().lower() == "true"
    notification_type = request.args.get("type", "").strip().lower()
    source = request.args.get("source", "").strip().lower()

    try:
        limit = _parse_limit(request.args.get("limit", "20"))
    except ValueError:
        return (
            jsonify(
                {
                    "error": "invalid_limit",
                    "message": "limit must be an integer between 1 and 100",
                }
            ),
            400,
        )

    notifications = deepcopy(_NOTIFICATIONS)
    if unread_only:
        notifications = [notification for notification in notifications if not notification["read"]]
    if notification_type:
        notifications = [notification for notification in notifications if notification["type"] == notification_type]
    if source:
        notifications = [notification for notification in notifications if notification["source"] == source]

    notifications = notifications[:limit]

    return jsonify(
        {
            "ok": True,
            "count": len(notifications),
            "notifications": notifications,
            "unread_count": sum(1 for notification in _NOTIFICATIONS if not notification["read"]),
            "total_count": len(_NOTIFICATIONS),
        }
    )


@notifications_bp.get("/digest")
def get_notifications_digest():
    return jsonify(
        {
            "ok": True,
            "digest": _notification_digest(deepcopy(_NOTIFICATIONS)),
        }
    )


@notifications_bp.get("/stats")
def get_notifications_stats():
    return jsonify(
        {
            "ok": True,
            **_notification_stats(deepcopy(_NOTIFICATIONS)),
        }
    )


@notifications_bp.get("/pending")
def get_pending_notifications():
    pending = deepcopy(_PENDING_NOTIFICATIONS)
    return jsonify(
        {
            "ok": True,
            "count": len(pending),
            "pending": pending,
        }
    )
