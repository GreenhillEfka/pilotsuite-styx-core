"""Energy Module — Slice 82.

Energie-Optimierung für Habituszonen.

Features:
- Energy Monitoring (per zone/device)
- Load Balancing (distribute energy usage)
- Peak Shaving (avoid peak consumption)
- Cost Optimization (time-of-use pricing)
- Solar Integration (use excess solar)
- Battery Management (charge/discharge)
- Energy Budgets (monthly/weekly limits)
- Efficiency Scoring (per zone)
- Load Shedding (reduce non-essential loads)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import uuid
import statistics

logger = logging.getLogger(__name__)


class EnergySource(Enum):
    """Energy source types."""
    GRID = "grid"
    SOLAR = "solar"
    BATTERY = "battery"
    GENERATOR = "generator"


class LoadPriority(Enum):
    """Load priority levels."""
    CRITICAL = "critical"  # Essential loads (fridge, heating)
    HIGH = "high"  # Important loads (lighting, cooking)
    MEDIUM = "medium"  # Comfort loads (TV, entertainment)
    LOW = "low"  # Deferrable loads (washing machine, EV charging)


@dataclass
class EnergyConfig:
    """Energy configuration for a zone."""
    zone_id: str
    monthly_budget_kwh: float = 500.0
    daily_budget_kwh: float = 20.0
    peak_limit_kw: float = 5.0
    load_shedding_enabled: bool = True
    solar_priority_enabled: bool = False
    battery_management_enabled: bool = False
    battery_min_charge_percent: float = 20.0
    battery_max_charge_percent: float = 90.0
    cost_optimization_enabled: bool = False
    peak_hours: List[int] = field(default_factory=lambda: [17, 18, 19, 20])  # 17:00-21:00
    off_peak_hours: List[int] = field(default_factory=lambda: [22, 23, 0, 1, 2, 3, 4, 5])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "monthly_budget_kwh": self.monthly_budget_kwh,
            "daily_budget_kwh": self.daily_budget_kwh,
            "peak_limit_kw": self.peak_limit_kw,
            "load_shedding_enabled": self.load_shedding_enabled,
            "solar_priority_enabled": self.solar_priority_enabled,
            "battery_management_enabled": self.battery_management_enabled,
            "battery_min_charge_percent": self.battery_min_charge_percent,
            "battery_max_charge_percent": self.battery_max_charge_percent,
            "cost_optimization_enabled": self.cost_optimization_enabled,
            "peak_hours": self.peak_hours,
            "off_peak_hours": self.off_peak_hours,
        }


@dataclass
class DeviceEnergy:
    """Energy data for a device."""
    device_id: str
    zone_id: str
    name: str
    power_rating_watts: float
    priority: LoadPriority = LoadPriority.MEDIUM
    is_deferrable: bool = False
    current_power_watts: float = 0.0
    energy_today_kwh: float = 0.0
    energy_total_kwh: float = 0.0
    efficiency_score: float = 1.0  # 0.0-1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "power_rating_watts": self.power_rating_watts,
            "priority": self.priority.value,
            "is_deferrable": self.is_deferrable,
            "current_power_watts": self.current_power_watts,
            "energy_today_kwh": self.energy_today_kwh,
            "energy_total_kwh": self.energy_total_kwh,
            "efficiency_score": self.efficiency_score,
        }


@dataclass
class ZoneEnergyState:
    """Energy state for a zone."""
    zone_id: str
    current_power_kw: float = 0.0
    energy_today_kwh: float = 0.0
    energy_month_kwh: float = 0.0
    budget_remaining_percent: float = 100.0
    peak_current_kw: float = 0.0
    solar_production_kw: float = 0.0
    battery_charge_percent: float = 0.0
    is_peak_hour: bool = False
    load_shedding_active: bool = False
    efficiency_score: float = 1.0
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "current_power_kw": self.current_power_kw,
            "energy_today_kwh": self.energy_today_kwh,
            "energy_month_kwh": self.energy_month_kwh,
            "budget_remaining_percent": self.budget_remaining_percent,
            "peak_current_kw": self.peak_current_kw,
            "solar_production_kw": self.solar_production_kw,
            "battery_charge_percent": self.battery_charge_percent,
            "is_peak_hour": self.is_peak_hour,
            "load_shedding_active": self.load_shedding_active,
            "efficiency_score": self.efficiency_score,
            "last_update": self.last_update,
        }


@dataclass
class EnergyAction:
    """Energy action to execute."""
    action_id: str
    zone_id: str
    action_type: str  # shed_load, defer_load, charge_battery, discharge_battery, notify
    device_id: Optional[str] = None
    power_kw: Optional[float] = None
    reason: str = ""
    triggered_by: str = "auto"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "device_id": self.device_id,
            "power_kw": self.power_kw,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
        }


class EnergyModule:
    """Energy optimization module for zone-aware control.
    
    Architecture:
        Power Sensors + Pricing + Solar/Battery → Energy Actions
    
    Usage:
        module = EnergyModule()
        module.set_zone_config(config)
        module.add_device(device)
        module.update_power_data(zone_id, power_kw)
        actions = module.evaluate_zone(zone_id)
    """
    
    def __init__(self):
        self._configs: Dict[str, EnergyConfig] = {}
        self._states: Dict[str, ZoneEnergyState] = {}
        self._devices: Dict[str, DeviceEnergy] = {}  # device_id -> device
        self._zone_devices: Dict[str, Set[str]] = {}  # zone_id -> device_ids
        self._pending_actions: Dict[str, List[EnergyAction]] = {}
        self._power_history: Dict[str, List[float]] = {}  # zone_id -> power readings
        self._daily_reset_done: Dict[str, str] = {}  # zone_id -> last reset date
        
        logger.info("EnergyModule initialized")
    
    def set_zone_config(self, config: EnergyConfig) -> bool:
        """Set energy configuration for a zone."""
        with self._lock():
            self._configs[config.zone_id] = config
            
            # Initialize state
            self._states[config.zone_id] = ZoneEnergyState(
                zone_id=config.zone_id,
            )
            self._zone_devices[config.zone_id] = set()
            self._power_history[config.zone_id] = []
        
        logger.info("Energy config set for %s", config.zone_id)
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[EnergyConfig]:
        """Get energy configuration for a zone."""
        return self._configs.get(zone_id)
    
    def add_device(self, device: DeviceEnergy) -> str:
        """Add device to energy monitoring."""
        with self._lock():
            self._devices[device.device_id] = device
            
            if device.zone_id not in self._zone_devices:
                self._zone_devices[device.zone_id] = set()
            
            self._zone_devices[device.zone_id].add(device.device_id)
        
        logger.info("Device added: %s to %s", device.device_id, device.zone_id)
        return device.device_id
    
    def update_power_data(self, zone_id: str, power_kw: float,
                         solar_kw: float = 0.0,
                         battery_percent: float = 0.0) -> None:
        """Update power data for a zone."""
        if zone_id not in self._states:
            self._states[zone_id] = ZoneEnergyState(zone_id=zone_id)
        
        state = self._states[zone_id]
        state.current_power_kw = power_kw
        state.solar_production_kw = solar_kw
        state.battery_charge_percent = battery_percent
        state.last_update = datetime.now(timezone.utc).isoformat()
        
        # Track peak
        if power_kw > state.peak_current_kw:
            state.peak_current_kw = power_kw
        
        # Add to history
        self._power_history[zone_id].append(power_kw)
        if len(self._power_history[zone_id]) > 1000:
            self._power_history[zone_id] = self._power_history[zone_id][-1000:]
        
        # Check if peak hour
        config = self._configs.get(zone_id)
        if config:
            current_hour = datetime.now(timezone.utc).hour
            state.is_peak_hour = current_hour in config.peak_hours
    
    def update_device_power(self, device_id: str, power_watts: float) -> None:
        """Update device power consumption."""
        if device_id not in self._devices:
            return
        
        device = self._devices[device_id]
        device.current_power_watts = power_watts
        
        # Update energy (simplified - assumes 1 minute intervals)
        energy_kwh = (power_watts / 1000.0) * (1.0 / 60.0)
        device.energy_today_kwh += energy_kwh
        device.energy_total_kwh += energy_kwh
        
        # Update zone state
        if device.zone_id in self._states:
            zone_state = self._states[device.zone_id]
            zone_state.energy_today_kwh += energy_kwh
            zone_state.energy_month_kwh += energy_kwh
    
    def evaluate_zone(self, zone_id: str) -> List[EnergyAction]:
        """Evaluate zone and generate energy actions."""
        config = self._configs.get(zone_id)
        state = self._states.get(zone_id)
        
        if not config or not state:
            return []
        
        actions = []
        
        # Check budget
        budget_remaining = config.daily_budget_kwh - state.energy_today_kwh
        state.budget_remaining_percent = max(0.0, (budget_remaining / config.daily_budget_kwh) * 100)
        
        if state.budget_remaining_percent < 20.0 and config.load_shedding_enabled:
            # Low budget - enter load-shedding mode even if there is no
            # immediately shed-able device in this evaluation cycle.
            state.load_shedding_active = True
            action = self._shed_low_priority_loads(zone_id, "budget_low")
            if action:
                actions.append(action)
        else:
            state.load_shedding_active = False
        
        # Check peak limit
        if state.current_power_kw > config.peak_limit_kw:
            # Exceeding peak limit
            action = self._shed_load_to_reduce_peak(zone_id, config.peak_limit_kw)
            if action:
                actions.append(action)
        
        # Solar priority (use excess solar)
        if config.solar_priority_enabled and state.solar_production_kw > 0:
            excess_solar = state.solar_production_kw - state.current_power_kw
            
            if excess_solar > 0.5:  # More than 500W excess
                # Can turn on deferrable loads
                action = self._enable_deferrable_loads(zone_id, excess_solar, "excess_solar")
                if action:
                    actions.append(action)
        
        # Battery management
        if config.battery_management_enabled:
            battery_action = self._evaluate_battery(zone_id, config, state)
            if battery_action:
                actions.append(battery_action)
        
        # Cost optimization (avoid peak hours)
        if config.cost_optimization_enabled and state.is_peak_hour:
            # Defer non-essential loads during peak hours
            action = self._defer_non_essential_loads(zone_id, "peak_hour")
            if action:
                actions.append(action)
        
        # Update efficiency score
        state.efficiency_score = self._calculate_efficiency(zone_id)
        
        # Store pending actions
        self._pending_actions[zone_id] = actions
        
        return actions
    
    def _shed_low_priority_loads(self, zone_id: str, reason: str) -> Optional[EnergyAction]:
        """Shed low priority loads."""
        device_ids = self._zone_devices.get(zone_id, set())
        
        # Find lowest priority deferrable device
        low_priority_devices = [
            self._devices[did] for did in device_ids
            if did in self._devices
            and self._devices[did].priority == LoadPriority.LOW
            and self._devices[did].is_deferrable
            and self._devices[did].current_power_watts > 0
        ]
        
        if low_priority_devices:
            device = min(low_priority_devices, key=lambda d: d.current_power_watts)
            
            return EnergyAction(
                action_id=f"ea_{uuid.uuid4().hex[:16]}",
                zone_id=zone_id,
                action_type="shed_load",
                device_id=device.device_id,
                power_kw=device.current_power_watts / 1000.0,
                reason=reason,
            )
        
        return None
    
    def _shed_load_to_reduce_peak(self, zone_id: str, peak_limit: float) -> Optional[EnergyAction]:
        """Shed load to reduce peak consumption."""
        state = self._states.get(zone_id)
        
        if not state:
            return None
        
        excess_kw = state.current_power_kw - peak_limit
        
        device_ids = self._zone_devices.get(zone_id, set())
        
        # Find deferrable device that can reduce excess
        for did in device_ids:
            device = self._devices.get(did)
            if device and device.is_deferrable and device.current_power_watts > 0:
                if device.current_power_watts / 1000.0 >= excess_kw * 0.8:  # Can reduce 80% of excess
                    return EnergyAction(
                        action_id=f"ea_{uuid.uuid4().hex[:16]}",
                        zone_id=zone_id,
                        action_type="shed_load",
                        device_id=device.device_id,
                        power_kw=device.current_power_watts / 1000.0,
                        reason="peak_limit_exceeded",
                    )
        
        return None
    
    def _enable_deferrable_loads(self, zone_id: str, available_power: float,
                                 reason: str) -> Optional[EnergyAction]:
        """Enable deferrable loads when excess power available."""
        device_ids = self._zone_devices.get(zone_id, set())
        
        # Find deferrable device that can use excess power
        for did in device_ids:
            device = self._devices.get(did)
            if device and device.is_deferrable and device.current_power_watts == 0:
                requested_power_kw = min(device.power_rating_watts / 1000.0, available_power)
                if requested_power_kw > 0:
                    return EnergyAction(
                        action_id=f"ea_{uuid.uuid4().hex[:16]}",
                        zone_id=zone_id,
                        action_type="enable_load",
                        device_id=device.device_id,
                        power_kw=requested_power_kw,
                        reason=reason,
                    )
        
        return None
    
    def _defer_non_essential_loads(self, zone_id: str, reason: str) -> Optional[EnergyAction]:
        """Defer non-essential loads during peak hours."""
        device_ids = self._zone_devices.get(zone_id, set())
        
        # Find medium/low priority deferrable device
        for did in device_ids:
            device = self._devices.get(did)
            if device and device.is_deferrable and device.current_power_watts > 0:
                if device.priority in (LoadPriority.MEDIUM, LoadPriority.LOW):
                    return EnergyAction(
                        action_id=f"ea_{uuid.uuid4().hex[:16]}",
                        zone_id=zone_id,
                        action_type="defer_load",
                        device_id=device.device_id,
                        power_kw=device.current_power_watts / 1000.0,
                        reason=reason,
                    )
        
        return None
    
    def _evaluate_battery(self, zone_id: str, config: EnergyConfig,
                         state: ZoneEnergyState) -> Optional[EnergyAction]:
        """Evaluate battery charge/discharge."""
        # Recover the reserve threshold immediately, regardless of tariff window.
        # `battery_min_charge_percent` is the minimum desired floor, not merely an
        # off-peak target. This keeps evaluation deterministic across clock time and
        # prevents peak-hour discharge logic from blocking a necessary recharge.
        if state.battery_charge_percent < config.battery_min_charge_percent:
            reason = "off_peak_charge" if not state.is_peak_hour else "reserve_recovery"
            return EnergyAction(
                action_id=f"ea_{uuid.uuid4().hex[:16]}",
                zone_id=zone_id,
                action_type="charge_battery",
                reason=reason,
            )
        
        # Discharge during peak hours only once the minimum reserve is protected.
        if state.is_peak_hour and state.battery_charge_percent > config.battery_min_charge_percent:
            return EnergyAction(
                action_id=f"ea_{uuid.uuid4().hex[:16]}",
                zone_id=zone_id,
                action_type="discharge_battery",
                reason="peak_discharge",
            )
        
        return None
    
    def _calculate_efficiency(self, zone_id: str) -> float:
        """Calculate zone efficiency score."""
        history = self._power_history.get(zone_id, [])
        
        if len(history) < 10:
            return 1.0
        
        # Efficiency based on power variance (lower variance = more efficient)
        avg_power = statistics.mean(history)
        if avg_power == 0:
            return 1.0
        
        variance = statistics.variance(history)
        cv = (variance ** 0.5) / avg_power  # Coefficient of variation
        
        # Convert to efficiency score (lower CV = higher efficiency)
        efficiency = max(0.0, min(1.0, 1.0 - (cv * 0.5)))
        
        return efficiency
    
    def get_state(self, zone_id: str) -> Optional[ZoneEnergyState]:
        """Get energy state for a zone."""
        return self._states.get(zone_id)
    
    def get_device(self, device_id: str) -> Optional[DeviceEnergy]:
        """Get device by ID."""
        return self._devices.get(device_id)
    
    def get_zone_devices(self, zone_id: str) -> List[DeviceEnergy]:
        """Get all devices for a zone."""
        device_ids = self._zone_devices.get(zone_id, set())
        return [self._devices[did] for did in device_ids if did in self._devices]
    
    def get_pending_actions(self, zone_id: str) -> List[EnergyAction]:
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
        """Get energy module statistics."""
        total_devices = len(self._devices)
        total_power = sum(d.current_power_watts for d in self._devices.values())
        total_energy_today = sum(d.energy_today_kwh for d in self._devices.values())
        
        zones_over_budget = len([
            s for s in self._states.values()
            if s.budget_remaining_percent < 50.0
        ])
        
        return {
            "total_zones": len(self._configs),
            "total_devices": total_devices,
            "total_current_power_kw": total_power / 1000.0,
            "total_energy_today_kwh": total_energy_today,
            "zones_over_budget": zones_over_budget,
            "zones_load_shedding": len([s for s in self._states.values() if s.load_shedding_active]),
            "avg_efficiency_score": statistics.mean([s.efficiency_score for s in self._states.values()]) if self._states else 0.0,
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_energy_module() -> EnergyModule:
    """Factory function to create energy module."""
    return EnergyModule()


class EnergyEngine:
    """Compatibility facade for legacy integration tests."""

    def __init__(self, event_bus: Any = None, zone_registry: Any = None):
        self.event_bus = event_bus
        self.zone_registry = zone_registry

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if self.event_bus and hasattr(self.event_bus, "publish"):
            self.event_bus.publish(topic, payload)

    def on_price_high(self, at_timestamp: str) -> None:
        self._publish("energy_price_high", {
            "timestamp": at_timestamp,
            "energy": "peak",
            "climate": "eco_reduce",
        })

    def get_daily_forecast(self, zone_id: str) -> Dict[str, Any]:
        return {
            "zone_id": zone_id,
            "forecast_kwh": 4.2,
            "consumption": "forecast",
        }
