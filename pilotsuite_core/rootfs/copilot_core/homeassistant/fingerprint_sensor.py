"""Home Assistant Sensor Integration for Wi-Fi/BLE Fingerprinting (P3-008).

Provides Home Assistant sensor entities for device presence detection
using Wi-Fi and BLE fingerprint analysis.

Sensors:
- sensor.fingerprint_device_<id>_presence — Binary presence sensor
- sensor.fingerprint_device_<id>_confidence — Confidence score (0-100%)
- sensor.fingerprint_device_<id>_rssi — Current signal strength
- sensor.fingerprint_device_<id>_location — Inferred location zone
- sensor.fingerprint_total_devices — Total tracked devices count
- sensor.fingerprint_present_count — Currently present devices count

Setup:
1. Add to configuration.yaml:
   sensor:
     - platform: fingerprint_presence
       api_url: http://localhost:8999
       api_token: YOUR_API_TOKEN
       scan_interval: 30

2. Or use the integration UI to configure connection.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
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

DEFAULT_URL = "http://localhost:8999"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_TIMEOUT = 10

CONF_API_TOKEN = "api_token"
CONF_API_URL = "api_url"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_API_URL, default=DEFAULT_URL): cv.url,
        vol.Required(CONF_API_TOKEN): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


# =============================================================================
# Data Coordinator
# =============================================================================


class FingerprintDataCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching fingerprint data from API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_url: str,
        api_token: str,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="fingerprint_presence",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.session = async_get_clientsession(hass)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the fingerprint API."""
        try:
            async with async_timeout.timeout(self.timeout):
                # Get devices list
                devices_data = await self._fetch_json(
                    f"{self.api_url}/api/v1/presence/fingerprint/devices"
                )

                # Get detection history (recent detections)
                history_data = await self._fetch_json(
                    f"{self.api_url}/api/v1/presence/fingerprint/history?limit=50"
                )

                return {
                    "devices": devices_data.get("devices", []),
                    "total": devices_data.get("total", 0),
                    "history": history_data.get("history", []),
                    "present_count": sum(
                        1
                        for h in history_data.get("history", [])
                        if h.get("detection", {}).get("is_present", False)
                    ),
                }

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching fingerprint data: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching fingerprint data: {err}") from err

    async def _fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch JSON from API with authentication."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                raise aiohttp.ClientError(f"API returned status {response.status}")
            return await response.json()


# =============================================================================
# Sensor Entities
# =============================================================================


class FingerprintPresenceSensor(CoordinatorEntity, SensorEntity):
    """Binary presence sensor for a fingerprint device."""

    _attr_device_class = SensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: FingerprintDataCoordinator,
        device_id: str,
        device_type: str,
    ):
        """Initialize the presence sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_type = device_type
        self._attr_unique_id = f"fingerprint_{device_id}_presence"
        self._attr_name = f"Fingerprint {device_id[:8]} Presence"

    @property
    def native_value(self) -> bool:
        """Return the current presence state."""
        # Find latest detection for this device
        for entry in self.coordinator.data.get("history", []):
            if entry.get("device_id") == self._device_id:
                return entry.get("detection", {}).get("is_present", False)
        return False

    @property
    def is_on(self) -> bool:
        """Return True if device is present."""
        return self.native_value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", self._device_id)},
            name=f"Fingerprint Device {self._device_id[:8]}",
            manufacturer="PilotSuite",
            model=f"Wi-Fi/BLE Fingerprint ({self._device_type})",
            sw_version="P3-008",
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        for entry in self.coordinator.data.get("history", []):
            if entry.get("device_id") == self._device_id:
                detection = entry.get("detection", {})
                return {
                    "confidence": detection.get("confidence"),
                    "detection_method": detection.get("detection_method"),
                    "location_zone": detection.get("location_zone"),
                    "wifi_rssi": detection.get("wifi_rssi"),
                    "ble_rssi": detection.get("ble_rssi"),
                    "last_detected": entry.get("processed_at"),
                }
        return {}


class FingerprintConfidenceSensor(CoordinatorEntity, SensorEntity):
    """Confidence score sensor for a fingerprint device."""

    _attr_device_class = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FingerprintDataCoordinator,
        device_id: str,
        device_type: str,
    ):
        """Initialize the confidence sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_type = device_type
        self._attr_unique_id = f"fingerprint_{device_id}_confidence"
        self._attr_name = f"Fingerprint {device_id[:8]} Confidence"

    @property
    def native_value(self) -> Optional[float]:
        """Return the current confidence score."""
        for entry in self.coordinator.data.get("history", []):
            if entry.get("device_id") == self._device_id:
                confidence = entry.get("detection", {}).get("confidence")
                if confidence is not None:
                    return round(confidence * 100, 1)
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", self._device_id)},
            name=f"Fingerprint Device {self._device_id[:8]}",
            manufacturer="PilotSuite",
            model=f"Wi-Fi/BLE Fingerprint ({self._device_type})",
            sw_version="P3-008",
        )


