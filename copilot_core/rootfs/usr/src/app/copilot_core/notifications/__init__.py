"""Notifications module for PilotSuite (v5.8.0).

Includes:
- NotificationEngine: Core notification engine
- HANotifyAdapter: HomeAssistant notify service integration
- Notification, Priority: Data structures
"""

from .engine import NotificationEngine, Notification, Priority  # noqa: F401
from .ha_notify_adapter import (  # noqa: F401
    HANotifyAdapter,
    HADevice,
    get_ha_notify_adapter,
    reset_ha_notify_adapter,
    PRIORITY_MAP,
    CATEGORY_MAP,
    SUPPORTED_NOTIFY_SERVICES,
)
