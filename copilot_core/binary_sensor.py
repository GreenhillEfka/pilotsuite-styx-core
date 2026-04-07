"""PilotSuite Binary Sensors — Status Binary Sensors."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PilotSuite binary sensors."""
    # Add binary sensors here when implemented
    sensors = []
    async_add_entities(sensors, True)


class PilotSuiteBinarySensorEntity(BinarySensorEntity):
    """Base class for PilotSuite binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, name: str, key: str):
        """Initialize binary sensor."""
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
