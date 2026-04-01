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

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from flask import Blueprint, Request, jsonify, request

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from copilot_core.action_closure import get_action_closure_store
from copilot_core.core.action_closure_read_model import build_action_closure_summary_read_model

_LOGGER = logging.getLogger(__name__)

_ACTION_CLOSURE_FAILURE_STATES = {"failed", "error", "blocked", "denied", "rejected", "cancelled"}
_ACTION_CLOSURE_OPEN_STATES = {"accepted", "feedback_received", "queued", "pending", "scheduled", "awaiting_execution"}

# Create blueprint
bp = Blueprint("notifications", __name__, url_prefix="/notifications")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth() -> Optional[tuple[dict[str, str], int]]:
    """Validate authentication token for all notification endpoints."""
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401
    return None


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
    
    def to_dict(self) -> dict[str, Any]:
        """Convert notification to dictionary representation.
        
        Returns:
            dict[str, Any]: Dictionary containing all notification fields.
        """
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
    
    def to_dict(self) -> dict[str, Any]:
        """Convert device subscription to dictionary representation.
        
        Returns:
            dict[str, Any]: Dictionary containing subscription details (with masked push_token).
        """
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
    
    def __init__(self) -> None:
        """Initialize the notification manager."""
        self._notifications: list[Notification] = []
        self._subscriptions: dict[str, DeviceSubscription] = {}
        self._ha_notify_service: str | None = None
    
    def set_ha_notify_service(self, service: str) -> None:
        """Set HA notification service name.
        
        Args:
            service: Name of the HA notify service (e.g., 'mobile_app').
        """
        self._ha_notify_service = service
    
    def create_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        type: str = "info",
        action_data: dict[str, Any] | None = None,
        action_url: str = "",
        target_devices: list[str] | None = None,
        target_users: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> Notification:
        """Create a new notification.
        
        Args:
            title: Notification title.
            message: Notification message body.
            priority: Priority level (low, normal, high, urgent).
            type: Notification type (mood_change, alert, suggestion, system, info, warning).
            action_data: Optional action data dictionary.
            action_url: Optional action URL.
            target_devices: Optional list of target device IDs.
            target_users: Optional list of target user IDs.
            tags: Optional list of tags for categorization.
        
        Returns:
            Notification: The created notification object.
        """
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
        ha_hass: HomeAssistant | None = None,
    ) -> bool:
        """Send notification via available channels.
        
        Args:
            notification: The notification to send.
            ha_hass: Optional Home Assistant instance for HA notify service.
        
        Returns:
            bool: True if notification was sent successfully, False otherwise.
        """
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
                services: Dict[str, Any] = current_app.config.get("COPILOT_SERVICES", {})
                webhook: Optional[Any] = services.get("webhook_pusher")
                if webhook and webhook.enabled:
                    webhook.push_notification({
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message,
                        "priority": notification.priority,
                        "type": notification.type,
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
        notification_type: str | None = None,
        limit: int = 20,
    ) -> list[Notification]:
        """Get notifications with optional filters.
        
        Args:
            unread_only: If True, only return unread notifications.
            notification_type: Optional filter by notification type.
            limit: Maximum number of notifications to return.
        
        Returns:
            List[Notification]: List of notifications matching the filters.
        """
        results = self._notifications
        
        # Filter by read status
        if unread_only:
            results = [n for n in results if not n.read]
        
        # Filter by type
        if notification_type:
            results = [n for n in results if n.type == notification_type]
        
        return results[:limit]
    
    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read.
        
        Args:
            notification_id: ID of the notification to mark as read.
        
        Returns:
            bool: True if notification was found and marked, False otherwise.
        """
        for notification in self._notifications:
            if notification.id == notification_id:
                notification.read = True
                return True
        return False
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a notification.
        
        Args:
            notification_id: ID of the notification to dismiss.
        
        Returns:
            bool: True if notification was found and dismissed, False otherwise.
        """
        for notification in self._notifications:
            if notification.id == notification_id:
                notification.dismissed = True
                return True
        return False
    
    def clear_notifications(self, notification_type: Optional[str] = None) -> int:
        """Clear notifications, optionally by type.
        
        Args:
            notification_type: Optional type filter (clears all if None).
        
        Returns:
            int: Number of notifications cleared.
        """
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
        preferences: dict[str, bool] | None = None,
    ) -> DeviceSubscription:
        """Subscribe a device for push notifications.
        
        Args:
            device_id: Unique device identifier.
            device_name: Human-readable device name.
            device_type: Device type (mobile, tablet, watch, speaker).
            push_token: Push notification token.
            ha_entity_id: Home Assistant entity ID for the device.
            preferences: Optional dictionary of notification preferences.
        
        Returns:
            DeviceSubscription: The created or updated subscription.
        """
        # Check if device already subscribed
        for sub in self._subscriptions.values():
            if sub.device_id == device_id:
                # Update existing
                sub.device_name = device_name or sub.device_name
                sub.push_token = push_token or sub.push_token
                sub.last_seen = datetime.now(timezone.utc).isoformat()
                if preferences:
                    sub.notify_mood = preferences.get('notify_mood', sub.notify_mood)
                    sub.notify_alerts = preferences.get('notify_alerts', sub.notify_alerts)
                    sub.notify_suggestions = preferences.get('notify_suggestions', sub.notify_suggestions)
                    sub.notify_system = preferences.get('notify_system', sub.notify_system)
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
        
        if preferences:
            subscription.notify_mood = preferences.get('notify_mood', True)
            subscription.notify_alerts = preferences.get('notify_alerts', True)
            subscription.notify_suggestions = preferences.get('notify_suggestions', True)
            subscription.notify_system = preferences.get('notify_system', True)
        
        self._subscriptions[subscription.id] = subscription
        return subscription
    
    def unsubscribe_device(self, device_id: str) -> bool:
        """Unsubscribe a device.
        
        Args:
            device_id: ID of the device to unsubscribe.
        
        Returns:
            bool: True if device was found and unsubscribed, False otherwise.
        """
        for sub_id, sub in list(self._subscriptions.items()):
            if sub.device_id == device_id:
                del self._subscriptions[sub_id]
                return True
        return False
    
    def get_subscriptions(self) -> list[DeviceSubscription]:
        """Get all device subscriptions.
        
        Returns:
            list[DeviceSubscription]: List of all device subscriptions.
        """
        return list(self._subscriptions.values())
    
    def update_subscription(
        self,
        device_id: str,
        preferences: dict[str, bool] | None = None,
        enabled: bool | None = None,
    ) -> DeviceSubscription | None:
        """Update subscription preferences.
        
        Args:
            device_id: ID of the device subscription to update.
            preferences: Optional dictionary of preference updates.
            enabled: Optional enabled/disabled flag.
        
        Returns:
            Optional[DeviceSubscription]: Updated subscription or None if not found.
        """
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
        """Get count of unread notifications.
        
        Returns:
            int: Number of unread notifications.
        """
        return sum(1 for n in self._notifications if not n.read)
    
    def notify_mood_change(
        self,
        old_mood: str,
        new_mood: str,
        confidence: float,
        ha_hass: HomeAssistant | None = None,
    ) -> Notification | None:
        """Create and send mood change notification.
        
        Args:
            old_mood: Previous mood value.
            new_mood: New mood value.
            confidence: Confidence score (0.0 to 1.0).
            ha_hass: Optional Home Assistant instance.
        
        Returns:
            Optional[Notification]: Created notification or None if failed.
        """
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
        ha_hass: HomeAssistant | None = None,
    ) -> Notification:
        """Create and send alert notification.
        
        Args:
            alert_title: Alert title.
            alert_message: Alert message body.
            severity: Alert severity (normal, high).
            ha_hass: Optional Home Assistant instance.
        
        Returns:
            Notification: Created notification object.
        """
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


