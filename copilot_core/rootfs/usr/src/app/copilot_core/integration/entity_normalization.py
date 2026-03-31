"""Entity Normalization Layer — Slice 69.

Normalisiert Home Assistant Entitäten für Habituszonen.

Features:
- HA Entity → Zone Mapping
- Entity Normalization (einheitliche Wertebereiche)
- Zone Entity Registry
- Normalized State Stream
- Entity Type Detection (sensor, binary_sensor, light, climate, etc.)
- Value Standardization (0-1, °C, %, etc.)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Entity types."""
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    LIGHT = "light"
    SWITCH = "switch"
    CLIMATE = "climate"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    CAMERA = "camera"
    DEVICE_TRACKER = "device_tracker"
    PERSON = "person"
    CUSTOM = "custom"


class NormalizedType(Enum):
    """Normalized value types."""
    PRESENCE = "presence"  # 0.0-1.0
    MOTION = "motion"  # 0.0-1.0
    LIGHT_LEVEL = "light_level"  # 0.0-1.0
    TEMPERATURE = "temperature"  # °C
    HUMIDITY = "humidity"  # %
    BRIGHTNESS = "brightness"  # 0.0-1.0
    COLOR_TEMP = "color_temp"  # Kelvin
    ENERGY = "energy"  # kWh
    POWER = "power"  # W
    VOLUME = "volume"  # 0.0-1.0
    STATE = "state"  # on/off → 0.0/1.0
    CUSTOM = "custom"


class ZoneEntityType(Enum):
    """Zone entity categories."""
    INPUT = "input"  # Sensors providing data to zone
    OUTPUT = "output"  # Actuators controlled by zone
    CONTEXT = "context"  # Context providers (time, weather)


@dataclass
class EntityMapping:
    """Mapping from HA entity to zone entity."""
    mapping_id: str
    ha_entity_id: str
    zone_id: str
    normalized_type: NormalizedType
    entity_type: EntityType
    name: str
    unit_of_measurement: Optional[str] = None
    normalization_fn: Optional[str] = None  # "linear", "threshold", "boolean"
    normalization_params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "ha_entity_id": self.ha_entity_id,
            "zone_id": self.zone_id,
            "normalized_type": self.normalized_type.value,
            "entity_type": self.entity_type.value,
            "name": self.name,
            "unit_of_measurement": self.unit_of_measurement,
            "normalization_fn": self.normalization_fn,
            "normalization_params": self.normalization_params,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass
class NormalizedState:
    """Normalized entity state."""
    state_id: str
    mapping_id: str
    zone_id: str
    normalized_type: NormalizedType
    value: float  # Normalized value (typically 0.0-1.0 or standard unit)
    raw_value: Any  # Original HA value
    unit: Optional[str]
    quality: float  # 0.0-1.0 (confidence/quality of data)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entity_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_id": self.state_id,
            "mapping_id": self.mapping_id,
            "zone_id": self.zone_id,
            "normalized_type": self.normalized_type.value,
            "value": self.value,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "quality": self.quality,
            "timestamp": self.timestamp,
            "entity_id": self.entity_id,
        }


@dataclass
class ZoneEntityRegistry:
    """Registry of entities for a zone."""
    zone_id: str
    input_entities: Dict[NormalizedType, List[str]] = field(default_factory=dict)
    output_entities: Dict[NormalizedType, List[str]] = field(default_factory=dict)
    context_entities: Dict[NormalizedType, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "input_entities": {k.value: v for k, v in self.input_entities.items()},
            "output_entities": {k.value: v for k, v in self.output_entities.items()},
            "context_entities": {k.value: v for k, v in self.context_entities.items()},
        }


