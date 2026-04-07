"""Base classes for all PilotSuite neurons.

Neurons are the building blocks of the neural orchestration system.
They evaluate specific aspects of the home state and contribute to
the overall mood calculation.

Architecture:
    Context Neurons (objective) → State Neurons (smoothed) → Mood Neurons (aggregated)

Each neuron:
1. Receives context from Home Assistant states
2. Evaluates its specific aspect (presence, time, energy, etc.)
3. Outputs a float value (0.0-1.0) and confidence
4. Contributes to mood calculation via weighted synapses
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class NeuronType(str, Enum):
    """Types of neurons in the neural system."""
    CONTEXT = "context"   # Objective environmental factors
    STATE = "state"       # Smoothed, inertial values
    MOOD = "mood"         # Aggregated decision triggers


class MoodType(str, Enum):
    """Available mood types for mood neurons."""
    RELAX = "relax"
    FOCUS = "focus"
    ACTIVE = "active"
    SLEEP = "sleep"
    AWAY = "away"
    ALERT = "alert"
    SOCIAL = "social"
    RECOVERY = "recovery"


@dataclass
class NeuronState:
    """Current state of a neuron.
    
    Attributes:
        active: Whether the neuron is currently firing
        value: Current output value (0.0-1.0)
        confidence: Confidence in the value (0.0-1.0)
        last_update: ISO timestamp of last update
        last_trigger: ISO timestamp of last trigger event
        trigger_count: Number of times neuron has triggered
    """
    active: bool = False
    value: float = 0.0
    confidence: float = 0.0
    last_update: Optional[str] = None
    last_trigger: Optional[str] = None
    trigger_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "active": self.active,
            "value": round(self.value, 3),
            "confidence": round(self.confidence, 3),
            "last_update": self.last_update,
            "last_trigger": self.last_trigger,
            "trigger_count": self.trigger_count
        }


@dataclass
class NeuronConfig:
    """Configuration for a neuron instance.
    
    Attributes:
        name: Unique identifier for this neuron
        neuron_type: Type of neuron (context, state, mood)
        threshold: Activation threshold (0.0-1.0)
        decay_rate: How fast the value decays when inactive (0.0-1.0)
        smoothing_factor: EMA smoothing factor (0.0-1.0)
        entity_ids: HA entity IDs this neuron watches
        weights: Weights for different inputs
        enabled: Whether the neuron is active
    """
    name: str
    neuron_type: NeuronType
    threshold: float = 0.5
    decay_rate: float = 0.1
    smoothing_factor: float = 0.3
    entity_ids: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "neuron_type": self.neuron_type.value,
            "threshold": self.threshold,
            "decay_rate": self.decay_rate,
            "smoothing_factor": self.smoothing_factor,
            "entity_ids": self.entity_ids,
            "weights": self.weights,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NeuronConfig":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            neuron_type=NeuronType(data["neuron_type"]),
            threshold=data.get("threshold", 0.5),
            decay_rate=data.get("decay_rate", 0.1),
            smoothing_factor=data.get("smoothing_factor", 0.3),
            entity_ids=data.get("entity_ids", []),
            weights=data.get("weights", {}),
            enabled=data.get("enabled", True)
        )


class BaseNeuron(ABC):
    """Abstract base class for all neurons.
    
    Neurons evaluate specific aspects of the home state and output
    a value and confidence that contribute to mood calculation.
    
    Lifecycle:
    1. __init__: Configure with entity IDs and parameters
    2. evaluate(): Called with HA state context, returns value
    3. update(): Updates internal state with new value
    4. reset(): Clears internal state
    
    The evaluate() method must be implemented by subclasses.
    """
    
    def __init__(self, config: NeuronConfig):
        """Initialize the neuron with configuration."""
        self.config = config
        self.state = NeuronState()
        self._previous_value: float = 0.0
        self._callbacks: List[Callable[[NeuronState], None]] = []
        
        _LOGGER.debug(
            "Initialized neuron %s (type=%s, threshold=%.2f)",
            config.name, config.neuron_type.value, config.threshold
        )
    
    @property
    def name(self) -> str:
        """Get neuron name."""
        return self.config.name
    
    @property
    def neuron_type(self) -> NeuronType:
        """Get neuron type."""
        return self.config.neuron_type
    
    @property
    def is_active(self) -> bool:
        """Check if neuron is currently firing."""
        return self.state.active
    
    @property
    def value(self) -> float:
        """Get current value."""
        return self.state.value
    
    @property
    def confidence(self) -> float:
        """Get current confidence."""
        return self.state.confidence
    
    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate the neuron based on context.
        
        This method must be implemented by subclasses to define
        the specific evaluation logic for each neuron type.
        
        Args:
            context: Dictionary containing HA states and other context
                     Keys typically include:
                     - 'states': Dict of entity_id -> state dict
                     - 'time': Current time info
                     - 'weather': Weather data
                     - 'presence': Presence data
        
        Returns:
            Float value between 0.0 and 1.0
        """
        pass
    
    def update(self, value: float, confidence: float = 1.0) -> NeuronState:
        """Update the neuron state with a new value.
        
        Applies smoothing and decay based on configuration.
        
        Args:
            value: New value to integrate
            confidence: Confidence in the value (0.0-1.0)
        
        Returns:
            Updated NeuronState
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Apply EMA smoothing
        if self._previous_value is not None:
            smoothed = (
                self.config.smoothing_factor * value +
                (1 - self.config.smoothing_factor) * self._previous_value
            )
        else:
            smoothed = value
        
        # Check if crossing threshold
        was_active = self.state.active
        now_active = smoothed >= self.config.threshold
        
        # Update state
        self.state.value = max(0.0, min(1.0, smoothed))
        self.state.confidence = confidence
        self.state.active = now_active
        self.state.last_update = now
        self._previous_value = smoothed
        
        # Track triggers
        if now_active and not was_active:
            self.state.last_trigger = now
            self.state.trigger_count += 1
            _LOGGER.info(
                "Neuron %s triggered (value=%.3f >= threshold=%.3f)",
                self.name, smoothed, self.config.threshold
            )
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self.state)
            except Exception as e:
                _LOGGER.error("Callback error in neuron %s: %s", self.name, e)
        
        return self.state
    
    def decay(self) -> NeuronState:
        """Apply decay to the current value.
        
        Called when the neuron doesn't receive updates.
        Value decays towards 0 based on decay_rate.
        
        Returns:
            Updated NeuronState
        """
        if self.state.value > 0:
            new_value = self.state.value * (1 - self.config.decay_rate)
            return self.update(new_value, self.state.confidence * 0.9)
        return self.state
    
    def reset(self) -> None:
        """Reset the neuron to initial state."""
        self.state = NeuronState()
        self._previous_value = 0.0
        _LOGGER.debug("Reset neuron %s", self.name)
    
    def on_trigger(self, callback: Callable[[NeuronState], None]) -> None:
        """Register a callback for when the neuron triggers.
        
        Args:
            callback: Function to call with NeuronState when triggered
        """
        self._callbacks.append(callback)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize neuron to dictionary."""
        return {
            "config": self.config.to_dict(),
            "state": self.state.to_dict()
        }
    
    @classmethod
    @abstractmethod
    def from_config(cls, config: NeuronConfig) -> "BaseNeuron":
        """Create a neuron instance from configuration.
        
        Must be implemented by subclasses.
        """
        pass


