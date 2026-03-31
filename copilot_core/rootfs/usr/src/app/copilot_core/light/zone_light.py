"""Zone-Aware Light Module — Slice 71.

Lichtsteuerung pro Habituszone mit Helligkeits-Thresholds.

Features:
- Zone Light State (on, off, dimmed, scene)
- Brightness Threshold Detection
- Presence-Based Automation
- Scene Support (reading, relaxing, focused, etc.)
- Color Temperature Control
- Light Schedules
- Manual Override Detection
- Energy Tracking
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class LightState(Enum):
    """Light states."""
    OFF = "off"
    ON = "on"
    DIMMED = "dimmed"
    SCENE = "scene"
    AUTO = "auto"


class LightScene(Enum):
    """Light scenes."""
    DEFAULT = "default"
    READING = "reading"
    RELAXING = "relaxing"
    FOCUSED = "focused"
    MOVIE = "movie"
    NIGHT = "night"
    AWAY = "away"
    CUSTOM = "custom"


@dataclass
class LightConfig:
    """Light configuration for a zone."""
    zone_id: str
    brightness_threshold: float = 0.3  # 0.0-1.0, below = turn on
    auto_on_enabled: bool = True
    auto_off_enabled: bool = True
    auto_off_delay_seconds: int = 300  # 5 minutes
    default_brightness: float = 0.8  # 0.0-1.0
    default_color_temp: int = 4000  # Kelvin
    min_brightness: float = 0.1
    max_brightness: float = 1.0
    scene_presets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "brightness_threshold": self.brightness_threshold,
            "auto_on_enabled": self.auto_on_enabled,
            "auto_off_enabled": self.auto_off_enabled,
            "auto_off_delay_seconds": self.auto_off_delay_seconds,
            "default_brightness": self.default_brightness,
            "default_color_temp": self.default_color_temp,
            "min_brightness": self.min_brightness,
            "max_brightness": self.max_brightness,
            "scene_presets": self.scene_presets,
        }


@dataclass
class LightEntity:
    """Light entity in a zone."""
    entity_id: str
    zone_id: str
    name: str
    enabled: bool = True
    is_primary: bool = False  # Primary light for zone
    supports_brightness: bool = True
    supports_color_temp: bool = False
    supports_color: bool = False
    power_consumption_watts: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "enabled": self.enabled,
            "is_primary": self.is_primary,
            "supports_brightness": self.supports_brightness,
            "supports_color_temp": self.supports_color_temp,
            "supports_color": self.supports_color,
            "power_consumption_watts": self.power_consumption_watts,
        }


@dataclass
class ZoneLightState:
    """Current light state for a zone."""
    zone_id: str
    state: LightState
    brightness: float  # 0.0-1.0
    color_temp: Optional[int] = None  # Kelvin
    scene: Optional[LightScene] = None
    manual_override: bool = False
    lights_on_count: int = 0
    lights_off_count: int = 0
    last_change: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_auto_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "state": self.state.value,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "scene": self.scene.value if self.scene else None,
            "manual_override": self.manual_override,
            "lights_on_count": self.lights_on_count,
            "lights_off_count": self.lights_off_count,
            "last_change": self.last_change,
            "last_auto_action": self.last_auto_action,
        }


@dataclass
class LightAction:
    """Light action suggestion/command."""
    action_id: str
    zone_id: str
    action_type: str  # "turn_on", "turn_off", "dim", "scene", "color_temp"
    target_entities: List[str]
    brightness: Optional[float] = None
    color_temp: Optional[int] = None
    scene: Optional[LightScene] = None
    reason: str = ""
    triggered_by: str = "auto"  # "auto", "manual", "schedule", "event"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "target_entities": self.target_entities,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "scene": self.scene.value if self.scene else None,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
        }


@dataclass
class LightHistoryEntry:
    """Light history entry."""
    timestamp: str
    zone_id: str
    state: LightState
    brightness: float
    action_type: Optional[str] = None
    triggered_by: Optional[str] = None
    energy_wh: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "zone_id": self.zone_id,
            "state": self.state.value,
            "brightness": self.brightness,
            "action_type": self.action_type,
            "triggered_by": self.triggered_by,
            "energy_wh": self.energy_wh,
        }


class LightModule:
    """Zone-aware light control module.
    
    Architecture:
        Normalized States (light_level, presence) → Threshold Logic → Light Actions
    
    Usage:
        module = LightModule()
        module.add_light_entity(entity_config)
        module.set_zone_config(zone_id, config)
        module.update_zone_context(zone_id, light_level, presence)
        actions = module.evaluate_zone(zone_id)
    """
    
    def __init__(self):
        self._light_entities: Dict[str, LightEntity] = {}
        self._zone_entities: Dict[str, List[str]] = {}  # zone_id -> entity_ids
        self._zone_configs: Dict[str, LightConfig] = {}
        self._zone_states: Dict[str, ZoneLightState] = {}
        self._zone_context: Dict[str, Dict[str, Any]] = {}  # zone_id -> {light_level, presence, etc.}
        self._entity_states: Dict[str, bool] = {}  # entity_id -> is_on
        self._entity_brightness: Dict[str, float] = {}  # entity_id -> brightness
        self._manual_override: Dict[str, datetime] = {}  # zone_id -> override_expiry
        self._light_history: Dict[str, List[LightHistoryEntry]] = {}  # zone_id -> history
        self._pending_actions: Dict[str, List[LightAction]] = {}  # zone_id -> actions
        
        # Default scene presets
        self._default_scenes = {
            LightScene.READING: {"brightness": 0.9, "color_temp": 5000},
            LightScene.RELAXING: {"brightness": 0.4, "color_temp": 3000},
            LightScene.FOCUSED: {"brightness": 1.0, "color_temp": 6000},
            LightScene.MOVIE: {"brightness": 0.2, "color_temp": 4000},
            LightScene.NIGHT: {"brightness": 0.1, "color_temp": 2700},
            LightScene.AWAY: {"brightness": 0.5, "color_temp": 4000},
        }
        
        logger.info("LightModule initialized")
    
    def add_light_entity(self, entity: LightEntity) -> str:
        """Add a light entity to a zone."""
        with self._lock():
            self._light_entities[entity.entity_id] = entity
            
            if entity.zone_id not in self._zone_entities:
                self._zone_entities[entity.zone_id] = []
            
            self._zone_entities[entity.zone_id].append(entity.entity_id)
            
            # Initialize entity state
            self._entity_states[entity.entity_id] = False
            self._entity_brightness[entity.entity_id] = 0.0
            
            # Initialize zone state if needed
            if entity.zone_id not in self._zone_states:
                self._zone_states[entity.zone_id] = ZoneLightState(
                    zone_id=entity.zone_id,
                    state=LightState.OFF,
                    brightness=0.0,
                )
        
        logger.info("Light entity added: %s to %s", entity.entity_id, entity.zone_id)
        
        return entity.entity_id
    
    def remove_light_entity(self, entity_id: str) -> bool:
        """Remove a light entity."""
        if entity_id not in self._light_entities:
            return False
        
        entity = self._light_entities[entity_id]
        
        with self._lock():
            del self._light_entities[entity_id]
            
            if entity.zone_id in self._zone_entities:
                if entity_id in self._zone_entities[entity.zone_id]:
                    self._zone_entities[entity.zone_id].remove(entity_id)
            
            if entity_id in self._entity_states:
                del self._entity_states[entity_id]
        
        return True
    
    def set_zone_config(self, zone_id: str, config: LightConfig) -> bool:
        """Set light configuration for a zone."""
        with self._lock():
            self._zone_configs[zone_id] = config
            
            # Merge default scenes
            if not config.scene_presets:
                config.scene_presets = {
                    scene.value: preset for scene, preset in self._default_scenes.items()
                }
        
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[LightConfig]:
        """Get light configuration for a zone."""
        return self._zone_configs.get(zone_id)
    
    def update_zone_context(self, zone_id: str,
                           light_level: Optional[float] = None,
                           presence: Optional[bool] = None,
                           time_of_day: Optional[str] = None) -> None:
        """Update zone context (sensor data)."""
        if zone_id not in self._zone_context:
            self._zone_context[zone_id] = {}
        
        ctx = self._zone_context[zone_id]
        
        if light_level is not None:
            ctx["light_level"] = light_level
        
        if presence is not None:
            ctx["presence"] = presence
        
        if time_of_day is not None:
            ctx["time_of_day"] = time_of_day
    
    def evaluate_zone(self, zone_id: str) -> List[LightAction]:
        """Evaluate zone and generate light actions."""
        config = self._zone_configs.get(zone_id)
        
        if not config:
            config = LightConfig(zone_id=zone_id)
        
        context = self._zone_context.get(zone_id, {})
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            return []
        
        actions = []
        now = datetime.now(timezone.utc)
        
        # Check manual override
        if self._is_manual_override_active(zone_id, now):
            zone_state.manual_override = True
            return []  # Don't auto-control during override
        
        zone_state.manual_override = False
        
        # Get presence state
        presence = context.get("presence", False)
        
        # Get light level
        light_level = context.get("light_level", 1.0)
        
        # Auto-on logic
        if presence and config.auto_on_enabled:
            if light_level < config.brightness_threshold:
                if zone_state.state == LightState.OFF:
                    action = self._create_turn_on_action(zone_id, config, "presence_low_light")
                    actions.append(action)
        
        # Auto-off logic
        if not presence and config.auto_off_enabled:
            if zone_state.state != LightState.OFF:
                # Check if off-delay has passed
                last_change = datetime.fromisoformat(zone_state.last_change.replace('Z', '+00:00'))
                elapsed = (now - last_change).total_seconds()
                
                if elapsed >= config.auto_off_delay_seconds:
                    action = self._create_turn_off_action(zone_id, "absence_timeout")
                    actions.append(action)
        
        # Store pending actions
        self._pending_actions[zone_id] = actions
        
        return actions
    
    def _is_manual_override_active(self, zone_id: str, now: datetime) -> bool:
        """Check if manual override is active."""
        if zone_id not in self._manual_override:
            return False
        
        expiry = self._manual_override[zone_id]
        
        return now < expiry
    
    def set_manual_override(self, zone_id: str, duration_seconds: int = 1800) -> bool:
        """Set manual override for a zone (30 min default)."""
        if zone_id not in self._zone_states:
            return False
        
        expiry = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        self._manual_override[zone_id] = expiry
        
        zone_state = self._zone_states[zone_id]
        zone_state.manual_override = True
        
        logger.info("Manual override set for %s (%d seconds)", zone_id, duration_seconds)
        
        return True
    
    def clear_manual_override(self, zone_id: str) -> bool:
        """Clear manual override for a zone."""
        if zone_id not in self._manual_override:
            return False
        
        del self._manual_override[zone_id]
        
        if zone_id in self._zone_states:
            self._zone_states[zone_id].manual_override = False
        
        return True
    
    def apply_scene(self, zone_id: str, scene: LightScene) -> List[LightAction]:
        """Apply a light scene to a zone."""
        config = self._zone_configs.get(zone_id)
        
        if not config:
            config = LightConfig(zone_id=zone_id)
        
        scene_config = config.scene_presets.get(scene.value, {})
        
        brightness = scene_config.get("brightness", config.default_brightness)
        color_temp = scene_config.get("color_temp", config.default_color_temp)
        
        entity_ids = self._zone_entities.get(zone_id, [])
        primary_entities = [
            eid for eid in entity_ids
            if self._light_entities.get(eid, LightEntity("", "", "")).is_primary
        ]
        
        target_entities = primary_entities if primary_entities else entity_ids
        
        action = LightAction(
            action_id=f"la_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="scene",
            target_entities=target_entities,
            brightness=brightness,
            color_temp=color_temp,
            scene=scene,
            reason=f"Scene: {scene.value}",
            triggered_by="manual",
        )
        
        # Update zone state
        if zone_id in self._zone_states:
            zone_state = self._zone_states[zone_id]
            zone_state.state = LightState.SCENE
            zone_state.scene = scene
            zone_state.brightness = brightness
            zone_state.color_temp = color_temp
            zone_state.last_change = datetime.now(timezone.utc).isoformat()
            zone_state.last_auto_action = "scene"
        
        # Record history
        self._record_history(zone_id, LightState.SCENE, brightness, "scene", "manual")
        
        return [action]
    
    def turn_on(self, zone_id: str, brightness: Optional[float] = None,
               color_temp: Optional[int] = None) -> List[LightAction]:
        """Turn on lights in a zone."""
        config = self._zone_configs.get(zone_id)
        
        if not config:
            config = LightConfig(zone_id=zone_id)
        
        target_brightness = brightness if brightness is not None else config.default_brightness
        target_color_temp = color_temp if color_temp is not None else config.default_color_temp
        
        entity_ids = self._zone_entities.get(zone_id, [])
        
        action = LightAction(
            action_id=f"la_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_on",
            target_entities=entity_ids,
            brightness=target_brightness,
            color_temp=target_color_temp,
            reason="Manual turn on",
            triggered_by="manual",
        )
        
        # Update entity states
        for entity_id in entity_ids:
            self._entity_states[entity_id] = True
            self._entity_brightness[entity_id] = target_brightness
        
        # Update zone state
        if zone_id in self._zone_states:
            zone_state = self._zone_states[zone_id]
            zone_state.state = LightState.ON
            zone_state.brightness = target_brightness
            zone_state.color_temp = target_color_temp
            zone_state.last_change = datetime.now(timezone.utc).isoformat()
            zone_state.last_auto_action = "manual_on"
        
        # Record history
        self._record_history(zone_id, LightState.ON, target_brightness, "turn_on", "manual")
        
        return [action]
    
    def turn_off(self, zone_id: str) -> List[LightAction]:
        """Turn off lights in a zone."""
        entity_ids = self._zone_entities.get(zone_id, [])
        
        action = self._create_turn_off_action(zone_id, "manual_off")
        
        # Update entity states
        for entity_id in entity_ids:
            self._entity_states[entity_id] = False
            self._entity_brightness[entity_id] = 0.0
        
        # Update zone state
        if zone_id in self._zone_states:
            zone_state = self._zone_states[zone_id]
            zone_state.state = LightState.OFF
            zone_state.brightness = 0.0
            zone_state.last_change = datetime.now(timezone.utc).isoformat()
            zone_state.last_auto_action = "manual_off"
        
        # Record history
        self._record_history(zone_id, LightState.OFF, 0.0, "turn_off", "manual")
        
        return [action]
    
    def _create_turn_on_action(self, zone_id: str, config: LightConfig,
                              reason: str) -> LightAction:
        """Create turn on action."""
        entity_ids = self._zone_entities.get(zone_id, [])
        
        return LightAction(
            action_id=f"la_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_on",
            target_entities=entity_ids,
            brightness=config.default_brightness,
            color_temp=config.default_color_temp,
            reason=reason,
            triggered_by="auto",
        )
    
    def _create_turn_off_action(self, zone_id: str, reason: str) -> LightAction:
        """Create turn off action."""
        entity_ids = self._zone_entities.get(zone_id, [])
        
        return LightAction(
            action_id=f"la_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_off",
            target_entities=entity_ids,
            reason=reason,
            triggered_by="auto",
        )
    
    def _record_history(self, zone_id: str, state: LightState,
                       brightness: float, action_type: Optional[str],
                       triggered_by: Optional[str]) -> None:
        """Record light state to history."""
        if zone_id not in self._light_history:
            self._light_history[zone_id] = []
        
        # Calculate energy
        energy_wh = 0.0
        if state != LightState.OFF:
            entity_ids = self._zone_entities.get(zone_id, [])
            for entity_id in entity_ids:
                entity = self._light_entities.get(entity_id)
                if entity:
                    energy_wh += entity.power_consumption_watts * brightness * (1/60)  # Wh per minute
        
        entry = LightHistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            zone_id=zone_id,
            state=state,
            brightness=brightness,
            action_type=action_type,
            triggered_by=triggered_by,
            energy_wh=energy_wh,
        )
        
        self._light_history[zone_id].append(entry)
        
        # Limit history (last 1000 per zone)
        if len(self._light_history[zone_id]) > 1000:
            self._light_history[zone_id] = self._light_history[zone_id][-1000:]
    
    def get_zone_light_state(self, zone_id: str) -> Optional[ZoneLightState]:
        """Get current light state for a zone."""
        return self._zone_states.get(zone_id)
    
    def get_light_entity(self, entity_id: str) -> Optional[LightEntity]:
        """Get light entity by ID."""
        return self._light_entities.get(entity_id)
    
    def get_zone_entities(self, zone_id: str) -> List[LightEntity]:
        """Get all light entities for a zone."""
        entity_ids = self._zone_entities.get(zone_id, [])
        return [self._light_entities[eid] for eid in entity_ids if eid in self._light_entities]
    
    def get_light_history(self, zone_id: str,
                         hours: int = 24,
                         limit: int = 100) -> List[LightHistoryEntry]:
        """Get light history for a zone."""
        if zone_id not in self._light_history:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        history = self._light_history[zone_id]
        
        filtered = [
            entry for entry in history
            if datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        return filtered[-limit:]
    
    def get_energy_consumption(self, zone_id: str,
                              hours: int = 24) -> float:
        """Get energy consumption for a zone in Wh."""
        history = self.get_light_history(zone_id, hours)
        
        return sum(entry.energy_wh for entry in history)
    
    def is_light_on(self, zone_id: str) -> bool:
        """Check if lights are on in a zone."""
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            return False
        
        return zone_state.state != LightState.OFF
    
    def get_pending_actions(self, zone_id: str) -> List[LightAction]:
        """Get pending actions for a zone."""
        return self._pending_actions.get(zone_id, [])
    
    def clear_pending_actions(self, zone_id: str) -> int:
        """Clear pending actions for a zone."""
        if zone_id not in self._pending_actions:
            return 0
        
        count = len(self._pending_actions[zone_id])
        self._pending_actions[zone_id] = []
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get light module statistics."""
        total_entities = len(self._light_entities)
        enabled_entities = len([e for e in self._light_entities.values() if e.enabled])
        zones_with_lights_on = len([
            z for z in self._zone_states.values()
            if z.state != LightState.OFF
        ])
        
        return {
            "total_entities": total_entities,
            "enabled_entities": enabled_entities,
            "disabled_entities": total_entities - enabled_entities,
            "total_zones": len(self._zone_states),
            "zones_with_lights_on": zones_with_lights_on,
            "zones_with_lights_off": len(self._zone_states) - zones_with_lights_on,
            "total_history_entries": sum(len(h) for h in self._light_history.values()),
            "active_manual_overrides": len(self._manual_override),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_light_module() -> LightModule:
    """Factory function to create light module."""
    return LightModule()
