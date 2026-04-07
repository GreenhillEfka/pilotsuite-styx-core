"""
Hebbian Learning — Adaptive synapse weight adjustment.

Implements "neurons that fire together, wire together" for the
neural pipeline. Synapse weights are adjusted based on co-activation
patterns observed during pipeline evaluations.

Update rule:
    Δw = η * (x_pre * x_post - λ * w)

Where:
    η = learning rate (default 0.01)
    λ = weight decay (default 0.001, prevents unbounded growth)
    x_pre = pre-synaptic neuron value
    x_post = post-synaptic neuron value
    w = current synapse weight
"""

from __future__ import annotations

import logging
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

# Defaults
DEFAULT_LEARNING_RATE = 0.01
DEFAULT_WEIGHT_DECAY = 0.001
DEFAULT_MAX_WEIGHT = 2.0
DEFAULT_MIN_WEIGHT = -2.0


@dataclass
class WeightUpdate:
    """Record of a single weight adjustment."""
    from_neuron: str
    to_neuron: str
    old_weight: float
    new_weight: float
    delta: float


@dataclass
class SynapseWeight:
    """A learnable synapse weight between two neurons."""
    from_neuron: str
    to_neuron: str
    weight: float
    base_weight: float  # Original weight from topology
    updates_count: int = 0


