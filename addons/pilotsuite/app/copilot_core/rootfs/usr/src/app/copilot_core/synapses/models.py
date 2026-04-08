"""Synapse models for neural connections."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

_LOGGER = logging.getLogger(__name__)


class SynapseType(str, Enum):
    """Types of synapse connections."""
    EXCITATORY = "excitatory"  # Increases target value
    INHIBITORY = "inhibitory"  # Decreases target value
    MODULATORY = "modulatory"  # Adjusts weight of other synapses


class SynapseState(str, Enum):
    """State of a synapse."""
    ACTIVE = "active"      # Recently fired
    DORMANT = "dormant"    # Not recently active
    LEARNING = "learning"  # Weight being adjusted
    PRUNED = "pruned"      # Removed due to low weight


@dataclass
class Synapse:
    """A connection between neurons or from neuron to suggestion.
    
    Attributes:
        id: Unique identifier
        source_id: ID of source neuron
        target_id: ID of target neuron or suggestion
        weight: Connection strength (-1.0 to 1.0)
        threshold: Minimum input to activate
        synapse_type: Excitatory, inhibitory, or modulatory
        state: Current state
        created_at: Creation timestamp
        last_fired: Last activation timestamp
        fire_count: Number of activations
        learning_rate: Rate of weight adjustment
        decay_rate: Rate of weight decay when inactive
        tags: Additional metadata
    """
    id: str
    source_id: str
    target_id: str
    weight: float = 1.0
    threshold: float = 0.3
    synapse_type: SynapseType = SynapseType.EXCITATORY
    state: SynapseState = SynapseState.DORMANT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_fired: Optional[str] = None
    fire_count: int = 0
    learning_rate: float = 0.01
    decay_rate: float = 0.001
    tags: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        """Validate synapse parameters."""
        if not -1.0 <= self.weight <= 1.0:
            raise ValueError(f"Weight must be between -1.0 and 1.0, got {self.weight}")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {self.threshold}")
    
    def can_fire(self, input_value: float) -> bool:
        """Check if synapse can fire based on input and threshold."""
        return input_value >= self.threshold
    
    def transmit(self, input_value: float) -> float:
        """Calculate transmitted signal strength.
        
        Args:
            input_value: Value from source neuron (0.0-1.0)
        
        Returns:
            Transmitted signal (can be negative for inhibitory)
        """
        if not self.can_fire(input_value):
            return 0.0
        
        # Base transmission
        signal = input_value * self.weight
        
        # Adjust for synapse type
        if self.synapse_type == SynapseType.INHIBITORY:
            signal = -abs(signal)
        elif self.synapse_type == SynapseType.MODULATORY:
            # Modulatory returns a multiplier
            signal = self.weight
        
        return signal
    
    def fire(self, input_value: float) -> float:
        """Fire the synapse and update state.
        
        Args:
            input_value: Value from source neuron
        
        Returns:
            Transmitted signal
        """
        signal = self.transmit(input_value)
        
        if signal != 0.0:
            self.last_fired = datetime.now(timezone.utc).isoformat()
            self.fire_count += 1
            self.state = SynapseState.ACTIVE
        
        return signal
    
    def learn(self, reward: float) -> None:
        """Adjust weight based on reward signal.
        
        Hebbian-like learning: connections that fire together, wire together.
        
        Args:
            reward: Reward signal (-1.0 to 1.0)
        """
        if self.state == SynapseState.PRUNED:
            return
        
        self.weight += self.learning_rate * reward
        
        # Clamp weight
        self.weight = max(-1.0, min(1.0, self.weight))
        
        # Mark as learning
        self.state = SynapseState.LEARNING
        
        # Prune very weak connections
        if abs(self.weight) < 0.01:
            self.state = SynapseState.PRUNED
            _LOGGER.debug("Synapse %s pruned due to low weight", self.id)
    
    def decay(self) -> None:
        """Apply decay when synapse is inactive.
        
        Gradually reduces weight for unused connections.
        """
        if self.state == SynapseState.PRUNED:
            return
        
        if self.last_fired:
            last = datetime.fromisoformat(self.last_fired.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_since_fire = (now - last).total_seconds() / 3600
            
            if hours_since_fire > 24:  # Decay after 24 hours of inactivity
                self.weight *= (1 - self.decay_rate)
                
                if abs(self.weight) < 0.1:
                    self.state = SynapseState.DORMANT
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "weight": round(self.weight, 4),
            "threshold": self.threshold,
            "synapse_type": self.synapse_type.value,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_fired": self.last_fired,
            "fire_count": self.fire_count,
            "learning_rate": self.learning_rate,
            "decay_rate": self.decay_rate,
            "tags": list(self.tags)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Synapse":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            weight=data.get("weight", 1.0),
            threshold=data.get("threshold", 0.3),
            synapse_type=SynapseType(data.get("synapse_type", "excitatory")),
            state=SynapseState(data.get("state", "dormant")),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_fired=data.get("last_fired"),
            fire_count=data.get("fire_count", 0),
            learning_rate=data.get("learning_rate", 0.01),
            decay_rate=data.get("decay_rate", 0.001),
            tags=set(data.get("tags", []))
        )


@dataclass
class Suggestion:
    """A suggestion generated by the neural system.
    
    Suggestions are outputs from mood neurons that can
    trigger actions or notifications.
    
    Attributes:
        id: Unique identifier
        source_mood: Mood that triggered this suggestion
        action_type: Type of action (light, climate, media, notification)
        action_data: Data for the action
        priority: Importance (0.0-1.0)
        confidence: Confidence in this suggestion (0.0-1.0)
        reasoning: Explanation for why this was suggested
        created_at: Creation timestamp
        expires_at: When this suggestion expires
        accepted: Whether user accepted
        rejected: Whether user rejected
    """
    id: str
    source_mood: str
    action_type: str
    action_data: Dict[str, Any]
    priority: float = 0.5
    confidence: float = 0.5
    reasoning: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    accepted: bool = False
    rejected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "source_mood": self.source_mood,
            "action_type": self.action_type,
            "action_data": self.action_data,
            "priority": round(self.priority, 3),
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accepted": self.accepted,
            "rejected": self.rejected
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Suggestion":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            source_mood=data["source_mood"],
            action_type=data["action_type"],
            action_data=data["action_data"],
            priority=data.get("priority", 0.5),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            expires_at=data.get("expires_at"),
            accepted=data.get("accepted", False),
            rejected=data.get("rejected", False)
        )