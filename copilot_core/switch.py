"""PilotSuite Switches — Control Switches."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
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
    """Set up PilotSuite switches."""
    # Add switches here when implemented
    switches = []
    async_add_entities(switches, True)


class PilotSuiteSwitchEntity(SwitchEntity):
    """Base class for PilotSuite switches."""

    _attr_has_entity_name = True

    def __init__(self, name: str, key: str):
        """Initialize switch."""
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
