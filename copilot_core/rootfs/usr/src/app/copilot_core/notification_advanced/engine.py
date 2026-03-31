"""Notification Advanced Engine — Slice 57.

Advanced notifications for PilotSuite Core.

Features:
- Multi-channel delivery
- Template system
- Batch notifications
- Priority queues
- User preferences
- Delivery tracking
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"


class Priority(Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DeliveryStatus(Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NotificationTemplate:
    """Notification template."""
    template_id: str
    name: str
    subject: str
    body: str
    channels: List[ChannelType] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def render(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render template with variables."""
        rendered = {
            "subject": self.subject,
            "body": self.body,
        }
        
        for key, value in variables.items():
            for field in rendered:
                rendered[field] = rendered[field].replace(f"{{{{{key}}}}}", str(value))
        
        return rendered
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "subject": self.subject,
            "body": self.body,
            "channels": [c.value for c in self.channels],
            "variables": self.variables,
            "created_at": self.created_at,
        }


@dataclass
class Notification:
    """Notification message."""
    notification_id: str
    template_id: Optional[str]
    channels: List[ChannelType]
    recipients: List[str]
    subject: str
    body: str
    priority: Priority = Priority.NORMAL
    status: DeliveryStatus = DeliveryStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    delivery_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "template_id": self.template_id,
            "channels": [c.value for c in self.channels],
            "recipients": self.recipients,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "metadata": self.metadata,
            "delivery_results": self.delivery_results,
        }


@dataclass
class UserPreferences:
    """User notification preferences."""
    user_id: str
    enabled_channels: List[ChannelType] = field(default_factory=list)
    disabled_templates: List[str] = field(default_factory=list)
    quiet_hours_start: Optional[int] = None  # Hour 0-23
    quiet_hours_end: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_channel_enabled(self, channel: ChannelType) -> bool:
        """Check if channel is enabled."""
        return channel in self.enabled_channels
    
    def is_template_enabled(self, template_id: str) -> bool:
        """Check if template is enabled."""
        return template_id not in self.disabled_templates
    
    def is_in_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False
        
        now = datetime.now().hour
        
        if self.quiet_hours_start < self.quiet_hours_end:
            return self.quiet_hours_start <= now < self.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 - 08:00)
            return now >= self.quiet_hours_start or now < self.quiet_hours_end
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "enabled_channels": [c.value for c in self.enabled_channels],
            "disabled_templates": self.disabled_templates,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "metadata": self.metadata,
        }


