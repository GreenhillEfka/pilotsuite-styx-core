"""
User Profile and Notification Preferences Contracts for PilotSuite Core.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    TELEGRAM = "telegram"
    PUSH = "push"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationCategory(str, Enum):
    """Notification categories for filtering."""
    ALERT = "alert"
    INFO = "info"
    REMINDER = "reminder"
    DIGEST = "digest"
    ACTION_REQUIRED = "action_required"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DeliveryMode(str, Enum):
    """Delivery mode preferences."""
    IMMEDIATE = "immediate"
    BATCHED = "batched"
    DIGEST_ONLY = "digest_only"
    SILENT = "silent"


@dataclass
class ChannelPreferencesV1:
    """
    Preferences for a single notification channel.
    """
    channel: NotificationChannel
    enabled: bool = True
    delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE
    min_priority: NotificationPriority = NotificationPriority.LOW
    allowed_categories: List[NotificationCategory] = field(default_factory=lambda: list(NotificationCategory))
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    max_per_hour: Optional[int] = None
    max_per_day: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "channel": self.channel.value,
            "enabled": self.enabled,
            "delivery_mode": self.delivery_mode.value,
            "min_priority": self.min_priority.value,
            "allowed_categories": [c.value for c in self.allowed_categories],
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "max_per_hour": self.max_per_hour,
            "max_per_day": self.max_per_day,
        }


@dataclass
class NotificationPreferencesV1:
    """
    User notification preferences across all channels.
    """
    user_id: str
    global_enabled: bool = True
    global_quiet_hours_start: Optional[str] = None
    global_quiet_hours_end: Optional[str] = None
    do_not_disturb: bool = False
    do_not_disturb_until: Optional[datetime] = None
    default_channel: NotificationChannel = NotificationChannel.TELEGRAM
    channel_preferences: dict = field(default_factory=dict)
    digest_schedule: Optional[str] = None  # cron expression
    digest_enabled: bool = False
    updated_at: Optional[datetime] = None
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "global_enabled": self.global_enabled,
            "global_quiet_hours_start": self.global_quiet_hours_start,
            "global_quiet_hours_end": self.global_quiet_hours_end,
            "do_not_disturb": self.do_not_disturb,
            "do_not_disturb_until": self.do_not_disturb_until.isoformat() if self.do_not_disturb_until else None,
            "default_channel": self.default_channel.value,
            "channel_preferences": {
                k: v.to_dict() if isinstance(v, ChannelPreferencesV1) else v
                for k, v in self.channel_preferences.items()
            },
            "digest_schedule": self.digest_schedule,
            "digest_enabled": self.digest_enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "revision": self.revision,
        }


@dataclass
class UserProfileV1:
    """
    User profile with basic information and settings.
    """
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    timezone: str = "Europe/Berlin"
    language: str = "de"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    revision: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "timezone": self.timezone,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
            "revision": self.revision,
        }


@dataclass
class UserSettingsV1:
    """
    Combined user profile and notification preferences.
    """
    profile: UserProfileV1
    preferences: NotificationPreferencesV1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "profile": self.profile.to_dict(),
            "preferences": self.preferences.to_dict(),
        }
