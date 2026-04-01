"""Module-Neuron Mapping — Struktur für Zone Automation (SOTA 2026).

Definiert WELCHE Neuronen zu WELCHEN Modulen in WELCHER Zone gehören.

Architecture:
- Zone → Module (light, climate, media, security)
- Module → Neurons (presence, brightness, temperature, etc.)
- Neurons → Status (autonomous/learning/off)
- Wenn ALLE Neuronen eines Moduls autonomous → Modul-Automation autonomous

Usage:
    mapping = get_module_neuron_map()
    
    # Get neurons for module
    neurons = mapping.get_module_neurons("living", "light")
    # → ["presence_living", "brightness_living", "light_living"]
    
    # Check if module can be autonomous
    can_autonomous = mapping.are_all_module_neurons_autonomous(
        "living", "light", neuron_tracker
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import threading

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# MODULE TYPES
# =============================================================================

class ModuleType(str, Enum):
    """Module Typen."""
    
    LIGHT = "light"
    CLIMATE = "climate"
    MEDIA = "media"
    SECURITY = "security"
    COVER = "cover"
    ENERGY = "energy"


# =============================================================================
# NEURON TYPES
# =============================================================================

class NeuronType(str, Enum):
    """Neuron Typen."""
    
    # Input Neurons (Sensors)
    PRESENCE = "presence"
    BRIGHTNESS = "brightness"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    MOTION = "motion"
    SOUND = "sound"
    ENERGY = "energy"
    TIME = "time"
    WEATHER = "weather"
    
    # Output Neurons (Actors)
    LIGHT = "light"
    CLIMATE_ACTOR = "climate_actor"
    MEDIA_ACTOR = "media_actor"
    COVER_ACTOR = "cover_actor"


# =============================================================================
# MODULE-NEURON MAPPING
# =============================================================================

@dataclass
class ModuleNeuronConfig:
    """Konfiguration für ein Modul."""
    
    module_type: ModuleType
    required_neurons: List[NeuronType]  # Muss vorhanden sein
    optional_neurons: List[NeuronType] = field(default_factory=list)  # Optional
    automations: List[str] = field(default_factory=list)  # Verfügbare Automationen
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_type": self.module_type.value,
            "required_neurons": [n.value for n in self.required_neurons],
            "optional_neurons": [n.value for n in self.optional_neurons],
            "automations": self.automations,
        }


class ModuleNeuronMap:
    """Mapping zwischen Zonen, Modulen und Neuronen."""
    
    # Standard-Konfiguration pro Modul-Typ
    DEFAULT_MODULE_CONFIGS: Dict[ModuleType, ModuleNeuronConfig] = {
        ModuleType.LIGHT: ModuleNeuronConfig(
            module_type=ModuleType.LIGHT,
            required_neurons=[NeuronType.PRESENCE, NeuronType.BRIGHTNESS],
            optional_neurons=[NeuronType.TIME, NeuronType.MOTION],
            automations=[
                "light_on_with_presence",
                "light_off_after_no_presence",
                "light_brightness_adaptive",
                "light_time_dependent",
                "light_mood_dependent",
            ],
        ),
        ModuleType.CLIMATE: ModuleNeuronConfig(
            module_type=ModuleType.CLIMATE,
            required_neurons=[NeuronType.TEMPERATURE, NeuronType.HUMIDITY],
            optional_neurons=[NeuronType.TIME, NeuronType.WEATHER],
            automations=[
                "climate_temperature_adaptive",
                "climate_humidity_control",
                "climate_time_dependent",
            ],
        ),
        ModuleType.MEDIA: ModuleNeuronConfig(
            module_type=ModuleType.MEDIA,
            required_neurons=[NeuronType.PRESENCE],
            optional_neurons=[NeuronType.TIME, NeuronType.SOUND],
            automations=[
                "media_start_with_presence",
                "media_stop_after_no_presence",
                "media_volume_adaptive",
            ],
        ),
        ModuleType.SECURITY: ModuleNeuronConfig(
            module_type=ModuleType.SECURITY,
            required_neurons=[NeuronType.MOTION],
            optional_neurons=[NeuronType.TIME, NeuronType.WEATHER],
            automations=[
                "security_alert_on_motion",
                "security_arm_when_away",
            ],
        ),
        ModuleType.COVER: ModuleNeuronConfig(
            module_type=ModuleType.COVER,
            required_neurons=[NeuronType.BRIGHTNESS, NeuronType.TIME],
            optional_neurons=[NeuronType.WEATHER],
            automations=[
                "cover_open_sunrise",
                "cover_close_sunset",
                "cover_brightness_adaptive",
            ],
        ),
        ModuleType.ENERGY: ModuleNeuronConfig(
            module_type=ModuleType.ENERGY,
            required_neurons=[NeuronType.ENERGY],
            optional_neurons=[NeuronType.TIME],
            automations=[
                "energy_save_mode",
                "energy_peak_avoidance",
            ],
        ),
    }
    
    def __init__(self):
        self._zone_modules: Dict[str, Dict[ModuleType, ModuleNeuronConfig]] = {}
        self._neuron_ids: Dict[str, Dict[str, str]] = {}  # zone → {neuron_type: entity_id}
        self._lock = threading.Lock()
        
        # Initialize default zones
        self._init_default_zones()
    
    def _init_default_zones(self) -> None:
        """Default Zonen initialisieren."""
        default_zones = {
            "living": "Wohnzimmer",
            "bath": "Bad",
            "kitchen": "Küche",
            "bedroom": "Schlafzimmer",
            "office": "Büro",
            "hallway": "Flur",
        }
        
        for zone_id, zone_name in default_zones.items():
            self._zone_modules[zone_id] = self.DEFAULT_MODULE_CONFIGS.copy()
            self._neuron_ids[zone_id] = {}
    
    def configure_zone_module(
        self,
        zone_id: str,
        module_type: ModuleType,
        config: Optional[ModuleNeuronConfig] = None,
    ) -> None:
        """Modul für Zone konfigurieren."""
        with self._lock:
            if zone_id not in self._zone_modules:
                self._zone_modules[zone_id] = {}
            
            if config:
                self._zone_modules[zone_id][module_type] = config
            else:
                # Use default
                self._zone_modules[zone_id][module_type] = self.DEFAULT_MODULE_CONFIGS.get(
                    module_type,
                    ModuleNeuronConfig(module_type=module_type, required_neurons=[])
                )
    
    def register_neuron(
        self,
        zone_id: str,
        neuron_type: NeuronType,
        neuron_id: str,
    ) -> None:
        """Neuron registrieren."""
        with self._lock:
            if zone_id not in self._neuron_ids:
                self._neuron_ids[zone_id] = {}
            
            key = f"{neuron_type.value}_{zone_id}"
            self._neuron_ids[zone_id][key] = neuron_id
            
            _LOGGER.debug(f"Registered neuron: {neuron_id} ({neuron_type.value} in {zone_id})")
    
    def get_module_neurons(
        self,
        zone_id: str,
        module_type: ModuleType,
    ) -> List[str]:
        """Neuron-IDs für Modul in Zone."""
        with self._lock:
            config = self._zone_modules.get(zone_id, {}).get(module_type)
            if not config:
                return []
            
            neurons = []
            zone_neurons = self._neuron_ids.get(zone_id, {})
            
            # Required neurons
            for neuron_type in config.required_neurons:
                key = f"{neuron_type.value}_{zone_id}"
                if key in zone_neurons:
                    neurons.append(zone_neurons[key])
            
            # Optional neurons
            for neuron_type in config.optional_neurons:
                key = f"{neuron_type.value}_{zone_id}"
                if key in zone_neurons:
                    neurons.append(zone_neurons[key])
            
            return neurons
    
    def get_module_config(
        self,
        zone_id: str,
        module_type: ModuleType,
    ) -> Optional[ModuleNeuronConfig]:
        """Modul-Konfiguration."""
        with self._lock:
            return self._zone_modules.get(zone_id, {}).get(module_type)
    
    def get_all_zones(self) -> List[str]:
        """Alle Zonen."""
        with self._lock:
            return list(self._zone_modules.keys())
    
    def get_zone_modules(self, zone_id: str) -> List[ModuleType]:
        """Module für Zone."""
        with self._lock:
            return list(self._zone_modules.get(zone_id, {}).keys())
    
    def get_full_map(self) -> Dict[str, Any]:
        """Vollständiges Mapping."""
        with self._lock:
            return {
                zone_id: {
                    "zone_name": zone_id,
                    "modules": {
                        module_type.value: config.to_dict()
                        for module_type, config in configs.items()
                    },
                    "neurons": self._neuron_ids.get(zone_id, {}),
                }
                for zone_id, configs in self._zone_modules.items()
            }
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total_neurons = sum(len(n) for n in self._neuron_ids.values())
            return {
                "total_zones": len(self._zone_modules),
                "total_modules": sum(len(m) for m in self._zone_modules.values()),
                "total_neurons": total_neurons,
                "neurons_per_zone": total_neurons / max(len(self._neuron_ids), 1),
            }


# =============================================================================
# Helper Functions
# =============================================================================

def are_all_module_neurons_autonomous(
    zone_id: str,
    module_type: ModuleType,
    neuron_tracker,  # NeuronStatusTracker
    map_instance: Optional[ModuleNeuronMap] = None,
) -> bool:
    """Prüfen ob ALLE Neuronen eines Moduls autonomous sind."""
    if map_instance is None:
        map_instance = get_module_neuron_map()
    
    # Get neuron IDs for module
    neuron_ids = map_instance.get_module_neurons(zone_id, module_type)
    
    if not neuron_ids:
        return False
    
    # Check if all are autonomous
    for neuron_id in neuron_ids:
        status = neuron_tracker.get_neuron(neuron_id, zone_id)
        if not status or status.mode.value != "autonomous":
            return False
    
    return True


def get_automations_for_module(
    zone_id: str,
    module_type: ModuleType,
    map_instance: Optional[ModuleNeuronMap] = None,
) -> List[str]:
    """Verfügbare Automationen für Modul."""
    if map_instance is None:
        map_instance = get_module_neuron_map()
    
    config = map_instance.get_module_config(zone_id, module_type)
    return config.automations if config else []


# =============================================================================
# Singleton
# =============================================================================

_map_instance: Optional[ModuleNeuronMap] = None


def get_module_neuron_map() -> ModuleNeuronMap:
    """Singleton-Zugriff."""
    global _map_instance
    
    if _map_instance is None:
        _map_instance = ModuleNeuronMap()
    
    return _map_instance
