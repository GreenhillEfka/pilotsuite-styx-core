"""Home Assistant Notification Sensors for PilotSuite Core.

Provides Home Assistant sensor entities for notification system monitoring:
- sensor.notification_delivery_status — Current delivery status
- sensor.notification_pending_count — Pending notifications count
- sensor.notification_rate_limit_status — Rate limit status
- sensor.notification_quiet_hours — Quiet hours status
- binary_sensor.notification_channel_<name> — Channel availability

Setup:
1. Add to configuration.yaml:
   sensor:
     - platform: pilotsuite_notifications
       api_url: http://localhost:8909
       api_token: YOUR_API_TOKEN
       scan_interval: 60

2. Or configure via Home Assistant integration UI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_URL = "http://localhost:8909"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_TIMEOUT = 10

CONF_API_TOKEN = "api_token"
CONF_API_URL = "api_url"
CONF_USER_ID = "user_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_API_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(CONF_API_TOKEN): cv.string,
        vol.Optional(CONF_USER_ID): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


# =============================================================================
# Data Coordinator
# =============================================================================


class NotificationDataCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching notification system data from API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_url: str,
        api_token: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="pilotsuite_notifications",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.user_id = user_id
        self.timeout = timeout
        self._session = None

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self._session = async_get_clientsession(self.hass)

    async def _async_fetch_data(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetch data from a specific endpoint."""
        url = f"{self.api_url}/api/v1/notifications/{endpoint}"
        headers = {}

        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            async with async_timeout.timeout(self.timeout):
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") or data
                    elif response.status == 401:
                        _LOGGER.warning("Authentication failed for notifications API")
                    else:
                        _LOGGER.warning(
                            "API request failed with status %d", response.status
                        )
        except aiohttp.ClientError as e:
            _LOGGER.debug("HTTP error fetching notification data: %s", e)
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout fetching notification data")

        return None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch all notification data."""
        data = {
            "channels": {},
            "rate_limit": None,
            "quiet_hours": None,
            "pending_count": 0,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }

        # Fetch channel status
        status_data = await self._async_fetch_data("status")
        if status_data:
            data["channels"] = status_data.get("channels", {})
            data["rate_limit"] = status_data.get("rate_limit")
            data["quiet_hours"] = status_data.get("quiet_hours")
            data["delivery_engine"] = status_data.get("delivery_engine", {})

        # Fetch pending count from rate limit if available
        if data["rate_limit"]:
            data["pending_count"] = data["rate_limit"].get("count", 0)

        return data

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# Sensor Entities
# =============================================================================


class NotificationChannelSensor(CoordinatorEntity, SensorEntity):
    """Sensor for notification channel status."""

    def __init__(
        self,
        coordinator: NotificationDataCoordinator,
        channel_name: str,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._channel_name = channel_name
        self._attr_unique_id = f"notification_channel_{channel_name}"
        self._attr_name = f"Notification Channel {channel_name.title()}"
        self._attr_icon = "mdi:notification-clear-all"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the channel status."""
        if self.coordinator.data is None:
            return "unknown"

        channel_data = self.coordinator.data.get("channels", {}).get(
            self._channel_name, {}
        )

        if channel_data.get("enabled") and channel_data.get("configured"):
            return "active"
        elif channel_data.get("configured"):
            return "configured"
        elif channel_data.get("enabled"):
            return "enabled"
        else:
            return "inactive"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        channel_data = self.coordinator.data.get("channels", {}).get(
            self._channel_name, {}
        )

        return {
            "enabled": channel_data.get("enabled", False),
            "configured": channel_data.get("configured", False),
            "last_update": self.coordinator.data.get("last_update"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            "identifiers": {("pilotsuite", "notifications")},
            "name": "PilotSuite Notifications",
            "manufacturer": "PilotSuite",
            "model": "Notification System",
        }


class NotificationPendingCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for pending notification count."""

    def __init__(self, coordinator: NotificationDataCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "notification_pending_count"
        self._attr_name = "Notification Pending Count"
        self._attr_icon = "mdi:email-outline"
        self._attr_native_unit_of_measurement = "notifications"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the pending count."""
        if self.coordinator.data is None:
            return 0

        return self.coordinator.data.get("pending_count", 0)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            "identifiers": {("pilotsuite", "notifications")},
            "name": "PilotSuite Notifications",
            "manufacturer": "PilotSuite",
            "model": "Notification System",
        }


