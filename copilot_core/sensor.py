"""PilotSuite Sensors — System and Status Sensors."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PilotSuite sensors."""
    # Add sensors here when implemented
    sensors = []
    async_add_entities(sensors, True)


class PilotSuiteSensorEntity(CoordinatorEntity, SensorEntity):
    """Base class for PilotSuite sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, name: str, key: str):
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