@dataclass
class ActionClosureDispatchCandidate:
    """Worker-facing dispatch candidate for closure follow-ups."""

    dispatch_id: str
    dedupe_key: str
    delivery_mode: str
    closure_id: str
    closure_revision: int
    zone_id: str | None = None
    module_id: str | None = None
    action_id: str | None = None
    state: str | None = None
    kind: str = "open"
    priority: str = "normal"
    title: str = ""
    message: str = ""
    updated_at: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    ack_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureFollowUpDispatchCandidateV1",
            "dispatch_id": self.dispatch_id,
            "dedupe_key": self.dedupe_key,
            "delivery_mode": self.delivery_mode,
            "closure_id": self.closure_id,
            "closure_revision": self.closure_revision,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "action_id": self.action_id,
            "state": self.state,
            "kind": self.kind,
            "priority": self.priority,
            "title": self.title,
            "message": self.message,
            "updated_at": self.updated_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "ack_note": self.ack_note,
            "delivery": {
                "mode": self.delivery_mode,
                "queue": "notifications" if self.delivery_mode == "notification_job" else "reminders",
                "topic": "action_closure_follow_up" if self.delivery_mode == "notification_job" else "action_closure_reminder",
            },
        }


@dataclass
class ActionClosureDispatchReceipt:
    """Latest worker/result state for one closure follow-up dispatch candidate."""

    receipt_id: str
    receipt_revision: int
    dispatch_id: str
    dedupe_key: str
    delivery_mode: str
    closure_id: str
    closure_revision: int
    zone_id: str | None = None
    module_id: str | None = None
    action_id: str | None = None
    state: str | None = None
    kind: str = "open"
    priority: str = "normal"
    title: str = ""
    message: str = ""
    updated_at: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    ack_note: str | None = None
    receipt_state: str = "acknowledged"
    receipt_at: str | None = None
    receipt_by: str | None = None
    receipt_note: str | None = None
    error: str | None = None
    retry_state: str | None = None
    retry_count: int = 0
    next_retry_at: str | None = None
    escalation_state: str | None = None
    escalation_at: str | None = None
    escalation_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureFollowUpReceiptV1",
            "receipt_id": self.receipt_id,
            "receipt_revision": self.receipt_revision,
            "dispatch_id": self.dispatch_id,
            "dedupe_key": self.dedupe_key,
            "delivery_mode": self.delivery_mode,
            "closure_id": self.closure_id,
            "closure_revision": self.closure_revision,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "action_id": self.action_id,
            "state": self.state,
            "kind": self.kind,
            "priority": self.priority,
            "title": self.title,
            "message": self.message,
            "updated_at": self.updated_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "ack_note": self.ack_note,
            "receipt_state": self.receipt_state,
            "receipt_at": self.receipt_at,
            "receipt_by": self.receipt_by,
            "receipt_note": self.receipt_note,
            "error": self.error,
            "retry_state": self.retry_state,
            "retry_count": self.retry_count,
            "next_retry_at": self.next_retry_at,
            "escalation_state": self.escalation_state,
            "escalation_at": self.escalation_at,
            "escalation_reason": self.escalation_reason,
            "delivery": {
                "mode": self.delivery_mode,
                "queue": "notifications" if self.delivery_mode == "notification_job" else "reminders",
                "topic": "action_closure_follow_up" if self.delivery_mode == "notification_job" else "action_closure_reminder",
            },
        }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dispatch_id(entry: dict[str, Any], delivery_mode: str) -> str:
    revision = int(entry.get("revision") or 0)
    seed = "|".join(
        [
            delivery_mode,
            str(entry.get("closure_id") or "unknown"),
            str(entry.get("kind") or "unknown"),
            str(revision),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"dispatch:{delivery_mode}:{digest}"


def _dispatch_dedupe_key(entry: dict[str, Any], delivery_mode: str) -> str:
    revision = int(entry.get("revision") or 0)
    return "|".join(
        [
            delivery_mode,
            str(entry.get("closure_id") or "unknown"),
            str(entry.get("kind") or "unknown"),
            str(revision),
        ]
    )


class ActionClosureFollowUpDispatchStore:
    """Tracks worker-facing dispatch candidates and acknowledgement state."""

    def __init__(self) -> None:
        self._candidate_index: dict[str, ActionClosureDispatchCandidate] = {}
        self._acknowledged: dict[str, dict[str, Any]] = {}
        self._receipt_index: dict[str, ActionClosureDispatchReceipt] = {}
        self._receipt_revision_counter: int = 0

    def clear(self) -> None:
        self._candidate_index.clear()
        self._acknowledged.clear()
        self._receipt_index.clear()
        self._receipt_revision_counter = 0

    def _next_receipt_revision(self) -> int:
        self._receipt_revision_counter += 1
        return self._receipt_revision_counter

    def get_current_receipt_revision(self) -> int:
        return self._receipt_revision_counter

    def _receipt_id(self, candidate: ActionClosureDispatchCandidate, revision: int) -> str:
        digest = hashlib.sha1(f"{candidate.dedupe_key}|{revision}".encode("utf-8")).hexdigest()[:16]
        return f"receipt:{candidate.delivery_mode}:{digest}"

    def _touch_receipt(
        self,
        candidate: ActionClosureDispatchCandidate,
        *,
        receipt_state: str,
        receipt_at: str | None = None,
        receipt_by: str | None = None,
        receipt_note: str | None = None,
        error: str | None = None,
        retry_state: str | None = None,
        retry_count: int | None = None,
        next_retry_at: str | None = None,
        escalation_state: str | None = None,
        escalation_at: str | None = None,
        escalation_reason: str | None = None,
    ) -> ActionClosureDispatchReceipt:
        revision = self._next_receipt_revision()
        existing = self._receipt_index.get(candidate.dedupe_key)
        receipt = ActionClosureDispatchReceipt(
            receipt_id=self._receipt_id(candidate, revision),
            receipt_revision=revision,
            dispatch_id=candidate.dispatch_id,
            dedupe_key=candidate.dedupe_key,
            delivery_mode=candidate.delivery_mode,
            closure_id=candidate.closure_id,
            closure_revision=candidate.closure_revision,
            zone_id=candidate.zone_id,
            module_id=candidate.module_id,
            action_id=candidate.action_id,
            state=candidate.state,
            kind=candidate.kind,
            priority=candidate.priority,
            title=candidate.title,
            message=candidate.message,
            updated_at=candidate.updated_at,
            acknowledged=candidate.acknowledged,
            acknowledged_at=candidate.acknowledged_at,
            acknowledged_by=candidate.acknowledged_by,
            ack_note=candidate.ack_note,
            receipt_state=str(receipt_state or "acknowledged").strip() or "acknowledged",
            receipt_at=receipt_at or _utcnow_iso(),
            receipt_by=str(receipt_by or candidate.acknowledged_by or "worker").strip() or "worker",
            receipt_note=str(receipt_note or candidate.ack_note or "").strip() or None,
            error=str(error or "").strip() or None,
            retry_state=str(retry_state).strip() if retry_state not in (None, "") else (existing.retry_state if existing else None),
            retry_count=int(retry_count if retry_count is not None else (existing.retry_count if existing else 0)),
            next_retry_at=next_retry_at if next_retry_at not in ("",) else None,
            escalation_state=(
                str(escalation_state).strip()
                if escalation_state not in (None, "")
                else (existing.escalation_state if existing else None)
            ),
            escalation_at=(
                escalation_at
                if escalation_state not in (None, "")
                else (existing.escalation_at if existing else None)
            ),
            escalation_reason=(
                str(escalation_reason).strip() or None
                if escalation_reason not in (None, "")
                else (existing.escalation_reason if existing else None)
            ),
        )
        if receipt.receipt_state in {"delivered", "sent", "queued"} and retry_state in (None, ""):
            receipt.retry_state = None
            receipt.next_retry_at = None
        if receipt.escalation_state in {"escalated", "triggered"} and not receipt.escalation_at:
            receipt.escalation_at = receipt.receipt_at
        self._receipt_index[candidate.dedupe_key] = receipt
        return receipt

    def candidate_from_follow_up(
        self,
        follow_up: dict[str, Any],
        *,
        delivery_mode: str,
    ) -> ActionClosureDispatchCandidate:
        dispatch_id = _dispatch_id(follow_up, delivery_mode)
        dedupe_key = _dispatch_dedupe_key(follow_up, delivery_mode)
        ack = self._acknowledged.get(dedupe_key) or {}
        candidate = ActionClosureDispatchCandidate(
            dispatch_id=dispatch_id,
            dedupe_key=dedupe_key,
            delivery_mode=delivery_mode,
            closure_id=str(follow_up.get("closure_id") or "unknown"),
            closure_revision=int(follow_up.get("revision") or 0),
            zone_id=follow_up.get("zone_id"),
            module_id=follow_up.get("module_id"),
            action_id=follow_up.get("action_id"),
            state=follow_up.get("state"),
            kind=str(follow_up.get("kind") or "open"),
            priority=str(follow_up.get("priority") or "normal"),
            title=str(follow_up.get("title") or ""),
            message=str(follow_up.get("message") or ""),
            updated_at=follow_up.get("updated_at"),
            acknowledged=bool(ack),
            acknowledged_at=ack.get("acknowledged_at"),
            acknowledged_by=ack.get("acknowledged_by"),
            ack_note=ack.get("ack_note"),
        )
        self._candidate_index[dispatch_id] = candidate
        return candidate

    def list_receipts(
        self,
        *,
        zone_id: str | None = None,
        delivery_mode: str | None = None,
        since_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        receipts = list(self._receipt_index.values())
        if zone_id:
            receipts = [receipt for receipt in receipts if receipt.zone_id == zone_id]
        if delivery_mode:
            receipts = [receipt for receipt in receipts if receipt.delivery_mode == delivery_mode]
        if since_revision is not None:
            receipts = [receipt for receipt in receipts if receipt.receipt_revision > since_revision]
        receipts.sort(
            key=lambda receipt: (receipt.receipt_revision, receipt.receipt_at or "", receipt.closure_id),
            reverse=True,
        )
        return [receipt.to_dict() for receipt in receipts]

    def acknowledge(
        self,
        dispatch_ids: list[str],
        *,
        acknowledged_by: str | None = None,
        note: str | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for dispatch_id in dispatch_ids:
            candidate = self._candidate_index.get(str(dispatch_id or "").strip())
            if candidate is None:
                continue
            timestamp = _utcnow_iso()
            ack = {
                "dispatch_id": candidate.dispatch_id,
                "closure_id": candidate.closure_id,
                "closure_revision": candidate.closure_revision,
                "delivery_mode": candidate.delivery_mode,
                "acknowledged_at": timestamp,
                "acknowledged_by": str(acknowledged_by or "worker").strip() or "worker",
                "ack_note": str(note or "").strip() or None,
            }
            self._acknowledged[candidate.dedupe_key] = ack
            candidate.acknowledged = True
            candidate.acknowledged_at = timestamp
            candidate.acknowledged_by = ack["acknowledged_by"]
            candidate.ack_note = ack["ack_note"]
            receipt = self._touch_receipt(
                candidate,
                receipt_state="acknowledged",
                receipt_at=timestamp,
                receipt_by=ack["acknowledged_by"],
                receipt_note=ack["ack_note"],
            )
            payload = candidate.to_dict()
            payload["contract"] = "ActionClosureFollowUpDispatchAckV1"
            payload["receipt_revision"] = receipt.receipt_revision
            results.append(payload)
        return results

    def record_receipts(
        self,
        dispatch_ids: list[str],
        *,
        receipt_state: str,
        receipt_by: str | None = None,
        note: str | None = None,
        error: str | None = None,
        retry_state: str | None = None,
        retry_count: int | None = None,
        next_retry_at: str | None = None,
        escalation_state: str | None = None,
        escalation_reason: str | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        timestamp = _utcnow_iso()
        for dispatch_id in dispatch_ids:
            candidate = self._candidate_index.get(str(dispatch_id or "").strip())
            if candidate is None:
                continue
            receipt = self._touch_receipt(
                candidate,
                receipt_state=receipt_state,
                receipt_at=timestamp,
                receipt_by=receipt_by,
                receipt_note=note,
                error=error,
                retry_state=retry_state,
                retry_count=retry_count,
                next_retry_at=next_retry_at,
                escalation_state=escalation_state,
                escalation_at=timestamp if escalation_state not in (None, "") else None,
                escalation_reason=escalation_reason,
            )
            results.append(receipt.to_dict())
        return results


# Singleton instances
_notification_manager: Optional[NotificationManager] = None
_action_closure_follow_up_dispatch_store: Optional[ActionClosureFollowUpDispatchStore] = None


def get_notification_manager() -> NotificationManager:
    """Get the singleton notification manager.
    
    Returns:
        NotificationManager: The singleton notification manager instance.
    """
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def get_action_closure_follow_up_dispatch_store() -> ActionClosureFollowUpDispatchStore:
    global _action_closure_follow_up_dispatch_store
    if _action_closure_follow_up_dispatch_store is None:
        _action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()
    return _action_closure_follow_up_dispatch_store


# =============================================================================
# API Endpoints
# =============================================================================

@bp.route("/send", methods=["POST"])
def send_notification() -> tuple[dict[str, Any], int]:
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
        tuple[dict[str, Any], int]: JSON response with notification_id and HTTP status code.
    """
    try:
        body = request.get_json(silent=True)
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


@bp.route("", methods=["GET", "POST"])
def handle_notifications() -> tuple[dict[str, Any], int]:
    """Handle GET/POST for notifications.
    
    GET Query params:
        unread_only: Only return unread (default false)
        type: Filter by notification type
        limit: Max results (default 20)
    
    POST JSON body:
        {"title": str, "message": str, "priority": str, "type": str}
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
    manager = get_notification_manager()
    
    if request.method == "POST":
        # Create notification
        body = request.get_json(silent=True) or {}
        title = body.get("title")
        message = body.get("message")
        
        if not title or not message:
            return jsonify({"ok": False, "error": "title and message required"}), 400
        
        priority = body.get("priority", "normal")
        # Convert numeric priority to string (1=CRITICAL, 2=HIGH, 3=NORMAL, 4=LOW)
        if isinstance(priority, int):
            priority_map = {1: "CRITICAL", 2: "HIGH", 3: "NORMAL", 4: "LOW"}
            priority = priority_map.get(priority, "normal")
        
        typ = body.get("type", "info")
        
        # Check for deduplication (simple title+message match within 60s)
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        for existing in manager._notifications:
            if (existing.title == title and existing.message == message and 
                datetime.fromisoformat(existing.timestamp.replace('Z', '+00:00')) > cutoff):
                return jsonify({
                    "ok": True,
                    "status": "deduplicated_or_rate_limited",
                    "existing_id": existing.id
                }), 200
        
        notification = manager.create_notification(
            title=title,
            message=message,
            priority=priority,
            type=typ,
        )
        
        return jsonify({
            "ok": True,
            "id": notification.id,
            "priority": notification.priority,
            "type": notification.type,
            "notification": notification.to_dict()
        }), 201
    
    else:
        # GET notifications
        unread_only = request.args.get("unread_only", "").lower() == "true"
        notification_type = request.args.get("type")
        limit = min(int(request.args.get("limit", "20")), 100)
        
        notifications = manager.get_notifications(unread_only, notification_type, limit)
        
        return jsonify({
            "ok": True,
            "count": len(notifications),
            "notifications": [n.to_dict() for n in notifications],
            "unread_count": manager.get_unread_count(),
            "total_count": len(manager._notifications),
        })


@bp.route("/<notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id: str) -> tuple[dict[str, Any], int]:
    """Mark notification as read.
    
    Args:
        notification_id: ID of the notification to mark as read.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
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
def dismiss_notification(notification_id: str) -> tuple[dict[str, Any], int]:
    """Dismiss a notification.
    
    Args:
        notification_id: ID of the notification to dismiss.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
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
def clear_notifications() -> tuple[dict[str, Any], int]:
    """Clear notifications.
    
    JSON body (optional):
        {"type": "alert"}  # Only clear alerts
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with cleared_count and HTTP status code.
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
def subscribe_device() -> tuple[dict[str, Any], int]:
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
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with subscription details and HTTP status code.
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
def unsubscribe_device() -> tuple[dict[str, Any], int]:
    """Unsubscribe a device.
    
    JSON body:
        {"device_id": str}
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
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
def get_subscriptions() -> tuple[dict[str, Any], int]:
    """Get all device subscriptions.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with subscriptions list and HTTP status code.
    """
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
def update_subscription(device_id: str) -> tuple[dict[str, Any], int]:
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
    
    Args:
        device_id: ID of the device subscription to update.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
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


@bp.route("/stats", methods=["GET"])
def get_notification_stats() -> tuple[dict[str, Any], int]:
    """Get notification statistics.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with stats and HTTP status code.
    """
    manager = get_notification_manager()
    stats = manager.get_stats()
    
    return jsonify({
        "ok": True,
        **stats
    })


@bp.route("/pending", methods=["GET"])
def get_pending_notifications() -> tuple[dict[str, Any], int]:
    """Get pending (unread) notifications.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with pending notifications and HTTP status code.
    """
    manager = get_notification_manager()
    pending = [n for n in manager._notifications if not n.read]
    response: dict[str, Any] = {
        "ok": True,
        "count": len(pending),
        "notifications": [n.to_dict() for n in pending],
    }

    if _parse_bool_arg("include_action_closures"):
        try:
            since_revision = _parse_optional_int_arg("action_closure_since")
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        response["action_closures"] = _build_action_closure_notification_digest(
            zone_id=(request.args.get("zone_id") or "").strip() or None,
            since_revision=since_revision,
            recent_limit=max(1, min(10, int(request.args.get("recent_limit", "5")))),
        )

    return jsonify(response)


@bp.route("/digest", methods=["GET"])
def get_notification_digest() -> tuple[dict[str, Any], int]:
    """Get notification digest summary.
    
    Query params:
        hours: Time window in hours (default 24)
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with digest and HTTP status code.
    """
    hours = float(request.args.get("hours", "24"))
    manager = get_notification_manager()
    digest = manager.get_digest(hours=hours)
    response: dict[str, Any] = {
        "ok": True,
        "digest": digest
    }

    if _parse_bool_arg("include_action_closures"):
        try:
            since_revision = _parse_optional_int_arg("action_closure_since")
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        response["digest"]["action_closures"] = _build_action_closure_notification_digest(
            zone_id=(request.args.get("zone_id") or "").strip() or None,
            since_revision=since_revision,
            recent_limit=max(1, min(10, int(request.args.get("recent_limit", "5")))),
        )

    return jsonify(response)


@bp.route("/action-closures/dispatch", methods=["GET"])
def get_action_closure_follow_up_dispatch() -> tuple[dict[str, Any], int]:
    """Get delivery-ready follow-up dispatch candidates for workers."""
    try:
        since_revision = _parse_optional_int_arg("action_closure_since")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    delivery_mode = (request.args.get("delivery_mode") or "notification_job").strip() or "notification_job"
    if delivery_mode not in {"notification_job", "reminder_queue"}:
        return jsonify({"ok": False, "error": f"Unsupported delivery_mode: {delivery_mode}"}), 400

    bundle = _build_action_closure_follow_up_dispatch_bundle(
        zone_id=(request.args.get("zone_id") or "").strip() or None,
        since_revision=since_revision,
        recent_limit=max(1, min(10, int(request.args.get("recent_limit", "5")))),
        delivery_mode=delivery_mode,
        include_acknowledged=_parse_bool_arg("include_acknowledged"),
    )
    return jsonify({"ok": True, "dispatch": bundle})


@bp.route("/action-closures/dispatch/ack", methods=["POST"])
def acknowledge_action_closure_follow_up_dispatch() -> tuple[dict[str, Any], int]:
    """Acknowledge worker dispatch candidates so they stay suppressed until closure change."""
    body = request.get_json(silent=True) or {}
    dispatch_ids = body.get("dispatch_ids") or []
    if not dispatch_ids and body.get("dispatch_id"):
        dispatch_ids = [body["dispatch_id"]]
    dispatch_ids = [str(item).strip() for item in dispatch_ids if str(item).strip()]
    if not dispatch_ids:
        return jsonify({"ok": False, "error": "dispatch_id or dispatch_ids required"}), 400

    acknowledgements = get_action_closure_follow_up_dispatch_store().acknowledge(
        dispatch_ids,
        acknowledged_by=body.get("acknowledged_by"),
        note=body.get("note"),
    )
    if not acknowledgements:
        return jsonify({"ok": False, "error": "No matching dispatch candidates found"}), 404

    return jsonify({"ok": True, "acknowledged": acknowledgements, "count": len(acknowledgements)})


@bp.route("/action-closures/dispatch/receipt", methods=["POST"])
def record_action_closure_follow_up_receipt() -> tuple[dict[str, Any], int]:
    """Record delivery/queue/retry/escalation results for dispatch candidates."""
    body = request.get_json(silent=True) or {}
    dispatch_ids = body.get("dispatch_ids") or []
    if not dispatch_ids and body.get("dispatch_id"):
        dispatch_ids = [body["dispatch_id"]]
    dispatch_ids = [str(item).strip() for item in dispatch_ids if str(item).strip()]
    if not dispatch_ids:
        return jsonify({"ok": False, "error": "dispatch_id or dispatch_ids required"}), 400

    receipt_state = str(body.get("receipt_state") or body.get("status") or "").strip()
    if not receipt_state:
        return jsonify({"ok": False, "error": "receipt_state required"}), 400

    retry_count_raw = body.get("retry_count")
    retry_count: int | None = None
    if retry_count_raw not in (None, ""):
        retry_count = int(retry_count_raw)
        if retry_count < 0:
            return jsonify({"ok": False, "error": "retry_count must be >= 0"}), 400

    receipts = get_action_closure_follow_up_dispatch_store().record_receipts(
        dispatch_ids,
        receipt_state=receipt_state,
        receipt_by=body.get("receipt_by"),
        note=body.get("note"),
        error=body.get("error"),
        retry_state=body.get("retry_state"),
        retry_count=retry_count,
        next_retry_at=body.get("next_retry_at"),
        escalation_state=body.get("escalation_state"),
        escalation_reason=body.get("escalation_reason"),
    )
    if not receipts:
        return jsonify({"ok": False, "error": "No matching dispatch candidates found"}), 404

    return jsonify({"ok": True, "receipts": receipts, "count": len(receipts)})


@bp.route("/action-closures/receipts", methods=["GET"])
def get_action_closure_follow_up_receipts() -> tuple[dict[str, Any], int]:
    """Get receipt/retry/escalation summary for closure follow-up workers."""
    try:
        since_revision = _parse_optional_int_arg("receipt_since")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    delivery_mode = (request.args.get("delivery_mode") or "").strip() or None
    if delivery_mode and delivery_mode not in {"notification_job", "reminder_queue"}:
        return jsonify({"ok": False, "error": f"Unsupported delivery_mode: {delivery_mode}"}), 400

    summary = _build_action_closure_follow_up_receipt_summary(
        zone_id=(request.args.get("zone_id") or "").strip() or None,
        delivery_mode=delivery_mode,
        since_revision=since_revision,
        recent_limit=max(1, min(10, int(request.args.get("recent_limit", "5")))),
    )
    return jsonify({"ok": True, "receipts": summary})


# Helper methods for NotificationManager
def _get_stats(self) -> dict[str, Any]:
    """Get notification statistics.
    
    Returns:
        dict[str, Any]: Statistics dictionary.
    """
    by_source: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_type: dict[str, int] = {}
    
    for n in self._notifications:
        # Count by type (used as source proxy)
        src = getattr(n, 'type', 'unknown')
        by_source[src] = by_source.get(src, 0) + 1
        
        # Count by priority
        prio = n.priority
        by_priority[prio] = by_priority.get(prio, 0) + 1
        
        # Count by type
        typ = n.type
        by_type[typ] = by_type.get(typ, 0) + 1
    
    return {
        "total_notifications": len(self._notifications),
        "unread_count": self.get_unread_count(),
        "by_source": by_source,
        "by_priority": by_priority,
        "by_type": by_type,
    }


def _get_digest(self, hours: float = 24.0) -> dict[str, Any]:
    """Get notification digest for time window.
    
    Args:
        hours: Time window in hours.
    
    Returns:
        dict[str, Any]: Digest summary.
    """
    cutoff: datetime = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent: list[Notification] = [
        n for n in self._notifications
        if datetime.fromisoformat(n.timestamp.replace('Z', '+00:00')) > cutoff
    ]
    
    by_source: dict[str, int] = {}
    for n in recent:
        src = getattr(n, 'type', 'unknown')
        by_source[src] = by_source.get(src, 0) + 1
    
    return {
        "period_hours": hours,
        "total": len(recent),
        "by_source": by_source,
    }


# Add methods to NotificationManager
NotificationManager.get_stats = _get_stats  # type: ignore
NotificationManager.get_digest = _get_digest  # type: ignore


def _parse_bool_arg(name: str, default: bool = False) -> bool:
    raw = (request.args.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _parse_optional_int_arg(name: str) -> int | None:
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 0:
        raise ValueError(f"Invalid integer for {name}: {raw}")
    return value


def _build_action_closure_follow_up(entry: dict[str, Any]) -> dict[str, Any] | None:
    state = str(entry.get("state") or "unknown").strip().lower()
    if state in _ACTION_CLOSURE_FAILURE_STATES:
        kind = "problematic"
        priority = "high"
        title = "Closure-Problem erkannt"
        message = f"{entry.get('zone_id') or entry.get('module_id') or entry.get('action_id')}: Status {state}"
    elif state in _ACTION_CLOSURE_OPEN_STATES:
        kind = "open"
        priority = "normal"
        title = "Closure noch offen"
        message = f"{entry.get('zone_id') or entry.get('module_id') or entry.get('action_id')}: wartet auf Abschluss"
    else:
        return None

    return {
        "closure_id": entry.get("closure_id"),
        "revision": int(entry.get("revision") or 0),
        "zone_id": entry.get("zone_id"),
        "module_id": entry.get("module_id"),
        "action_id": entry.get("action_id"),
        "state": entry.get("state"),
        "kind": kind,
        "priority": priority,
        "title": title,
        "message": message,
        "updated_at": entry.get("updated_at"),
    }


def _build_action_closure_notification_digest(
    *,
    zone_id: str | None = None,
    since_revision: int | None = None,
    recent_limit: int = 5,
) -> dict[str, Any]:
    summary = build_action_closure_summary_read_model(
        get_action_closure_store(),
        zone_id=zone_id,
        recent_limit=recent_limit,
        since_revision=since_revision,
    ).to_dict()

    follow_ups: list[dict[str, Any]] = []
    for entry in summary.get("recent_closures", []):
        follow_up = _build_action_closure_follow_up(entry)
        if follow_up is not None:
            follow_ups.append(follow_up)

    return {
        "contract": "ActionClosureNotificationDigestV1",
        "zone_id": zone_id,
        "revision": summary.get("revision", 0),
        "latest_change_at": summary.get("latest_change_at"),
        "open_count": summary.get("open_count", 0),
        "failure_count": summary.get("failure_count", 0),
        "success_count": summary.get("success_count", 0),
        "total_closures": summary.get("total_closures", 0),
        "delta": summary.get("delta", {}),
        "follow_ups": follow_ups,
        "delivery_receipts": _build_action_closure_follow_up_receipt_summary(
            zone_id=zone_id,
            recent_limit=recent_limit,
        ),
    }


def _describe_action_closure_follow_up_receipt_summary(summary: dict[str, Any]) -> str | None:
    counts = summary.get("counts") or {}
    total = int(counts.get("total_receipts") or 0)
    if total <= 0:
        return None

    parts = [f"Follow-up-Zustellung: {total} Receipts"]
    delivered = int(counts.get("delivered") or 0)
    failed = int(counts.get("failed") or 0)
    retry_pending = int(counts.get("retry_pending") or 0)
    escalated = int(counts.get("escalated") or 0)
    acknowledged = int(counts.get("acknowledged") or 0)

    if delivered:
        parts.append(f"{delivered} zugestellt")
    if acknowledged:
        parts.append(f"{acknowledged} bestaetigt")
    if failed:
        parts.append(f"{failed} fehlgeschlagen")
    if retry_pending:
        parts.append(f"{retry_pending} Retry offen")
    if escalated:
        parts.append(f"{escalated} eskaliert")
    return ", ".join(parts)


def _build_action_closure_follow_up_receipt_summary(
    *,
    zone_id: str | None = None,
    delivery_mode: str | None = None,
    since_revision: int | None = None,
    recent_limit: int = 5,
) -> dict[str, Any]:
    store = get_action_closure_follow_up_dispatch_store()
    receipts = store.list_receipts(
        zone_id=zone_id,
        delivery_mode=delivery_mode,
        since_revision=None,
    )
    delta_receipts = store.list_receipts(
        zone_id=zone_id,
        delivery_mode=delivery_mode,
        since_revision=since_revision,
    )

    latest_change_at = None
    if receipts:
        latest_change_at = receipts[0].get("receipt_at") or receipts[0].get("acknowledged_at")

    states: dict[str, int] = {}
    delivery_modes: dict[str, int] = {}
    counts = {
        "total_receipts": len(receipts),
        "acknowledged": 0,
        "delivered": 0,
        "failed": 0,
        "retry_pending": 0,
        "escalated": 0,
    }

    for receipt in receipts:
        state = str(receipt.get("receipt_state") or "unknown")
        states[state] = states.get(state, 0) + 1
        mode = str(receipt.get("delivery_mode") or "unknown")
        delivery_modes[mode] = delivery_modes.get(mode, 0) + 1
        if receipt.get("acknowledged"):
            counts["acknowledged"] += 1
        if state in {"queued", "sent", "delivered"}:
            counts["delivered"] += 1
        if state in {"failed", "retry_failed", "delivery_failed"}:
            counts["failed"] += 1
        if str(receipt.get("retry_state") or "").strip() in {"scheduled", "pending", "retrying"}:
            counts["retry_pending"] += 1
        if str(receipt.get("escalation_state") or "").strip() in {"escalated", "triggered", "pending"}:
            counts["escalated"] += 1

    return {
        "contract": "ActionClosureFollowUpReceiptSummaryV1",
        "zone_id": zone_id,
        "delivery_mode": delivery_mode,
        "receipt_revision": store.get_current_receipt_revision(),
        "latest_change_at": latest_change_at,
        "counts": counts,
        "states": dict(sorted(states.items(), key=lambda item: (-item[1], item[0]))),
        "delivery_modes": dict(sorted(delivery_modes.items(), key=lambda item: (-item[1], item[0]))),
        "highlights": [line for line in [_describe_action_closure_follow_up_receipt_summary({"counts": counts})] if line],
        "recent_receipts": receipts[: max(1, recent_limit)],
        "delta": {
            "contract": "ActionClosureFollowUpReceiptDeltaV1",
            "since_revision": since_revision,
            "current_revision": store.get_current_receipt_revision(),
            "changed": bool(delta_receipts),
            "changed_count": len(delta_receipts),
            "latest_change_at": (
                (delta_receipts[0].get("receipt_at") or delta_receipts[0].get("acknowledged_at"))
                if delta_receipts
                else None
            ),
            "recent_receipts": delta_receipts[: max(1, recent_limit)],
        },
    }


def _build_action_closure_follow_up_dispatch_bundle(
    *,
    zone_id: str | None = None,
    since_revision: int | None = None,
    recent_limit: int = 5,
    delivery_mode: str = "notification_job",
    include_acknowledged: bool = False,
) -> dict[str, Any]:
    digest = _build_action_closure_notification_digest(
        zone_id=zone_id,
        since_revision=since_revision,
        recent_limit=recent_limit,
    )
    store = get_action_closure_follow_up_dispatch_store()
    candidates: list[dict[str, Any]] = []
    acknowledged_count = 0
    for follow_up in digest.get("follow_ups", []):
        candidate = store.candidate_from_follow_up(follow_up, delivery_mode=delivery_mode)
        if candidate.acknowledged:
            acknowledged_count += 1
            if not include_acknowledged:
                continue
        candidates.append(candidate.to_dict())

    return {
        "contract": "ActionClosureFollowUpDispatchV1",
        "delivery_mode": delivery_mode,
        "zone_id": zone_id,
        "revision": digest.get("revision", 0),
        "latest_change_at": digest.get("latest_change_at"),
        "cursor": {
            "contract": "ActionClosureFollowUpDispatchCursorV1",
            "since_revision": since_revision,
            "current_revision": digest.get("revision", 0),
            "changed": bool((digest.get("delta") or {}).get("changed")),
            "changed_count": int((digest.get("delta") or {}).get("changed_count") or 0),
            "latest_change_at": (digest.get("delta") or {}).get("latest_change_at") or digest.get("latest_change_at"),
        },
        "counts": {
            "total_follow_ups": len(digest.get("follow_ups", [])),
            "dispatchable": len(candidates),
            "acknowledged": acknowledged_count,
            "open": digest.get("open_count", 0),
            "problematic": digest.get("failure_count", 0),
        },
        "digest": digest,
        "receipts": _build_action_closure_follow_up_receipt_summary(
            zone_id=zone_id,
            delivery_mode=delivery_mode,
            recent_limit=recent_limit,
        ),
        "candidates": candidates,
    }


# =============================================================================
# HomeAssistant Notify Integration Endpoints
# =============================================================================

def _get_ha_adapter():
    """Get or create HA Notify adapter.
    
    Returns:
        HANotifyAdapter: The HA notify adapter instance.
    """
    from copilot_core.notifications.ha_notify_adapter import get_ha_notify_adapter
    return get_ha_notify_adapter()


@bp.route("/ha/register", methods=["POST"])
def register_ha_device() -> tuple[dict[str, Any], int]:
    """Register a HomeAssistant notify device.
    
    JSON body:
        {
            "user_id": str,
            "ha_entity_id": str,  # e.g., "notify.mobile_app_iphone"
            "device_name": str,   # optional, defaults to entity_id
            "device_type": str    # optional: mobile, telegram, whatsapp, etc.
        }
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with device details and HTTP status code.
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({
                "success": False,
                "error": "No JSON body provided"
            }), 400
        
        # Validate required fields
        user_id = body.get("user_id")
        ha_entity_id = body.get("ha_entity_id")
        
        if not user_id:
            return jsonify({
                "success": False,
                "error": "user_id is required"
            }), 400
        
        if not ha_entity_id:
            return jsonify({
                "success": False,
                "error": "ha_entity_id is required"
            }), 400
        
        # Validate entity_id format
        if not ha_entity_id.startswith("notify."):
            return jsonify({
                "success": False,
                "error": "ha_entity_id must start with 'notify.' (e.g., notify.mobile_app_iphone)"
            }), 400
        
        adapter = _get_ha_adapter()
        
        device = adapter.register_ha_device(
            user_id=user_id,
            ha_entity_id=ha_entity_id,
            device_name=body.get("device_name", ""),
            device_type=body.get("device_type", ""),
        )
        
        return jsonify({
            "success": True,
            "data": device.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except Exception as e:
        _LOGGER.error("Error registering HA device: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/ha/devices", methods=["GET"])
def get_ha_devices() -> tuple[dict[str, Any], int]:
    """Get registered HomeAssistant devices.
    
    Query params:
        user_id: Filter by user ID (optional, returns all if omitted)
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with devices list and HTTP status code.
    """
    try:
        user_id = request.args.get("user_id")
        adapter = _get_ha_adapter()
        
        if user_id:
            devices = adapter.get_ha_devices(user_id)
        else:
            devices = adapter.get_all_devices()
        
        return jsonify({
            "success": True,
            "data": {
                "devices": [d.to_dict() for d in devices],
                "count": len(devices),
            }
        })
        
    except Exception as e:
        _LOGGER.error("Error getting HA devices: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/ha/devices/<device_id>", methods=["DELETE"])
def unregister_ha_device(device_id: str) -> tuple[dict[str, Any], int]:
    """Unregister a HomeAssistant device.
    
    Args:
        device_id: ID of the device to unregister.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
    try:
        adapter = _get_ha_adapter()
        
        if adapter.unregister_ha_device(device_id):
            return jsonify({
                "success": True,
                "data": {"device_id": device_id}
            })
        else:
            return jsonify({
                "success": False,
                "error": "Device not found"
            }), 404
            
    except Exception as e:
        _LOGGER.error("Error unregistering HA device: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/ha/devices/<device_id>/enable", methods=["POST"])
def enable_ha_device(device_id: str) -> tuple[dict[str, Any], int]:
    """Enable a HomeAssistant device.
    
    Args:
        device_id: ID of the device to enable.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
    adapter = _get_ha_adapter()
    
    if adapter.enable_device(device_id):
        return jsonify({
            "success": True,
            "data": {"device_id": device_id, "enabled": True}
        })
    else:
        return jsonify({
            "success": False,
            "error": "Device not found"
        }), 404


@bp.route("/ha/devices/<device_id>/disable", methods=["POST"])
def disable_ha_device(device_id: str) -> tuple[dict[str, Any], int]:
    """Disable a HomeAssistant device.
    
    Args:
        device_id: ID of the device to disable.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response and HTTP status code.
    """
    adapter = _get_ha_adapter()
    
    if adapter.disable_device(device_id):
        return jsonify({
            "success": True,
            "data": {"device_id": device_id, "enabled": False}
        })
    else:
        return jsonify({
            "success": False,
            "error": "Device not found"
        }), 404


@bp.route("/send/ha", methods=["POST"])
def send_ha_notification() -> tuple[dict[str, Any], int]:
    """Send notification via HomeAssistant notify service.
    
    JSON body:
        {
            "device_id": str,         # Registered device ID
            "message": str,           # Notification message (required)
            "title": str,             # Optional title
            "priority": str,          # low, normal, high, urgent (default: normal)
            "type": str,              # mood_change, alert, suggestion, etc. (default: info)
            "data": {...}             # Optional additional data payload
        }
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with send status and HTTP status code.
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({
                "success": False,
                "error": "No JSON body provided"
            }), 400
        
        # Validate required fields
        device_id = body.get("device_id")
        message = body.get("message")
        
        if not device_id:
            return jsonify({
                "success": False,
                "error": "device_id is required"
            }), 400
        
        if not message:
            return jsonify({
                "success": False,
                "error": "message is required"
            }), 400
        
        adapter = _get_ha_adapter()
        
        # Send notification
        success = adapter.send_to_ha_service(
            device_id=device_id,
            message=message,
            priority=body.get("priority", "normal"),
            title=body.get("title", ""),
            notification_type=body.get("type", "info"),
            data=body.get("data"),
        )
        
        if success:
            return jsonify({
                "success": True,
                "data": {
                    "device_id": device_id,
                    "message": message[:50] + "..." if len(message) > 50 else message,
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to send notification. Device may be disabled or service unavailable."
            }), 500
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except RuntimeError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 503
    except Exception as e:
        _LOGGER.error("Error sending HA notification: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/ha/test", methods=["GET"])
def test_ha_connection() -> tuple[dict[str, Any], int]:
    """Test HomeAssistant connection and notify service availability.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with connection test results.
    """
    try:
        adapter = _get_ha_adapter()
        result = adapter.test_ha_connection()
        
        status_code = 200 if result["success"] else 503
        
        return jsonify({
            "success": result["success"],
            "data": result
        }), status_code
        
    except Exception as e:
        _LOGGER.error("Error testing HA connection: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/ha/services", methods=["GET"])
def get_ha_notify_services() -> tuple[dict[str, Any], int]:
    """Get available HomeAssistant notify services.
    
    Returns:
        tuple[dict[str, Any], int]: JSON response with services list.
    """
    try:
        adapter = _get_ha_adapter()
        services = adapter.get_available_notify_services()
        
        return jsonify({
            "success": True,
            "data": {
                "services": services,
                "count": len(services),
            }
        })
        
    except Exception as e:
        _LOGGER.error("Error getting HA notify services: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


__all__ = [
    "bp",
    "get_notification_manager",
    "get_action_closure_follow_up_dispatch_store",
    "_build_action_closure_follow_up_receipt_summary",
    "_describe_action_closure_follow_up_receipt_summary",
    "NotificationManager",
    "ActionClosureFollowUpDispatchStore",
    "register_ha_device",
    "get_action_closure_follow_up_dispatch",
    "acknowledge_action_closure_follow_up_dispatch",
    "record_action_closure_follow_up_receipt",
    "get_action_closure_follow_up_receipts",
    "get_ha_devices",
    "send_ha_notification",
    "test_ha_connection",
]
