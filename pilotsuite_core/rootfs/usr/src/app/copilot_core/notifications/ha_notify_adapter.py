"""HomeAssistant Notify Service Adapter for PilotSuite.

Provides integration with HomeAssistant's notify.* entities for push notifications.

Supported notify services:
- notify.mobile_app_* — Mobile app notifications (iOS/Android)
- notify.telegram — Telegram bot notifications
- notify.whatsapp — WhatsApp notifications
- notify.pushover — Pushover notifications
- notify.email — Email notifications

Features:
- Device registration and management
- Priority/category mapping to HA payload
- Health check and connection testing
- Support for HA notify data payload (title, message, data)

Usage:
    adapter =HANotifyAdapter(hass)
    adapter.register_ha_device(user_id, "notify.mobile_app_iphone")
    adapter.send_to_ha_service(device_id, "Alert", "High priority message", priority="high")

Author: PilotSuite Team
Version: 1.0.0
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Priority mapping from PilotSuite to HomeAssistant
PRIORITY_MAP = {
    "low": {"priority": 0, "urgency": "low"},
    "normal": {"priority": 1, "urgency": "normal"},
    "high": {"priority": 2, "urgency": "high"},
    "urgent": {"priority": 3, "urgency": "emergency"},
    "CRITICAL": {"priority": 3, "urgency": "emergency"},
    "HIGH": {"priority": 2, "urgency": "high"},
    "NORMAL": {"priority": 1, "urgency": "normal"},
    "LOW": {"priority": 0, "urgency": "low"},
}

# Category mapping for mobile apps
CATEGORY_MAP = {
    "mood_change": "mood",
    "alert": "alert",
    "suggestion": "suggestion",
    "system": "system",
    "info": "info",
    "warning": "warning",
    "error": "error",
}

# Supported notify service types
SUPPORTED_NOTIFY_SERVICES = {
    "mobile_app": "Mobile app notifications (iOS/Android Companion App)",
    "telegram": "Telegram bot notifications",
    "whatsapp": "WhatsApp notifications",
    "pushover": "Pushover push notifications",
    "email": "Email notifications",
    "signal": "Signal messenger notifications",
    "slack": "Slack workspace notifications",
}


@dataclass
class HADevice:
    """HomeAssistant device registration data."""
    id: str = field(default_factory=lambda: str(datetime.now(timezone.utc).timestamp()))
    user_id: str = ""
    ha_entity_id: str = ""
    device_name: str = ""
    device_type: str = "mobile"  # mobile, telegram, whatsapp, etc.
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            dict[str, Any]: Dictionary containing device details.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ha_entity_id": self.ha_entity_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_used": self.last_used,
        }


class HANotifyAdapter:
    """Adapter for HomeAssistant notify services.
    
    This adapter provides a unified interface for sending notifications
    through HomeAssistant's notify.* entities. It handles device registration,
    priority mapping, and payload construction for different notification services.
    
    Attributes:
        hass: HomeAssistant instance for service calls.
        _devices: Dictionary of registered devices by user_id.
        _notify_services: Cache of available notify services.
    """
    
    def __init__(self, hass: HomeAssistant | None = None) -> None:
        """Initialize the HA Notify adapter.
        
        Args:
            hass: Optional HomeAssistant instance. Can be set later via set_hass().
        """
        self.hass = hass
        self._devices: dict[str, list[HADevice]] = {}
        self._notify_services: list[str] = []
    
    def set_hass(self, hass: HomeAssistant) -> None:
        """Set HomeAssistant instance.
        
        Args:
            hass: HomeAssistant instance for service calls.
        """
        self.hass = hass
        self._refresh_notify_services()
    
    def _refresh_notify_services(self) -> None:
        """Refresh the list of available notify services from HA."""
        if not self.hass:
            return
        
        try:
            services = self.hass.services.async_services().get("notify", {})
            self._notify_services = list(services.keys())
            _LOGGER.debug("Available notify services: %s", self._notify_services)
        except Exception as e:
            _LOGGER.warning("Failed to refresh notify services: %s", e)
            self._notify_services = []
    
    def _get_notify_service_name(self, entity_id: str) -> str:
        """Extract notify service name from entity ID.
        
        Args:
            entity_id: HA entity ID (e.g., 'notify.mobile_app_iphone').
        
        Returns:
            str: Service name (e.g., 'mobile_app_iphone').
        """
        if entity_id.startswith("notify."):
            return entity_id[7:]  # Remove 'notify.' prefix
        return entity_id
    
    def _build_payload(
        self,
        message: str,
        title: str = "",
        priority: str = "normal",
        notification_type: str = "info",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build HomeAssistant notify service payload.
        
        Args:
            message: Notification message body.
            title: Optional notification title.
            priority: Priority level (low, normal, high, urgent).
            notification_type: Type for category mapping.
            data: Optional additional data dictionary.
        
        Returns:
            dict[str, Any]: Payload dictionary for HA notify service call.
        """
        payload: dict[str, Any] = {
            "message": message,
        }
        
        if title:
            payload["title"] = title
        
        # Add priority/urgency mapping (handle None)
        priority_key = priority.lower() if priority else "normal"
        priority_config = PRIORITY_MAP.get(priority_key, PRIORITY_MAP["normal"])
        
        # Add data payload with priority and category
        payload_data: dict[str, Any] = {
            "priority": priority_config["priority"],
            "urgency": priority_config["urgency"],
        }
        
        # Add category for mobile apps
        category = CATEGORY_MAP.get(notification_type, "info")
        payload_data["category"] = category
        
        # Merge additional data
        if data:
            payload_data.update(data)
        
        payload["data"] = payload_data
        
        return payload
    
    def _is_service_available(self, service_name: str) -> bool:
        """Check if a notify service is available.
        
        Args:
            service_name: Name of the notify service.
        
        Returns:
            bool: True if service is available, False otherwise.
        """
        return service_name in self._notify_services
    
    def send_to_ha_service(
        self,
        device_id: str,
        message: str,
        priority: str = "normal",
        title: str = "",
        notification_type: str = "info",
        data: dict[str, Any] | None = None,
    ) -> bool:
        """Send notification via HomeAssistant notify service.
        
        Args:
            device_id: ID of the registered device to send to.
            message: Notification message body.
            priority: Priority level (low, normal, high, urgent).
            title: Optional notification title.
            notification_type: Type for category mapping.
            data: Optional additional data dictionary.
        
        Returns:
            bool: True if notification was sent successfully, False otherwise.
        
        Raises:
            ValueError: If device_id is not registered.
            RuntimeError: If HomeAssistant instance is not configured.
        """
        if not self.hass:
            _LOGGER.error("HomeAssistant instance not configured")
            raise RuntimeError("HomeAssistant instance not configured")
        
        # Find device
        device = self._find_device(device_id)
        if not device:
            _LOGGER.error("Device not found: %s", device_id)
            raise ValueError(f"Device not found: {device_id}")
        
        if not device.enabled:
            _LOGGER.warning("Device is disabled: %s", device_id)
            return False
        
        # Extract service name from entity_id
        service_name = self._get_notify_service_name(device.ha_entity_id)
        
        # Check if service is available
        if not self._is_service_available(service_name):
            _LOGGER.warning("Notify service not available: %s", service_name)
            # Try to refresh services
            self._refresh_notify_services()
            if not self._is_service_available(service_name):
                return False
        
        # Build payload
        payload = self._build_payload(
            message=message,
            title=title,
            priority=priority,
            notification_type=notification_type,
            data=data,
        )
        
        try:
            # Call HA notify service
            self.hass.services.call(
                "notify",
                service_name,
                payload,
                blocking=False,
            )
            
            # Update last_used timestamp
            device.last_used = datetime.now(timezone.utc).isoformat()
            
            _LOGGER.info(
                "Sent HA notification to %s [%s]: %s",
                device.ha_entity_id,
                priority.upper(),
                message[:50] + "..." if len(message) > 50 else message,
            )
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to send HA notification: %s", e)
            return False
    
    def register_ha_device(
        self,
        user_id: str,
        ha_entity_id: str,
        device_name: str = "",
        device_type: str | None = None,
    ) -> HADevice:
        """Register a HomeAssistant notify device.
        
        Args:
            user_id: User ID to associate the device with.
            ha_entity_id: HomeAssistant notify entity ID (e.g., 'notify.mobile_app_iphone').
            device_name: Optional human-readable device name.
            device_type: Device type (mobile, telegram, whatsapp, etc.). Auto-detected if None.
        
        Returns:
            HADevice: The registered device object.
        
        Raises:
            ValueError: If ha_entity_id is invalid or not a notify entity.
        """
        # Validate entity_id format
        if not ha_entity_id.startswith("notify."):
            raise ValueError(f"Invalid entity_id: must start with 'notify.' (got: {ha_entity_id})")
        
        # Determine device type from entity_id if not provided
        if device_type is None:
            if "mobile_app" in ha_entity_id:
                device_type = "mobile"
            elif "telegram" in ha_entity_id:
                device_type = "telegram"
            elif "whatsapp" in ha_entity_id:
                device_type = "whatsapp"
            else:
                device_type = "other"
        
        # Create device
        device = HADevice(
            user_id=user_id,
            ha_entity_id=ha_entity_id,
            device_name=device_name or ha_entity_id,
            device_type=device_type,
        )
        
        # Add to user's devices
        if user_id not in self._devices:
            self._devices[user_id] = []
        
        self._devices[user_id].append(device)
        
        _LOGGER.info(
            "Registered HA device: %s (%s) for user %s",
            ha_entity_id,
            device_type,
            user_id,
        )
        
        return device
    
    def unregister_ha_device(self, device_id: str) -> bool:
        """Unregister a HomeAssistant device.
        
        Args:
            device_id: ID of the device to unregister.
        
        Returns:
            bool: True if device was found and unregistered, False otherwise.
        """
        for user_id, devices in self._devices.items():
            for i, device in enumerate(devices):
                if device.id == device_id:
                    devices.pop(i)
                    _LOGGER.info("Unregistered HA device: %s", device_id)
                    return True
        return False
    
    def get_ha_devices(self, user_id: str) -> list[HADevice]:
        """Get all registered devices for a user.
        
        Args:
            user_id: User ID to get devices for.
        
        Returns:
            list[HADevice]: List of registered devices.
        """
        return self._devices.get(user_id, [])
    
    def get_all_devices(self) -> list[HADevice]:
        """Get all registered devices across all users.
        
        Returns:
            list[HADevice]: List of all registered devices.
        """
        all_devices = []
        for devices in self._devices.values():
            all_devices.extend(devices)
        return all_devices
    
    def _find_device(self, device_id: str) -> HADevice | None:
        """Find a device by ID.
        
        Args:
            device_id: Device ID to search for.
        
        Returns:
            Optional[HADevice]: Device object or None if not found.
        """
        for devices in self._devices.values():
            for device in devices:
                if device.id == device_id:
                    return device
        return None
    
    def test_ha_connection(self) -> dict[str, Any]:
        """Test HomeAssistant connection and notify service availability.
        
        Returns:
            dict[str, Any]: Connection test results with status and details.
        """
        result: dict[str, Any] = {
            "success": False,
            "hass_connected": False,
            "notify_services_available": False,
            "services_count": 0,
            "services": [],
            "error": None,
        }
        
        # Check HA connection
        if not self.hass:
            result["error"] = "HomeAssistant instance not configured"
            return result
        
        result["hass_connected"] = True
        
        try:
            # Refresh and check notify services
            self._refresh_notify_services()
            result["notify_services_available"] = len(self._notify_services) > 0
            result["services_count"] = len(self._notify_services)
            result["services"] = self._notify_services
            
            result["success"] = True
            
            _LOGGER.info(
                "HA connection test: %s, %d notify services available",
                "OK" if result["success"] else "FAILED",
                len(self._notify_services),
            )
            
        except Exception as e:
            result["error"] = str(e)
            _LOGGER.error("HA connection test failed: %s", e)
        
        return result
    
    def get_available_notify_services(self) -> list[str]:
        """Get list of available notify services.
        
        Returns:
            list[str]: List of notify service names.
        """
        if not self._notify_services:
            self._refresh_notify_services()
        return self._notify_services
    
    def enable_device(self, device_id: str) -> bool:
        """Enable a registered device.
        
        Args:
            device_id: ID of the device to enable.
        
        Returns:
            bool: True if device was found and enabled, False otherwise.
        """
        device = self._find_device(device_id)
        if device:
            device.enabled = True
            return True
        return False
    
    def disable_device(self, device_id: str) -> bool:
        """Disable a registered device.
        
        Args:
            device_id: ID of the device to disable.
        
        Returns:
            bool: True if device was found and disabled, False otherwise.
        """
        device = self._find_device(device_id)
        if device:
            device.enabled = False
            return True
        return False


# Singleton instance for module-level access
_adapter: Optional[HANotifyAdapter] = None


def get_ha_notify_adapter(hass: HomeAssistant | None = None) -> HANotifyAdapter:
    """Get the singleton HA Notify adapter.
    
    Args:
        hass: Optional HomeAssistant instance to set on the adapter.
    
    Returns:
        HANotifyAdapter: The singleton adapter instance.
    """
    global _adapter
    if _adapter is None:
        _adapter = HANotifyAdapter(hass)
    elif hass and _adapter.hass is None:
        _adapter.set_hass(hass)
    return _adapter


def reset_ha_notify_adapter() -> None:
    """Reset the singleton adapter (useful for testing)."""
    global _adapter
    _adapter = None


__all__ = [
    "HANotifyAdapter",
    "HADevice",
    "get_ha_notify_adapter",
    "reset_ha_notify_adapter",
    "PRIORITY_MAP",
    "CATEGORY_MAP",
    "SUPPORTED_NOTIFY_SERVICES",
]
