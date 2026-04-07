"""PilotSuite Notify — Notification Service."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.notify import BaseNotificationService
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

logger = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    discovery_info: Optional[Dict[str, Any]] = None,
) -> BaseNotificationService:
    """Get the PilotSuite notification service."""
    return PilotSuiteNotificationService(hass, config_entry)


class PilotSuiteNotificationService(BaseNotificationService):
    """Implement the PilotSuite notification service."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the notification service."""
        self.hass = hass
        self.config_entry = config_entry

    async def async_send_message(self, message: str = "", title: str = "", **kwargs) -> None:
        """Send a notification message."""
        # Get notification manager from hass.data
        manager = self.hass.data.get(DOMAIN, {}).get("notification_manager")
        
        if manager:
            from .integrations.notifications import Notification, NotificationPriority
            
            # Parse priority from kwargs
            priority_str = kwargs.get("priority", "normal")
            priority_map = {
                "low": NotificationPriority.LOW,
                "normal": NotificationPriority.NORMAL,
                "high": NotificationPriority.HIGH,
                "urgent": NotificationPriority.EMERGENCY,
            }
            priority = priority_map.get(priority_str.lower(), NotificationPriority.NORMAL)
            
            notification = Notification(
                title=title or "PilotSuite",
                message=message,
                priority=priority,
                url=kwargs.get("url"),
                url_title=kwargs.get("url_title"),
            )
            
            await manager.send(notification)
        else:
            logger.warning("Notification manager not initialized")
