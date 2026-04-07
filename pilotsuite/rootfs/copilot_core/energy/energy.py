"""Energy Module — Slice 82.

Core energy management for PilotSuite:
- Zone-level energy budgets and tracking
- Device energy profiles and priorities
- Load shedding and optimization
- Solar/battery integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EnergySource(str, Enum):
    """Energy source types."""
    GRID = "grid"
    SOLAR = "solar"
    BATTERY = "battery"


class LoadPriority(str, Enum):
    """Load priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class EnergyConfig:
    """Configuration for zone energy management."""
    zone_id: str
    daily_budget_kwh: float = 12.0
    monthly_budget_kwh: float = 500.0
    peak_limit_kw: float = 5.0
    load_shedding_enabled: bool = True
    solar_priority_enabled: bool = False
    battery_management_enabled: bool = False
    cost_optimization_enabled: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "daily_budget_kwh": self.daily_budget_kwh,
            "monthly_budget_kwh": self.monthly_budget_kwh,
            "peak_limit_kw": self.peak_limit_kw,
            "load_shedding_enabled": self.load_shedding_enabled,
            "solar_priority_enabled": self.solar_priority_enabled,
            "battery_management_enabled": self.battery_management_enabled,
            "cost_optimization_enabled": self.cost_optimization_enabled,
        }


@dataclass
class DeviceEnergy:
    """Device energy profile."""
    device_id: str
    zone_id: str
    name: str
    power_rating_watts: float
    current_power_watts: float = 0.0
    priority: LoadPriority = LoadPriority.MEDIUM
    is_deferrable: bool = False
    daily_energy_kwh: float = 0.0
    monthly_energy_kwh: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "power_rating_watts": self.power_rating_watts,
            "current_power_watts": self.current_power_watts,
            "priority": self.priority.value,
            "is_deferrable": self.is_deferrable,
            "daily_energy_kwh": self.daily_energy_kwh,
            "monthly_energy_kwh": self.monthly_energy_kwh,
        }


@dataclass
class ZoneEnergyState:
    """Current energy state for a zone."""
    zone_id: str
    current_power_kw: float = 0.0
    energy_today_kwh: float = 0.0
    energy_month_kwh: float = 0.0
    budget_remaining_percent: float = 100.0
    load_shedding_active: bool = False
    efficiency_score: float = 1.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "current_power_kw": self.current_power_kw,
            "energy_today_kwh": self.energy_today_kwh,
            "energy_month_kwh": self.energy_month_kwh,
            "budget_remaining_percent": self.budget_remaining_percent,
            "load_shedding_active": self.load_shedding_active,
            "efficiency_score": self.efficiency_score,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class EnergyAction:
    """Energy management action."""
    action_id: str
    zone_id: str
    action_type: str  # shed_load, charge_battery, discharge_battery, shift_load
    device_id: Optional[str] = None
    power_kw: Optional[float] = None
    reason: Optional[str] = None
    triggered_by: str = "auto"  # auto, user, schedule
    executed_at: Optional[datetime] = None
    result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "device_id": self.device_id,
            "power_kw": self.power_kw,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "result": self.result,
        }


class EnergyModule:
    """Energy management module for a zone."""
    
    def __init__(self):
        self._configs: Dict[str, EnergyConfig] = {}
        self._devices: Dict[str, DeviceEnergy] = {}
        self._states: Dict[str, ZoneEnergyState] = {}
        self._actions: List[EnergyAction] = []
    
    def set_zone_config(self, config: EnergyConfig) -> bool:
        """Set energy configuration for a zone."""
        self._configs[config.zone_id] = config
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[EnergyConfig]:
        """Get energy configuration for a zone."""
        return self._configs.get(zone_id)
    
    def register_device(self, device: DeviceEnergy) -> bool:
        """Register a device for energy tracking."""
        self._devices[device.device_id] = device
        return True
    
    def get_device(self, device_id: str) -> Optional[DeviceEnergy]:
        """Get device energy profile."""
        return self._devices.get(device_id)
    
    def update_zone_state(self, state: ZoneEnergyState) -> bool:
        """Update zone energy state."""
        self._states[state.zone_id] = state
        return True
    
    def get_zone_state(self, zone_id: str) -> Optional[ZoneEnergyState]:
        """Get zone energy state."""
        return self._states.get(zone_id)
    
    def record_action(self, action: EnergyAction) -> bool:
        """Record an energy management action."""
        self._actions.append(action)
        return True
    
    def get_actions(self, zone_id: Optional[str] = None, limit: int = 50) -> List[EnergyAction]:
        """Get recent energy actions."""
        actions = self._actions
        if zone_id:
            actions = [a for a in actions if a.zone_id == zone_id]
        return actions[-limit:]
    
    def calculate_budget_remaining(self, zone_id: str) -> float:
        """Calculate remaining budget percentage for a zone."""
        config = self._configs.get(zone_id)
        state = self._states.get(zone_id)
        if not config or not state:
            return 100.0
        
        if config.daily_budget_kwh <= 0:
            return 100.0
        
        remaining = max(0, config.daily_budget_kwh - state.energy_today_kwh)
        return min(100.0, (remaining / config.daily_budget_kwh) * 100)
    
    def should_shed_load(self, zone_id: str) -> bool:
        """Determine if load shedding should be activated."""
        config = self._configs.get(zone_id)
        state = self._states.get(zone_id)
        if not config or not state:
            return False
        
        if not config.load_shedding_enabled:
            return False
        
        # Shed if over peak limit or budget exceeded
        if state.current_power_kw > config.peak_limit_kw:
            return True
        
        if state.budget_remaining_percent < 10.0:
            return True
        
        return False


def create_energy_module() -> EnergyModule:
    """Factory function to create an energy module."""
    return EnergyModule()
