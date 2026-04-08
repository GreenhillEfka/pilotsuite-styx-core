"""Notification System for PilotSuite.

Provides push notifications for:
- Mood changes
- Alert triggers
- Suggestions
- System health warnings

Supports multiple channels:
- HA Notifications (persistent)
- Mobile App notifications
- Telegram (via HA notify service)

Endpoints:
- POST /api/v1/notifications/send - Send notification
- GET /api/v1/notifications - List recent notifications
- POST /api/v1/notifications/subscribe - Register device
- DELETE /api/v1/notifications/<id> - Dismiss notification
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

_LOGGER = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint("notifications", __name__, url_prefix="/notifications")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(Enum):
    """Notification types."""
    MOOD_CHANGE = "mood_change"
    ALERT = "alert"
    SUGGESTION = "suggestion"
    SYSTEM = "system"
    INFO = "info"
    WARNING = "warning"


@dataclass
class Notification:
    """Notification data structure."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    message: str = ""
    priority: str = "normal"
    type: str = "info"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Action data
    action_data: Dict[str, Any] = field(default_factory=dict)
    action_url: str = ""
    
    # Targeting
    target_devices: List[str] = field(default_factory=list)
    target_users: List[str] = field(default_factory=list)
    
    # State
    read: bool = False
    dismissed: bool = False
    sent: bool = False
    
    # Metadata
    source: str = "copilot"
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "type": self.type,
            "timestamp": self.timestamp,
            "action_data": self.action_data,
            "action_url": self.action_url,
            "target_devices": self.target_devices,
            "target_users": self.target_users,
            "read": self.read,
            "dismissed": self.dismissed,
            "sent": self.sent,
            "source": self.source,
            "tags": self.tags,
        }


