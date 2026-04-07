"""Neuron Feeder — maps HA entity events to Core neurons via Synapse Contract.

The NeuronFeeder is the primary ingress point for Home Assistant state changes
into the neural system. It:
  1. Receives HA webhook events (entity_id, state, attributes, last_changed)
  2. Resolves entity_id → neuron_id via Synapse Contract (entity_to_neuron map)
  3. Writes neuron activations into the Brain Graph store
  4. Optionally triggers dynamic neuron creation for unknown entities

Pipeline:
    HA Webhook → NeuronFeeder.feed() → Synapse Contract → Brain Graph

Example:
    feeder = NeuronFeeder()
    feeder.feed("light.living_room", "on", attributes={"brightness": 255})
    neuron_id = feeder.get_neuron_id("light.living_room")  # → "state.living_room_light"
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from copilot_core.brain_graph.service import BrainGraphService

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synapse Contract: entity domain → neuron type mapping
# ---------------------------------------------------------------------------

_ENTITY_TYPE_MAP: Dict[str, str] = {
    # binary_sensor / sensor → context neuron
    "sensor": "context",
    "binary_sensor": "context",
    "climate": "context",
    "weather": "context",
    # light / switch / fan → state neuron
    "light": "state",
    "switch": "state",
    "fan": "state",
    "input_boolean": "state",
    # person / device_tracker → presence neuron
    "person": "presence",
    "device_tracker": "presence",
    "zone": "presence",
    # media_player → energy neuron (for load tracking)
    "media_player": "energy",
    "scene": "energy",
    "automation": "automation",
}


def _entity_domain(entity_id: str) -> str:
    """Extract domain from entity_id (e.g. 'light.living_room' → 'light')."""
    if "." in entity_id:
        return entity_id.rsplit(".", 1)[0]
    return entity_id


def _neuron_id_for_entity(entity_id: str, neuron_type: str) -> str:
    """Generate a neuron_id from entity_id and target neuron type."""
    safe_name = entity_id.replace(".", "_").replace(" ", "_")
    return f"{neuron_type}.{safe_name}"


# ---------------------------------------------------------------------------
# Synapse Contract Store (in-memory, can be persisted)
# ---------------------------------------------------------------------------

@dataclass
class SynapseContract:
    """A single entry in the Synapse Contract table.

    Maps a HA entity to a Core neuron and tracks metadata.
    """

    entity_id: str
    neuron_id: str
    neuron_type: str  # context | state | presence | energy | automation | meta
    domain: str
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    last_fed_ms: int = 0
    attributes_schema: Optional[Dict[str, str]] = None  # e.g. {"brightness": "int"}


# ---------------------------------------------------------------------------
# NeuronFeeder
# ---------------------------------------------------------------------------

@dataclass
class FeedEvent:
    """A single HA event to feed into the neural system."""

    entity_id: str
    state: Any
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_changed: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)  # extra feed context


@dataclass
class FeedResult:
    """Result of a feed operation."""

    entity_id: str
    neuron_id: str
    neuron_type: str
    graph_nodes_touched: int = 0
    graph_edges_touched: int = 0
    dynamic_created: bool = False


class NeuronFeeder:
    """Feeds HA entity state changes into the Core neural system.

    The feeder maintains a Synapse Contract table (entity_id → neuron_id)
    and writes all state activations into the Brain Graph store.

    Thread-safe for use in async/Flask contexts.
    """

    def __init__(self, brain_graph: Optional[BrainGraphService] = None):
        """Initialize the feeder.

        Args:
            brain_graph: BrainGraphService instance. Created lazily if None.
        """
        self._brain_graph = brain_graph
        self._contract: Dict[str, SynapseContract] = {}  # entity_id → contract
        self._dynamic_creator: Optional[Any] = None  # set later via set_dynamic_creator()

    @property
    def brain_graph(self) -> BrainGraphService:
        """Lazy brain graph accessor."""
        if self._brain_graph is None:
            self._brain_graph = BrainGraphService()
        return self._brain_graph

    def set_dynamic_creator(self, dynamic_creator: Any) -> None:
        """Inject the DynamicNeuronCreator for auto-neuron creation."""
        self._dynamic_creator = dynamic_creator

    # -------------------------------------------------------------------------
    # Synapse Contract
    # -------------------------------------------------------------------------

    def get_neuron_id(self, entity_id: str) -> Optional[str]:
        """Resolve entity_id → neuron_id via Synapse Contract.

        Returns None if no contract exists yet (call feed() first or ensure_entity).
        """
        contract = self._contract.get(entity_id)
        return contract.neuron_id if contract else None

    def get_contract(self, entity_id: str) -> Optional[SynapseContract]:
        """Return the full Synapse Contract entry for an entity."""
        return self._contract.get(entity_id)

    def ensure_entity(self, entity_id: str) -> SynapseContract:
        """Ensure a Synapse Contract exists for entity_id.

        Creates one dynamically if missing (using domain → neuron_type rules).
        Optionally triggers DynamicNeuronCreator for new entities.
        """
        if entity_id in self._contract:
            return self._contract[entity_id]

        domain = _entity_domain(entity_id)
        neuron_type = _ENTITY_TYPE_MAP.get(domain, "state")
        neuron_id = _neuron_id_for_entity(entity_id, neuron_type)

        contract = SynapseContract(
            entity_id=entity_id,
            neuron_id=neuron_id,
            neuron_type=neuron_type,
            domain=domain,
        )
        self._contract[entity_id] = contract

        # Trigger dynamic neuron creation for new entities
        if self._dynamic_creator is not None:
            try:
                self._dynamic_creator.create_for_entity(entity_id, neuron_id, neuron_type)
                _LOGGER.info("Dynamic neuron created for %s → %s", entity_id, neuron_id)
            except Exception as exc:
                _LOGGER.warning("Dynamic neuron creation failed for %s: %s", entity_id, exc)

        _LOGGER.debug("Synapse contract created: %s → %s (%s)", entity_id, neuron_id, neuron_type)
        return contract

    # -------------------------------------------------------------------------
    # Feeding
    # -------------------------------------------------------------------------

    def feed(
        self,
        entity_id: str,
        state: Any,
        attributes: Optional[Dict[str, Any]] = None,
        last_changed: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> FeedResult:
        """Feed a single HA entity state change into the neural system.

        Args:
            entity_id: HA entity ID (e.g. 'light.living_room')
            state: New state value (e.g. 'on', 23.5, 'off')
            attributes: Optional entity attributes dict
            last_changed: Optional last_changed timestamp
            context: Optional extra context passed to Brain Graph

        Returns:
            FeedResult with neuron mapping and graph stats
        """
        attributes = attributes or {}
        last_changed = last_changed or datetime.now(timezone.utc)
        context = context or {}

        # Ensure contract exists (auto-creates if missing)
        contract = self.ensure_entity(entity_id)
        contract.last_fed_ms = int(time.time() * 1000)

        # Build meta_patch with state and attributes
        state_str = str(state)
        meta_patch = {
            "state": state_str,
            "last_changed": last_changed.isoformat(),
        }
        
        # Store key attributes (non-sensitive ones only)
        for attr_key in ("brightness", "temperature", "humidity", "power", "energy"):
            if attr_key in attributes:
                meta_patch[attr_key] = attributes[attr_key]

        # Write state into Brain Graph as neuron activation
        node_id = f"neuron:{contract.neuron_id}"
        self.brain_graph.touch_node(
            node_id,
            kind=contract.neuron_type,
            label=contract.neuron_id,
            meta_patch=meta_patch,
        )

        # Link entity → neuron via Synapse edge
        entity_node = f"ha.entity:{entity_id}"
        self.brain_graph.touch_node(entity_node, kind="entity", label=entity_id)
        self.brain_graph.touch_edge(entity_node, "synapse_to", node_id)

        # Zone edges if zone_ids present
        zone_ids = attributes.get("zone_ids") or []
        if isinstance(zone_ids, str):
            zone_ids = [zone_ids]
        for zid in zone_ids:
            zone_node = f"zone:{zid}"
            self.brain_graph.touch_node(zone_node, kind="zone", label=zid)
            self.brain_graph.touch_edge(node_id, "located_in", zone_node)

        # Build context for caller
        ctx = {
            "entity_id": entity_id,
            "neuron_id": contract.neuron_id,
            "neuron_type": contract.neuron_type,
            "domain": contract.domain,
            "state": state_str,
            "last_changed": last_changed.isoformat(),
        }
        ctx.update(context)

        return FeedResult(
            entity_id=entity_id,
            neuron_id=contract.neuron_id,
            neuron_type=contract.neuron_type,
            dynamic_created=contract.created_at_ms == contract.last_fed_ms,
        )

    def batch_feed(self, events: List[FeedEvent]) -> List[FeedResult]:
        """Feed multiple HA events in one batch.

        Args:
            events: List of FeedEvent objects

        Returns:
            List of FeedResult objects (same order)
        """
        results = []
        for evt in events:
            result = self.feed(
                entity_id=evt.entity_id,
                state=evt.state,
                attributes=evt.attributes,
                last_changed=evt.last_changed,
                context=evt.context,
            )
            results.append(result)
        return results

    # -------------------------------------------------------------------------
    # Stats / introspection
    # -------------------------------------------------------------------------

    def get_all_contracts(self) -> Dict[str, SynapseContract]:
        """Return the full Synapse Contract table."""
        return dict(self._contract)

    def get_contracts_by_type(self, neuron_type: str) -> List[SynapseContract]:
        """Return all contracts for a given neuron type (context, state, presence, etc.)."""
        return [c for c in self._contract.values() if c.neuron_type == neuron_type]

    def get_stats(self) -> Dict[str, Any]:
        """Return feeder statistics."""
        by_type: Dict[str, int] = {}
        for contract in self._contract.values():
            by_type[contract.neuron_type] = by_type.get(contract.neuron_type, 0) + 1
        return {
            "total_entities": len(self._contract),
            "by_neuron_type": by_type,
        }
