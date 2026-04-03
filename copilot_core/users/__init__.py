"""
Users module for PilotSuite Core.

Provides user profile and notification preferences management.
"""

from .contracts import (
    UserProfileV1,
    NotificationPreferencesV1,
    ChannelPreferencesV1,
    UserSettingsV1,
    NotificationChannel,
    NotificationCategory,
    NotificationPriority,
    DeliveryMode,
)
from .store import UserStore

__all__ = [
    "UserProfileV1",
    "NotificationPreferencesV1",
    "ChannelPreferencesV1",
    "UserSettingsV1",
    "NotificationChannel",
    "NotificationCategory",
    "NotificationPriority",
    "DeliveryMode",
    "UserStore",
]
