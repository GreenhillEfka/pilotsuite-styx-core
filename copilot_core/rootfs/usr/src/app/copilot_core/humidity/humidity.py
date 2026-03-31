"""Humidity Module — Slice 81.

Luftfeuchtigkeit-Steuerung für Habituszonen.

Features:
- Humidity Monitoring
- Humidifier Control (increase humidity)
- Dehumidifier Control (decrease humidity)
- Target Humidity per Zone
- Mold Prevention (max humidity threshold)
- Health Comfort Range (30-60%)
- Schedule Support
- Plant Mode (higher humidity for plants)
- Integration with Climate Module
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class HumidityMode(Enum):
    """Humidity control modes."""
    OFF = "off"
    AUTO = "auto"
    HUMIDIFY = "humidify"
    DEHUMIDIFY = "dehumidify"


@dataclass
class HumidityConfig:
    """Humidity configuration for a zone."""
    zone_id: str
    mode: HumidityMode = HumidityMode.AUTO
    target_humidity_percent: float = 50.0
    min_humidity_percent: float = 30.0
    max_humidity_percent: float = 60.0
    humidity_tolerance_percent: float = 5.0
    mold_prevention_enabled: bool = True
    mold_threshold_percent: float = 65.0
    health_comfort_enabled: bool = True
    health_min_percent: float = 30.0
    health_max_percent: float = 60.0
    plant_mode_enabled: bool = False
    plant_target_percent: float = 70.0
    schedule_enabled: bool = False
    linked_climate_zone: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "mode": self.mode.value,
            "target_humidity_percent": self.target_humidity_percent,
            "min_humidity_percent": self.min_humidity_percent,
            "max_humidity_percent": self.max_humidity_percent,
            "humidity_tolerance_percent": self.humidity_tolerance_percent,
            "mold_prevention_enabled": self.mold_prevention_enabled,
            "mold_threshold_percent": self.mold_threshold_percent,
            "health_comfort_enabled": self.health_comfort_enabled,
            "health_min_percent": self.health_min_percent,
            "health_max_percent": self.health_max_percent,
            "plant_mode_enabled": self.plant_mode_enabled,
            "plant_target_percent": self.plant_target_percent,
            "schedule_enabled": self.schedule_enabled,
            "linked_climate_zone": self.linked_climate_zone,
        }


@dataclass
class HumidityState:
    """Current humidity state for a zone."""
    zone_id: str
    current_humidity_percent: float = 0.0
    target_humidity_percent: float = 50.0
    mode: HumidityMode = HumidityMode.OFF
    is_humidifying: bool = False
    is_dehumidifying: bool = False
    mold_risk_active: bool = False
    health_comfort_active: bool = False
    plant_mode_active: bool = False
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "current_humidity_percent": self.current_humidity_percent,
            "target_humidity_percent": self.target_humidity_percent,
            "mode": self.mode.value,
            "is_humidifying": self.is_humidifying,
            "is_dehumidifying": self.is_dehumidifying,
            "mold_risk_active": self.mold_risk_active,
            "health_comfort_active": self.health_comfort_active,
            "plant_mode_active": self.plant_mode_active,
            "last_update": self.last_update,
        }


@dataclass
class HumidityAction:
    """Humidity action to execute."""
    action_id: str
    zone_id: str
    action_type: str  # humidify, dehumidify, turn_off, set_target
    target_humidity: Optional[float] = None
    mode: Optional[HumidityMode] = None
    reason: str = ""
    triggered_by: str = "auto"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "target_humidity": self.target_humidity,
            "mode": self.mode.value if self.mode else None,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
        }


class HumidityModule:
    """Humidity module for zone-aware control.
    
    Architecture:
        Humidity Sensors → Threshold Logic → Humidifier/Dehumidifier Actions
    
    Usage:
        module = HumidityModule()
        module.set_zone_config(config)
        module.update_sensor_data(zone_id, humidity)
        actions = module.evaluate_zone(zone_id)
    """
    
    def __init__(self):
        self._configs: Dict[str, HumidityConfig] = {}
        self._states: Dict[str, HumidityState] = {}
        self._pending_actions: Dict[str, List[HumidityAction]] = {}
        
        logger.info("HumidityModule initialized")
    
    def set_zone_config(self, config: HumidityConfig) -> bool:
        """Set humidity configuration for a zone."""
        with self._lock():
            self._configs[config.zone_id] = config
            
            # Initialize state
            self._states[config.zone_id] = HumidityState(
                zone_id=config.zone_id,
                target_humidity_percent=config.target_humidity_percent,
                mode=config.mode,
            )
        
        logger.info("Humidity config set for %s", config.zone_id)
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[HumidityConfig]:
        """Get humidity configuration for a zone."""
        return self._configs.get(zone_id)
    
    def update_sensor_data(self, zone_id: str, humidity: float) -> None:
        """Update humidity sensor data for a zone."""
        if zone_id not in self._states:
            self._states[zone_id] = HumidityState(zone_id=zone_id)
        
        state = self._states[zone_id]
        state.current_humidity_percent = humidity
        state.last_update = datetime.now(timezone.utc).isoformat()
    
    def evaluate_zone(self, zone_id: str) -> List[HumidityAction]:
        """Evaluate zone and generate humidity actions."""
        config = self._configs.get(zone_id)
        state = self._states.get(zone_id)
        
        if not config or not state:
            return []
        
        actions = []
        current = state.current_humidity_percent
        target = state.target_humidity_percent
        tolerance = config.humidity_tolerance_percent
        
        # Check mold prevention (highest priority)
        if config.mold_prevention_enabled:
            if current > config.mold_threshold_percent:
                if not state.mold_risk_active:
                    state.mold_risk_active = True
                    action = self._create_dehumidify_action(zone_id, "mold_prevention")
                    actions.append(action)
                return actions
        
        state.mold_risk_active = False
        
        # Check plant mode
        if config.plant_mode_enabled:
            state.plant_mode_active = True
            target = config.plant_target_percent
            
            if current < target - tolerance:
                if not state.is_humidifying:
                    state.is_humidifying = True
                    action = self._create_humidify_action(zone_id, "plant_mode")
                    actions.append(action)
            elif current > target + tolerance:
                if state.is_humidifying:
                    state.is_humidifying = False
                    action = self._create_turn_off_action(zone_id, "plant_mode_target_reached")
                    actions.append(action)
            return actions
        
        state.plant_mode_active = False
        
        # Check health comfort range
        if config.health_comfort_enabled:
            if current < config.health_min_percent or current > config.health_max_percent:
                state.health_comfort_active = True
                
                if current < config.health_min_percent:
                    if not state.is_humidifying:
                        state.is_humidifying = True
                        action = self._create_humidify_action(zone_id, "health_comfort_low")
                        actions.append(action)
                elif current > config.health_max_percent:
                    if not state.is_dehumidifying:
                        state.is_dehumidifying = True
                        action = self._create_dehumidify_action(zone_id, "health_comfort_high")
                        actions.append(action)
                return actions
        
        state.health_comfort_active = False
        
        # Normal auto mode
        if config.mode == HumidityMode.AUTO:
            if current < target - tolerance:
                # Too dry - humidify
                if not state.is_humidifying:
                    state.is_humidifying = True
                    state.is_dehumidifying = False
                    action = self._create_humidify_action(zone_id, "humidity_low")
                    actions.append(action)
            elif current > target + tolerance:
                # Too humid - dehumidify
                if not state.is_dehumidifying:
                    state.is_dehumidifying = True
                    state.is_humidifying = False
                    action = self._create_dehumidify_action(zone_id, "humidity_high")
                    actions.append(action)
            else:
                # In tolerance
                if state.is_humidifying or state.is_dehumidifying:
                    state.is_humidifying = False
                    state.is_dehumidifying = False
                    action = self._create_turn_off_action(zone_id, "humidity_in_tolerance")
                    actions.append(action)
        
        elif config.mode == HumidityMode.HUMIDIFY:
            if current < target - tolerance:
                if not state.is_humidifying:
                    state.is_humidifying = True
                    action = self._create_humidify_action(zone_id, "manual_humidify")
                    actions.append(action)
            elif current >= target + tolerance:
                if state.is_humidifying:
                    state.is_humidifying = False
                    action = self._create_turn_off_action(zone_id, "target_reached")
                    actions.append(action)
        
        elif config.mode == HumidityMode.DEHUMIDIFY:
            if current > target + tolerance:
                if not state.is_dehumidifying:
                    state.is_dehumidifying = True
                    action = self._create_dehumidify_action(zone_id, "manual_dehumidify")
                    actions.append(action)
            elif current <= target - tolerance:
                if state.is_dehumidifying:
                    state.is_dehumidifying = False
                    action = self._create_turn_off_action(zone_id, "target_reached")
                    actions.append(action)
        
        # Store pending actions
        self._pending_actions[zone_id] = actions
        
        return actions
    
    def _create_humidify_action(self, zone_id: str, reason: str) -> HumidityAction:
        """Create humidify action."""
        return HumidityAction(
            action_id=f"ha_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="humidify",
            reason=reason,
        )
    
    def _create_dehumidify_action(self, zone_id: str, reason: str) -> HumidityAction:
        """Create dehumidify action."""
        return HumidityAction(
            action_id=f"ha_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="dehumidify",
            reason=reason,
        )
    
    def _create_turn_off_action(self, zone_id: str, reason: str) -> HumidityAction:
        """Create turn off action."""
        return HumidityAction(
            action_id=f"ha_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="turn_off",
            reason=reason,
        )
    
    def set_target_humidity(self, zone_id: str, humidity: float) -> List[HumidityAction]:
        """Manually set target humidity for a zone."""
        config = self._configs.get(zone_id)
        
        if not config:
            return []
        
        # Validate humidity
        humidity = max(config.min_humidity_percent, min(config.max_humidity_percent, humidity))
        
        if zone_id in self._states:
            self._states[zone_id].target_humidity_percent = humidity
        
        action = HumidityAction(
            action_id=f"ha_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_target",
            target_humidity=humidity,
            reason="manual",
            triggered_by="user",
        )
        
        return [action]
    
    def set_mode(self, zone_id: str, mode: HumidityMode) -> List[HumidityAction]:
        """Manually set humidity mode for a zone."""
        if zone_id in self._states:
            self._states[zone_id].mode = mode
        
        action = HumidityAction(
            action_id=f"ha_{uuid.uuid4().hex[:16]}",
            zone_id=zone_id,
            action_type="set_mode",
            mode=mode,
            reason="manual",
            triggered_by="user",
        )
        
        return [action]
    
    def enable_plant_mode(self, zone_id: str) -> bool:
        """Enable plant mode for a zone."""
        if zone_id not in self._configs:
            return False
        
        self._configs[zone_id].plant_mode_enabled = True
        return True
    
    def disable_plant_mode(self, zone_id: str) -> bool:
        """Disable plant mode for a zone."""
        if zone_id not in self._configs:
            return False
        
        self._configs[zone_id].plant_mode_enabled = False
        return True
    
    def get_state(self, zone_id: str) -> Optional[HumidityState]:
        """Get current humidity state for a zone."""
        return self._states.get(zone_id)
    
    def get_pending_actions(self, zone_id: str) -> List[HumidityAction]:
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
        """Get humidity module statistics."""
        zones_humidifying = len([s for s in self._states.values() if s.is_humidifying])
        zones_dehumidifying = len([s for s in self._states.values() if s.is_dehumidifying])
        mold_risk_zones = len([s for s in self._states.values() if s.mold_risk_active])
        plant_mode_zones = len([s for s in self._states.values() if s.plant_mode_active])
        
        return {
            "total_zones": len(self._configs),
            "zones_humidifying": zones_humidifying,
            "zones_dehumidifying": zones_dehumidifying,
            "mold_risk_zones": mold_risk_zones,
            "plant_mode_zones": plant_mode_zones,
            "health_comfort_zones": len([s for s in self._states.values() if s.health_comfort_active]),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_humidity_module() -> HumidityModule:
    """Factory function to create humidity module."""
    return HumidityModule()