class EntityNormalizationEngine:
    """Entity normalization engine for Habitus zones.
    
    Architecture:
        HA Entities → Entity Mapping → Normalization → Normalized States → Zone Stream
    
    Usage:
        engine = EntityNormalizationEngine()
        engine.map_entity(ha_entity, zone_id, normalized_type)
        engine.update_state(ha_entity_id, state)
        normalized = engine.get_normalized_state(zone_id, normalized_type)
    """
    
    def __init__(self):
        self._mappings: Dict[str, EntityMapping] = {}
        self._zone_mappings: Dict[str, List[str]] = {}  # zone_id -> mapping_ids
        self._ha_entity_to_mapping: Dict[str, str] = {}  # ha_entity_id -> mapping_id
        self._normalized_states: Dict[str, NormalizedState] = {}  # state_id -> state
        self._zone_states: Dict[str, Dict[str, NormalizedState]] = {}  # zone_id -> type -> state
        self._zone_registries: Dict[str, ZoneEntityRegistry] = {}
        self._state_history: Dict[str, List[NormalizedState]] = {}  # mapping_id -> history
        
        # Default normalization functions
        self._normalization_fns: Dict[str, Callable] = {
            "linear": self._normalize_linear,
            "threshold": self._normalize_threshold,
            "boolean": self._normalize_boolean,
            "percentage": self._normalize_percentage,
            "temperature": self._normalize_temperature,
        }
        
        logger.info("EntityNormalizationEngine initialized")
    
    def map_entity(self, ha_entity_id: str, zone_id: str,
                  normalized_type: NormalizedType,
                  name: Optional[str] = None,
                  entity_type: Optional[EntityType] = None,
                  unit_of_measurement: Optional[str] = None,
                  normalization_fn: str = "linear",
                  normalization_params: Optional[Dict[str, Any]] = None,
                  zone_entity_type: ZoneEntityType = ZoneEntityType.INPUT) -> str:
        """Map a HA entity to a zone with normalization."""
        mapping_id = f"map_{uuid.uuid4().hex[:16]}"
        
        # Detect entity type from entity_id if not provided
        if not entity_type:
            entity_type = self._detect_entity_type(ha_entity_id)
        
        # Generate name from entity_id if not provided
        if not name:
            name = ha_entity_id.split(".")[-1].replace("_", " ").title()
        
        mapping = EntityMapping(
            mapping_id=mapping_id,
            ha_entity_id=ha_entity_id,
            zone_id=zone_id,
            normalized_type=normalized_type,
            entity_type=entity_type,
            name=name,
            unit_of_measurement=unit_of_measurement,
            normalization_fn=normalization_fn,
            normalization_params=normalization_params or {},
        )
        
        with self._lock():
            self._mappings[mapping_id] = mapping
            self._ha_entity_to_mapping[ha_entity_id] = mapping_id
            
            if zone_id not in self._zone_mappings:
                self._zone_mappings[zone_id] = []
            self._zone_mappings[zone_id].append(mapping_id)
            
            # Update zone registry
            self._update_zone_registry(zone_id, mapping_id, zone_entity_type, normalized_type)
        
        logger.info("Entity mapped: %s → %s (%s)", ha_entity_id, zone_id, normalized_type.value)
        
        return mapping_id
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()
    
    def _detect_entity_type(self, entity_id: str) -> EntityType:
        """Detect entity type from entity_id."""
        domain = entity_id.split(".")[0]
        
        type_map = {
            "sensor": EntityType.SENSOR,
            "binary_sensor": EntityType.BINARY_SENSOR,
            "light": EntityType.LIGHT,
            "switch": EntityType.SWITCH,
            "climate": EntityType.CLIMATE,
            "cover": EntityType.COVER,
            "media_player": EntityType.MEDIA_PLAYER,
            "camera": EntityType.CAMERA,
            "device_tracker": EntityType.DEVICE_TRACKER,
            "person": EntityType.PERSON,
        }
        
        return type_map.get(domain, EntityType.CUSTOM)
    
    def _update_zone_registry(self, zone_id: str, mapping_id: str,
                             zone_entity_type: ZoneEntityType,
                             normalized_type: NormalizedType) -> None:
        """Update zone entity registry."""
        if zone_id not in self._zone_registries:
            self._zone_registries[zone_id] = ZoneEntityRegistry(zone_id=zone_id)
        
        registry = self._zone_registries[zone_id]
        
        if zone_entity_type == ZoneEntityType.INPUT:
            if normalized_type not in registry.input_entities:
                registry.input_entities[normalized_type] = []
            registry.input_entities[normalized_type].append(mapping_id)
        
        elif zone_entity_type == ZoneEntityType.OUTPUT:
            if normalized_type not in registry.output_entities:
                registry.output_entities[normalized_type] = []
            registry.output_entities[normalized_type].append(mapping_id)
        
        elif zone_entity_type == ZoneEntityType.CONTEXT:
            if normalized_type not in registry.context_entities:
                registry.context_entities[normalized_type] = []
            registry.context_entities[normalized_type].append(mapping_id)
    
    def update_state(self, ha_entity_id: str, state: Any,
                    attributes: Optional[Dict[str, Any]] = None) -> Optional[NormalizedState]:
        """Update state for a HA entity and return normalized state."""
        mapping_id = self._ha_entity_to_mapping.get(ha_entity_id)
        
        if not mapping_id:
            logger.debug("No mapping for entity: %s", ha_entity_id)
            return None
        
        mapping = self._mappings.get(mapping_id)
        
        if not mapping or not mapping.enabled:
            return None
        
        # Normalize value
        normalized_value = self._normalize_value(state, mapping, attributes)
        
        # Get unit
        unit = attributes.get("unit_of_measurement") if attributes else None
        if not unit:
            unit = mapping.unit_of_measurement
        
        # Calculate quality (based on state age, source reliability, etc.)
        quality = self._calculate_quality(state, attributes)
        
        # Create normalized state
        state_id = f"state_{uuid.uuid4().hex[:16]}"
        
        normalized_state = NormalizedState(
            state_id=state_id,
            mapping_id=mapping_id,
            zone_id=mapping.zone_id,
            normalized_type=mapping.normalized_type,
            value=normalized_value,
            raw_value=state,
            unit=unit,
            quality=quality,
            entity_id=ha_entity_id,
        )
        
        with self._lock():
            # Store state
            self._normalized_states[state_id] = normalized_state
            
            # Store in zone states
            if mapping.zone_id not in self._zone_states:
                self._zone_states[mapping.zone_id] = {}
            
            type_key = mapping.normalized_type.value
            self._zone_states[mapping.zone_id][type_key] = normalized_state
            
            # Store in history
            if mapping_id not in self._state_history:
                self._state_history[mapping_id] = []
            
            self._state_history[mapping_id].append(normalized_state)
            
            # Limit history (last 100 per mapping)
            if len(self._state_history[mapping_id]) > 100:
                self._state_history[mapping_id] = self._state_history[mapping_id][-100:]
        
        return normalized_state
    
    def _normalize_value(self, state: Any, mapping: EntityMapping,
                        attributes: Optional[Dict[str, Any]] = None) -> float:
        """Normalize a value based on mapping configuration."""
        fn_name = mapping.normalization_fn or "linear"
        fn = self._normalization_fns.get(fn_name, self._normalize_linear)
        
        return fn(state, mapping, attributes)
    
    def _normalize_linear(self, state: Any, mapping: EntityMapping,
                         attributes: Optional[Dict[str, Any]] = None) -> float:
        """Linear normalization (min-max scaling)."""
        params = mapping.normalization_params
        
        try:
            value = float(state)
        except (TypeError, ValueError):
            return 0.0
        
        min_val = params.get("min", 0)
        max_val = params.get("max", 100)
        
        if max_val == min_val:
            return 0.5
        
        normalized = (value - min_val) / (max_val - min_val)
        
        return max(0.0, min(1.0, normalized))
    
    def _normalize_threshold(self, state: Any, mapping: EntityMapping,
                            attributes: Optional[Dict[str, Any]] = None) -> float:
        """Threshold-based normalization (boolean-like)."""
        params = mapping.normalization_params
        
        threshold = params.get("threshold", 0.5)
        invert = params.get("invert", False)
        
        try:
            value = float(state)
        except (TypeError, ValueError):
            # Try boolean
            if isinstance(state, bool):
                value = 1.0 if state else 0.0
            elif isinstance(state, str):
                value = 1.0 if state.lower() in ("on", "true", "yes", "1") else 0.0
            else:
                value = 0.0
        
        if invert:
            return 1.0 if value < threshold else 0.0
        else:
            return 1.0 if value >= threshold else 0.0
    
    def _normalize_boolean(self, state: Any, mapping: EntityMapping,
                          attributes: Optional[Dict[str, Any]] = None) -> float:
        """Boolean normalization (on/off → 1.0/0.0)."""
        if isinstance(state, bool):
            return 1.0 if state else 0.0
        
        if isinstance(state, str):
            return 1.0 if state.lower() in ("on", "true", "yes", "1", "detected", "home") else 0.0
        
        if isinstance(state, (int, float)):
            return 1.0 if state > 0 else 0.0
        
        return 0.0
    
    def _normalize_percentage(self, state: Any, mapping: EntityMapping,
                             attributes: Optional[Dict[str, Any]] = None) -> float:
        """Percentage normalization (0-100 → 0.0-1.0)."""
        try:
            value = float(state)
        except (TypeError, ValueError):
            return 0.0
        
        return max(0.0, min(1.0, value / 100.0))
    
    def _normalize_temperature(self, state: Any, mapping: EntityMapping,
                              attributes: Optional[Dict[str, Any]] = None) -> float:
        """Temperature normalization (returns °C as-is)."""
        try:
            return float(state)
        except (TypeError, ValueError):
            return 20.0  # Default room temperature
    
    def _calculate_quality(self, state: Any,
                          attributes: Optional[Dict[str, Any]] = None) -> float:
        """Calculate data quality score."""
        quality = 1.0
        
        # Check if state is available
        if state is None or state == "unavailable":
            return 0.0
        
        # Check if state is unknown
        if state == "unknown":
            return 0.1
        
        # Check attributes for quality hints
        if attributes:
            # Battery level affects quality
            battery = attributes.get("battery_level")
            if battery is not None:
                battery_quality = battery / 100.0
                quality = quality * (0.5 + 0.5 * battery_quality)
            
            # Device class affects quality
            device_class = attributes.get("device_class")
            if device_class == "moving":
                quality = quality * 1.1  # Moving sensors are reliable
        
        return min(1.0, max(0.0, quality))
    
    def get_normalized_state(self, zone_id: str,
                            normalized_type: NormalizedType) -> Optional[NormalizedState]:
        """Get current normalized state for a zone and type."""
        zone_states = self._zone_states.get(zone_id, {})
        type_key = normalized_type.value
        
        return zone_states.get(type_key)
    
    def get_zone_states(self, zone_id: str) -> Dict[str, NormalizedState]:
        """Get all normalized states for a zone."""
        return self._zone_states.get(zone_id, {}).copy()
    
    def get_mapping(self, mapping_id: str) -> Optional[EntityMapping]:
        """Get entity mapping by ID."""
        return self._mappings.get(mapping_id)
    
    def get_mappings_for_zone(self, zone_id: str) -> List[EntityMapping]:
        """Get all mappings for a zone."""
        mapping_ids = self._zone_mappings.get(zone_id, [])
        return [self._mappings[mid] for mid in mapping_ids if mid in self._mappings]
    
    def get_mappings_for_entity(self, ha_entity_id: str) -> List[EntityMapping]:
        """Get all mappings for a HA entity."""
        mapping_id = self._ha_entity_to_mapping.get(ha_entity_id)
        
        if not mapping_id:
            return []
        
        mapping = self._mappings.get(mapping_id)
        
        return [mapping] if mapping else []
    
    def get_zone_registry(self, zone_id: str) -> Optional[ZoneEntityRegistry]:
        """Get zone entity registry."""
        return self._zone_registries.get(zone_id)
    
    def get_state_history(self, mapping_id: str,
                         limit: int = 50) -> List[NormalizedState]:
        """Get state history for a mapping."""
        history = self._state_history.get(mapping_id, [])
        return history[-limit:]
    
    def enable_mapping(self, mapping_id: str) -> bool:
        """Enable a mapping."""
        mapping = self._mappings.get(mapping_id)
        
        if not mapping:
            return False
        
        mapping.enabled = True
        
        return True
    
    def disable_mapping(self, mapping_id: str) -> bool:
        """Disable a mapping."""
        mapping = self._mappings.get(mapping_id)
        
        if not mapping:
            return False
        
        mapping.enabled = False
        
        return True
    
    def unmap_entity(self, mapping_id: str) -> bool:
        """Remove an entity mapping."""
        if mapping_id not in self._mappings:
            return False
        
        mapping = self._mappings[mapping_id]
        
        # Remove from mappings
        del self._mappings[mapping_id]
        
        # Remove from HA entity mapping
        if mapping.ha_entity_id in self._ha_entity_to_mapping:
            del self._ha_entity_to_mapping[mapping.ha_entity_id]
        
        # Remove from zone mappings
        if mapping.zone_id in self._zone_mappings:
            if mapping_id in self._zone_mappings[mapping.zone_id]:
                self._zone_mappings[mapping.zone_id].remove(mapping_id)
        
        return True
    
    def list_mappings(self, zone_id: Optional[str] = None,
                     normalized_type: Optional[NormalizedType] = None,
                     entity_type: Optional[EntityType] = None) -> List[Dict[str, Any]]:
        """List mappings with filters."""
        mappings = list(self._mappings.values())
        
        if zone_id:
            mappings = [m for m in mappings if m.zone_id == zone_id]
        
        if normalized_type:
            mappings = [m for m in mappings if m.normalized_type == normalized_type]
        
        if entity_type:
            mappings = [m for m in mappings if m.entity_type == entity_type]
        
        return [m.to_dict() for m in mappings]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get normalization statistics."""
        total_mappings = len(self._mappings)
        enabled_mappings = len([m for m in self._mappings.values() if m.enabled])
        total_states = len(self._normalized_states)
        total_zones = len(self._zone_registries)
        
        return {
            "total_mappings": total_mappings,
            "enabled_mappings": enabled_mappings,
            "disabled_mappings": total_mappings - enabled_mappings,
            "total_states": total_states,
            "total_zones": total_zones,
            "total_history_entries": sum(len(h) for h in self._state_history.values()),
        }
    
    def clear_history(self, mapping_id: Optional[str] = None) -> int:
        """Clear state history."""
        if mapping_id:
            if mapping_id in self._state_history:
                count = len(self._state_history[mapping_id])
                self._state_history[mapping_id] = []
                return count
            return 0
        else:
            count = sum(len(h) for h in self._state_history.values())
            for key in self._state_history:
                self._state_history[key] = []
            return count
    
    def bulk_map_entities(self, zone_id: str,
                         entity_patterns: List[Dict[str, Any]]) -> List[str]:
        """Bulk map multiple entities to a zone."""
        mapping_ids = []
        
        for pattern in entity_patterns:
            ha_entity_id = pattern.get("entity_id")
            normalized_type = NormalizedType(pattern.get("normalized_type", "custom"))
            name = pattern.get("name")
            normalization_fn = pattern.get("normalization_fn", "linear")
            normalization_params = pattern.get("normalization_params", {})
            
            if ha_entity_id:
                mapping_id = self.map_entity(
                    ha_entity_id=ha_entity_id,
                    zone_id=zone_id,
                    normalized_type=normalized_type,
                    name=name,
                    normalization_fn=normalization_fn,
                    normalization_params=normalization_params,
                )
                mapping_ids.append(mapping_id)
        
        return mapping_ids
    
    def auto_detect_zone_entities(self, ha_entities: Dict[str, Any],
                                 zone_keywords: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Auto-detect zone entities from HA entity list."""
        suggestions = []
        
        for entity_id, state_data in ha_entities.items():
            # Extract keywords from entity_id
            entity_keywords = entity_id.lower().replace("_", " ").split()
            
            # Try to match zone
            matched_zone = None
            for zone_id, keywords in zone_keywords.items():
                if any(kw in entity_keywords for kw in keywords):
                    matched_zone = zone_id
                    break
            
            if not matched_zone:
                continue
            
            # Try to detect normalized type
            normalized_type = self._detect_normalized_type(entity_id, state_data)
            
            if normalized_type:
                suggestions.append({
                    "entity_id": entity_id,
                    "zone_id": matched_zone,
                    "normalized_type": normalized_type.value,
                    "confidence": 0.8,  # Auto-detect confidence
                })
        
        return suggestions
    
    def _detect_normalized_type(self, entity_id: str,
                               state_data: Any) -> Optional[NormalizedType]:
        """Detect normalized type from entity."""
        # Check entity_id keywords
        entity_lower = entity_id.lower()
        
        type_keywords = {
            NormalizedType.PRESENCE: ["presence", "occupancy", "occupied"],
            NormalizedType.MOTION: ["motion", "pir", "movement"],
            NormalizedType.LIGHT_LEVEL: ["lux", "illumination", "light_level"],
            NormalizedType.TEMPERATURE: ["temperature", "temp"],
            NormalizedType.HUMIDITY: ["humidity", "humid"],
            NormalizedType.BRIGHTNESS: ["brightness", "bright"],
            NormalizedType.ENERGY: ["energy", "kwh"],
            NormalizedType.POWER: ["power", "watt"],
            NormalizedType.VOLUME: ["volume", "level"],
        }
        
        for norm_type, keywords in type_keywords.items():
            if any(kw in entity_lower for kw in keywords):
                return norm_type
        
        # Check device class from attributes
        if isinstance(state_data, dict):
            device_class = state_data.get("attributes", {}).get("device_class")
            
            class_map = {
                "motion": NormalizedType.MOTION,
                "occupancy": NormalizedType.PRESENCE,
                "illuminance": NormalizedType.LIGHT_LEVEL,
                "temperature": NormalizedType.TEMPERATURE,
                "humidity": NormalizedType.HUMIDITY,
                "power": NormalizedType.POWER,
                "energy": NormalizedType.ENERGY,
            }
            
            if device_class in class_map:
                return class_map[device_class]
        
        return None


def create_entity_normalization_engine() -> EntityNormalizationEngine:
    """Factory function to create entity normalization engine."""
    return EntityNormalizationEngine()