class ContextNeuron(BaseNeuron):
    """Base class for context neurons (objective environmental factors).
    
    Context neurons evaluate objective data from Home Assistant:
    - Presence (room, house, person)
    - TimeOfDay / DayType
    - LightLevel / SunPosition
    - Weather / Forecast
    - CalendarLoad
    - NoiseLevel
    - MediaActivity
    - SystemHealth
    - NetworkQuality
    - SecurityState
    """
    
    def __init__(self, config: NeuronConfig):
        if config.neuron_type != NeuronType.CONTEXT:
            raise ValueError(f"ContextNeuron requires neuron_type=CONTEXT, got {config.neuron_type}")
        super().__init__(config)
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "ContextNeuron":
        return cls(config)


class StateNeuron(BaseNeuron):
    """Base class for state neurons (smoothed, inertial values).
    
    State neurons maintain smoothed values that change slowly:
    - EnergyLevel
    - StressIndex
    - RoutineStability
    - SleepDebt
    - AttentionLoad
    - ComfortIndex
    """
    
    def __init__(self, config: NeuronConfig):
        if config.neuron_type != NeuronType.STATE:
            raise ValueError(f"StateNeuron requires neuron_type=STATE, got {config.neuron_type}")
        # State neurons have more smoothing by default
        config.smoothing_factor = min(config.smoothing_factor, 0.2)
        super().__init__(config)
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "StateNeuron":
        return cls(config)


class MoodNeuron(BaseNeuron):
    """Base class for mood neurons (aggregated decision triggers).
    
    Mood neurons aggregate inputs from context and state neurons
    to produce mood values that trigger suggestions:
    - mood.relax
    - mood.focus
    - mood.active
    - mood.sleep
    - mood.away
    - mood.alert
    - mood.social
    - mood.recovery
    """
    
    def __init__(self, config: NeuronConfig, mood_type: MoodType):
        if config.neuron_type != NeuronType.MOOD:
            raise ValueError(f"MoodNeuron requires neuron_type=MOOD, got {config.neuron_type}")
        super().__init__(config)
        self.mood_type = mood_type
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "MoodNeuron":
        # Mood type should be in config.weights or derived from name
        mood_str = config.name.replace("mood.", "").upper()
        mood_type = MoodType[mood_str]
        return cls(config, mood_type)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["mood_type"] = self.mood_type.value
        return data