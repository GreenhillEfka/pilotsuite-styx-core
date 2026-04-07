"""Zone-Aware Neuron Manager — Slice 67.

Optimiert den Neuron Manager für Habituszone-Konfigurierbarkeit.

Features:
- Per-Zone Neuron Configuration
- Zone-spezifische Neuron-Prioritäten
- Zone Context Propagation
- Module-to-Zone Mapping
- Zone-aware Evaluation Pipeline
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
import uuid

from .base import ContextNeuron, StateNeuron, MoodNeuron, NeuronConfig, NeuronType
from .presence import mmWavePresenceNeuron, MotionPresenceNeuron, CombinedPresenceNeuron, PresenceState
from .context import LightLevelNeuron, TimeOfDayNeuron, WeatherNeuron
from .state import ComfortIndexNeuron, EnergyLevelNeuron

logger = logging.getLogger(__name__)


class ZoneType(str, Enum):
    """Habituszone-Typen."""
    LIVING = "living"
    BATH = "bath"
    KITCHEN = "kitchen"
    OFFICE = "office"
    HALLWAY = "hallway"
    BEDROOM = "bedroom"
    ROOM_MIRA = "room_mira"
    ROOM_PAUL = "room_paul"
    TERRACE = "terrace"
    OUTSIDE = "outside"
    CUSTOM = "custom"


class ModuleType(str, Enum):
    """Modul-Typen für Habituszonen."""
    LIGHT = "light"
    CLIMATE = "climate"
    MOTION = "motion"
    PRESENCE = "presence"
    MUSIC = "music"
    VOLUME = "volume"
    TV = "tv"
    CAMERA = "camera"
    BLINDS = "blinds"
    ENERGY = "energy"
    COMFORT = "comfort"
    CUSTOM = "custom"


@dataclass
class ZoneModuleConfig:
    """Konfiguration eines Moduls für eine Habituszone."""
    module_type: ModuleType
    enabled: bool = True
    priority: int = 50  # 0-100, höhere = wichtiger
    suggestion_mode: str = "explainable_manual"  # "auto", "explainable_manual", "manual_only"
    neuron_targets: List[str] = field(default_factory=list)
    input_signals: List[str] = field(default_factory=list)
    output_mode: str = "service_call_or_proposal"
    zone_overrides: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_type": self.module_type.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "suggestion_mode": self.suggestion_mode,
            "neuron_targets": self.neuron_targets,
            "input_signals": self.input_signals,
            "output_mode": self.output_mode,
            "zone_overrides": self.zone_overrides,
        }


@dataclass
class HabitusZoneConfig:
    """Konfiguration einer Habituszone."""
    zone_id: str
    zone_type: ZoneType
    name: str
    modules: Dict[ModuleType, ZoneModuleConfig] = field(default_factory=dict)
    default_neuron_config: Dict[str, Any] = field(default_factory=dict)
    quiet_hours_start: Optional[int] = None  # 0-23
    quiet_hours_end: Optional[int] = None
    occupancy_timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_type": self.zone_type.value,
            "name": self.name,
            "modules": {k.value: v.to_dict() for k, v in self.modules.items()},
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "occupancy_timeout_seconds": self.occupancy_timeout_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ZoneNeuronState:
    """State eines Neurons in einer Zone."""
    zone_id: str
    neuron_id: str
    neuron_type: str
    value: float
    confidence: float
    last_update: str
    module_context: Optional[str] = None


@dataclass
class ZoneEvaluationResult:
    """Ergebnis einer Zone-Evaluation."""
    zone_id: str
    timestamp: str
    context_values: Dict[str, float]
    state_values: Dict[str, float]
    mood_values: Dict[str, float]
    module_states: Dict[str, Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    dominant_mood: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "timestamp": self.timestamp,
            "context_values": self.context_values,
            "state_values": self.state_values,
            "mood_values": self.mood_values,
            "module_states": self.module_states,
            "suggestions": self.suggestions,
            "dominant_mood": self.dominant_mood,
            "confidence": self.confidence,
        }


class ZoneAwareNeuronManager:
    """Zone-aware Neuron Manager für Habituszonen.
    
    Architecture:
        HA States → Zone Context → Per-Zone Neurons → Module Suggestions
    
    Usage:
        manager = ZoneAwareNeuronManager()
        manager.register_zone(zone_config)
        manager.configure_module_neurons(zone_id, module_type, neurons)
        
        # Evaluate specific zone
        result = manager.evaluate_zone(zone_id, ha_states)
    """
    
    def __init__(self):
        self._zones: Dict[str, HabitusZoneConfig] = {}
        self._zone_neurons: Dict[str, Dict[str, BaseNeuron]] = {}  # zone_id -> neuron_id -> neuron
        self._zone_module_configs: Dict[str, Dict[ModuleType, ZoneModuleConfig]] = {}
        self._zone_states: Dict[str, Dict[str, ZoneNeuronState]] = {}
        self._ha_states: Dict[str, Any] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        
        logger.info("ZoneAwareNeuronManager initialized")
    
    def register_zone(self, config: HabitusZoneConfig) -> str:
        """Register a Habitus zone."""
        zone_id = config.zone_id
        
        self._zones[zone_id] = config
        self._zone_neurons[zone_id] = {}
        self._zone_module_configs[zone_id] = config.modules.copy()
        self._zone_states[zone_id] = {}
        
        logger.info("Zone registered: %s (%s)", config.name, zone_id)
        
        return zone_id
    
    def unregister_zone(self, zone_id: str) -> bool:
        """Unregister a zone."""
        if zone_id not in self._zones:
            return False
        
        del self._zones[zone_id]
        del self._zone_neurons[zone_id]
        del self._zone_module_configs[zone_id]
        del self._zone_states[zone_id]
        
        return True
    
    def get_zone(self, zone_id: str) -> Optional[HabitusZoneConfig]:
        """Get zone configuration."""
        return self._zones.get(zone_id)
    
    def list_zones(self) -> List[Dict[str, Any]]:
        """List all zones."""
        return [z.to_dict() for z in self._zones.values()]
    
    def configure_module_neurons(self, zone_id: str, module_type: ModuleType,
                                neurons: List[BaseNeuron]) -> bool:
        """Configure neurons for a specific module in a zone."""
        if zone_id not in self._zones:
            return False
        
        for neuron in neurons:
            neuron_id = f"{zone_id}_{module_type.value}_{neuron.neuron_id}"
            self._zone_neurons[zone_id][neuron_id] = neuron
        
        logger.info("Configured %d neurons for module %s in zone %s",
                   len(neurons), module_type.value, zone_id)
        
        return True
    
    def set_module_config(self, zone_id: str, module_type: ModuleType,
                         config: ZoneModuleConfig) -> bool:
        """Set module configuration for a zone."""
        if zone_id not in self._zones:
            return False
        
        self._zone_module_configs[zone_id][module_type] = config
        
        # Update zone config
        self._zones[zone_id].modules[module_type] = config
        
        logger.info("Module config updated: %s in %s", module_type.value, zone_id)
        
        return True
    
    def get_module_config(self, zone_id: str,
                         module_type: ModuleType) -> Optional[ZoneModuleConfig]:
        """Get module configuration for a zone."""
        return self._zone_module_configs.get(zone_id, {}).get(module_type)
    
    def enable_module(self, zone_id: str, module_type: ModuleType) -> bool:
        """Enable a module in a zone."""
        if zone_id not in self._zone_module_configs:
            return False
        
        config = self._zone_module_configs[zone_id].get(module_type)
        if not config:
            return False
        
        config.enabled = True
        
        return True
    
    def disable_module(self, zone_id: str, module_type: ModuleType) -> bool:
        """Disable a module in a zone."""
        if zone_id not in self._zone_module_configs:
            return False
        
        config = self._zone_module_configs[zone_id].get(module_type)
        if not config:
            return False
        
        config.enabled = False
        
        return True
    
    def set_module_priority(self, zone_id: str, module_type: ModuleType,
                           priority: int) -> bool:
        """Set module priority in a zone."""
        if zone_id not in self._zone_module_configs:
            return False
        
        config = self._zone_module_configs[zone_id].get(module_type)
        if not config:
            return False
        
        config.priority = max(0, min(100, priority))
        
        return True
    
    def update_ha_states(self, zone_id: str, states: Dict[str, Any]) -> None:
        """Update HA states for a zone."""
        self._ha_states[zone_id] = states
    
    def evaluate_zone(self, zone_id: str,
                     ha_states: Optional[Dict[str, Any]] = None) -> ZoneEvaluationResult:
        """Evaluate all neurons for a specific zone."""
        if zone_id not in self._zones:
            return ZoneEvaluationResult(
                zone_id=zone_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                context_values={},
                state_values={},
                mood_values={},
                module_states={},
                suggestions=[],
            )
        
        zone_config = self._zones[zone_id]
        now = datetime.now(timezone.utc)
        
        # Update HA states if provided
        if ha_states:
            self.update_ha_states(zone_id, ha_states)
        
        zone_ha_states = self._ha_states.get(zone_id, {})
        
        # Evaluate context neurons
        context_values = {}
        for neuron_id, neuron in self._zone_neurons[zone_id].items():
            if neuron.neuron_type == NeuronType.CONTEXT:
                value = neuron.evaluate({"ha_states": zone_ha_states})
                context_values[neuron_id] = value
                
                # Update state
                self._zone_states[zone_id][neuron_id] = ZoneNeuronState(
                    zone_id=zone_id,
                    neuron_id=neuron_id,
                    neuron_type=neuron.neuron_type.value,
                    value=value,
                    confidence=neuron.get_confidence() if hasattr(neuron, 'get_confidence') else 1.0,
                    last_update=now.isoformat(),
                )
        
        # Evaluate state neurons
        state_values = {}
        for neuron_id, neuron in self._zone_neurons[zone_id].items():
            if neuron.neuron_type == NeuronType.STATE:
                value = neuron.evaluate({
                    "ha_states": zone_ha_states,
                    "context": context_values,
                })
                state_values[neuron_id] = value
                
                self._zone_states[zone_id][neuron_id] = ZoneNeuronState(
                    zone_id=zone_id,
                    neuron_id=neuron_id,
                    neuron_type=neuron.neuron_type.value,
                    value=value,
                    confidence=neuron.get_confidence() if hasattr(neuron, 'get_confidence') else 1.0,
                    last_update=now.isoformat(),
                )
        
        # Evaluate mood neurons
        mood_values = {}
        for neuron_id, neuron in self._zone_neurons[zone_id].items():
            if neuron.neuron_type == NeuronType.MOOD:
                value = neuron.evaluate({
                    "ha_states": zone_ha_states,
                    "context": context_values,
                    "state": state_values,
                })
                mood_values[neuron_id] = value
        
        # Determine dominant mood
        dominant_mood = None
        max_value = 0.0
        for mood, value in mood_values.items():
            if value > max_value:
                max_value = value
                dominant_mood = mood
        
        # Generate module states and suggestions
        module_states = {}
        suggestions = []
        
        for module_type, module_config in self._zone_module_configs.get(zone_id, {}).items():
            if not module_config.enabled:
                continue
            
            module_state = self._evaluate_module(
                zone_id, module_type, module_config,
                context_values, state_values, mood_values,
            )
            module_states[module_type.value] = module_state
            
            # Generate suggestions
            if module_state.get("suggestions"):
                suggestions.extend(module_state["suggestions"])
        
        return ZoneEvaluationResult(
            zone_id=zone_id,
            timestamp=now.isoformat(),
            context_values=context_values,
            state_values=state_values,
            mood_values=mood_values,
            module_states=module_states,
            suggestions=suggestions,
            dominant_mood=dominant_mood,
            confidence=max_value,
        )
    
    def _evaluate_module(self, zone_id: str, module_type: ModuleType,
                        module_config: ZoneModuleConfig,
                        context_values: Dict[str, float],
                        state_values: Dict[str, float],
                        mood_values: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate a specific module in a zone."""
        zone_ha_states = self._ha_states.get(zone_id, {})
        
        # Collect relevant neuron values
        relevant_neurons = module_config.neuron_targets
        neuron_inputs = {}
        
        for neuron_id, value in context_values.items():
            if any(target in neuron_id for target in relevant_neurons):
                neuron_inputs[neuron_id] = value
        
        for neuron_id, value in state_values.items():
            if any(target in neuron_id for target in relevant_neurons):
                neuron_inputs[neuron_id] = value
        
        # Module-specific evaluation logic
        module_state = {
            "module_type": module_type.value,
            "enabled": module_config.enabled,
            "priority": module_config.priority,
            "suggestion_mode": module_config.suggestion_mode,
            "neuron_inputs": neuron_inputs,
            "suggestions": [],
        }
        
        # Generate suggestions based on module type
        if module_type == ModuleType.LIGHT:
            module_state["suggestions"] = self._generate_light_suggestions(
                zone_id, module_config, neuron_inputs, zone_ha_states,
            )
        elif module_type == ModuleType.CLIMATE:
            module_state["suggestions"] = self._generate_climate_suggestions(
                zone_id, module_config, neuron_inputs, zone_ha_states,
            )
        elif module_type == ModuleType.MOTION:
            module_state["suggestions"] = self._generate_motion_suggestions(
                zone_id, module_config, neuron_inputs, zone_ha_states,
            )
        elif module_type == ModuleType.PRESENCE:
            module_state["suggestions"] = self._generate_presence_suggestions(
                zone_id, module_config, neuron_inputs, zone_ha_states,
            )
        
        return module_state
    
    def _generate_light_suggestions(self, zone_id: str,
                                   module_config: ZoneModuleConfig,
                                   neuron_inputs: Dict[str, float],
                                   ha_states: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate light-related suggestions."""
        suggestions = []
        
        # Check light level context
        light_level = neuron_inputs.get("light_level", 0.5)
        presence = neuron_inputs.get("presence", 0.0)
        
        if presence > 0.5 and light_level < 0.3:
            suggestions.append({
                "type": "light_on",
                "priority": module_config.priority,
                "zone_id": zone_id,
                "reason": "Presence detected, low light level",
                "action": {"service": "light.turn_on", "brightness_pct": 70},
            })
        elif presence < 0.3 and light_level > 0.7:
            suggestions.append({
                "type": "light_off",
                "priority": module_config.priority,
                "zone_id": zone_id,
                "reason": "No presence, high light level",
                "action": {"service": "light.turn_off"},
            })
        
        return suggestions
    
    def _generate_climate_suggestions(self, zone_id: str,
                                     module_config: ZoneModuleConfig,
                                     neuron_inputs: Dict[str, float],
                                     ha_states: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate climate-related suggestions."""
        suggestions = []
        
        comfort = neuron_inputs.get("comfort_index", 0.5)
        presence = neuron_inputs.get("presence", 0.0)
        
        if presence > 0.5:
            if comfort < 0.3:
                suggestions.append({
                    "type": "climate_adjust",
                    "priority": module_config.priority,
                    "zone_id": zone_id,
                    "reason": "Low comfort, presence detected",
                    "action": {"service": "climate.set_hvac_mode", "hvac_mode": "heat"},
                })
            elif comfort > 0.8:
                suggestions.append({
                    "type": "climate_eco",
                    "priority": module_config.priority,
                    "zone_id": zone_id,
                    "reason": "High comfort, can reduce energy",
                    "action": {"service": "climate.set_hvac_mode", "hvac_mode": "eco"},
                })
        
        return suggestions
    
    def _generate_motion_suggestions(self, zone_id: str,
                                    module_config: ZoneModuleConfig,
                                    neuron_inputs: Dict[str, float],
                                    ha_states: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate motion-related suggestions."""
        suggestions = []
        
        motion = neuron_inputs.get("motion", 0.0)
        
        if motion > 0.7:
            suggestions.append({
                "type": "motion_detected",
                "priority": module_config.priority,
                "zone_id": zone_id,
                "reason": "Motion detected",
                "metadata": {"motion_level": motion},
            })
        
        return suggestions
    
    def _generate_presence_suggestions(self, zone_id: str,
                                      module_config: ZoneModuleConfig,
                                      neuron_inputs: Dict[str, float],
                                      ha_states: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate presence-related suggestions."""
        suggestions = []
        
        presence = neuron_inputs.get("presence", 0.0)
        confidence = neuron_inputs.get("presence_confidence", 0.0)
        
        if presence > 0.5 and confidence > 0.7:
            suggestions.append({
                "type": "presence_confirmed",
                "priority": module_config.priority,
                "zone_id": zone_id,
                "reason": "Presence confirmed with high confidence",
                "metadata": {"presence_level": presence, "confidence": confidence},
            })
        elif presence < 0.3:
            suggestions.append({
                "type": "absence_detected",
                "priority": module_config.priority,
                "zone_id": zone_id,
                "reason": "No presence detected",
            })
        
        return suggestions
    
    def get_zone_state(self, zone_id: str) -> Dict[str, ZoneNeuronState]:
        """Get current state for a zone."""
        return self._zone_states.get(zone_id, {})
    
    def get_neuron_state(self, zone_id: str, neuron_id: str) -> Optional[ZoneNeuronState]:
        """Get state for a specific neuron in a zone."""
        return self._zone_states.get(zone_id, {}).get(neuron_id)
    
    def register_callback(self, zone_id: str, callback: Callable) -> None:
        """Register callback for zone updates."""
        if zone_id not in self._callbacks:
            self._callbacks[zone_id] = []
        self._callbacks[zone_id].append(callback)
    
    def _notify_callbacks(self, zone_id: str, result: ZoneEvaluationResult) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks.get(zone_id, []):
            try:
                callback(result)
            except Exception as e:
                logger.exception("Callback failed for zone %s: %s", zone_id, e)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get zone-aware neuron statistics."""
        total_neurons = sum(len(n) for n in self._zone_neurons.values())
        total_zones = len(self._zones)
        enabled_modules = sum(
            sum(1 for m in mods.values() if m.enabled)
            for mods in self._zone_module_configs.values()
        )
        
        return {
            "total_zones": total_zones,
            "total_neurons": total_neurons,
            "total_modules": enabled_modules,
            "zones": list(self._zones.keys()),
        }


def create_zone_aware_neuron_manager() -> ZoneAwareNeuronManager:
    """Factory function to create zone-aware neuron manager."""
    return ZoneAwareNeuronManager()
