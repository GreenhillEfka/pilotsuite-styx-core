from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import uuid

from flask import Blueprint, jsonify, request


notifications_bp = Blueprint("notifications_v1", __name__, url_prefix="/api/v1/notifications")

_DEFAULT_NOTIFICATIONS = [
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

_NOTIFICATIONS = deepcopy(_DEFAULT_NOTIFICATIONS)

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

_DEFAULT_SUBSCRIPTIONS = [
    {
        "id": "sub_mobile_andreas",
        "device_id": "mobile_andreas_iphone",
        "device_name": "Andreas iPhone",
        "device_type": "mobile",
        "push_token": "expo_andre...",
        "enabled": True,
        "preferences": {
            "notify_mood": True,
            "notify_alerts": True,
            "notify_suggestions": True,
            "notify_system": False,
        },
        "ha_entity_id": "notify.mobile_app_andreas_iphone",
        "last_seen": "2026-04-08T04:44:00+00:00",
        "created_at": "2026-04-08T03:10:00+00:00",
    },
    {
        "id": "sub_wallpanel_kitchen",
        "device_id": "wallpanel_kitchen",
        "device_name": "Kitchen Wall Panel",
        "device_type": "tablet",
        "push_token": "expo_kitch...",
        "enabled": True,
        "preferences": {
            "notify_mood": False,
            "notify_alerts": True,
            "notify_suggestions": True,
            "notify_system": False,
        },
        "ha_entity_id": "notify.kitchen_wallpanel",
        "last_seen": "2026-04-08T04:39:00+00:00",
        "created_at": "2026-04-08T02:55:00+00:00",
    },
    {
        "id": "sub_voice_hub_livingroom",
        "device_id": "voice_hub_livingroom",
        "device_name": "Living Room Voice Hub",
        "device_type": "speaker",
        "push_token": "local_voice...",
        "enabled": False,
        "preferences": {
            "notify_mood": False,
            "notify_alerts": True,
            "notify_suggestions": False,
            "notify_system": True,
        },
        "ha_entity_id": "notify.living_room_voice_hub",
        "last_seen": "2026-04-08T03:58:00+00:00",
        "created_at": "2026-04-08T01:40:00+00:00",
    },
]

_SUBSCRIPTION_PREFERENCE_KEYS = frozenset(
    {
        "notify_mood",
        "notify_alerts",
        "notify_suggestions",
        "notify_system",
    }
)

_SUBSCRIPTION_DEVICE_TYPES = frozenset({"mobile", "tablet", "watch", "speaker"})
_NOTIFICATION_PRIORITY_VALUES = frozenset({"low", "normal", "high", "urgent"})
_NOTIFICATION_TYPE_VALUES = frozenset({"mood_change", "alert", "suggestion", "system", "info", "warning"})
_LEGACY_INTEGER_NOTIFICATION_PRIORITY_MAP = {
    1: "urgent",
    2: "high",
    3: "normal",
    4: "low",
}
_NOTIFICATION_CREATE_ERROR_MESSAGES = {
    "invalid_action_data": "action_data or legacy data must be a JSON object",
    "invalid_channel": "channel must be a non-empty string when provided",
    "invalid_source": "source must be a non-empty string when provided",
}

_SUBSCRIPTIONS = deepcopy(_DEFAULT_SUBSCRIPTIONS)


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


def _get_notification(notification_id: str) -> dict | None:
    return next((notification for notification in _NOTIFICATIONS if notification["id"] == notification_id), None)


def _get_subscription(device_id: str) -> dict | None:
    return next((subscription for subscription in _SUBSCRIPTIONS if subscription["device_id"] == device_id), None)


def _pop_subscription(device_id: str) -> dict | None:
    for index, subscription in enumerate(_SUBSCRIPTIONS):
        if subscription["device_id"] == device_id:
            return _SUBSCRIPTIONS.pop(index)
    return None


def _validated_subscription_preferences(preferences: object) -> dict:
    if not isinstance(preferences, dict):
        raise ValueError("invalid_preferences")

    invalid_keys = sorted(set(preferences) - _SUBSCRIPTION_PREFERENCE_KEYS)
    if invalid_keys:
        raise ValueError("invalid_preferences")

    if any(not isinstance(value, bool) for value in preferences.values()):
        raise ValueError("invalid_preferences")

    return preferences


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _masked_push_token(push_token: str) -> str:
    normalized_push_token = push_token.strip()
    if not normalized_push_token:
        return ""
    return f"{normalized_push_token[:10]}..."


def _validated_string_list(raw_value: object, *, error_code: str) -> list[str]:
    if raw_value is None:
        return []

    if not isinstance(raw_value, list):
        raise ValueError(error_code)

    normalized_values = []
    for value in raw_value:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(error_code)
        normalized_values.append(value.strip())

    return normalized_values


def _validated_notification_action_data(body: dict) -> dict:
    action_data = body.get("action_data")
    if action_data is None and "data" in body:
        action_data = body.get("data")
    if action_data is None:
        action_data = {}
    if not isinstance(action_data, dict):
        raise ValueError("invalid_action_data")
    return action_data


def _validated_notification_channel_alias(body: dict) -> str | None:
    if "channel" not in body or body.get("channel") is None:
        return None

    channel = body.get("channel")
    if not isinstance(channel, str) or not channel.strip():
        raise ValueError("invalid_channel")

    return channel.strip()


def _validated_notification_source_alias(body: dict) -> str:
    if "source" not in body or body.get("source") is None:
        return "api"

    source = body.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("invalid_source")

    return source.strip().lower()


def _validated_notification_priority(raw_priority: object) -> str:
    if isinstance(raw_priority, int) and not isinstance(raw_priority, bool):
        return _LEGACY_INTEGER_NOTIFICATION_PRIORITY_MAP.get(raw_priority, "normal")

    if not isinstance(raw_priority, str) or raw_priority.strip() not in _NOTIFICATION_PRIORITY_VALUES:
        raise ValueError("invalid_priority")

    return raw_priority.strip()


def _validated_notification_legacy_hints(body: dict) -> tuple[dict, str]:
    action_data = _validated_notification_action_data(body)
    _validated_notification_channel_alias(body)
    source = _validated_notification_source_alias(body)
    return action_data, source


def _create_notification_from_request():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return (
            jsonify(
                {
                    "error": "invalid_body",
                    "message": "JSON object body required",
                }
            ),
            400,
        )

    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return (
            jsonify(
                {
                    "error": "invalid_title",
                    "message": "title must be a non-empty string",
                }
            ),
            400,
        )

    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return (
            jsonify(
                {
                    "error": "invalid_message",
                    "message": "message must be a non-empty string",
                }
            ),
            400,
        )

    try:
        priority = _validated_notification_priority(body.get("priority", "normal"))
    except ValueError:
        return (
            jsonify(
                {
                    "error": "invalid_priority",
                    "message": "priority must be one of low, normal, high or urgent",
                }
            ),
            400,
        )

    notification_type = body.get("type", "info")
    if not isinstance(notification_type, str) or notification_type.strip() not in _NOTIFICATION_TYPE_VALUES:
        return (
            jsonify(
                {
                    "error": "invalid_type",
                    "message": "type must be one of mood_change, alert, suggestion, system, info or warning",
                }
            ),
            400,
        )

    try:
        action_data, source = _validated_notification_legacy_hints(body)
    except ValueError as error:
        error_code = str(error)
        return (
            jsonify(
                {
                    "error": error_code,
                    "message": _NOTIFICATION_CREATE_ERROR_MESSAGES[error_code],
                }
            ),
            400,
        )

    action_url = body.get("action_url", "")
    if not isinstance(action_url, str):
        return (
            jsonify(
                {
                    "error": "invalid_action_url",
                    "message": "action_url must be a string",
                }
            ),
            400,
        )

    try:
        target_devices = _validated_string_list(body.get("target_devices"), error_code="invalid_target_devices")
        target_users = _validated_string_list(body.get("target_users"), error_code="invalid_target_users")
        tags = _validated_string_list(body.get("tags"), error_code="invalid_tags")
    except ValueError as error:
        error_code = str(error)
        error_messages = {
            "invalid_target_devices": "target_devices must be an array of non-empty strings",
            "invalid_target_users": "target_users must be an array of non-empty strings",
            "invalid_tags": "tags must be an array of non-empty strings",
        }
        return (
            jsonify(
                {
                    "error": error_code,
                    "message": error_messages[error_code],
                }
            ),
            400,
        )

    notification = {
        "id": f"notif_api_{uuid.uuid4().hex[:12]}",
        "title": title.strip(),
        "message": message.strip(),
        "priority": priority.strip(),
        "type": notification_type.strip(),
        "timestamp": _utcnow_iso(),
        "action_data": deepcopy(action_data),
        "action_url": action_url.strip(),
        "target_devices": target_devices,
        "target_users": target_users,
        "read": False,
        "dismissed": False,
        "sent": True,
        "source": source,
        "tags": tags,
    }
    _NOTIFICATIONS.insert(0, notification)

    return jsonify(
        {
            "ok": True,
            "notification": deepcopy(notification),
        }
    )


@notifications_bp.post("")
def create_notification():
    return _create_notification_from_request()


@notifications_bp.post("/send")
def send_notification():
    return _create_notification_from_request()


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


@notifications_bp.post("/<notification_id>/read")
def mark_notification_read(notification_id: str):
    notification = _get_notification(notification_id)
    if notification is None:
        return (
            jsonify(
                {
                    "error": "notification_not_found",
                    "message": f"notification '{notification_id}' not found",
                }
            ),
            404,
        )

    notification["read"] = True

    return jsonify(
        {
            "ok": True,
            "notification": deepcopy(notification),
        }
    )


@notifications_bp.delete("/<notification_id>")
def dismiss_notification(notification_id: str):
    notification = _get_notification(notification_id)
    if notification is None:
        return (
            jsonify(
                {
                    "error": "notification_not_found",
                    "message": f"notification '{notification_id}' not found",
                }
            ),
            404,
        )

    notification["dismissed"] = True

    return jsonify(
        {
            "ok": True,
            "notification": deepcopy(notification),
        }
    )


@notifications_bp.post("/subscribe")
def subscribe_notification_device():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return (
            jsonify(
                {
                    "error": "invalid_body",
                    "message": "JSON object body required",
                }
            ),
            400,
        )

    device_id = body.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return (
            jsonify(
                {
                    "error": "invalid_device_id",
                    "message": "device_id must be a non-empty string",
                }
            ),
            400,
        )

    device_name = body.get("device_name", "")
    if not isinstance(device_name, str):
        return (
            jsonify(
                {
                    "error": "invalid_device_name",
                    "message": "device_name must be a string",
                }
            ),
            400,
        )

    device_type = body.get("device_type", "mobile")
    if not isinstance(device_type, str) or device_type.strip() not in _SUBSCRIPTION_DEVICE_TYPES:
        return (
            jsonify(
                {
                    "error": "invalid_device_type",
                    "message": "device_type must be one of mobile, tablet, watch or speaker",
                }
            ),
            400,
        )

    push_token = body.get("push_token", "")
    if not isinstance(push_token, str):
        return (
            jsonify(
                {
                    "error": "invalid_push_token",
                    "message": "push_token must be a string",
                }
            ),
            400,
        )

    ha_entity_id = body.get("ha_entity_id", "")
    if not isinstance(ha_entity_id, str):
        return (
            jsonify(
                {
                    "error": "invalid_ha_entity_id",
                    "message": "ha_entity_id must be a string",
                }
            ),
            400,
        )

    try:
        preferences = (
            _validated_subscription_preferences(body["preferences"])
            if "preferences" in body
            else None
        )
    except ValueError:
        return (
            jsonify(
                {
                    "error": "invalid_preferences",
                    "message": "preferences must be a JSON object with known boolean flags",
                }
            ),
            400,
        )

    normalized_device_id = device_id.strip()
    normalized_device_type = device_type.strip()
    subscription = _get_subscription(normalized_device_id)
    created = subscription is None

    if created:
        timestamp = _utcnow_iso()
        subscription = {
            "id": f"sub_{normalized_device_id}",
            "device_id": normalized_device_id,
            "device_name": device_name.strip(),
            "device_type": normalized_device_type,
            "push_token": _masked_push_token(push_token),
            "enabled": True,
            "preferences": {
                "notify_mood": True,
                "notify_alerts": True,
                "notify_suggestions": True,
                "notify_system": False,
            },
            "ha_entity_id": ha_entity_id.strip(),
            "last_seen": timestamp,
            "created_at": timestamp,
        }
        if preferences is not None:
            subscription["preferences"].update(preferences)
        _SUBSCRIPTIONS.append(subscription)
    else:
        subscription["enabled"] = True
        subscription["last_seen"] = _utcnow_iso()
        if device_name.strip():
            subscription["device_name"] = device_name.strip()
        subscription["device_type"] = normalized_device_type
        if push_token.strip():
            subscription["push_token"] = _masked_push_token(push_token)
        if "ha_entity_id" in body:
            subscription["ha_entity_id"] = ha_entity_id.strip()
        if preferences is not None:
            subscription["preferences"].update(preferences)

    return jsonify(
        {
            "ok": True,
            "created": created,
            "subscription": deepcopy(subscription),
        }
    )


@notifications_bp.get("/subscriptions")
def get_notification_subscriptions():
    subscriptions = deepcopy(_SUBSCRIPTIONS)
    return jsonify(
        {
            "ok": True,
            "count": len(subscriptions),
            "enabled_count": sum(1 for subscription in subscriptions if subscription["enabled"]),
            "subscriptions": subscriptions,
        }
    )


@notifications_bp.put("/subscriptions/<device_id>")
def update_notification_subscription(device_id: str):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return (
            jsonify(
                {
                    "error": "invalid_body",
                    "message": "JSON object body required",
                }
            ),
            400,
        )

    if "enabled" not in body and "preferences" not in body:
        return (
            jsonify(
                {
                    "error": "empty_update",
                    "message": "enabled and/or preferences must be provided",
                }
            ),
            400,
        )

    if "enabled" in body and not isinstance(body["enabled"], bool):
        return (
            jsonify(
                {
                    "error": "invalid_enabled",
                    "message": "enabled must be a boolean",
                }
            ),
            400,
        )

    try:
        preferences = (
            _validated_subscription_preferences(body["preferences"])
            if "preferences" in body
            else None
        )
    except ValueError:
        return (
            jsonify(
                {
                    "error": "invalid_preferences",
                    "message": "preferences must be a JSON object with known boolean flags",
                }
            ),
            400,
        )

    if "enabled" not in body and preferences == {}:
        return (
            jsonify(
                {
                    "error": "empty_update",
                    "message": "enabled and/or non-empty preferences must be provided",
                }
            ),
            400,
        )

    subscription = _get_subscription(device_id)
    if subscription is None:
        return (
            jsonify(
                {
                    "error": "device_not_found",
                    "message": f"subscription for device '{device_id}' not found",
                }
            ),
            404,
        )

    if "enabled" in body:
        subscription["enabled"] = body["enabled"]
    if preferences is not None:
        subscription["preferences"].update(preferences)

    return jsonify(
        {
            "ok": True,
            "subscription": deepcopy(subscription),
        }
    )


@notifications_bp.post("/unsubscribe")
def unsubscribe_notification_device():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return (
            jsonify(
                {
                    "error": "invalid_body",
                    "message": "JSON object body required",
                }
            ),
            400,
        )

    device_id = body.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return (
            jsonify(
                {
                    "error": "invalid_device_id",
                    "message": "device_id must be a non-empty string",
                }
            ),
            400,
        )

    normalized_device_id = device_id.strip()
    removed_subscription = _pop_subscription(normalized_device_id)
    if removed_subscription is None:
        return (
            jsonify(
                {
                    "error": "device_not_found",
                    "message": f"subscription for device '{normalized_device_id}' not found",
                }
            ),
            404,
        )

    return jsonify(
        {
            "ok": True,
            "unsubscribed": deepcopy(removed_subscription),
        }
    )
