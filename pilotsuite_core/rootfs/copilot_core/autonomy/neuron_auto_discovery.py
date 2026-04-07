"""Neuron Auto-Discovery — Automatische Neuron-Registrierung (SOTA 2026).

Features:
1. Auto-Discovery bei HA Entity Hinzufügung
2. Entity → Neuron Mapping (domain-based)
3. Zone Auto-Assignment (via Area Registry)
4. Neuron Mode Auto-Set (default: learning)
5. Discovery Event → Habitus Learning

Integration:
- HA Entity Registry Events
- ModuleNeuronMap Registration
- NeuronStatusTracker Auto-Update
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import threading
import re

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# ENTITY → NEURON MAPPING
# =============================================================================

class EntityDomain(str, Enum):
    """HA Entity Domains."""
    
    LIGHT = "light"
    SWITCH = "switch"
    BINARY_SENSOR = "binary_sensor"
    SENSOR = "sensor"
    CLIMATE = "climate"
    MEDIA_PLAYER = "media_player"
    COVER = "cover"
    LOCK = "lock"
    CAMERA = "camera"


# Mapping: Entity Domain → Neuron Type
ENTITY_NEURON_MAP: Dict[str, List[str]] = {
    EntityDomain.LIGHT.value: ["light"],
    EntityDomain.SWITCH.value: ["light"],
    EntityDomain.BINARY_SENSOR.value: ["presence", "motion"],
    EntityDomain.SENSOR.value: ["brightness", "temperature", "humidity", "energy", "sound"],
    EntityDomain.CLIMATE.value: ["climate_actor"],
    EntityDomain.MEDIA_PLAYER.value: ["media_actor"],
    EntityDomain.COVER.value: ["cover_actor"],
    EntityDomain.LOCK.value: ["security"],
    EntityDomain.CAMERA.value: ["security"],
}

# Sub-Typ Mapping (aus entity_id oder attributes)
SUBTYPE_KEYWORDS: Dict[str, List[str]] = {
    "presence": ["presence", "occupancy", "motion"],
    "motion": ["motion"],
    "brightness": ["brightness", "illuminance", "light_level"],
    "temperature": ["temperature", "temp"],
    "humidity": ["humidity"],
    "energy": ["power", "energy", "electricity"],
    "sound": ["sound", "noise", "volume"],
    "light": ["light"],
    "climate_actor": ["climate", "thermostat", "hvac"],
    "media_actor": ["media", "tv", "speaker", "audio"],
    "cover_actor": ["cover", "blind", "shutter", "curtain"],
    "security": ["lock", "camera", "alarm"],
}


@dataclass
class DiscoveredNeuron:
    """Entdecktes Neuron."""
    
    neuron_id: str
    entity_id: str
    neuron_type: str
    zone_id: Optional[str]
    area_id: Optional[str]
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    auto_assigned: bool = True
    confidence: float = 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# NEURON AUTO-DISCOVERY ENGINE
# =============================================================================

class NeuronAutoDiscovery:
    """Auto-Discovery für Neuronen."""
    
    def __init__(self, module_neuron_map, neuron_tracker):
        self._module_neuron_map = module_neuron_map
        self._neuron_tracker = neuron_tracker
        self._discovered_neurons: Dict[str, DiscoveredNeuron] = {}
        self._entity_neuron_map: Dict[str, str] = {}  # entity_id → neuron_id
        self._discovery_hooks: List[Callable[[DiscoveredNeuron], None]] = []
        self._lock = threading.Lock()
        _LOGGER.info("NeuronAutoDiscovery initialized")
    
    def discover_entity(
        self,
        entity_id: str,
        entity_data: Dict[str, Any],
        area_id: Optional[str] = None,
    ) -> Optional[DiscoveredNeuron]:
        """Entity entdecken und Neuron registrieren."""
        # Parse entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if not domain:
            return None
        
        # Get neuron types for domain
        neuron_types = ENTITY_NEURON_MAP.get(domain, [])
        if not neuron_types:
            return None  # Unknown domain
        
        # Determine specific neuron type from entity_id and attributes
        neuron_type = self._determine_neuron_type(entity_id, entity_data, neuron_types)
        
        # Generate neuron_id
        neuron_id = f"{neuron_type}_{entity_id.replace('.', '_')}"
        
        # Determine zone from area
        zone_id = area_id if area_id else None
        
        # Create discovered neuron
        discovered = DiscoveredNeuron(
            neuron_id=neuron_id,
            entity_id=entity_id,
            neuron_type=neuron_type,
            zone_id=zone_id,
            area_id=area_id,
        )
        
        with self._lock:
            # Register
            self._discovered_neurons[neuron_id] = discovered
            self._entity_neuron_map[entity_id] = neuron_id
            
            # Register in ModuleNeuronMap
            self._module_neuron_map.register_neuron(
                zone_id=zone_id or "unknown",
                neuron_type=self._str_to_neuron_type(neuron_type),
                neuron_id=neuron_id,
            )
            
            # Update NeuronStatusTracker (default: learning mode)
            from .zone_automation_controller import NeuronMode
            self._neuron_tracker.update_neuron(
                neuron_id=neuron_id,
                zone_id=zone_id or "unknown",
                mode=NeuronMode.LEARNING,
                activity_type="auto_discovery",
            )
        
        _LOGGER.info(f"Discovered neuron: {neuron_id} from entity {entity_id}")
        
        # Notify hooks
        for hook in self._discovery_hooks:
            try:
                hook(discovered)
            except Exception as e:
                _LOGGER.error(f"Discovery hook error: {e}")
        
        return discovered
    
    def _determine_neuron_type(
        self,
        entity_id: str,
        entity_data: Dict[str, Any],
        neuron_types: List[str],
    ) -> str:
        """Spezifischen Neuron-Typ bestimmen."""
        entity_lower = entity_id.lower()
        attributes = entity_data.get("attributes", {})
        friendly_name = attributes.get("friendly_name", "").lower()
        device_class = attributes.get("device_class", "").lower()
        
        # Search in keywords
        for neuron_type in neuron_types:
            keywords = SUBTYPE_KEYWORDS.get(neuron_type, [])
            
            # Check entity_id
            if any(kw in entity_lower for kw in keywords):
                return neuron_type
            
            # Check friendly_name
            if any(kw in friendly_name for kw in keywords):
                return neuron_type
            
            # Check device_class
            if any(kw in device_class for kw in keywords):
                return neuron_type
        
        # Default to first type
        return neuron_types[0] if neuron_types else "unknown"
    
    def _str_to_neuron_type(self, neuron_type_str: str):
        """String zu NeuronType Enum."""
        from .module_neuron_map import NeuronType
        try:
            return NeuronType(neuron_type_str)
        except ValueError:
            # Custom neuron type
            from .module_neuron_map import NeuronType
            return NeuronType.PRESENCE  # Default
    
    def get_neuron_for_entity(self, entity_id: str) -> Optional[DiscoveredNeuron]:
        """Neuron für Entity holen."""
        with self._lock:
            neuron_id = self._entity_neuron_map.get(entity_id)
            if neuron_id:
                return self._discovered_neurons.get(neuron_id)
            return None
    
    def get_discovered_neurons(self) -> List[DiscoveredNeuron]:
        """Alle entdeckten Neuronen."""
        with self._lock:
            return list(self._discovered_neurons.values())
    
    def register_discovery_hook(self, hook: Callable[[DiscoveredNeuron], None]) -> None:
        """Hook für neue Entdeckungen."""
        self._discovery_hooks.append(hook)
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_discovered": len(self._discovered_neurons),
                "entities_mapped": len(self._entity_neuron_map),
                "discovery_hooks": len(self._discovery_hooks),
                "by_neuron_type": self._count_by_type(),
            }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count by neuron type."""
        counts: Dict[str, int] = {}
        for neuron in self._discovered_neurons.values():
            counts[neuron.neuron_type] = counts.get(neuron.neuron_type, 0) + 1
        return counts


# =============================================================================
# Singleton Factory
# =============================================================================

_discovery_instance: Optional[NeuronAutoDiscovery] = None


def get_neuron_auto_discovery(module_neuron_map, neuron_tracker) -> NeuronAutoDiscovery:
    """Singleton-Zugriff."""
    global _discovery_instance
    
    if _discovery_instance is None:
        _discovery_instance = NeuronAutoDiscovery(module_neuron_map, neuron_tracker)
    
    return _discovery_instance
