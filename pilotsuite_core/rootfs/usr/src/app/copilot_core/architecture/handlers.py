"""CQRS Command & Query Handlers (Slice 188 - Codex Workers).

Implements the first batch of concrete handlers for the CQRS Bus.
Focus: Zone Management & Module State.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from copilot_core.architecture.hexagonal_cqrs import Command, Query

_LOGGER = logging.getLogger(__name__)

# --- Commands (Write) ---
@dataclass
class SetModuleStateCommand(Command):
    module_id: str
    state: str

@dataclass
class CreateZoneCommand(Command):
    zone_id: str
    name: str
    zone_type: str

# --- Queries (Read) ---
@dataclass
class GetZoneOverviewQuery(Query[Dict[str, Any]]):
    pass

@dataclass
class GetModuleRegistryQuery(Query[Dict[str, str]]):
    pass

# --- Handlers ---
class ZoneCommandHandler:
    def handle_create_zone(self, cmd: CreateZoneCommand):
        _LOGGER.info("CQRS: Creating zone %s", cmd.zone_id)
        # Logic to call HabitusZoneEngine
        return True

class ModuleCommandHandler:
    def handle_set_state(self, cmd: SetModuleStateCommand):
        _LOGGER.info("CQRS: Setting module %s to %s", cmd.module_id, cmd.state)
        # Logic to call ModuleRegistry
        return True

class RegistryQueryHandler:
    def handle_get_registry(self, query: GetModuleRegistryQuery):
        # Mock retrieval
        return {"presence": "active", "light": "active"}

# Registration Helper
def register_base_handlers(bus):
    z_handler = ZoneCommandHandler()
    m_handler = ModuleCommandHandler()
    q_handler = RegistryQueryHandler()
    
    bus.register(CreateZoneCommand, z_handler.handle_create_zone)
    bus.register(SetModuleStateCommand, m_handler.handle_set_state)
    bus.register(GetModuleRegistryQuery, q_handler.handle_get_registry)
