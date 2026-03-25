"""
Dynamic Neuron Factory — Creates new neurons from discovered patterns.

When the CrossModuleAnalyzer repeatedly discovers strong correlations,
this factory can propose and create new neurons that aggregate those
signals. For example:

    "morning + solar_high + low_activity" → routine.morning_solar
    "habitus_pattern + calendar_meeting"  → meta.pre_meeting_focus

New neurons are always placed in Layer 3 (Meta) and aggregate outputs
from existing neurons in layers 0-2. They enrich the evaluation context
and feed into the suggestion pipeline.

Architecture:
    CrossModuleAnalyzer → ProposedNeuron → DynamicNeuronFactory
                                               → create_neuron()
                                               → connect_to_existing()
                                               → NeuronManager.add_neuron()

Safety:
    - Maximum 10 dynamic neurons (prevents unbounded growth)
    - Minimum confidence threshold for proposals (0.7)
    - Neurons can be removed if they decay below relevance
    - All dynamic neurons are persisted to /data/dynamic_neurons.json
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    BaseNeuron,
    NeuronConfig,
    NeuronState,
    NeuronType,
    ContextNeuron,
    StateNeuron,
)

_LOGGER = logging.getLogger(__name__)

# Safety bounds
MAX_DYNAMIC_NEURONS = 10
MIN_PROPOSAL_CONFIDENCE = 0.7
RELEVANCE_DECAY_RATE = 0.01
MIN_RELEVANCE = 0.1
DEFAULT_PERSIST_PATH = "/data/dynamic_neurons.json"


@dataclass
class ProposedNeuron:
    """A proposal for a new dynamic neuron."""

    neuron_id: str
    name: str
    description: str
    source_neurons: List[str]
    weights: Dict[str, float]
    confidence: float
    pattern_ids: List[str] = field(default_factory=list)
    proposed_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "neuron_id": self.neuron_id,
            "name": self.name,
            "description": self.description,
            "source_neurons": self.source_neurons,
            "weights": self.weights,
            "confidence": self.confidence,
            "pattern_ids": self.pattern_ids,
            "proposed_at_ms": self.proposed_at_ms,
        }


class DynamicMetaNeuron(BaseNeuron):
    """A dynamically created meta-neuron that aggregates existing neurons.

    Meta neurons compute a weighted average of their source neurons and
    apply the standard EMA smoothing from BaseNeuron.
    """

    def __init__(
        self,
        config: NeuronConfig,
        source_neurons: List[str],
        source_weights: Dict[str, float],
        relevance: float = 1.0,
    ) -> None:
        super().__init__(config)
        self.source_neurons = source_neurons
        self.source_weights = source_weights
        self.relevance = relevance
        self._evaluation_count = 0

    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate by computing weighted average of source neurons.

        Reads source neuron values from the evaluation context
        (populated by previous pipeline stages).

        Args:
            context: Evaluation context with 'neurons' dict containing
                     source neuron states.

        Returns:
            Weighted average value (0.0-1.0).
        """
        neurons_data = context.get("neurons", {})
        total_weight = 0.0
        weighted_sum = 0.0

        for source_id in self.source_neurons:
            weight = self.source_weights.get(source_id, 1.0)
            # Try direct lookup and prefixed lookup
            state = neurons_data.get(source_id, {})
            if not state:
                # Try without prefix
                short_id = source_id.split(".")[-1] if "." in source_id else source_id
                for key, val in neurons_data.items():
                    if key.endswith(f".{short_id}"):
                        state = val
                        break

            value = state.get("value", 0.0) if isinstance(state, dict) else 0.0
            weighted_sum += value * abs(weight)
            total_weight += abs(weight)

        if total_weight < 1e-6:
            return 0.0

        result = weighted_sum / total_weight
        self._evaluation_count += 1
        return max(0.0, min(1.0, result))

    @classmethod
    def from_config(cls, config: NeuronConfig) -> "DynamicMetaNeuron":
        """Create from config (source_neurons stored in weights)."""
        source_neurons = list(config.weights.keys())
        return cls(
            config=config,
            source_neurons=source_neurons,
            source_weights=config.weights,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["source_neurons"] = self.source_neurons
        data["source_weights"] = self.source_weights
        data["relevance"] = round(self.relevance, 4)
        data["evaluation_count"] = self._evaluation_count
        data["dynamic"] = True
        return data


class DynamicNeuronFactory:
    """Creates new neurons from discovered cross-module patterns.

    Monitors patterns from CrossModuleAnalyzer and proposes new
    meta-neurons when strong, repeated correlations are found.

    Usage:
        factory = DynamicNeuronFactory(bus, cross_analyzer, neuron_manager)
        # Factory subscribes to bus events and proposes neurons automatically

        # Manual proposal
        proposal = factory.propose_neuron(pattern)
        neuron = factory.create_neuron(proposal)

    Safety:
        - Max 10 dynamic neurons (configurable via max_neurons)
        - Confidence threshold prevents low-quality proposals
        - Relevance decay removes stale neurons
        - Persisted to disk for restart survival

    Args:
        bus: IntegrationBus for event subscription.
        cross_analyzer: CrossModuleAnalyzer for pattern discovery.
        neuron_manager: NeuronManager to register new neurons.
        max_neurons: Maximum dynamic neurons allowed.
        min_confidence: Minimum confidence for proposals.
        persist_path: Path to persist dynamic neuron configs.
    """

    def __init__(
        self,
        bus=None,
        cross_analyzer=None,
        neuron_manager=None,
        max_neurons: int = MAX_DYNAMIC_NEURONS,
        min_confidence: float = MIN_PROPOSAL_CONFIDENCE,
        persist_path: Optional[str] = None,
    ) -> None:
        self._bus = bus
        self._cross_analyzer = cross_analyzer
        self._neuron_manager = neuron_manager
        self._max_neurons = max_neurons
        self._min_confidence = min_confidence
        self._persist_path = persist_path or DEFAULT_PERSIST_PATH
        self._lock = threading.Lock()

        # Active dynamic neurons: neuron_id → DynamicMetaNeuron
        self._dynamic_neurons: Dict[str, DynamicMetaNeuron] = {}

        # Proposal history
        self._proposals: List[ProposedNeuron] = []

        # Subscribe to pattern discovery events
        if bus:
            bus.subscribe("pattern.discovered", self._on_pattern_discovered)

        # Load persisted neurons
        self._load_persisted()

        _LOGGER.info(
            "DynamicNeuronFactory initialized (max=%d, min_conf=%.2f, persisted=%d)",
            max_neurons,
            min_confidence,
            len(self._dynamic_neurons),
        )

    def _on_pattern_discovered(self, event) -> None:
        """Handle pattern.discovered bus event — evaluate for neuron proposal."""
        try:
            data = event.data if hasattr(event, "data") else event
            pattern_id = data.get("pattern_id", "")
            confidence = data.get("confidence", 0.0)
            if confidence >= self._min_confidence:
                _LOGGER.debug(
                    "High-confidence pattern %s (%.2f) — evaluating for neuron proposal",
                    pattern_id,
                    confidence,
                )
        except Exception:
            _LOGGER.debug("Ignored pattern event in DynamicNeuronFactory")

    def propose_neuron_from_patterns(self) -> List[ProposedNeuron]:
        """Analyze current cross-module patterns and propose neurons.

        Queries the CrossModuleAnalyzer for strong patterns and generates
        ProposedNeuron objects for patterns that meet the confidence
        threshold and don't already have corresponding dynamic neurons.

        Returns:
            List of new proposals (empty if no strong patterns found
            or max neurons reached).
        """
        if not self._cross_analyzer:
            return []

        with self._lock:
            if len(self._dynamic_neurons) >= self._max_neurons:
                _LOGGER.debug("Max dynamic neurons reached (%d)", self._max_neurons)
                return []

        patterns = self._cross_analyzer.get_patterns()
        proposals = []

        for pattern in patterns:
            correlation = abs(pattern.get("correlation", 0.0))
            if correlation < self._min_confidence:
                continue

            module_a = pattern.get("module_a", "")
            module_b = pattern.get("module_b", "")
            pattern_id = pattern.get("pattern_id", f"{module_a}~{module_b}")

            # Skip if we already have a neuron for this pattern
            neuron_id = self._pattern_to_neuron_id(module_a, module_b)
            with self._lock:
                if neuron_id in self._dynamic_neurons:
                    continue

            # Build source neuron list and weights
            source_neurons = [module_a, module_b]
            weights = {
                module_a: correlation,
                module_b: correlation,
            }

            # Create descriptive name
            a_short = module_a.split(".")[-1] if "." in module_a else module_a
            b_short = module_b.split(".")[-1] if "." in module_b else module_b
            name = f"meta.{a_short}_{b_short}"

            proposal = ProposedNeuron(
                neuron_id=neuron_id,
                name=name,
                description=pattern.get(
                    "description",
                    f"Dynamic aggregation of {module_a} and {module_b}",
                ),
                source_neurons=source_neurons,
                weights=weights,
                confidence=correlation,
                pattern_ids=[pattern_id],
            )
            proposals.append(proposal)

        with self._lock:
            self._proposals.extend(proposals)

        return proposals

    def propose_neuron(
        self,
        source_neurons: List[str],
        weights: Dict[str, float],
        name: str,
        description: str = "",
        confidence: float = 1.0,
    ) -> Optional[ProposedNeuron]:
        """Manually propose a new dynamic neuron.

        Args:
            source_neurons: List of source neuron IDs to aggregate.
            weights: Weights for each source neuron.
            name: Human-readable name (e.g. "meta.morning_routine").
            description: Description of what this neuron captures.
            confidence: Confidence in the proposal (0.0-1.0).

        Returns:
            ProposedNeuron if valid, None if rejected (low confidence
            or max neurons reached).
        """
        if confidence < self._min_confidence:
            _LOGGER.debug("Proposal rejected: confidence %.2f < %.2f", confidence, self._min_confidence)
            return None

        with self._lock:
            if len(self._dynamic_neurons) >= self._max_neurons:
                _LOGGER.warning("Proposal rejected: max dynamic neurons reached (%d)", self._max_neurons)
                return None

        neuron_id = f"dynamic.{name.replace('meta.', '').replace('.', '_')}"

        proposal = ProposedNeuron(
            neuron_id=neuron_id,
            name=name,
            description=description or f"Dynamic neuron aggregating {', '.join(source_neurons)}",
            source_neurons=source_neurons,
            weights=weights,
            confidence=confidence,
        )

        with self._lock:
            self._proposals.append(proposal)

        return proposal

    def create_neuron(self, proposal: ProposedNeuron) -> Optional[DynamicMetaNeuron]:
        """Create a DynamicMetaNeuron from a proposal.

        Validates the proposal, creates the neuron, and registers it
        with the NeuronManager if available.

        Args:
            proposal: The ProposedNeuron to instantiate.

        Returns:
            Created DynamicMetaNeuron, or None if creation failed.
        """
        with self._lock:
            if len(self._dynamic_neurons) >= self._max_neurons:
                _LOGGER.warning("Cannot create neuron: max limit reached")
                return None

            if proposal.neuron_id in self._dynamic_neurons:
                _LOGGER.debug("Neuron %s already exists", proposal.neuron_id)
                return self._dynamic_neurons[proposal.neuron_id]

        config = NeuronConfig(
            name=proposal.name,
            neuron_type=NeuronType.STATE,  # Meta neurons use STATE type
            threshold=0.5,
            decay_rate=RELEVANCE_DECAY_RATE,
            smoothing_factor=0.2,
            entity_ids=[],
            weights=proposal.weights,
            enabled=True,
        )

        neuron = DynamicMetaNeuron(
            config=config,
            source_neurons=proposal.source_neurons,
            source_weights=proposal.weights,
            relevance=proposal.confidence,
        )

        with self._lock:
            self._dynamic_neurons[proposal.neuron_id] = neuron

        # Register with NeuronManager
        if self._neuron_manager:
            self._neuron_manager.add_neuron("state", proposal.neuron_id, neuron)
            _LOGGER.info("Registered dynamic neuron: %s", proposal.neuron_id)

        # Publish creation event
        if self._bus:
            try:
                self._bus.publish("neuron.dynamic_created", {
                    "neuron_id": proposal.neuron_id,
                    "name": proposal.name,
                    "source_neurons": proposal.source_neurons,
                    "confidence": proposal.confidence,
                }, source="dynamic_neuron_factory")
            except Exception:
                _LOGGER.debug("Failed to publish neuron.dynamic_created event")

        # Persist
        self._save_persisted()

        return neuron

    def connect_to_existing(
        self,
        neuron_id: str,
    ) -> List[Tuple[str, str, float]]:
        """Generate synapse connections for a dynamic neuron.

        Returns a list of (from_neuron, to_neuron, weight) tuples that
        connect the dynamic neuron's sources to it.

        Args:
            neuron_id: ID of the dynamic neuron.

        Returns:
            List of synapse tuples (source → dynamic neuron).
        """
        with self._lock:
            neuron = self._dynamic_neurons.get(neuron_id)
            if not neuron:
                return []

        connections = []
        for source_id in neuron.source_neurons:
            weight = neuron.source_weights.get(source_id, 0.5)
            connections.append((source_id, neuron_id, weight))

        return connections

    def remove_neuron(self, neuron_id: str) -> bool:
        """Remove a dynamic neuron.

        Args:
            neuron_id: ID of the neuron to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if neuron_id not in self._dynamic_neurons:
                return False
            del self._dynamic_neurons[neuron_id]

        _LOGGER.info("Removed dynamic neuron: %s", neuron_id)
        self._save_persisted()
        return True

    def decay_relevance(self) -> List[str]:
        """Decay relevance of all dynamic neurons and remove stale ones.

        Should be called periodically (e.g. every evaluation cycle).

        Returns:
            List of neuron IDs that were removed due to low relevance.
        """
        removed = []
        with self._lock:
            for neuron_id, neuron in list(self._dynamic_neurons.items()):
                neuron.relevance *= (1 - RELEVANCE_DECAY_RATE)
                if neuron.relevance < MIN_RELEVANCE:
                    del self._dynamic_neurons[neuron_id]
                    removed.append(neuron_id)
                    _LOGGER.info(
                        "Dynamic neuron %s removed (relevance %.4f < %.2f)",
                        neuron_id,
                        neuron.relevance,
                        MIN_RELEVANCE,
                    )

        if removed:
            self._save_persisted()

        return removed

    def get_dynamic_neurons(self) -> List[Dict[str, Any]]:
        """Return all dynamic neurons as dicts for API."""
        with self._lock:
            return [
                neuron.to_dict()
                for neuron in self._dynamic_neurons.values()
            ]

    def get_proposals(self) -> List[Dict[str, Any]]:
        """Return all proposals as dicts."""
        with self._lock:
            return [p.to_dict() for p in self._proposals]

    def get_stats(self) -> Dict[str, Any]:
        """Return factory statistics."""
        with self._lock:
            return {
                "dynamic_neurons_count": len(self._dynamic_neurons),
                "max_neurons": self._max_neurons,
                "proposals_total": len(self._proposals),
                "min_confidence": self._min_confidence,
                "neuron_ids": list(self._dynamic_neurons.keys()),
            }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_persisted(self) -> None:
        """Persist dynamic neuron configs to disk."""
        try:
            with self._lock:
                data = {}
                for nid, neuron in self._dynamic_neurons.items():
                    data[nid] = {
                        "name": neuron.config.name,
                        "source_neurons": neuron.source_neurons,
                        "source_weights": neuron.source_weights,
                        "relevance": neuron.relevance,
                        "threshold": neuron.config.threshold,
                        "decay_rate": neuron.config.decay_rate,
                        "smoothing_factor": neuron.config.smoothing_factor,
                    }
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(data, f, indent=2)
            _LOGGER.debug("Persisted %d dynamic neurons", len(data))
        except OSError:
            _LOGGER.exception("Failed to persist dynamic neurons")

    def _load_persisted(self) -> None:
        """Load persisted dynamic neurons from disk."""
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            for nid, cfg in data.items():
                config = NeuronConfig(
                    name=cfg["name"],
                    neuron_type=NeuronType.STATE,
                    threshold=cfg.get("threshold", 0.5),
                    decay_rate=cfg.get("decay_rate", RELEVANCE_DECAY_RATE),
                    smoothing_factor=cfg.get("smoothing_factor", 0.2),
                    entity_ids=[],
                    weights=cfg.get("source_weights", {}),
                    enabled=True,
                )
                neuron = DynamicMetaNeuron(
                    config=config,
                    source_neurons=cfg.get("source_neurons", []),
                    source_weights=cfg.get("source_weights", {}),
                    relevance=cfg.get("relevance", 1.0),
                )
                self._dynamic_neurons[nid] = neuron
            _LOGGER.info("Loaded %d persisted dynamic neurons", len(data))
        except (OSError, json.JSONDecodeError, KeyError):
            _LOGGER.exception("Failed to load persisted dynamic neurons")

    @staticmethod
    def _pattern_to_neuron_id(module_a: str, module_b: str) -> str:
        """Generate a deterministic neuron ID from two module names."""
        a = module_a.replace(".", "_")
        b = module_b.replace(".", "_")
        parts = sorted([a, b])
        return f"dynamic.{parts[0]}_x_{parts[1]}"

    # -------------------------------------------------------------------------
    # Entity-driven neuron creation (used by NeuronFeeder)
    # -------------------------------------------------------------------------

    def create_for_entity(
        self,
        entity_id: str,
        neuron_id: str,
        neuron_type: str,
    ) -> Optional[DynamicMetaNeuron]:
        """Create or ensure a dynamic neuron exists for a HA entity.

        Called by NeuronFeeder when a new entity_id is encountered that
        has no Synapse Contract yet.

        Args:
            entity_id: HA entity_id (e.g. "light.living_room")
            neuron_id: Target neuron_id (e.g. "state.light_living_room")
            neuron_type: Neuron type string (e.g. "context", "state", "presence")

        Returns:
            The created or existing DynamicMetaNeuron, or None if the type
            is not handled / max limit reached.
        """
        # Only create meta-layer dynamic neurons (Layer 3)
        # Direct entity neurons are created by NeuronFeeder's contract
        # This hook is for cross-entity meta patterns discovered later
        safe_name = neuron_id.replace(".", "_").replace(" ", "_")
        meta_neuron_id = f"meta.entity_{safe_name}"

        # Check if already exists
        with self._lock:
            if meta_neuron_id in self._dynamic_neurons:
                return self._dynamic_neurons[meta_neuron_id]
            if len(self._dynamic_neurons) >= self._max_neurons:
                return None

        # Build config for a context-type meta neuron
        config = NeuronConfig(
            name=f"meta.entity_{safe_name}",
            neuron_type=NeuronType.CONTEXT,
            threshold=0.5,
            decay_rate=RELEVANCE_DECAY_RATE,
            smoothing_factor=0.2,
            entity_ids=[entity_id],
            weights={},
            enabled=True,
        )

        neuron = DynamicMetaNeuron(
            config=config,
            source_neurons=[neuron_id],  # aggregates the direct entity neuron
            source_weights={neuron_id: 1.0},
            relevance=0.8,  # start with high relevance for entity-driven neurons
        )

        with self._lock:
            self._dynamic_neurons[meta_neuron_id] = neuron

        # Register with NeuronManager if available
        if self._neuron_manager:
            self._neuron_manager.add_neuron("context", meta_neuron_id, neuron)
            _LOGGER.info("Entity-driven dynamic neuron registered: %s", meta_neuron_id)

        # Persist
        self._save_persisted()

        return neuron

    def get_dynamic_neuron(self, neuron_id: str) -> Optional[DynamicMetaNeuron]:
        """Return a specific dynamic neuron by ID."""
        with self._lock:
            return self._dynamic_neurons.get(neuron_id)

    def get_by_type(self, neuron_type: str) -> List[Dict[str, Any]]:
        """Return all dynamic neurons filtered by their type field."""
        with self._lock:
            return [
                n.to_dict()
                for n in self._dynamic_neurons.values()
                if n.config.neuron_type.value == neuron_type
            ]
