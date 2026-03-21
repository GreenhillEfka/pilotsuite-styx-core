"""Presence Neurons for mmWave and motion detection.

Implements context neurons for presence detection:
- mmWavePresenceNeuron: High-precision presence via mmWave radar
- MotionPresenceNeuron: Traditional PIR/motion sensor presence
- CombinedPresenceNeuron: Multi-sensor fusion for robust presence

mmWave advantages:
- Detects presence without movement (breathing, micro-movements)
- No cameras needed (privacy-friendly)
- Works through light blankets/clothing
- Industry trend for smart homes 2026

See: Industry research from Perplexity audit (2026-02-15)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base import ContextNeuron, NeuronConfig, NeuronType

_LOGGER = logging.getLogger(__name__)


@dataclass
class PresenceState:
    """State for presence detection."""
    detected: bool = False
    confidence: float = 0.0
    last_motion: Optional[datetime] = None
    last_mmwave: Optional[datetime] = None
    entity_count: int = 0
    source: str = "none"  # "mmwave", "motion", "combined"


class mmWavePresenceNeuron(ContextNeuron):
    """Presence neuron using mmWave radar sensors.
    
    mmWave radar advantages:
    - Detects presence without movement (breathing detection)
    - No cameras needed (privacy-friendly)
    - Works in darkness
    - Can detect multiple people
    - Zone/room localization possible
    
    Compatible sensors:
    - Aqara Presence Sensor FP1/FP2
    - Tuya mmWave sensors
    - LD2410/LD2450 modules
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        # mmWave-specific config
        self.mmwave_entities: List[str] = config.extra.get("mmwave_entities", [])
        self.presence_timeout_seconds: int = config.extra.get("presence_timeout", 60)
        self.confidence_threshold: float = config.extra.get("confidence_threshold", 0.7)
        
        # State
        self._presence_state = PresenceState()
        self._last_update: Optional[datetime] = None
    
    @property
    def presence_state(self) -> PresenceState:
        return self._presence_state
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate mmWave presence.
        
        Returns:
            Presence confidence (0.0 - 1.0)
        """
        ha_states = context.get("ha_states", {})
        now = datetime.now(timezone.utc)
        
        detected_count = 0
        total_confidence = 0.0
        latest_detection = None
        
        for entity_id in self.mmwave_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            # Check for presence
            state_value = str(state.state).lower()
            
            # mmWave sensors typically report:
            # - "on"/"off" for presence
            # - Or numeric distance/target count
            is_present = state_value in ("on", "home", "detected", "true", "1")
            
            if is_present:
                detected_count += 1
                
                # Check for confidence attribute
                confidence = 1.0
                attrs = state.attributes or {}
                if "confidence" in attrs:
                    confidence = float(attrs["confidence"]) / 100.0
                elif "presence_confidence" in attrs:
                    confidence = float(attrs["presence_confidence"]) / 100.0
                elif "target_count" in attrs:
                    # More targets = higher confidence
                    target_count = int(attrs["target_count"])
                    confidence = min(1.0, 0.5 + target_count * 0.2)
                
                total_confidence += confidence
                
                # Track latest detection
                last_changed = state.last_changed
                if last_changed:
                    if isinstance(last_changed, str):
                        try:
                            last_changed = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        except Exception:
                            last_changed = now
                    if latest_detection is None or last_changed > latest_detection:
                        latest_detection = last_changed
        
        # Calculate presence score
        if detected_count == 0:
            # Check for recent presence within timeout
            if self._presence_state.last_mmwave:
                elapsed = (now - self._presence_state.last_mmwave).total_seconds()
                if elapsed < self.presence_timeout_seconds:
                    # Grace period - still considered present
                    grace_factor = 1.0 - (elapsed / self.presence_timeout_seconds)
                    self._presence_state.confidence = grace_factor * 0.5
                    return self._presence_state.confidence
            
            self._presence_state.detected = False
            self._presence_state.confidence = 0.0
            self._presence_state.source = "mmwave"
            return 0.0
        
        # Average confidence
        avg_confidence = total_confidence / detected_count
        
        # Update state
        self._presence_state.detected = True
        self._presence_state.confidence = avg_confidence
        self._presence_state.entity_count = detected_count
        self._presence_state.last_mmwave = latest_detection or now
        self._presence_state.source = "mmwave"
        self._last_update = now
        
        return avg_confidence
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "mmWavePresenceNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "detected": self._presence_state.detected,
            "confidence": self._presence_state.confidence,
            "source": self._presence_state.source,
            "entity_count": self._presence_state.entity_count,
            "last_detection": self._presence_state.last_mmwave.isoformat() if self._presence_state.last_mmwave else None,
        }


class MotionPresenceNeuron(ContextNeuron):
    """Presence neuron using traditional motion sensors (PIR, etc.).
    
    Works with:
    - PIR motion sensors
    - Door/window sensors (activity-based)
    - Light switch activity
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        self.motion_entities: List[str] = config.extra.get("motion_entities", [])
        self.presence_timeout_seconds: int = config.extra.get("presence_timeout", 120)
        
        self._presence_state = PresenceState()
        self._last_update: Optional[datetime] = None
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate motion-based presence."""
        ha_states = context.get("ha_states", {})
        now = datetime.now(timezone.utc)
        
        latest_motion = None
        motion_count = 0
        
        for entity_id in self.motion_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            state_value = str(state.state).lower()
            is_active = state_value in ("on", "detected", "motion", "open")
            
            if is_active:
                motion_count += 1
                last_changed = state.last_changed
                if last_changed:
                    if isinstance(last_changed, str):
                        try:
                            last_changed = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        except Exception:
                            last_changed = now
                    if latest_motion is None or last_changed > latest_motion:
                        latest_motion = last_changed
        
        # Check timeout
        if latest_motion:
            elapsed = (now - latest_motion).total_seconds()
            
            if elapsed < self.presence_timeout_seconds:
                # Still in presence window
                presence_factor = 1.0 - (elapsed / self.presence_timeout_seconds)
                
                self._presence_state.detected = True
                self._presence_state.confidence = presence_factor
                self._presence_state.last_motion = latest_motion
                self._presence_state.entity_count = motion_count
                self._presence_state.source = "motion"
                
                return presence_factor
        
        # No recent motion
        self._presence_state.detected = False
        self._presence_state.confidence = 0.0
        self._presence_state.source = "motion"
        
        return 0.0
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "MotionPresenceNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "detected": self._presence_state.detected,
            "confidence": self._presence_state.confidence,
            "source": self._presence_state.source,
            "last_motion": self._presence_state.last_motion.isoformat() if self._presence_state.last_motion else None,
        }


class CombinedPresenceNeuron(ContextNeuron):
    """Presence neuron combining mmWave and motion sensors.
    
    Uses sensor fusion for robust presence detection:
    - mmWave provides breathing detection (static presence)
    - Motion provides activity detection
    
    Fusion strategy:
    - OR logic: present if EITHER detects presence
    - Confidence weighted by sensor type
    - mmWave has higher weight for static presence
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        self.mmwave_entities: List[str] = config.extra.get("mmwave_entities", [])
        self.motion_entities: List[str] = config.extra.get("motion_entities", [])
        self.presence_timeout_seconds: int = config.extra.get("presence_timeout", 120)
        
        # Weights for fusion
        self.mmwave_weight: float = config.extra.get("mmwave_weight", 0.7)
        self.motion_weight: float = config.extra.get("motion_weight", 0.3)
        
        self._presence_state = PresenceState()
        self._mmwave_neuron: Optional[mmWavePresenceNeuron] = None
        self._motion_neuron: Optional[MotionPresenceNeuron] = None
    
    def _ensure_neurons(self):
        """Create sub-neurons if needed."""
        if self._mmwave_neuron is None and self.mmwave_entities:
            mmwave_config = NeuronConfig(
                id=f"{self.config.id}_mmwave",
                name=f"{self.config.name} (mmWave)",
                extra={
                    "mmwave_entities": self.mmwave_entities,
                    "presence_timeout": self.presence_timeout_seconds,
                },
            )
            self._mmwave_neuron = mmWavePresenceNeuron(mmwave_config)
        
        if self._motion_neuron is None and self.motion_entities:
            motion_config = NeuronConfig(
                id=f"{self.config.id}_motion",
                name=f"{self.config.name} (Motion)",
                extra={
                    "motion_entities": self.motion_entities,
                    "presence_timeout": self.presence_timeout_seconds,
                },
            )
            self._motion_neuron = MotionPresenceNeuron(motion_config)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate combined presence using sensor fusion."""
        self._ensure_neurons()
        
        mmwave_confidence = 0.0
        motion_confidence = 0.0
        
        if self._mmwave_neuron:
            mmwave_confidence = self._mmwave_neuron.evaluate(context)
        
        if self._motion_neuron:
            motion_confidence = self._motion_neuron.evaluate(context)
        
        # Weighted fusion
        combined = (mmwave_confidence * self.mmwave_weight + 
                   motion_confidence * self.motion_weight)
        
        # Normalize
        total_weight = self.mmwave_weight + self.motion_weight
        if total_weight > 0:
            combined /= total_weight
        
        # Update state
        self._presence_state.detected = combined > 0.3
        self._presence_state.confidence = combined
        self._presence_state.source = "combined"
        
        if self._mmwave_neuron:
            self._presence_state.last_mmwave = self._mmwave_neuron.presence_state.last_mmwave
        if self._motion_neuron:
            self._presence_state.last_motion = self._motion_neuron.presence_state.last_motion
        
        return combined
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "CombinedPresenceNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        state = {
            "detected": self._presence_state.detected,
            "confidence": self._presence_state.confidence,
            "source": self._presence_state.source,
        }
        
        if self._mmwave_neuron:
            state["mmwave"] = self._mmwave_neuron.get_state()
        if self._motion_neuron:
            state["motion"] = self._motion_neuron.get_state()
        
        return state


# Factory functions
def create_mmwave_presence_neuron(
    entity_ids: List[str],
    timeout: int = 60,
    name: str = "mmWave Presence",
) -> mmWavePresenceNeuron:
    """Create mmWave presence neuron."""
    config = NeuronConfig(
        id="presence_mmwave",
        name=name,
        extra={
            "mmwave_entities": entity_ids,
            "presence_timeout": timeout,
        },
    )
    return mmWavePresenceNeuron(config)


def create_motion_presence_neuron(
    entity_ids: List[str],
    timeout: int = 120,
    name: str = "Motion Presence",
) -> MotionPresenceNeuron:
    """Create motion presence neuron."""
    config = NeuronConfig(
        id="presence_motion",
        name=name,
        extra={
            "motion_entities": entity_ids,
            "presence_timeout": timeout,
        },
    )
    return MotionPresenceNeuron(config)


def create_combined_presence_neuron(
    mmwave_entities: List[str],
    motion_entities: List[str],
    timeout: int = 120,
    mmwave_weight: float = 0.7,
    motion_weight: float = 0.3,
    name: str = "Combined Presence",
) -> CombinedPresenceNeuron:
    """Create combined presence neuron."""
    config = NeuronConfig(
        id="presence_combined",
        name=name,
        extra={
            "mmwave_entities": mmwave_entities,
            "motion_entities": motion_entities,
            "presence_timeout": timeout,
            "mmwave_weight": mmwave_weight,
            "motion_weight": motion_weight,
        },
    )
    return CombinedPresenceNeuron(config)


# Register neuron classes
PRESENCE_NEURON_CLASSES = {
    "mmwave_presence": mmWavePresenceNeuron,
    "motion_presence": MotionPresenceNeuron,
    "combined_presence": CombinedPresenceNeuron,
}