class NotificationEngine:
    """Advanced notification engine."""
    
    def __init__(self):
        self._templates: Dict[str, NotificationTemplate] = {}
        self._notifications: Dict[str, Notification] = {}
        self._user_preferences: Dict[str, UserPreferences] = {}
        self._channel_handlers: Dict[ChannelType, Callable[[Notification, str], bool]] = {}
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "by_channel": {},
            "by_priority": {},
        }
    
    def register_channel_handler(self, channel: ChannelType,
                                handler: Callable[[Notification, str], bool]) -> None:
        """Register a channel handler."""
        self._channel_handlers[channel] = handler
        logger.info("Channel handler registered: %s", channel.value)
    
    def create_template(self, name: str, subject: str, body: str,
                       channels: Optional[List[ChannelType]] = None,
                       variables: Optional[List[str]] = None) -> str:
        """Create a notification template."""
        template_id = f"tpl_{uuid.uuid4().hex[:16]}"
        
        template = NotificationTemplate(
            template_id=template_id,
            name=name,
            subject=subject,
            body=body,
            channels=channels or [ChannelType.EMAIL],
            variables=variables or [],
        )
        
        with self._lock:
            self._templates[template_id] = template
        
        logger.info("Template created: %s (%s)", name, template_id)
        
        return template_id
    
    def update_template(self, template_id: str,
                       name: Optional[str] = None,
                       subject: Optional[str] = None,
                       body: Optional[str] = None,
                       channels: Optional[List[ChannelType]] = None) -> bool:
        """Update a template."""
        with self._lock:
            template = self._templates.get(template_id)
            
            if not template:
                return False
            
            if name:
                template.name = name
            if subject:
                template.subject = subject
            if body:
                template.body = body
            if channels:
                template.channels = channels
        
        return True
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        with self._lock:
            if template_id not in self._templates:
                return False
            
            del self._templates[template_id]
        
        return True
    
    def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """Get template by ID."""
        return self._templates.get(template_id)
    
    def list_templates(self) -> List[NotificationTemplate]:
        """List all templates."""
        return list(self._templates.values())
    
    def set_user_preferences(self, user_id: str,
                            enabled_channels: Optional[List[ChannelType]] = None,
                            disabled_templates: Optional[List[str]] = None,
                            quiet_hours: Optional[tuple] = None) -> str:
        """Set user notification preferences."""
        with self._lock:
            if user_id in self._user_preferences:
                prefs = self._user_preferences[user_id]
            else:
                prefs = UserPreferences(user_id=user_id)
            
            if enabled_channels is not None:
                prefs.enabled_channels = enabled_channels
            if disabled_templates is not None:
                prefs.disabled_templates = disabled_templates
            if quiet_hours:
                prefs.quiet_hours_start, prefs.quiet_hours_end = quiet_hours
            
            self._user_preferences[user_id] = prefs
        
        return user_id
    
    def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences."""
        return self._user_preferences.get(user_id)
    
    def send(self, template_id: str, recipients: List[str],
            variables: Optional[Dict[str, Any]] = None,
            channels: Optional[List[ChannelType]] = None,
            priority: Priority = Priority.NORMAL,
            metadata: Optional[Dict[str, Any]] = None) -> str:
        """Send notification using template."""
        template = self._templates.get(template_id)
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Render template
        rendered = template.render(variables or {})
        
        notification_id = self._create_notification(
            template_id=template_id,
            channels=channels or template.channels,
            recipients=recipients,
            subject=rendered["subject"],
            body=rendered["body"],
            priority=priority,
            metadata=metadata,
        )
        
        # Process notification
        self._process_notification(notification_id)
        
        return notification_id
    
    def send_direct(self, channels: List[ChannelType], recipients: List[str],
                   subject: str, body: str,
                   priority: Priority = Priority.NORMAL,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Send direct notification without template."""
        notification_id = self._create_notification(
            template_id=None,
            channels=channels,
            recipients=recipients,
            subject=subject,
            body=body,
            priority=priority,
            metadata=metadata,
        )
        
        self._process_notification(notification_id)
        
        return notification_id
    
    def _create_notification(self, template_id: Optional[str],
                            channels: List[ChannelType],
                            recipients: List[str],
                            subject: str,
                            body: str,
                            priority: Priority,
                            metadata: Optional[Dict[str, Any]]) -> str:
        """Create notification record."""
        notification_id = f"notif_{uuid.uuid4().hex[:16]}"
        
        notification = Notification(
            notification_id=notification_id,
            template_id=template_id,
            channels=channels,
            recipients=recipients,
            subject=subject,
            body=body,
            priority=priority,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._notifications[notification_id] = notification
        
        return notification_id
    
    def _process_notification(self, notification_id: str) -> None:
        """Process notification for delivery."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            
            if not notification:
                return
            
            notification.status = DeliveryStatus.SENT
            notification.sent_at = datetime.now(timezone.utc).isoformat()
        
        # Deliver to each recipient/channel
        for recipient in notification.recipients:
            for channel in notification.channels:
                self._deliver_to_channel(notification, recipient, channel)
    
    def _deliver_to_channel(self, notification: Notification,
                           recipient: str, channel: ChannelType) -> bool:
        """Deliver notification to specific channel."""
        # Check user preferences
        prefs = self._user_preferences.get(recipient)
        
        if prefs:
            # Check channel enabled
            if not prefs.is_channel_enabled(channel):
                self._record_delivery(notification, recipient, channel.value,
                                     DeliveryStatus.SKIPPED, "Channel disabled by user")
                return False
            
            # Check template enabled
            if notification.template_id:
                if not prefs.is_template_enabled(notification.template_id):
                    self._record_delivery(notification, recipient, channel.value,
                                         DeliveryStatus.SKIPPED, "Template disabled by user")
                    return False
            
            # Check quiet hours
            if prefs.is_in_quiet_hours() and notification.priority != Priority.URGENT:
                self._record_delivery(notification, recipient, channel.value,
                                     DeliveryStatus.SKIPPED, "Quiet hours")
                return False
        
        # Get channel handler
        handler = self._channel_handlers.get(channel)
        
        if not handler:
            # No handler registered - simulate success
            self._record_delivery(notification, recipient, channel.value,
                                 DeliveryStatus.DELIVERED, "Simulated (no handler)")
            return True
        
        try:
            success = handler(notification, recipient)
            
            if success:
                self._record_delivery(notification, recipient, channel.value,
                                     DeliveryStatus.DELIVERED, "Success")
            else:
                self._record_delivery(notification, recipient, channel.value,
                                     DeliveryStatus.FAILED, "Handler returned false")
            
            return success
            
        except Exception as e:
            self._record_delivery(notification, recipient, channel.value,
                                 DeliveryStatus.FAILED, str(e))
            return False
    
    def _record_delivery(self, notification: Notification, recipient: str,
                        channel: str, status: DeliveryStatus, message: str) -> None:
        """Record delivery result."""
        key = f"{recipient}:{channel}"
        
        notification.delivery_results[key] = {
            "recipient": recipient,
            "channel": channel,
            "status": status.value,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Update statistics
        self._stats[f"total_{status.value}"] = self._stats.get(f"total_{status.value}", 0) + 1
        self._stats["by_channel"][channel] = self._stats["by_channel"].get(channel, 0) + 1
        self._stats["by_priority"][notification.priority.value] = \
            self._stats["by_priority"].get(notification.priority.value, 0) + 1
        
        # Update notification status
        if status == DeliveryStatus.DELIVERED:
            notification.delivered_at = datetime.now(timezone.utc).isoformat()
            notification.status = DeliveryStatus.DELIVERED
    
    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get notification by ID."""
        return self._notifications.get(notification_id)
    
    def list_notifications(self, status: Optional[DeliveryStatus] = None,
                          priority: Optional[Priority] = None,
                          limit: int = 100) -> List[Notification]:
        """List notifications with filters."""
        with self._lock:
            notifications = list(self._notifications.values())
            
            if status:
                notifications = [n for n in notifications if n.status == status]
            
            if priority:
                notifications = [n for n in notifications if n.priority == priority]
            
            # Sort by created_at descending
            notifications.sort(key=lambda n: n.created_at, reverse=True)
            
            return notifications[:limit]
    
    def get_delivery_status(self, notification_id: str) -> Dict[str, Any]:
        """Get delivery status for notification."""
        notification = self._notifications.get(notification_id)
        
        if not notification:
            return {"error": "Notification not found"}
        
        return {
            "notification_id": notification_id,
            "status": notification.status.value,
            "total_recipients": len(notification.recipients),
            "total_channels": len(notification.channels),
            "delivery_results": notification.delivery_results,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_notifications": len(self._notifications),
                "total_templates": len(self._templates),
                "total_users": len(self._user_preferences),
            }
    
    def clear_notifications(self, older_than_days: Optional[int] = None) -> int:
        """Clear old notifications."""
        with self._lock:
            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                cutoff_str = cutoff.isoformat()
                
                keys_to_delete = [
                    key for key, notif in self._notifications.items()
                    if notif.created_at < cutoff_str
                ]
                
                for key in keys_to_delete:
                    del self._notifications[key]
                
                return len(keys_to_delete)
            else:
                count = len(self._notifications)
                self._notifications.clear()
                return count
    
    def batch_send(self, template_id: str,
                   recipient_groups: List[Dict[str, Any]]) -> List[str]:
        """Send batch notifications with different variables per group."""
        notification_ids = []
        
        for group in recipient_groups:
            recipients = group.get("recipients", [])
            variables = group.get("variables", {})
            
            if not recipients:
                continue
            
            notification_id = self.send(
                template_id=template_id,
                recipients=recipients,
                variables=variables,
            )
            
            notification_ids.append(notification_id)
        
        return notification_ids
    
    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel a pending notification."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            
            if not notification:
                return False
            
            if notification.status != DeliveryStatus.PENDING:
                return False
            
            notification.status = DeliveryStatus.SKIPPED
            
            return True


def create_notification_engine() -> NotificationEngine:
    """Factory function to create notification engine."""
    return NotificationEngine()
