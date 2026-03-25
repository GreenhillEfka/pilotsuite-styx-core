"""Synapse Integration — Automation ↔ Neuron Mapping Layer.

Maps HA Automations to Core neurons:
  - Extracts trigger/condition/action entity_ids from automations
  - Resolves entity_ids → neuron_ids via Synapse Contract
  - Stores automation → [neuron_ids] mapping in zone_synapses
  - Triggered by presence changes → re-evaluates affected automations

This is the Synapsen-Layer: the connection between HA automation entities
and the Core neural network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synapse Link: automation → neuron_ids
# ---------------------------------------------------------------------------

@dataclass
class SynapseLink:
    """A link between an automation and its participating neurons."""
    automation_id: str
    automation_name: str
    zone_id: str
    trigger_entities: List[str] = field(default_factory=list)
    condition_entities: List[str] = field(default_factory=list)
    action_entities: List[str] = field(default_factory=list)
    all_entities: List[str] = field(default_factory=list)
    neuron_ids: List[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None


# ---------------------------------------------------------------------------
# SynapseRegistry — stores all automation ↔ neuron links
# ---------------------------------------------------------------------------

class SynapseRegistry:
    """
    Registry of all SynapseLinks (automation → neurons).

    In-memory store with persistence hooks.
    Use `scan_automations()` to populate from HA,
    or `register_link()` to add manually.
    """

    def __init__(self):
        self._links: Dict[str, SynapseLink] = {}
        self._entity_to_automations: Dict[str, Set[str]] = {}  # entity_id → {automation_ids}

    def register_link(self, link: SynapseLink) -> None:
        """Register or update a SynapseLink."""
        link.last_updated = datetime.now(timezone.utc)
        self._links[link.automation_id] = link

        # Update entity → automations index
        for entity_id in link.all_entities:
            if entity_id not in self._entity_to_automations:
                self._entity_to_automations[entity_id] = set()
            self._entity_to_automations[entity_id].add(link.automation_id)

        _LOGGER.debug(f"SynapseLink registered: {link.automation_id} → {link.neuron_ids}")

    def get_link(self, automation_id: str) -> Optional[SynapseLink]:
        return self._links.get(automation_id)

    def get_automations_for_entity(self, entity_id: str) -> List[SynapseLink]:
        """Get all automations that use a given entity."""
        auto_ids = self._entity_to_automations.get(entity_id, set())
        return [self._links[aid] for aid in auto_ids if aid in self._links]

    def get_neuron_ids_for_automation(self, automation_id: str) -> List[str]:
        """Get all neuron_ids that an automation touches."""
        link = self._links.get(automation_id)
        return link.neuron_ids if link else []

    def get_automations_for_zone(self, zone_id: str) -> List[SynapseLink]:
        """Get all automation synapses for a zone."""
        return [link for link in self._links.values() if link.zone_id == zone_id]

    def list_all(self) -> List[SynapseLink]:
        return list(self._links.values())

    def clear(self) -> None:
        self._links.clear()
        self._entity_to_automations.clear()


# ---------------------------------------------------------------------------
# SynapseScanner — extracts entities from HA automations
# ---------------------------------------------------------------------------

# Global registry instance
_registry = SynapseRegistry()


def get_synapse_registry() -> SynapseRegistry:
    return _registry


def resolve_entity_to_neuron(entity_id: str, entity_state: Any = None) -> str:
    """
    Resolve a single HA entity_id to a Core neuron_id.

    Format: {neuron_type}.{normalized_name}
    Examples:
        light.living_room    → state.living_room_light
        sensor.temperature   → context.temperature_sensor
        person.andreas        → presence.andreas
    """
    # Import here to avoid circular dependency
    from copilot_core.neurons.feeding import _entity_domain, _ENTITY_TYPE_MAP

    domain = _entity_domain(entity_id)
    neuron_type = _ENTITY_TYPE_MAP.get(domain, "state")

    # Normalize entity name (remove domain prefix, sanitize)
    name = entity_id.replace(f"{domain}.", "").replace(".", "_").replace("-", "_")

    return f"{neuron_type}.{name}"


def scan_automation_entities(
    trigger_entities: List[str],
    condition_entities: List[str],
    action_entities: List[str],
) -> List[str]:
    """
    Given automation entity lists, return all unique neuron_ids.

    This is the core resolution function:
        [entity_ids] → [neuron_ids] via Synapse Contract
    """
    all_entities = trigger_entities + condition_entities + action_entities
    seen = set()
    neuron_ids = []

    for entity_id in all_entities:
        if entity_id not in seen:
            seen.add(entity_id)
            neuron_ids.append(resolve_entity_to_neuron(entity_id))

    return neuron_ids


def register_automation_synapse(
    automation_id: str,
    automation_name: str,
    zone_id: str,
    trigger_entities: Optional[List[str]] = None,
    condition_entities: Optional[List[str]] = None,
    action_entities: Optional[List[str]] = None,
) -> SynapseLink:
    """
    Register a complete automation → neuron synapse link.

    Call this when:
      - HA reports a new/modified automation
      - Zone presence changes and automations need re-evaluation
    """
    trigger_entities = trigger_entities or []
    condition_entities = condition_entities or []
    action_entities = action_entities or []
    all_entities = trigger_entities + condition_entities + action_entities

    neuron_ids = scan_automation_entities(
        trigger_entities, condition_entities, action_entities
    )

    link = SynapseLink(
        automation_id=automation_id,
        automation_name=automation_name,
        zone_id=zone_id,
        trigger_entities=trigger_entities,
        condition_entities=condition_entities,
        action_entities=action_entities,
        all_entities=all_entities,
        neuron_ids=neuron_ids,
        last_updated=datetime.now(timezone.utc),
    )

    _registry.register_link(link)
    return link


def get_zone_automation_synapses(zone_id: str) -> List[SynapseLink]:
    """Get all SynapseLinks for automations in a given zone."""
    return _registry.get_automations_for_zone(zone_id)


def get_affected_automations_on_entity_change(entity_id: str) -> List[str]:
    """
    When an entity changes, which automations might be affected?
    Returns list of automation_ids.
    """
    links = _registry.get_automations_for_entity(entity_id)
    return [link.automation_id for link in links]