class NotificationRateLimitSensor(CoordinatorEntity, SensorEntity):
    """Sensor for rate limit status."""

    def __init__(self, coordinator: NotificationDataCoordinator, user_id: Optional[str] = None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._user_id = user_id
        self._attr_unique_id = "notification_rate_limit"
        self._attr_name = "Notification Rate Limit"
        self._attr_icon = "mdi:speedometer"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the rate limit status."""
        if self.coordinator.data is None:
            return "unknown"

        rate_limit = self.coordinator.data.get("rate_limit")
        if rate_limit is None:
            return "not_limited"

        if rate_limit.get("is_limited"):
            return "limited"
        else:
            return "active"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        rate_limit = self.coordinator.data.get("rate_limit", {})
        if not rate_limit:
            return {
                "count": 0,
                "limit": 60,
                "reset_at": None,
            }

        return {
            "count": rate_limit.get("count", 0),
            "limit": rate_limit.get("limit", 60),
            "reset_at": rate_limit.get("reset_at"),
            "is_limited": rate_limit.get("is_limited", False),
            "window_start": rate_limit.get("window_start"),
            "window_end": rate_limit.get("window_end"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            "identifiers": {("pilotsuite", "notifications")},
            "name": "PilotSuite Notifications",
            "manufacturer": "PilotSuite",
            "model": "Notification System",
        }


class NotificationQuietHoursSensor(CoordinatorEntity, SensorEntity):
    """Sensor for quiet hours status."""

    def __init__(self, coordinator: NotificationDataCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "notification_quiet_hours"
        self._attr_name = "Notification Quiet Hours"
        self._attr_icon = "mdi:bell-off"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the quiet hours status."""
        if self.coordinator.data is None:
            return "unknown"

        quiet_hours = self.coordinator.data.get("quiet_hours")
        if quiet_hours is None:
            return "inactive"

        if quiet_hours.get("is_quiet_hours"):
            return "active"
        else:
            return "inactive"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        quiet_hours = self.coordinator.data.get("quiet_hours", {})
        if not quiet_hours:
            return {
                "start_hour": 22,
                "end_hour": 7,
                "is_quiet_hours": False,
            }

        return {
            "is_quiet_hours": quiet_hours.get("is_quiet_hours", False),
            "quiet_hours_start": quiet_hours.get("quiet_hours_start", 22),
            "quiet_hours_end": quiet_hours.get("quiet_hours_end", 7),
            "current_hour": quiet_hours.get("current_hour"),
            "priority_override": quiet_hours.get("priority_override", True),
            "next_quiet_hours_start": quiet_hours.get("next_quiet_hours_start"),
            "next_quiet_hours_end": quiet_hours.get("next_quiet_hours_end"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            "identifiers": {("pilotsuite", "notifications")},
            "name": "PilotSuite Notifications",
            "manufacturer": "PilotSuite",
            "model": "Notification System",
        }


class NotificationChannelBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for notification channel availability."""

    def __init__(
        self,
        coordinator: NotificationDataCoordinator,
        channel_name: str,
    ):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._channel_name = channel_name
        self._attr_unique_id = f"notification_channel_available_{channel_name}"
        self._attr_name = f"Notification {channel_name.title()} Available"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return true if channel is available."""
        if self.coordinator.data is None:
            return False

        channel_data = self.coordinator.data.get("channels", {}).get(
            self._channel_name, {}
        )

        return channel_data.get("enabled", False) and channel_data.get("configured", False)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return {}

        channel_data = self.coordinator.data.get("channels", {}).get(
            self._channel_name, {}
        )

        return {
            "enabled": channel_data.get("enabled", False),
            "configured": channel_data.get("configured", False),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            "identifiers": {("pilotsuite", "notifications")},
            "name": "PilotSuite Notifications",
            "manufacturer": "PilotSuite",
            "model": "Notification System",
        }


# =============================================================================
# Setup Functions
# =============================================================================


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the notification sensors from configuration.yaml."""
    api_url = config.get(CONF_API_URL, DEFAULT_URL)
    api_token = config.get(CONF_API_TOKEN)
    user_id = config.get(CONF_USER_ID)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    await async_setup_entry(
        hass,
        type("MockConfigEntry", (), {
            "data": {
                "api_url": api_url,
                "api_token": api_token,
                "user_id": user_id,
            },
            "options": {"scan_interval": scan_interval.total_seconds()},
        })(),
        async_add_entities,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the notification sensors from a config entry."""
    api_url = config_entry.data.get("api_url", DEFAULT_URL)
    api_token = config_entry.data.get("api_token")
    user_id = config_entry.data.get("user_id")

    coordinator = NotificationDataCoordinator(
        hass,
        api_url=api_url,
        api_token=api_token,
        user_id=user_id,
    )

    await coordinator.async_config_entry_first_refresh()

    # Create sensors for all known channels
    known_channels = ["telegram", "pushover", "email", "webhook", "ha_notification"]
    entities = []

    # Channel status sensors
    for channel in known_channels:
        entities.append(NotificationChannelSensor(coordinator, channel))
        entities.append(NotificationChannelBinarySensor(coordinator, channel))

    # System sensors
    entities.append(NotificationPendingCountSensor(coordinator))
    entities.append(NotificationRateLimitSensor(coordinator, user_id))
    entities.append(NotificationQuietHoursSensor(coordinator))

    async_add_entities(entities)


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    # Nothing special to clean up
    return True


__all__ = [
    "PLATFORM_SCHEMA",
    "async_setup_platform",
    "async_setup_entry",
    "async_unload_entry",
    "NotificationDataCoordinator",
    "NotificationChannelSensor",
    "NotificationChannelBinarySensor",
    "NotificationPendingCountSensor",
    "NotificationRateLimitSensor",
    "NotificationQuietHoursSensor",
]
