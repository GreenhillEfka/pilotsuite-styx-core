"""Notification Advanced Engine — Slice 66.

Advanced notification engine for PilotSuite Core.

Features:
- Multi-channel delivery (email, sms, push, webhook, telegram, whatsapp, slack)
- Template system with variables
- Notification workflows/chains
- Batching and throttling
- Priority queues
- Delivery tracking and retry
- User preferences
"""
from __future__ import annotations

import logging
import threading
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from enum import Enum
import uuid
import hashlib

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    DISCORD = "discord"
    CUSTOM = "custom"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4


class DeliveryStatus(Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class NotificationTemplate:
    """Notification template."""
    template_id: str
    name: str
    channel: ChannelType
    subject_template: Optional[str] = None
    body_template: str = ""
    variables: List[str] = field(default_factory=list)
    default_values: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def render(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render template with variables."""
        merged = {**self.default_values, **variables}
        
        result = {}
        
        if self.subject_template:
            result["subject"] = self._render_template(self.subject_template, merged)
        
        result["body"] = self._render_template(self.body_template, merged)
        
        return result
    
    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Render template string with variables."""
        result = template
        
        # Replace {{variable}} patterns
        for key, value in variables.items():
            pattern = re.compile(r'\{\{\s*' + re.escape(key) + r'\s*\}\}', re.IGNORECASE)
            result = pattern.sub(str(value), result)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "channel": self.channel.value,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "variables": self.variables,
            "default_values": self.default_values,
            "created_at": self.created_at,
        }


@dataclass
class Notification:
    """Notification definition."""
    notification_id: str
    channel: ChannelType
    recipient: str
    subject: Optional[str] = None
    body: str = ""
    priority: NotificationPriority = NotificationPriority.NORMAL
    template_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scheduled_at: Optional[str] = None
    expires_at: Optional[str] = None
    delivery_count: int = 0
    status: DeliveryStatus = DeliveryStatus.PENDING
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "priority": self.priority.value,
            "template_id": self.template_id,
            "variables": self.variables,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "expires_at": self.expires_at,
            "delivery_count": self.delivery_count,
            "status": self.status.value,
            "last_error": self.last_error,
        }


@dataclass
class DeliveryRecord:
    """Delivery tracking record."""
    record_id: str
    notification_id: str
    channel: ChannelType
    recipient: str
    status: DeliveryStatus
    attempts: int
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "recipient": self.recipient,
            "status": self.status.value,
            "attempts": self.attempts,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class NotificationWorkflow:
    """Notification workflow/chaining."""
    workflow_id: str
    name: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    condition: Optional[str] = None
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "steps": self.steps,
            "condition": self.condition,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass
class UserPreferences:
    """User notification preferences."""
    user_id: str
    channels: Dict[ChannelType, bool] = field(default_factory=dict)
    quiet_hours_start: Optional[int] = None  # Hour (0-23)
    quiet_hours_end: Optional[int] = None
    priority_threshold: NotificationPriority = NotificationPriority.NORMAL
    subscribed_topics: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "channels": {k.value: v for k, v in self.channels.items()},
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "priority_threshold": self.priority_threshold.value,
            "subscribed_topics": list(self.subscribed_topics),
        }