@dataclass
class DeviceSubscription:
    """Device subscription for push notifications."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    device_name: str = ""
    device_type: str = "mobile"  # mobile, tablet, watch, speaker
    push_token: str = ""
    
    # Preferences
    enabled: bool = True
    notify_mood: bool = True
    notify_alerts: bool = True
    notify_suggestions: bool = True
    notify_system: bool = False
    
    # HA integration
    ha_entity_id: str = ""
    
    # State
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "push_token": self.push_token[:10] + "..." if self.push_token else "",  # Mask token
            "enabled": self.enabled,
            "preferences": {
                "notify_mood": self.notify_mood,
                "notify_alerts": self.notify_alerts,
                "notify_suggestions": self.notify_suggestions,
                "notify_system": self.notify_system,
            },
            "ha_entity_id": self.ha_entity_id,
            "last_seen": self.last_seen,
            "created_at": self.created_at,
        }


class NotificationManager:
    """Manages notifications and device subscriptions."""
    
    # Maximum notifications to keep in history
    MAX_HISTORY = 100
    
    # Maximum subscriptions
    MAX_SUBSCRIPTIONS = 20
    
    def __init__(self):
        self._notifications: List[Notification] = []
        self._subscriptions: Dict[str, DeviceSubscription] = {}
        self._ha_notify_service: Optional[str] = None
    
    def set_ha_notify_service(self, service: str) -> None:
        """Set HA notification service name."""
        self._ha_notify_service = service
    
    def create_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        type: str = "info",
        action_data: Optional[Dict[str, Any]] = None,
        action_url: str = "",
        target_devices: Optional[List[str]] = None,
        target_users: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            title=title,
            message=message,
            priority=priority,
            type=type,
            action_data=action_data or {},
            action_url=action_url,
            target_devices=target_devices or [],
            target_users=target_users or [],
            tags=tags or [],
        )
        
        # Add to history
        self._notifications.insert(0, notification)
        
        # Trim history
        if len(self._notifications) > self.MAX_HISTORY:
            self._notifications = self._notifications[:self.MAX_HISTORY]
        
        return notification
    
    def send_notification(
        self,
        notification: Notification,
        ha_hass=None,
    ) -> bool:
        """Send notification via available channels."""
        try:
            # Mark as sent
            notification.sent = True
            
            _LOGGER.info(
                "Notification sent: [%s] %s - %s",
                notification.priority.upper(),
                notification.title,
                notification.message,
            )

            # Send via webhook pusher if available
            try:
                from flask import current_app
                services = current_app.config.get("COPILOT_SERVICES", {})
                webhook = services.get("webhook_pusher")
                if webhook and webhook.enabled:
                    webhook.push_notification({
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message,
                        "priority": notification.priority,
                        "type": notification.notification_type,
                    })
            except Exception as e:
                _LOGGER.debug("Webhook push failed (non-critical): %s", e)

            # If HA notify service is configured, send via HA
            if self._ha_notify_service and ha_hass:
                try:
                    ha_hass.services.call(
                        "notify",
                        self._ha_notify_service,
                        {
                            "title": notification.title,
                            "message": notification.message,
                            "data": {
                                "priority": notification.priority,
                                "tag": notification.id,
                                **notification.action_data,
                            }
                        },
                        blocking=False,
                    )
                except Exception as e:
                    _LOGGER.warning("Failed to send via HA notify: %s", e)
            
            return True
            
        except Exception as e:
            _LOGGER.error("Error sending notification: %s", e)
            return False
    
    def get_notifications(
        self,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Notification]:
        """Get notifications with optional filters."""
        results = self._notifications
        
        # Filter by read status
        if unread_only:
            results = [n for n in results if not n.read]
        
        # Filter by type
        if notification_type:
            results = [n for n in results if n.type == notification_type]
        
        return results[:limit]
    
    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        for notification in self._notifications:
            if notification.id == notification_id:
                notification.read = True
                return True
        return False
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a notification."""
        for notification in self._notifications:
            if notification.id == notification_id:
                notification.dismissed = True
                return True
        return False
    
    def clear_notifications(self, notification_type: Optional[str] = None) -> int:
        """Clear notifications, optionally by type."""
        if notification_type:
            original_count = len(self._notifications)
            self._notifications = [
                n for n in self._notifications if n.type != notification_type
            ]
            return original_count - len(self._notifications)
        else:
            count = len(self._notifications)
            self._notifications = []
            return count
    
    def subscribe_device(
        self,
        device_id: str,
        device_name: str = "",
        device_type: str = "mobile",
        push_token: str = "",
        ha_entity_id: str = "",
    ) -> DeviceSubscription:
        """Subscribe a device for push notifications."""
        # Check if device already subscribed
        for sub in self._subscriptions.values():
            if sub.device_id == device_id:
                # Update existing
                sub.device_name = device_name or sub.device_name
                sub.push_token = push_token or sub.push_token
                sub.last_seen = datetime.now(timezone.utc).isoformat()
                return sub
        
        # Check max subscriptions
        if len(self._subscriptions) >= self.MAX_SUBSCRIPTIONS:
            # Remove oldest
            oldest = min(self._subscriptions.values(), key=lambda s: s.last_seen)
            del self._subscriptions[oldest.id]
        
        # Create new subscription
        subscription = DeviceSubscription(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            push_token=push_token,
            ha_entity_id=ha_entity_id,
        )
        
        self._subscriptions[subscription.id] = subscription
        return subscription
    
    def unsubscribe_device(self, device_id: str) -> bool:
        """Unsubscribe a device."""
        for sub_id, sub in list(self._subscriptions.items()):
            if sub.device_id == device_id:
                del self._subscriptions[sub_id]
                return True
        return False
    
    def get_subscriptions(self) -> List[DeviceSubscription]:
        """Get all device subscriptions."""
        return list(self._subscriptions.values())
    
    def update_subscription(
        self,
        device_id: str,
        preferences: Optional[Dict[str, bool]] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[DeviceSubscription]:
        """Update subscription preferences."""
        for sub in self._subscriptions.values():
            if sub.device_id == device_id:
                if preferences:
                    if "notify_mood" in preferences:
                        sub.notify_mood = preferences["notify_mood"]
                    if "notify_alerts" in preferences:
                        sub.notify_alerts = preferences["notify_alerts"]
                    if "notify_suggestions" in preferences:
                        sub.notify_suggestions = preferences["notify_suggestions"]
                    if "notify_system" in preferences:
                        sub.notify_system = preferences["notify_system"]
                if enabled is not None:
                    sub.enabled = enabled
                return sub
        return None
    
    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self._notifications if not n.read)
    
    def notify_mood_change(
        self,
        old_mood: str,
        new_mood: str,
        confidence: float,
        ha_hass=None,
    ) -> Optional[Notification]:
        """Create and send mood change notification."""
        mood_icons = {
            "relax": "🧘",
            "focus": "💻",
            "active": "🏃",
            "sleep": "😴",
            "away": "🏠",
            "alert": "⚠️",
            "social": "🎉",
            "recovery": "🌿",
        }
        
        icon = mood_icons.get(new_mood, "🤖")
        
        notification = self.create_notification(
            title=f"{icon} Mood Changed",
            message=f"Stimmung gewechselt von {old_mood} zu {new_mood} ({confidence:.0%})",
            type=NotificationType.MOOD_CHANGE.value,
            priority="low",
            tags=["mood", "mood_change"],
        )
        
        self.send_notification(notification, ha_hass)
        return notification
    
    def notify_alert(
        self,
        alert_title: str,
        alert_message: str,
        severity: str = "normal",
        ha_hass=None,
    ) -> Notification:
        """Create and send alert notification."""
        priority = "high" if severity == "high" else "normal"
        
        notification = self.create_notification(
            title=f"⚠️ {alert_title}",
            message=alert_message,
            type=NotificationType.ALERT.value,
            priority=priority,
            tags=["alert", severity],
        )
        
        self.send_notification(notification, ha_hass)
        return notification


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the singleton notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


