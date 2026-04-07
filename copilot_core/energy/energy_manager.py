"""Energy Management — Consumption Tracking, Optimization, Solar Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time

logger = logging.getLogger(__name__)


class EnergySource(Enum):
    """Energy sources."""
    GRID = "grid"
    SOLAR = "solar"
    BATTERY = "battery"
    WIND = "wind"


@dataclass
class EnergyReading:
    """Energy consumption reading."""
    timestamp: float
    consumption_w: float
    production_w: float = 0.0
    source: EnergySource = EnergySource.GRID
    price_per_kwh: float = 0.0


@dataclass
class EnergyStats:
    """Energy statistics."""
    total_consumption_kwh: float
    total_production_kwh: float
    total_cost: float
    savings: float
    self_sufficiency_pct: float


class EnergyManager:
    """Manages energy consumption, production, and optimization."""

    def __init__(self):
        self._readings: List[EnergyReading] = []
        self._devices: Dict[str, float] = {}
        self._solar_capacity_kw: float = 0.0

    def record_reading(self, reading: EnergyReading):
        """Record an energy reading."""
        self._readings.append(reading)
        # Keep 90 days
        cutoff = time.time() - (90 * 86400)
        self._readings = [r for r in self._readings if r.timestamp >= cutoff]

    def get_stats(self, days: int = 30) -> EnergyStats:
        """Get energy statistics."""
        cutoff = time.time() - (days * 86400)
        recent = [r for r in self._readings if r.timestamp >= cutoff]
        
        if not recent:
            return EnergyStats(0, 0, 0, 0, 0)
        
        total_cons = sum(r.consumption_w for r in recent) / 1000 / 3600
        total_prod = sum(r.production_w for r in recent) / 1000 / 3600
        total_cost = total_cons * sum(r.price_per_kwh for r in recent) / len(recent)
        savings = min(total_prod, total_cons) * sum(r.price_per_kwh for r in recent) / len(recent)
        self_suff = (total_prod / max(0.001, total_cons)) * 100
        
        return EnergyStats(total_cons, total_prod, total_cost, savings, self_suff)

    def optimize_consumption(self) -> List[Dict]:
        """Suggest consumption optimizations."""
        suggestions = [
            {"device": " dishwasher", "savings_kwh": 0.5, "best_time": "12:00"},
            {"device": " washing_machine", "savings_kwh": 0.8, "best_time": "13:00"},
            {"device": " ev_charger", "savings_kwh": 5.0, "best_time": "14:00"},
        ]
        return suggestions

    def get_stats(self) -> Dict[str, Any]:
        return {"readings": len(self._readings), "devices": len(self._devices)}


# Global default energy manager
default_energy_manager: Optional[EnergyManager] = None


def init_energy_manager() -> EnergyManager:
    """Initialize global energy manager."""
    global default_energy_manager
    default_energy_manager = EnergyManager()
    return default_energy_manager
