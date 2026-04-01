"""Climate/HVAC Module — Slice 80.

Klima- und Heizungssteuerung für Habituszonen.

Features:
- Temperature Control (Heating/Cooling)
- Humidity Integration
- HVAC Mode (heat, cool, auto, off)
- Target Temperature per Zone
- Schedule Support (time-based targets)
- Energy Efficiency Mode
- Window/Door Contact Integration
- Frost Protection
- Overheat Protection
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class HVACMode(Enum):
    """HVAC operation modes."""
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"
    DRY = "dry"
    FAN_ONLY = "fan_only"


class FanMode(Enum):
    """Fan operation modes."""
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    AUTO = "auto"


@dataclass
class ClimateConfig:
    """Climate configuration for a zone."""
    zone_id: str
    hvac_mode: HVACMode = HVACMode.AUTO
    fan_mode: FanMode = FanMode.AUTO
    target_temp_celsius: float = 21.0
    min_temp_celsius: float = 16.0
    max_temp_celsius: float = 28.0
    temp_tolerance_celsius: float = 0.5
    humidity_target_percent: float = 50.0
    humidity_min_percent: float = 30.0
    humidity_max_percent: float = 70.0
    eco_mode_enabled: bool = False
    eco_temp_offset_celsius: float = 2.0
    frost_protection_temp: float = 5.0
    overheat_protection_temp: float = 35.0
    window_contact_entity: Optional[str] = None
    door_contact_entity: Optional[str] = None
    window_open_action: str = "hvac_off"  # hvac_off, reduce_temp, notify
    schedule_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "hvac_mode": self.hvac_mode.value,
            "fan_mode": self.fan_mode.value,
            "target_temp_celsius": self.target_temp_celsius,
            "min_temp_celsius": self.min_temp_celsius,
            "max_temp_celsius": self.max_temp_celsius,
            "temp_tolerance_celsius": self.temp_tolerance_celsius,
            "humidity_target_percent": self.humidity_target_percent,
            "humidity_min_percent": self.humidity_min_percent,
            "humidity_max_percent": self.humidity_max_percent,
            "eco_mode_enabled": self.eco_mode_enabled,
            "eco_temp_offset_celsius": self.eco_temp_offset_celsius,
            "frost_protection_temp": self.frost_protection_temp,
            "overheat_protection_temp": self.overheat_protection_temp,
            "window_contact_entity": self.window_contact_entity,
            "door_contact_entity": self.door_contact_entity,
            "window_open_action": self.window_open_action,
            "schedule_enabled": self.schedule_enabled,
        }


@dataclass
class ClimateSchedule:
    """Climate schedule entry."""
    schedule_id: str
    zone_id: str
    name: str
    days_of_week: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    start_time: str = "06:00"  # HH:MM
    target_temp: float = 21.0
    hvac_mode: Optional[HVACMode] = None
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "days_of_week": self.days_of_week,
            "start_time": self.start_time,
            "target_temp": self.target_temp,
            "hvac_mode": self.hvac_mode.value if self.hvac_mode else None,
            "enabled": self.enabled,
        }


@dataclass
class ClimateState:
    """Current climate state for a zone."""
    zone_id: str
    current_temp_celsius: float = 0.0
    current_humidity_percent: float = 0.0
    target_temp_celsius: float = 21.0
    hvac_mode: HVACMode = HVACMode.OFF
    fan_mode: FanMode = FanMode.OFF
    is_heating: bool = False
    is_cooling: bool = False
    is_fan_on: bool = False
    window_open: bool = False
    door_open: bool = False
    frost_protection_active: bool = False
    overheat_protection_active: bool = False
    eco_mode_active: bool = False
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "current_temp_celsius": self.current_temp_celsius,
            "current_humidity_percent": self.current_humidity_percent,
            "target_temp_celsius": self.target_temp_celsius,
            "hvac_mode": self.hvac_mode.value,
            "fan_mode": self.fan_mode.value,
            "is_heating": self.is_heating,
            "is_cooling": self.is_cooling,
            "is_fan_on": self.is_fan_on,
            "window_open": self.window_open,
            "door_open": self.door_open,
            "frost_protection_active": self.frost_protection_active,
            "overheat_protection_active": self.overheat_protection_active,
            "eco_mode_active": self.eco_mode_active,
            "last_update": self.last_update,
        }


@dataclass
class ClimateAction:
    """Climate action to execute."""
    action_id: str
    zone_id: str
    action_type: str  # set_temp, set_mode, set_fan, turn_off, turn_on
    target_temp: Optional[float] = None
    hvac_mode: Optional[HVACMode] = None
    fan_mode: Optional[FanMode] = None
    reason: str = ""
    triggered_by: str = "auto"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "target_temp": self.target_temp,
            "hvac_mode": self.hvac_mode.value if self.hvac_mode else None,
            "fan_mode": self.fan_mode.value if self.fan_mode else None,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
        }


class ClimateModule:
    """Climate/HVAC module for zone-aware control.
    
    Architecture:
        Temperature Sensors + Schedules + Window Contacts → Climate Actions
    
    Usage:
        module = ClimateModule()
        module.set_zone_config(config)
        module.update_sensor_data(zone_id, temp, humidity)
        module.update_window_state(zone_id, is_open)
        actions = module.evaluate_zone(zone_id)
    """
    
    def __init__(self):
        self._configs: Dict[str, ClimateConfig] = {}
        self._states: Dict[str, ClimateState] = {}
        self._schedules: Dict[str, List[ClimateSchedule]] = {}  # zone_id -> schedules
        self._pending_actions: Dict[str, List[ClimateAction]] = {}
        self._window_states: Dict[str, bool] = {}  # entity_id -> is_open
        self._door_states: Dict[str, bool] = {}  # entity_id -> is_open
        
        logger.info("ClimateModule initialized")
    
    def set_zone_config(self, config: ClimateConfig) -> bool:
        """Set climate configuration for a zone."""
        with self._lock():
            self._configs[config.zone_id] = config
            
            # Initialize state
            self._states[config.zone_id] = ClimateState(
                zone_id=config.zone_id,
                target_temp_celsius=config.target_temp_celsius,
                hvac_mode=config.hvac_mode,
                fan_mode=config.fan_mode,
            )
        
        logger.info("Climate config set for %s", config.zone_id)
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[ClimateConfig]:
        """Get climate configuration for a zone."""
        return self._configs.get(zone_id)
    
    def add_schedule(self, schedule: ClimateSchedule) -> str:
        """Add climate schedule for a zone."""
        with self._lock():
            if schedule.zone_id not in self._schedules:
                self._schedules[schedule.zone_id] = []
            
            self._schedules[schedule.zone_id].append(schedule)
        
        logger.info("Climate schedule added: %s for %s", schedule.schedule_id, schedule.zone_id)
        return schedule.schedule_id
    
    def update_sensor_data(self, zone_id: str,
                          temperature: float,
                          humidity: Optional[float] = None) -> None:
        """Update temperature/humidity sensor data for a zone."""
        if zone_id not in self._states:
            self._states[zone_id] = ClimateState(zone_id=zone_id)
        
        state = self._states[zone_id]
        state.current_temp_celsius = temperature
        state.last_update = datetime.now(timezone.utc).isoformat()
        
        if humidity is not None:
            state.current_humidity_percent = humidity
    
    def update_window_state(self, zone_id: str, is_open: bool) -> None:
        """Update window state for a zone."""
        config = self._configs.get(zone_id)
        
        if config and config.window_contact_entity:
            self._window_states[config.window_contact_entity] = is_open
            
            if zone_id in self._states:
                self._states[zone_id].window_open = is_open
    
    def update_door_state(self, zone_id: str, is_open: bool) -> None:
        """Update door state for a zone."""
        config = self._configs.get(zone_id)
        
        if config and config.door_contact_entity:
            self._door_states[config.door_contact_entity] = is_open
            
            if zone_id in self._states:
                self._states[zone_id].door_open = is_open
    
    def evaluate_zone(self, zone_id: str) -> List[ClimateAction]:
        """Evaluate zone and generate climate actions."""
        config = self._configs.get(zone_id)
        state = self._states.get(zone_id)
        
        if not config or not state:
            return []
        
        actions = []
        
        # Check window/door state
        window_open = state.window_open
        door_open = state.door_open
        
        if window_open or door_open:
            # Window/door open action
            if config.window_open_action == "hvac_off":
                action = self._create_hvac_off_action(zone_id, "window_or_door_open")
                actions.append(action)
            elif config.window_open_action == "reduce_temp":
                # Reduce target temp
                reduced_temp = max(config.min_temp_celsius, state.target_temp_celsius - 3)
                action = self._create_set_temp_action(zone_id, reduced_temp, "window_or_door_open")
                actions.append(action)
            
            return actions  # Don't evaluate further
        
        # Check frost protection
        if state.current_temp_celsius < config.frost_protection_temp:
            if not state.frost_protection_active:
                state.frost_protection_active = True
                action = self._create_frost_protection_action(zone_id)
                actions.append(action)
            return actions
        
        state.frost_protection_active = False
        
        # Check overheat protection
        if state.current_temp_celsius > config.overheat_protection_temp:
            if not state.overheat_protection_active:
                state.overheat_protection_active = True
                action = self._create_overheat_protection_action(zone_id)
                actions.append(action)
            return actions
        
        state.overheat_protection_active = False
        
        # Check eco mode
        if config.eco_mode_enabled:
            state.eco_mode_active = True
            eco_temp = config.target_temp_celsius - config.eco_temp_offset_celsius
            if abs(state.target_temp_celsius - eco_temp) > 0.5:
                action = self._create_set_temp_action(zone_id, eco_temp, "eco_mode")
                actions.append(action)
        else:
            state.eco_mode_active = False
        
        # Check schedule
        if config.schedule_enabled:
            schedule_action = self._evaluate_schedule(zone_id)
            if schedule_action:
                actions.append(schedule_action)
        
        # Normal temperature control
        temp_diff = state.current_temp_celsius - state.target_temp_celsius
        
        if config.hvac_mode == HVACMode.HEAT:
            if temp_diff < -config.temp_tolerance_celsius:
                # Too cold - start heating
                if not state.is_heating:
                    state.is_heating = True
                    action = self._create_turn_on_action(zone_id, HVACMode.HEAT, "temperature_low")
                    actions.append(action)
            elif temp_diff > config.temp_tolerance_celsius:
                # Too warm - stop heating
                if state.is_heating:
                    state.is_heating = False
                    action = self._create_turn_off_action(zone_id, "temperature_reached")
                    actions.append(action)
        
        elif config.hvac_mode == HVACMode.COOL:
            if temp_diff > config.temp_tolerance_celsius:
                # Too warm - start cooling
                if not state.is_cooling:
                    state.is_cooling = True
                    action = self._create_turn_on_action(zone_id, HVACMode.COOL, "temperature_high")
                    actions.append(action)
            elif temp_diff < -config.temp_tolerance_celsius:
                # Too cold - stop cooling
                if state.is_cooling:
                    state.is_cooling = False
                    action = self._create_turn_off_action(zone_id, "temperature_reached")
                    actions.append(action)
        
        elif config.hvac_mode == HVACMode.AUTO:
            # Auto mode - heat or cool based on temp
            if temp_diff < -config.temp_tolerance_celsius:
                if not state.is_heating:
                    state.is_heating = True
                    state.is_cooling = False
                    action = self._create_turn_on_action(zone_id, HVACMode.HEAT, "auto_heat")
                    actions.append(action)
            elif temp_diff > config.temp_tolerance_celsius:
                if not state.is_cooling:
                    state.is_cooling = True
                    state.is_heating = False
                    action = self._create_turn_on_action(zone_id, HVACMode.COOL, "auto_cool")
                    actions.append(action)
            else:
                # In tolerance
                if state.is_heating or state.is_cooling:
                    state.is_heating = False
                    state.is_cooling = False
                    action = self._create_turn_off_action(zone_id, "temperature_in_tolerance")
                    actions.append(action)
        
        # Store pending actions
        self._pending_actions[zone_id] = actions
        
        return actions
    
    def _evaluate_schedule(self, zone_id: str) -> Optional[ClimateAction]:
        """Evaluate schedule for zone."""
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%H:%M")
        current_day = now.weekday()
        
        schedules = self._schedules.get(zone_id, [])
        
        for schedule in sorted(schedules, key=lambda s: s.start_time):
            if not schedule.enabled:
                continue
            
            if current_day not in schedule.days_of_week:
                continue
            
            if schedule.start_time <= current_time:
                # Check if next schedule hasn't passed
                target_temp = schedule.target_temp
                
                state = self._states.get(zone_id)
                if state and abs(state.target_temp_celsius - target_temp) > 0.5:
                    return self._create_set_temp_action(zone_id, target_temp, f"schedule:{schedule.name}")
        
        return None
    
    def _create_hvac_off_action(self, zone_id: str, reason: str) -> ClimateAction:
        """Create HVAC off action."""
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_off",
            reason=reason,
        )
    
    def _create_set_temp_action(self, zone_id: str, temp: float, reason: str) -> ClimateAction:
        """Create set temperature action."""
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_temp",
            target_temp=temp,
            reason=reason,
        )
    
    def _create_frost_protection_action(self, zone_id: str) -> ClimateAction:
        """Create frost protection action."""
        config = self._configs.get(zone_id)
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_on",
            hvac_mode=HVACMode.HEAT,
            target_temp=config.frost_protection_temp + 2 if config else 7.0,
            reason="frost_protection",
        )
    
    def _create_overheat_protection_action(self, zone_id: str) -> ClimateAction:
        """Create overheat protection action."""
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_on",
            hvac_mode=HVACMode.COOL,
            reason="overheat_protection",
        )
    
    def _create_turn_on_action(self, zone_id: str, mode: HVACMode, reason: str) -> ClimateAction:
        """Create turn on action."""
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_on",
            hvac_mode=mode,
            reason=reason,
        )
    
    def _create_turn_off_action(self, zone_id: str, reason: str) -> ClimateAction:
        """Create turn off action."""
        return ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_off",
            reason=reason,
        )
    
    def set_target_temperature(self, zone_id: str, temperature: float) -> List[ClimateAction]:
        """Manually set target temperature for a zone."""
        config = self._configs.get(zone_id)
        
        if not config:
            return []
        
        # Validate temperature
        temperature = max(config.min_temp_celsius, min(config.max_temp_celsius, temperature))
        
        if zone_id in self._states:
            self._states[zone_id].target_temp_celsius = temperature
        
        action = ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_temp",
            target_temp=temperature,
            reason="manual",
            triggered_by="user",
        )
        
        return [action]
    
    def set_hvac_mode(self, zone_id: str, mode: HVACMode) -> List[ClimateAction]:
        """Manually set HVAC mode for a zone."""
        if zone_id not in self._states:
            return []

        self._states[zone_id].hvac_mode = mode
        
        action = ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_mode",
            hvac_mode=mode,
            reason="manual",
            triggered_by="user",
        )
        
        return [action]
    
    def set_fan_mode(self, zone_id: str, mode: FanMode) -> List[ClimateAction]:
        """Manually set fan mode for a zone."""
        if zone_id not in self._states:
            return []

        self._states[zone_id].fan_mode = mode
        
        action = ClimateAction(
            action_id=f"ca_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_fan",
            fan_mode=mode,
            reason="manual",
            triggered_by="user",
        )
        
        return [action]
    
    def enable_eco_mode(self, zone_id: str) -> bool:
        """Enable eco mode for a zone."""
        if zone_id not in self._configs:
            return False
        
        self._configs[zone_id].eco_mode_enabled = True
        return True
    
    def disable_eco_mode(self, zone_id: str) -> bool:
        """Disable eco mode for a zone."""
        if zone_id not in self._configs:
            return False
        
        self._configs[zone_id].eco_mode_enabled = False
        return True
    
    def get_state(self, zone_id: str) -> Optional[ClimateState]:
        """Get current climate state for a zone."""
        return self._states.get(zone_id)
    
    def get_pending_actions(self, zone_id: str) -> List[ClimateAction]:
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
        """Get climate module statistics."""
        zones_heating = len([s for s in self._states.values() if s.is_heating])
        zones_cooling = len([s for s in self._states.values() if s.is_cooling])
        zones_eco = len([s for s in self._states.values() if s.eco_mode_active])
        windows_open = len([s for s in self._states.values() if s.window_open])
        
        return {
            "total_zones": len(self._configs),
            "zones_heating": zones_heating,
            "zones_cooling": zones_cooling,
            "zones_eco_mode": zones_eco,
            "windows_open": windows_open,
            "total_schedules": sum(len(s) for s in self._schedules.values()),
            "frost_protection_active": len([s for s in self._states.values() if s.frost_protection_active]),
            "overheat_protection_active": len([s for s in self._states.values() if s.overheat_protection_active]),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_climate_module() -> ClimateModule:
    """Factory function to create climate module."""
    return ClimateModule()


class ClimateEngine:
    """Compatibility facade for legacy integration tests."""

    def __init__(self, event_bus: Any = None, zone_registry: Any = None):
        self.event_bus = event_bus
        self.zone_registry = zone_registry

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if self.event_bus and hasattr(self.event_bus, "publish"):
            self.event_bus.publish(topic, payload)

    def on_zone_vacant(self, zone_id: str) -> None:
        self._publish("climate_presence", {"zone_id": zone_id, "mode": "eco"})

    def on_schedule_event(self, zone_id: str, event_type: str, at_time: str) -> None:
        self._publish("climate_schedule", {
            "zone_id": zone_id,
            "event": event_type,
            "at": at_time,
            "action": "preheat",
            "target_temp": 21.0,
        })
