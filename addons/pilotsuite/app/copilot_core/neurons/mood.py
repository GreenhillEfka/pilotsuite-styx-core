"""Mood Neurons - Aggregated decision triggers.

Mood neurons aggregate inputs from context and state neurons
to produce mood values that trigger suggestions.

Mood Types:
- relax: Relaxed, calm state
- focus: Concentrated, productive state
- active: Active, energetic state
- sleep: Sleepy, rest-needed state
- away: User not present
- alert: Alert, attention-needed state
- social: Social, interactive state
- recovery: Recovery, healing state
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseNeuron, NeuronConfig, NeuronType, MoodNeuron, MoodType

_LOGGER = logging.getLogger(__name__)


class RelaxMoodNeuron(MoodNeuron):
    """Mood neuron for relaxed state.
    
    Triggered by:
        - Low stress
        - High comfort
        - Low attention load
        - Evening/night time
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.RELAX)
        
        # Default weights for inputs
        self.input_weights = {
            "stress_index": -0.4,  # Lower stress = more relax
            "comfort_index": 0.3,  # Higher comfort = more relax
            "attention_load": -0.2,  # Lower load = more relax
            "energy_level": -0.1,  # Lower energy = more relax
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate relaxation mood."""
        neurons = context.get("neurons", {})
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            # Normalize and shift to 0-1 range
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "RelaxMoodNeuron":
        return cls(config)


class FocusMoodNeuron(MoodNeuron):
    """Mood neuron for focused state.
    
    Triggered by:
        - Moderate energy
        - Low stress
        - Day time
        - Low media activity
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.FOCUS)
        
        self.input_weights = {
            "energy_level": 0.3,
            "stress_index": -0.3,
            "attention_load": -0.2,
            "routine_stability": 0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate focus mood."""
        neurons = context.get("neurons", {})
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "FocusMoodNeuron":
        return cls(config)


class ActiveMoodNeuron(MoodNeuron):
    """Mood neuron for active state.
    
    Triggered by:
        - High energy
        - Day time
        - Motion/activity
        - Presence
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.ACTIVE)
        
        self.input_weights = {
            "energy_level": 0.4,
            "presence": 0.3,
            "comfort_index": 0.1,
            "sleep_debt": -0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate active mood."""
        neurons = context.get("neurons", {})
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "ActiveMoodNeuron":
        return cls(config)


class SleepMoodNeuron(MoodNeuron):
    """Mood neuron for sleepy state.
    
    Triggered by:
        - High sleep debt
        - Low energy
        - Night time
        - Low activity
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.SLEEP)
        
        self.input_weights = {
            "sleep_debt": 0.5,
            "energy_level": -0.3,
            "attention_load": -0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate sleep mood."""
        neurons = context.get("neurons", {})
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "SleepMoodNeuron":
        return cls(config)


class AwayMoodNeuron(MoodNeuron):
    """Mood neuron for away state.
    
    Triggered by:
        - No presence
        - Extended inactivity
        - Away mode enabled
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.AWAY)
        
        self.input_weights = {
            "presence": -0.7,  # No presence = away
            "energy_level": -0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate away mood."""
        neurons = context.get("neurons", {})
        presence = context.get("presence", {})
        
        # Direct presence check
        if not presence.get("home", True):
            return 0.9
        
        # Check presence neuron
        if "presence" in neurons:
            presence_value = neurons["presence"].get("value", 1.0)
            # Invert: low presence = high away
            return max(0.0, min(1.0, 1.0 - presence_value))
        
        return 0.1  # Default to not away
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "AwayMoodNeuron":
        return cls(config)


class AlertMoodNeuron(MoodNeuron):
    """Mood neuron for alert state.
    
    Triggered by:
        - Security events
        - Unexpected activity
        - System issues
        - Stress spikes
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.ALERT)
        
        self.input_weights = {
            "stress_index": 0.5,
            "routine_stability": -0.3,  # Low stability = alert
            "attention_load": 0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate alert mood."""
        neurons = context.get("neurons", {})
        security = context.get("security", {})
        
        # Check for security alerts
        if security.get("alert_active", False):
            return 0.9
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "AlertMoodNeuron":
        return cls(config)


class SocialMoodNeuron(MoodNeuron):
    """Mood neuron for social state.
    
    Triggered by:
        - Multiple presence
        - Media activity (music, TV)
        - Guests detected
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.SOCIAL)
        
        self.input_weights = {
            "presence": 0.3,
            "attention_load": 0.3,
            "energy_level": 0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate social mood."""
        neurons = context.get("neurons", {})
        presence = context.get("presence", {})
        
        # Check for multiple people
        people_count = presence.get("people_count", 1)
        if people_count > 1:
            base_score = min(1.0, people_count / 4)
        else:
            base_score = 0.2
        
        score = base_score * 0.5
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value * 0.5
                total_weight += abs(weight)
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "SocialMoodNeuron":
        return cls(config)


class RecoveryMoodNeuron(MoodNeuron):
    """Mood neuron for recovery state.
    
    Triggered by:
        - After alert state
        - Low activity
        - Comfortable environment
        - Sleep debt resolution
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, MoodType.RECOVERY)
        
        self.input_weights = {
            "stress_index": -0.3,
            "comfort_index": 0.4,
            "energy_level": -0.1,
            "routine_stability": 0.2,
        }
        self.input_weights.update(config.weights)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate recovery mood."""
        neurons = context.get("neurons", {})
        
        score = 0.0
        total_weight = 0.0
        
        for input_name, weight in self.input_weights.items():
            if input_name in neurons:
                input_value = neurons[input_name].get("value", 0.5)
                score += weight * input_value
                total_weight += abs(weight)
        
        if total_weight > 0:
            score = (score / total_weight + 1) / 2
        
        return max(0.0, min(1.0, score))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "RecoveryMoodNeuron":
        return cls(config)


# Register all mood neurons
MOOD_NEURON_CLASSES = {
    "relax": RelaxMoodNeuron,
    "focus": FocusMoodNeuron,
    "active": ActiveMoodNeuron,
    "sleep": SleepMoodNeuron,
    "away": AwayMoodNeuron,
    "alert": AlertMoodNeuron,
    "social": SocialMoodNeuron,
    "recovery": RecoveryMoodNeuron,
}


def create_mood_neuron(name: str, config: NeuronConfig) -> MoodNeuron:
    """Factory function to create mood neurons by name."""
    neuron_class = MOOD_NEURON_CLASSES.get(name)
    if neuron_class:
        return neuron_class.from_config(config)
    raise ValueError(f"Unknown mood neuron type: {name}")