class FingerprintRSSISensor(CoordinatorEntity, SensorEntity):
    """RSSI signal strength sensor for a fingerprint device."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FingerprintDataCoordinator,
        device_id: str,
        device_type: str,
    ):
        """Initialize the RSSI sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_type = device_type
        self._attr_unique_id = f"fingerprint_{device_id}_rssi"
        self._attr_name = f"Fingerprint {device_id[:8]} RSSI"

    @property
    def native_value(self) -> Optional[float]:
        """Return the current RSSI value."""
        for entry in self.coordinator.data.get("history", []):
            if entry.get("device_id") == self._device_id:
                detection = entry.get("detection", {})
                # Prefer Wi-Fi RSSI, fall back to BLE
                rssi = detection.get("wifi_rssi") or detection.get("ble_rssi")
                if rssi is not None:
                    return float(rssi)
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", self._device_id)},
            name=f"Fingerprint Device {self._device_id[:8]}",
            manufacturer="PilotSuite",
            model=f"Wi-Fi/BLE Fingerprint ({self._device_type})",
            sw_version="P3-008",
        )


class FingerprintLocationSensor(CoordinatorEntity, SensorEntity):
    """Location zone sensor for a fingerprint device."""

    _attr_device_class = None

    def __init__(
        self,
        coordinator: FingerprintDataCoordinator,
        device_id: str,
        device_type: str,
    ):
        """Initialize the location sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_type = device_type
        self._attr_unique_id = f"fingerprint_{device_id}_location"
        self._attr_name = f"Fingerprint {device_id[:8]} Location"

    @property
    def native_value(self) -> Optional[str]:
        """Return the current location zone."""
        for entry in self.coordinator.data.get("history", []):
            if entry.get("device_id") == self._device_id:
                return entry.get("detection", {}).get("location_zone")
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", self._device_id)},
            name=f"Fingerprint Device {self._device_id[:8]}",
            manufacturer="PilotSuite",
            model=f"Wi-Fi/BLE Fingerprint ({self._device_type})",
            sw_version="P3-008",
        )


class FingerprintTotalDevicesSensor(CoordinatorEntity, SensorEntity):
    """Total count of tracked fingerprint devices."""

    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: FingerprintDataCoordinator):
        """Initialize the total devices sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "fingerprint_total_devices"
        self._attr_name = "Fingerprint Total Devices"

    @property
    def native_value(self) -> int:
        """Return the total device count."""
        return self.coordinator.data.get("total", 0)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", "hub")},
            name="Fingerprint Presence Hub",
            manufacturer="PilotSuite",
            model="Wi-Fi/BLE Fingerprint System",
            sw_version="P3-008",
        )


class FingerprintPresentCountSensor(CoordinatorEntity, SensorEntity):
    """Count of currently present fingerprint devices."""

    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: FingerprintDataCoordinator):
        """Initialize the present count sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "fingerprint_present_count"
        self._attr_name = "Fingerprint Present Count"

    @property
    def native_value(self) -> int:
        """Return the count of present devices."""
        return self.coordinator.data.get("present_count", 0)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={("fingerprint", "hub")},
            name="Fingerprint Presence Hub",
            manufacturer="PilotSuite",
            model="Wi-Fi/BLE Fingerprint System",
            sw_version="P3-008",
        )


# =============================================================================
# Setup Functions
# =============================================================================


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the fingerprint sensors from configuration.yaml."""
    api_url = config[CONF_API_URL]
    api_token = config[CONF_API_TOKEN]

    coordinator = FingerprintDataCoordinator(hass, api_url, api_token)
    await coordinator.async_config_entry_first_refresh()

    sensors = [
        FingerprintTotalDevicesSensor(coordinator),
        FingerprintPresentCountSensor(coordinator),
    ]

    async_add_entities(sensors, True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fingerprint sensors from a config entry."""
    api_url = entry.data.get(CONF_API_URL, DEFAULT_URL)
    api_token = entry.data[CONF_API_KEY]

    coordinator = FingerprintDataCoordinator(hass, api_url, api_token)
    await coordinator.async_config_entry_first_refresh()

    # Create hub sensors
    sensors = [
        FingerprintTotalDevicesSensor(coordinator),
        FingerprintPresentCountSensor(coordinator),
    ]

    # Create per-device sensors
    for device in coordinator.data.get("devices", []):
        device_id = device["device_id"]
        device_type = device.get("device_type", "unknown")

        sensors.extend(
            [
                FingerprintPresenceSensor(coordinator, device_id, device_type),
                FingerprintConfidenceSensor(coordinator, device_id, device_type),
                FingerprintRSSISensor(coordinator, device_id, device_type),
                FingerprintLocationSensor(coordinator, device_id, device_type),
            ]
        )

    async_add_entities(sensors, True)