# =============================================================================
# API Endpoints
# =============================================================================

@bp.route("/send", methods=["POST"])
def send_notification():
    """Send a notification.
    
    JSON body:
        {
            "title": str,
            "message": str,
            "priority": "low|normal|high|urgent",
            "type": "mood_change|alert|suggestion|system|info|warning",
            "action_data": {...},
            "action_url": str,
            "target_devices": [...],
            "tags": [...]
        }
    
    Returns:
        {"success": true, "data": {"notification_id": str}}
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({
                "success": False,
                "error": "No JSON body provided"
            }), 400
        
        required = ["title", "message"]
        for field in required:
            if field not in body:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        manager = get_notification_manager()
        
        notification = manager.create_notification(
            title=body["title"],
            message=body["message"],
            priority=body.get("priority", "normal"),
            type=body.get("type", "info"),
            action_data=body.get("action_data"),
            action_url=body.get("action_url"),
            target_devices=body.get("target_devices"),
            target_users=body.get("target_users"),
            tags=body.get("tags"),
        )
        
        # Try to send (requires HA hass object in production)
        manager.send_notification(notification)
        
        return jsonify({
            "success": True,
            "data": {
                "notification_id": notification.id,
                "timestamp": notification.timestamp,
            }
        })
    except Exception as e:
        _LOGGER.error("Error sending notification: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("", methods=["GET"])
def get_notifications():
    """Get notifications.
    
    Query params:
        unread_only: Only return unread (default false)
        type: Filter by notification type
        limit: Max results (default 20)
    """
    unread_only = request.args.get("unread_only", "").lower() == "true"
    notification_type = request.args.get("type")
    limit = min(int(request.args.get("limit", "20")), 100)
    
    manager = get_notification_manager()
    notifications = manager.get_notifications(unread_only, notification_type, limit)
    
    return jsonify({
        "success": True,
        "data": {
            "notifications": [n.to_dict() for n in notifications],
            "unread_count": manager.get_unread_count(),
            "total_count": len(manager._notifications),
        }
    })


@bp.route("/<notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id: str):
    """Mark notification as read."""
    manager = get_notification_manager()
    
    if manager.mark_as_read(notification_id):
        return jsonify({
            "success": True,
            "data": {"notification_id": notification_id}
        })
    else:
        return jsonify({
            "success": False,
            "error": "Notification not found"
        }), 404


@bp.route("/<notification_id>", methods=["DELETE"])
def dismiss_notification(notification_id: str):
    """Dismiss a notification."""
    manager = get_notification_manager()
    
    if manager.dismiss_notification(notification_id):
        return jsonify({
            "success": True,
            "data": {"notification_id": notification_id}
        })
    else:
        return jsonify({
            "success": False,
            "error": "Notification not found"
        }), 404


@bp.route("/clear", methods=["POST"])
def clear_notifications():
    """Clear notifications.
    
    JSON body (optional):
        {"type": "alert"}  # Only clear alerts
    
    Returns:
        {"success": true, "data": {"cleared_count": int}}
    """
    body = request.get_json(silent=True) or {}
    notification_type = body.get("type")
    
    manager = get_notification_manager()
    cleared = manager.clear_notifications(notification_type)
    
    return jsonify({
        "success": True,
        "data": {"cleared_count": cleared}
    })


@bp.route("/subscribe", methods=["POST"])
def subscribe_device():
    """Subscribe a device for push notifications.
    
    JSON body:
        {
            "device_id": str,
            "device_name": str,
            "device_type": "mobile|tablet|watch|speaker",
            "push_token": str,
            "ha_entity_id": str,
            "preferences": {
                "notify_mood": bool,
                "notify_alerts": bool,
                "notify_suggestions": bool,
                "notify_system": bool
            }
        }
    """
    try:
        body = request.get_json()
        if not body or "device_id" not in body:
            return jsonify({
                "success": False,
                "error": "device_id is required"
            }), 400
        
        manager = get_notification_manager()
        
        subscription = manager.subscribe_device(
            device_id=body["device_id"],
            device_name=body.get("device_name", ""),
            device_type=body.get("device_type", "mobile"),
            push_token=body.get("push_token", ""),
            ha_entity_id=body.get("ha_entity_id", ""),
        )
        
        # Apply preferences if provided
        if "preferences" in body:
            manager.update_subscription(
                body["device_id"],
                preferences=body["preferences"],
            )
        
        return jsonify({
            "success": True,
            "data": subscription.to_dict()
        })
    except Exception as e:
        _LOGGER.error("Error subscribing device: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/unsubscribe", methods=["POST"])
def unsubscribe_device():
    """Unsubscribe a device.
    
    JSON body:
        {"device_id": str}
    """
    body = request.get_json()
    if not body or "device_id" not in body:
        return jsonify({
            "success": False,
            "error": "device_id is required"
        }), 400
    
    manager = get_notification_manager()
    
    if manager.unsubscribe_device(body["device_id"]):
        return jsonify({
            "success": True,
            "data": {"device_id": body["device_id"]}
        })
    else:
        return jsonify({
            "success": False,
            "error": "Device not found"
        }), 404


@bp.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    """Get all device subscriptions."""
    manager = get_notification_manager()
    subscriptions = manager.get_subscriptions()
    
    return jsonify({
        "success": True,
        "data": {
            "subscriptions": [s.to_dict() for s in subscriptions],
            "count": len(subscriptions),
        }
    })


@bp.route("/subscriptions/<device_id>", methods=["PUT"])
def update_subscription(device_id: str):
    """Update subscription preferences.
    
    JSON body:
        {
            "enabled": bool,
            "preferences": {
                "notify_mood": bool,
                "notify_alerts": bool,
                "notify_suggestions": bool,
                "notify_system": bool
            }
        }
    """
    body = request.get_json()
    if not body:
        return jsonify({
            "success": False,
            "error": "No JSON body provided"
        }), 400
    
    manager = get_notification_manager()
    
    subscription = manager.update_subscription(
        device_id,
        preferences=body.get("preferences"),
        enabled=body.get("enabled"),
    )
    
    if subscription:
        return jsonify({
            "success": True,
            "data": subscription.to_dict()
        })
    else:
        return jsonify({
            "success": False,
            "error": "Device not found"
        }), 404


__all__ = ["bp", "get_notification_manager", "NotificationManager"]