class HebbianLearning:
    """Hebbian learning engine for synapse weight adaptation.

    Subscribes to ``neuron.evaluated`` bus events and adjusts synapse
    weights based on co-activation patterns.

    Args:
        topology: List of (from_neuron, to_neuron, base_weight) tuples.
        learning_rate: Speed of weight adaptation (default 0.01).
        weight_decay: Prevents unbounded weight growth (default 0.001).
        persist_path: Optional path to persist learned weights.
    """

    def __init__(
        self,
        topology: List[Tuple[str, str, float]],
        learning_rate: float = DEFAULT_LEARNING_RATE,
        weight_decay: float = DEFAULT_WEIGHT_DECAY,
        persist_path: Optional[str] = None,
    ) -> None:
        self._lr = learning_rate
        self._decay = weight_decay
        self._persist_path = persist_path
        self._lock = threading.Lock()
        self._total_updates = 0

        # Initialize synapse weights from topology
        self._synapses: Dict[str, SynapseWeight] = {}
        for from_n, to_n, weight in topology:
            key = f"{from_n}->{to_n}"
            self._synapses[key] = SynapseWeight(
                from_neuron=from_n,
                to_neuron=to_n,
                weight=weight,
                base_weight=weight,
            )

        # Load persisted weights if available
        if persist_path:
            self._load_weights()

        _LOGGER.info(
            "HebbianLearning initialized: %d synapses, lr=%.4f, decay=%.4f",
            len(self._synapses), self._lr, self._decay,
        )

    def update_weights(
        self,
        neuron_values: Dict[str, float],
    ) -> List[WeightUpdate]:
        """Update all synapse weights based on current neuron values.

        Args:
            neuron_values: Dict mapping neuron IDs to their current values
                (e.g. ``{"context.presence": 0.8, "state.energy_level": 0.6}``).

        Returns:
            List of ``WeightUpdate`` records for all adjusted synapses.
        """
        updates = []

        with self._lock:
            for key, synapse in self._synapses.items():
                x_pre = neuron_values.get(synapse.from_neuron, 0.0)
                x_post = neuron_values.get(synapse.to_neuron, 0.0)

                # Hebbian update: Δw = η * (x_pre * x_post - λ * w)
                delta = self._lr * (x_pre * x_post - self._decay * synapse.weight)

                if abs(delta) < 1e-6:
                    continue

                old_weight = synapse.weight
                new_weight = synapse.weight + delta

                # Clamp to bounds
                new_weight = max(DEFAULT_MIN_WEIGHT, min(DEFAULT_MAX_WEIGHT, new_weight))

                synapse.weight = new_weight
                synapse.updates_count += 1

                updates.append(WeightUpdate(
                    from_neuron=synapse.from_neuron,
                    to_neuron=synapse.to_neuron,
                    old_weight=old_weight,
                    new_weight=new_weight,
                    delta=delta,
                ))

            self._total_updates += len(updates)

        return updates

    def apply_feedback(
        self,
        related_neurons: List[str],
        accepted: bool,
        strength: float = 0.05,
    ) -> List[WeightUpdate]:
        """Adjust weights based on user feedback on a suggestion.

        Reinforces (accepted) or weakens (rejected) synapses between
        the related neurons.

        Args:
            related_neurons: Neuron IDs involved in the suggestion.
            accepted: Whether the suggestion was accepted.
            strength: Magnitude of adjustment.

        Returns:
            List of weight updates applied.
        """
        delta_sign = 1.0 if accepted else -1.0
        updates = []

        with self._lock:
            for key, synapse in self._synapses.items():
                if (synapse.from_neuron in related_neurons and
                        synapse.to_neuron in related_neurons):
                    old_weight = synapse.weight
                    delta = delta_sign * strength
                    new_weight = max(
                        DEFAULT_MIN_WEIGHT,
                        min(DEFAULT_MAX_WEIGHT, synapse.weight + delta),
                    )
                    synapse.weight = new_weight
                    synapse.updates_count += 1
                    updates.append(WeightUpdate(
                        from_neuron=synapse.from_neuron,
                        to_neuron=synapse.to_neuron,
                        old_weight=old_weight,
                        new_weight=new_weight,
                        delta=delta,
                    ))

        return updates

    def get_weight(self, from_neuron: str, to_neuron: str) -> Optional[float]:
        """Get the current weight for a specific synapse."""
        key = f"{from_neuron}->{to_neuron}"
        synapse = self._synapses.get(key)
        return synapse.weight if synapse else None

    def get_all_weights(self) -> Dict[str, float]:
        """Return all current synapse weights."""
        with self._lock:
            return {key: s.weight for key, s in self._synapses.items()}

    def get_weight_drift(self) -> Dict[str, float]:
        """Return how much each weight has drifted from its base value."""
        with self._lock:
            return {
                key: round(s.weight - s.base_weight, 6)
                for key, s in self._synapses.items()
                if abs(s.weight - s.base_weight) > 1e-6
            }

    def reset_to_base(self) -> None:
        """Reset all weights to their base (topology) values."""
        with self._lock:
            for synapse in self._synapses.values():
                synapse.weight = synapse.base_weight
                synapse.updates_count = 0
            self._total_updates = 0
        _LOGGER.info("All synapse weights reset to base values")

    def get_stats(self) -> Dict[str, Any]:
        """Return learning engine statistics."""
        with self._lock:
            total_drift = sum(
                abs(s.weight - s.base_weight) for s in self._synapses.values()
            )
            max_drift_synapse = max(
                self._synapses.values(),
                key=lambda s: abs(s.weight - s.base_weight),
                default=None,
            )
        return {
            "total_synapses": len(self._synapses),
            "total_updates": self._total_updates,
            "learning_rate": self._lr,
            "weight_decay": self._decay,
            "total_drift": round(total_drift, 6),
            "max_drift_synapse": (
                f"{max_drift_synapse.from_neuron}->{max_drift_synapse.to_neuron}"
                if max_drift_synapse else None
            ),
            "max_drift_value": (
                round(max_drift_synapse.weight - max_drift_synapse.base_weight, 6)
                if max_drift_synapse else 0.0
            ),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_weights(self) -> None:
        """Persist current weights to disk."""
        if not self._persist_path:
            return
        try:
            with self._lock:
                data = {
                    key: {"weight": s.weight, "updates": s.updates_count}
                    for key, s in self._synapses.items()
                }
            with open(self._persist_path, "w") as f:
                json.dump(data, f, indent=2)
            _LOGGER.debug("Saved %d synapse weights to %s", len(data), self._persist_path)
        except OSError:
            _LOGGER.exception("Failed to save synapse weights")

    def _load_weights(self) -> None:
        """Load persisted weights from disk."""
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            loaded = 0
            with self._lock:
                for key, vals in data.items():
                    if key in self._synapses:
                        self._synapses[key].weight = vals["weight"]
                        self._synapses[key].updates_count = vals.get("updates", 0)
                        loaded += 1
            _LOGGER.info("Loaded %d persisted synapse weights", loaded)
        except (OSError, json.JSONDecodeError):
            _LOGGER.exception("Failed to load synapse weights")