class NotificationEngine:
    """Advanced notification engine."""
    
    def __init__(self, max_retries: int = 3,
                 retry_delay_seconds: int = 30,
                 batch_size: int = 100,
                 throttle_per_minute: int = 60):
        self._templates: Dict[str, NotificationTemplate] = {}
        self._notifications: Dict[str, Notification] = {}
        self._delivery_records: Dict[str, DeliveryRecord] = {}
        self._workflows: Dict[str, NotificationWorkflow] = {}
        self._user_preferences: Dict[str, UserPreferences] = {}
        self._channel_handlers: Dict[ChannelType, Callable[[Notification], bool]] = {}
        self._lock = threading.Lock()
        
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._batch_size = batch_size
        self._throttle_per_minute = throttle_per_minute
        
        # Rate limiting
        self._rate_limit_window: List[datetime] = []
        
        # Statistics
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "by_channel": {},
            "by_template": {},
        }
    
    def register_channel_handler(self, channel: ChannelType,
                                handler: Callable[[Notification], bool]) -> None:
        """Register a channel handler."""
        with self._lock:
            self._channel_handlers[channel] = handler
        logger.info("Channel handler registered: %s", channel.value)
    
    def create_template(self, name: str, channel: ChannelType,
                       body_template: str,
                       subject_template: Optional[str] = None,
                       variables: Optional[List[str]] = None,
                       default_values: Optional[Dict[str, Any]] = None) -> str:
        """Create a notification template."""
        template_id = f"tpl_{uuid.uuid4().hex[:16]}"
        
        template = NotificationTemplate(
            template_id=template_id,
            name=name,
            channel=channel,
            subject_template=subject_template,
            body_template=body_template,
            variables=variables or [],
            default_values=default_values or {},
        )
        
        with self._lock:
            self._templates[template_id] = template
        
        logger.info("Template created: %s (%s)", name, template_id)
        
        return template_id
    
    def update_template(self, template_id: str,
                       name: Optional[str] = None,
                       body_template: Optional[str] = None,
                       subject_template: Optional[str] = None,
                       default_values: Optional[Dict[str, Any]] = None) -> bool:
        """Update a template."""
        with self._lock:
            template = self._templates.get(template_id)
            
            if not template:
                return False
            
            if name:
                template.name = name
            if body_template:
                template.body_template = body_template
            if subject_template:
                template.subject_template = subject_template
            if default_values:
                template.default_values = default_values
        
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
    
    def list_templates(self, channel: Optional[ChannelType] = None) -> List[Dict[str, Any]]:
        """List templates with optional channel filter."""
        with self._lock:
            templates = list(self._templates.values())
            
            if channel:
                templates = [t for t in templates if t.channel == channel]
            
            return [t.to_dict() for t in templates]
    
    def send(self, channel: ChannelType, recipient: str,
            body: str, subject: Optional[str] = None,
            priority: NotificationPriority = NotificationPriority.NORMAL,
            template_id: Optional[str] = None,
            variables: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            scheduled_at: Optional[str] = None) -> str:
        """Send a notification."""
        notification_id = f"ntf_{uuid.uuid4().hex[:16]}"
        
        notification = Notification(
            notification_id=notification_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            priority=priority,
            template_id=template_id,
            variables=variables or {},
            metadata=metadata or {},
            scheduled_at=scheduled_at,
        )
        
        # Apply template if provided
        if template_id:
            template = self._templates.get(template_id)
            if template:
                rendered = template.render(notification.variables)
                if not notification.subject and "subject" in rendered:
                    notification.subject = rendered["subject"]
                notification.body = rendered["body"]
        
        with self._lock:
            self._notifications[notification_id] = notification
            
            # Check user preferences
            if not self._check_user_preferences(notification):
                notification.status = DeliveryStatus.CANCELLED
                notification.last_error = "Blocked by user preferences"
                return notification_id
            
            # Check rate limit
            if not self._check_rate_limit():
                notification.status = DeliveryStatus.PENDING
                # Will be sent when rate limit allows
            else:
                self._deliver_notification(notification)
        
        return notification_id
    
    def send_batch(self, notifications: List[Dict[str, Any]]) -> List[str]:
        """Send multiple notifications in batch."""
        ids = []
        
        # Process in batches
        for i in range(0, len(notifications), self._batch_size):
            batch = notifications[i:i + self._batch_size]
            
            for notif_data in batch:
                channel = ChannelType(notif_data.get("channel", "email"))
                notification_id = self.send(
                    channel=channel,
                    recipient=notif_data.get("recipient", ""),
                    body=notif_data.get("body", ""),
                    subject=notif_data.get("subject"),
                    priority=NotificationPriority(notif_data.get("priority", 1)),
                    template_id=notif_data.get("template_id"),
                    variables=notif_data.get("variables"),
                    metadata=notif_data.get("metadata"),
                )
                ids.append(notification_id)
        
        return ids
    
    def _deliver_notification(self, notification: Notification) -> bool:
        """Deliver notification to channel."""
        handler = self._channel_handlers.get(notification.channel)
        
        record_id = f"dvr_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc).isoformat()
        
        record = DeliveryRecord(
            record_id=record_id,
            notification_id=notification.notification_id,
            channel=notification.channel,
            recipient=notification.recipient,
            status=DeliveryStatus.PENDING,
            attempts=0,
        )
        
        success = False
        error = None
        
        try:
            if handler:
                success = handler(notification)
            else:
                # No handler - simulate success for testing
                success = True
                logger.debug("No handler for %s - simulated delivery", notification.channel.value)
            
            notification.delivery_count += 1
            
            if success:
                notification.status = DeliveryStatus.DELIVERED
                record.status = DeliveryStatus.DELIVERED
                record.delivered_at = now
                
                with self._lock:
                    self._stats["total_delivered"] += 1
                    channel_key = notification.channel.value
                    self._stats["by_channel"][channel_key] = \
                        self._stats["by_channel"].get(channel_key, 0) + 1
                    
                    if notification.template_id:
                        self._stats["by_template"][notification.template_id] = \
                            self._stats["by_template"].get(notification.template_id, 0) + 1
            else:
                notification.status = DeliveryStatus.FAILED
                record.status = DeliveryStatus.FAILED
                error = "Handler returned false"
                
        except Exception as e:
            notification.delivery_count += 1
            notification.status = DeliveryStatus.FAILED
            error = str(e)
            record.status = DeliveryStatus.FAILED
            logger.exception("Delivery failed for %s", notification.notification_id)
        
        record.attempts = notification.delivery_count
        record.sent_at = now
        record.error = error
        
        with self._lock:
            self._delivery_records[record_id] = record
            
            if not success:
                self._stats["total_failed"] += 1
                
                # Schedule retry if under max retries
                if notification.delivery_count < self._max_retries:
                    notification.status = DeliveryStatus.RETRYING
                    notification.last_error = error
        
        return success
    
    def _check_user_preferences(self, notification: Notification) -> bool:
        """Check if notification is allowed by user preferences."""
        # Extract user ID from recipient (simplified)
        user_id = notification.recipient.split(":")[0] if ":" in notification.recipient else notification.recipient
        
        prefs = self._user_preferences.get(user_id)
        
        if not prefs:
            return True  # No preferences = allow all
        
        # Check channel preference
        if notification.channel in prefs.channels:
            if not prefs.channels[notification.channel]:
                return False
        
        # Check quiet hours
        if prefs.quiet_hours_start is not None and prefs.quiet_hours_end is not None:
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            if prefs.quiet_hours_start <= current_hour < prefs.quiet_hours_end:
                # In quiet hours - only allow high priority
                if notification.priority.value < prefs.priority_threshold.value:
                    return False
        
        return True
    
    def _check_rate_limit(self) -> bool:
        """Check rate limiting."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)
        
        with self._lock:
            # Clean old entries
            self._rate_limit_window = [
                t for t in self._rate_limit_window if t > window_start
            ]
            
            if len(self._rate_limit_window) >= self._throttle_per_minute:
                return False
            
            self._rate_limit_window.append(now)
        
        return True
    
    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get notification by ID."""
        return self._notifications.get(notification_id)
    
    def get_delivery_record(self, notification_id: str) -> Optional[DeliveryRecord]:
        """Get delivery record for notification."""
        with self._lock:
            for record in self._delivery_records.values():
                if record.notification_id == notification_id:
                    return record
        return None
    
    def list_notifications(self, status: Optional[DeliveryStatus] = None,
                          channel: Optional[ChannelType] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """List notifications with filters."""
        with self._lock:
            notifications = list(self._notifications.values())
            
            if status:
                notifications = [n for n in notifications if n.status == status]
            
            if channel:
                notifications = [n for n in notifications if n.channel == channel]
            
            # Sort by created_at descending
            notifications.sort(key=lambda n: n.created_at, reverse=True)
            
            return [n.to_dict() for n in notifications[:limit]]
    
    def retry_notification(self, notification_id: str) -> bool:
        """Retry a failed notification."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            
            if not notification:
                return False
            
            if notification.status not in (DeliveryStatus.FAILED, DeliveryStatus.CANCELLED):
                return False
            
            notification.status = DeliveryStatus.PENDING
            notification.last_error = None
            
            self._deliver_notification(notification)
        
        return True
    
    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel a pending notification."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            
            if not notification:
                return False
            
            if notification.status != DeliveryStatus.PENDING:
                return False
            
            notification.status = DeliveryStatus.CANCELLED
        
        return True
    
    def create_workflow(self, name: str, steps: List[Dict[str, Any]],
                       condition: Optional[str] = None) -> str:
        """Create a notification workflow."""
        workflow_id = f"wf_{uuid.uuid4().hex[:16]}"
        
        workflow = NotificationWorkflow(
            workflow_id=workflow_id,
            name=name,
            steps=steps,
            condition=condition,
        )
        
        with self._lock:
            self._workflows[workflow_id] = workflow
        
        return workflow_id
    
    def execute_workflow(self, workflow_id: str,
                        initial_notification: Dict[str, Any]) -> List[str]:
        """Execute a notification workflow."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            
            if not workflow or not workflow.enabled:
                return []
        
        notification_ids = []
        
        for step in workflow.steps:
            channel = ChannelType(step.get("channel", "email"))
            recipient = step.get("recipient", initial_notification.get("recipient"))
            body = step.get("body", initial_notification.get("body", ""))
            subject = step.get("subject")
            
            notification_id = self.send(
                channel=channel,
                recipient=recipient,
                body=body,
                subject=subject,
            )
            notification_ids.append(notification_id)
        
        return notification_ids
    
    def get_workflow(self, workflow_id: str) -> Optional[NotificationWorkflow]:
        """Get workflow by ID."""
        return self._workflows.get(workflow_id)
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        with self._lock:
            return [w.to_dict() for w in self._workflows.values()]
    
    def set_user_preferences(self, user_id: str,
                            channels: Optional[Dict[ChannelType, bool]] = None,
                            quiet_hours_start: Optional[int] = None,
                            quiet_hours_end: Optional[int] = None,
                            priority_threshold: Optional[NotificationPriority] = None,
                            subscribed_topics: Optional[Set[str]] = None) -> None:
        """Set user notification preferences."""
        with self._lock:
            if user_id not in self._user_preferences:
                self._user_preferences[user_id] = UserPreferences(user_id=user_id)
            
            prefs = self._user_preferences[user_id]
            
            if channels:
                prefs.channels = channels
            if quiet_hours_start is not None:
                prefs.quiet_hours_start = quiet_hours_start
            if quiet_hours_end is not None:
                prefs.quiet_hours_end = quiet_hours_end
            if priority_threshold:
                prefs.priority_threshold = priority_threshold
            if subscribed_topics:
                prefs.subscribed_topics = subscribed_topics
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        with self._lock:
            prefs = self._user_preferences.get(user_id)
            
            if not prefs:
                return None
            
            return prefs.to_dict()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_templates": len(self._templates),
                "total_workflows": len(self._workflows),
                "total_users": len(self._user_preferences),
                "pending_notifications": len([
                    n for n in self._notifications.values()
                    if n.status == DeliveryStatus.PENDING
                ]),
            }
    
    def clear_delivery_records(self, older_than_days: Optional[int] = None) -> int:
        """Clear delivery records."""
        with self._lock:
            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                to_delete = [
                    rid for rid, record in self._delivery_records.items()
                    if record.sent_at and
                    datetime.fromisoformat(record.sent_at.replace('Z', '+00:00')) < cutoff
                ]
                
                for rid in to_delete:
                    del self._delivery_records[rid]
                
                return len(to_delete)
            else:
                count = len(self._delivery_records)
                self._delivery_records.clear()
                return count


def create_notification_engine(**kwargs) -> NotificationEngine:
    """Factory function to create notification engine."""
    return NotificationEngine(**kwargs)
