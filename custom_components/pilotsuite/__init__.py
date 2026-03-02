"""PilotSuite - Smart Home Intelligence Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

DOMAIN = "pilotsuite"
VERSION = "v12.15.0"

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the PilotSuite component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PilotSuite from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    core_url = entry.data.get("core_url", "http://localhost:8000")
    enable_ml = entry.options.get("enable_ml", True)
    enable_anomaly = entry.options.get("enable_anomaly_detection", True)
    
    hass.data[DOMAIN][entry.entry_id] = {
        "core_url": core_url,
        "enable_ml": enable_ml,
        "enable_anomaly": enable_anomaly,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
