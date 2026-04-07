"""Synapse Manager for PilotSuite neural connections.

Manages synapses between neurons and from neurons to suggestions.
Handles signal propagation, learning, and decay.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import Synapse, SynapseType, SynapseState, Suggestion

_LOGGER = logging.getLogger(__name__)


class SynapseManager:
    """Manages all synapses in the neural network.
    
    Responsibilities:
    - Create and delete synapses
    - Propagate signals between neurons
    - Generate suggestions from mood neurons
    - Apply learning and decay
    - Persist synapse state
    """
    
    def __init__(self):
        """Initialize the synapse manager."""
        self._synapses: Dict[str, Synapse] = {}
        self._outgoing: Dict[str, Set[str]] = defaultdict(set)  # source_id -> synapse_ids
        self._incoming: Dict[str, Set[str]] = defaultdict(set)  # target_id -> synapse_ids
        self._suggestions: Dict[str, Suggestion] = {}
        self._suggestion_handlers: List[callable] = []
    
    def create_synapse(
        self,
        source_id: str,
        target_id: str,
        weight: float = 1.0,
        threshold: float = 0.3,
        synapse_type: SynapseType = SynapseType.EXCITATORY,
        tags: Optional[Set[str]] = None
    ) -> Synapse:
        """Create a new synapse between neurons.
        
        Args:
            source_id: ID of source neuron
            target_id: ID of target neuron
            weight: Connection strength (-1.0 to 1.0)
            threshold: Minimum input to activate
            synapse_type: Excitatory, inhibitory, or modulatory
            tags: Additional metadata
        
        Returns:
            Created synapse
        """
        synapse_id = f"{source_id}->{target_id}"
        
        # Check if synapse already exists
        if synapse_id in self._synapses:
            _LOGGER.debug("Synapse %s already exists, updating", synapse_id)
            existing = self._synapses[synapse_id]
            existing.weight = weight
            existing.threshold = threshold
            return existing
        
        synapse = Synapse(
            id=synapse_id,
            source_id=source_id,
            target_id=target_id,
            weight=weight,
            threshold=threshold,
            synapse_type=synapse_type,
            tags=tags or set()
        )
        
        self._synapses[synapse_id] = synapse
        self._outgoing[source_id].add(synapse_id)
        self._incoming[target_id].add(synapse_id)
        
        _LOGGER.debug(
            "Created synapse %s (weight=%.2f, type=%s)",
            synapse_id, weight, synapse_type.value
        )
        
        return synapse
    
    def delete_synapse(self, synapse_id: str) -> bool:
        """Delete a synapse.
        
        Args:
            synapse_id: ID of synapse to delete
        
        Returns:
            True if deleted, False if not found
        """
        if synapse_id not in self._synapses:
            return False
        
        synapse = self._synapses[synapse_id]
        
        # Remove from indexes
        self._outgoing[synapse.source_id].discard(synapse_id)
        self._incoming[synapse.target_id].discard(synapse_id)
        
        # Remove synapse
        del self._synapses[synapse_id]
        
        _LOGGER.debug("Deleted synapse %s", synapse_id)
        return True
    
    def get_synapses_from(self, source_id: str) -> List[Synapse]:
        """Get all synapses originating from a neuron.
        
        Args:
            source_id: Source neuron ID
        
        Returns:
            List of synapses
        """
        synapse_ids = self._outgoing.get(source_id, set())
        return [self._synapses[sid] for sid in synapse_ids if sid in self._synapses]
    
    def get_synapses_to(self, target_id: str) -> List[Synapse]:
        """Get all synapses targeting a neuron.
        
        Args:
            target_id: Target neuron ID
        
        Returns:
            List of synapses
        """
        synapse_ids = self._incoming.get(target_id, set())
        return [self._synapses[sid] for sid in synapse_ids if sid in self._synapses]
    
    def propagate(
        self,
        source_id: str,
        input_value: float,
        neuron_states: Dict[str, float]
    ) -> Dict[str, float]:
        """Propagate signal from a source neuron to targets.
        
        Args:
            source_id: ID of firing neuron
            input_value: Value from source neuron (0.0-1.0)
            neuron_states: Current states of all neurons
        
        Returns:
            Dictionary of target_id -> transmitted_signal
        """
        synapses = self.get_synapses_from(source_id)
        outputs: Dict[str, float] = {}
        
        for synapse in synapses:
            if synapse.state == SynapseState.PRUNED:
                continue
            
            signal = synapse.fire(input_value)
            
            if signal != 0.0:
                target_id = synapse.target_id
                
                # Aggregate signals to same target
                if target_id not in outputs:
                    outputs[target_id] = 0.0
                
                outputs[target_id] += signal
        
        return outputs
    
    def aggregate_inputs(
        self,
        target_id: str,
        neuron_states: Dict[str, float]
    ) -> Tuple[float, List[str]]:
        """Aggregate all inputs to a target neuron.
        
        Args:
            target_id: Target neuron ID
            neuron_states: Current states of all neurons
        
        Returns:
            Tuple of (aggregated_value, list_of_firing_sources)
        """
        synapses = self.get_synapses_to(target_id)
        total_signal = 0.0
        firing_sources: List[str] = []
        
        for synapse in synapses:
            if synapse.state == SynapseState.PRUNED:
                continue
            
            source_value = neuron_states.get(synapse.source_id, 0.0)
            
            if synapse.can_fire(source_value):
                signal = synapse.fire(source_value)
                total_signal += signal
                firing_sources.append(synapse.source_id)
        
        # Clamp to 0-1 range for neuron input
        total_signal = max(0.0, min(1.0, total_signal))
        
        return total_signal, firing_sources
    
    def generate_suggestions(
        self,
        mood_values: Dict[str, float],
        context: Dict[str, Any]
    ) -> List[Suggestion]:
        """Generate suggestions based on mood values.
        
        Args:
            mood_values: Dictionary of mood_name -> value
            context: Additional context for suggestions
        
        Returns:
            List of generated suggestions
        """
        suggestions: List[Suggestion] = []
        
        # Find dominant mood
        if not mood_values:
            return suggestions
        
        dominant_mood = max(mood_values.items(), key=lambda x: x[1])
        mood_name, mood_value = dominant_mood
        
        # Only generate if above threshold
        if mood_value < 0.5:
            return suggestions
        
        # Generate suggestion based on mood
        suggestion = self._create_suggestion_for_mood(mood_name, mood_value, context)
        
        if suggestion:
            self._suggestions[suggestion.id] = suggestion
            suggestions.append(suggestion)
            
            # Notify handlers
            for handler in self._suggestion_handlers:
                try:
                    handler(suggestion)
                except Exception as e:
                    _LOGGER.error("Suggestion handler error: %s", e)
        
        return suggestions
    
    def _create_suggestion_for_mood(
        self,
        mood: str,
        value: float,
        context: Dict[str, Any]
    ) -> Optional[Suggestion]:
        """Create a suggestion for a specific mood.
        
        Args:
            mood: Mood name
            value: Mood value
            context: Context data
        
        Returns:
            Suggestion or None
        """
        from datetime import timedelta
        
        suggestion_id = f"sugg_{mood}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        
        # Mood-specific suggestions
        if mood == "relax":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="light",
                action_data={
                    "action": "dim_lights",
                    "brightness": 30,
                    "reason": "Relaxation mood detected"
                },
                priority=0.6 * value,
                confidence=value,
                reasoning=f"Detected relaxed state (confidence: {value:.0%}). Consider dimming lights for ambiance.",
                expires_at=expires
            )
        
        elif mood == "focus":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="environment",
                action_data={
                    "action": "optimize_for_focus",
                    "temperature": 21,
                    "brightness": 80,
                    "reason": "Focus mood detected"
                },
                priority=0.7 * value,
                confidence=value,
                reasoning=f"Detected focus state (confidence: {value:.0%}). Optimizing environment for concentration.",
                expires_at=expires
            )
        
        elif mood == "sleep":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="light",
                action_data={
                    "action": "night_mode",
                    "brightness": 5,
                    "color_temp": 2200,
                    "reason": "Sleep mood detected"
                },
                priority=0.8 * value,
                confidence=value,
                reasoning=f"Detected sleepy state (confidence: {value:.0%}). Preparing for rest.",
                expires_at=expires
            )
        
        elif mood == "active":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="environment",
                action_data={
                    "action": "boost_energy",
                    "brightness": 100,
                    "temperature": 22,
                    "reason": "Active mood detected"
                },
                priority=0.5 * value,
                confidence=value,
                reasoning=f"Detected active state (confidence: {value:.0%}). Brightening environment.",
                expires_at=expires
            )
        
        elif mood == "alert":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="notification",
                action_data={
                    "action": "alert_user",
                    "priority": "high",
                    "reason": "Alert mood detected"
                },
                priority=0.9 * value,
                confidence=value,
                reasoning=f"Detected alert state (confidence: {value:.0%}). User attention may be needed.",
                expires_at=expires
            )
        
        elif mood == "away":
            return Suggestion(
                id=suggestion_id,
                source_mood=mood,
                action_type="automation",
                action_data={
                    "action": "away_mode",
                    "lights_off": True,
                    "temperature_eco": True,
                    "reason": "Away mood detected"
                },
                priority=0.7 * value,
                confidence=value,
                reasoning=f"Detected away state (confidence: {value:.0%}). Activating energy saving mode.",
                expires_at=expires
            )
        
        # social and recovery have no automatic actions
        return None
    
    def apply_learning(
        self,
        suggestion_id: str,
        accepted: bool
    ) -> None:
        """Apply learning based on user feedback.
        
        Strengthens synapses that led to accepted suggestions,
        weakens those for rejected suggestions.
        
        Args:
            suggestion_id: ID of the suggestion
            accepted: Whether user accepted
        """
        if suggestion_id not in self._suggestions:
            return
        
        suggestion = self._suggestions[suggestion_id]
        
        if accepted:
            suggestion.accepted = True
            reward = 0.1  # Positive reinforcement
        else:
            suggestion.rejected = True
            reward = -0.1  # Negative reinforcement
        
        # Find synapses that led to this mood
        mood_name = suggestion.source_mood
        
        # Get all synapses to this mood neuron
        mood_synapses = self.get_synapses_to(f"mood.{mood_name}")
        
        for synapse in mood_synapses:
            synapse.learn(reward)
        
        _LOGGER.debug(
            "Applied learning for suggestion %s: reward=%.2f",
            suggestion_id, reward
        )
    
    def apply_decay(self) -> int:
        """Apply decay to all inactive synapses.
        
        Returns:
            Number of synapses that were pruned
        """
        pruned = 0
        
        for synapse in list(self._synapses.values()):
            synapse.decay()
            
            if synapse.state == SynapseState.PRUNED:
                pruned += 1
        
        if pruned > 0:
            _LOGGER.info("Pruned %d inactive synapses", pruned)
        
        return pruned
    
    def on_suggestion(self, handler: callable) -> None:
        """Register a handler for new suggestions.
        
        Args:
            handler: Function to call with new suggestions
        """
        self._suggestion_handlers.append(handler)
    
    def get_active_suggestions(self) -> List[Suggestion]:
        """Get all active (non-expired, non-decided) suggestions.
        
        Returns:
            List of active suggestions
        """
        now = datetime.now(timezone.utc)
        active = []
        
        for suggestion in self._suggestions.values():
            if suggestion.accepted or suggestion.rejected:
                continue
            
            if suggestion.expires_at:
                expires = datetime.fromisoformat(suggestion.expires_at.replace('Z', '+00:00'))
                if now > expires:
                    continue
            
            active.append(suggestion)
        
        return active
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the synapse network.
        
        Returns:
            Dictionary of statistics
        """
        total = len(self._synapses)
        active = sum(1 for s in self._synapses.values() if s.state == SynapseState.ACTIVE)
        dormant = sum(1 for s in self._synapses.values() if s.state == SynapseState.DORMANT)
        learning = sum(1 for s in self._synapses.values() if s.state == SynapseState.LEARNING)
        pruned = sum(1 for s in self._synapses.values() if s.state == SynapseState.PRUNED)
        
        excitatory = sum(1 for s in self._synapses.values() if s.synapse_type == SynapseType.EXCITATORY)
        inhibitory = sum(1 for s in self._synapses.values() if s.synapse_type == SynapseType.INHIBITORY)
        
        avg_weight = sum(s.weight for s in self._synapses.values()) / max(total, 1)
        
        return {
            "total_synapses": total,
            "active": active,
            "dormant": dormant,
            "learning": learning,
            "pruned": pruned,
            "excitatory": excitatory,
            "inhibitory": inhibitory,
            "avg_weight": round(avg_weight, 4),
            "total_suggestions": len(self._suggestions),
            "active_suggestions": len(self.get_active_suggestions())
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "synapses": [s.to_dict() for s in self._synapses.values()],
            "suggestions": [s.to_dict() for s in self._suggestions.values()]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynapseManager":
        """Restore manager state from dictionary.
        
        Args:
            data: Dictionary representation
        
        Returns:
            Restored SynapseManager
        """
        manager = cls()
        
        for synapse_data in data.get("synapses", []):
            synapse = Synapse.from_dict(synapse_data)
            manager._synapses[synapse.id] = synapse
            manager._outgoing[synapse.source_id].add(synapse.id)
            manager._incoming[synapse.target_id].add(synapse.id)
        
        for suggestion_data in data.get("suggestions", []):
            suggestion = Suggestion.from_dict(suggestion_data)
            manager._suggestions[suggestion.id] = suggestion
        
        return manager