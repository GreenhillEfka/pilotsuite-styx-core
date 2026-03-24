"""Zone Health Module for PilotSuite Core.

Provides per-zone health metrics derived from HomeAssistant entity data:
- Temperature: current, min, max, comfort range
- Humidity: current, min, max, comfort range
- CO2: current, air quality level
- Light: brightness, lux level
- Overall health score (0-100)

This is the Core-side counterpart to the HA-side zone_health.
It receives normalized entity data via the HA→Core contract.

Unlike HA's zone_health (which reads HA states directly),
this module works with already-normalized entity snapshots
passed through the event pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from ..homeassistant.entity_mapper import SensorDeviceClass

_LOGGER = logging.getLogger(__name__)

__version__ = "0.1.0"

# Comfort ranges (standard indoor comfort)
TEMP_COMFORT_MIN = 18.0
TEMP_COMFORT_MAX = 26.0
HUMIDITY_COMFORT_MIN = 30.0
HUMIDITY_COMFORT_MAX = 70.0
CO2_GOOD_MAX = 800.0
CO2_MODERATE_MAX = 1200.0

# Score weights
TEMP_PENALTY_MAX = 20.0
HUMIDITY_PENALTY_MAX = 15.0
CO2_PENALTY_MAX = 25.0


@dataclass
class ZoneHealthMetrics:
    """Health metrics for a single zone."""
    zone_id: str
    zone_name: str
    
    # Temperature
    temperature: float | None = None
    temperature_min: float | None = None
    temperature_max: float | None = None
    temperature_comfort: bool = True
    
    # Humidity
    humidity: float | None = None
    humidity_min: float | None = None
    humidity_max: float | None = None
    humidity_comfort: bool = True
    
    # CO2 / Air Quality
    co2: float | None = None
    air_quality: str = "good"  # good, moderate, poor, unknown
    
    # Light
    brightness: float | None = None
    lux: float | None = None
    
    # Overall health
    health_score: float = 100.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["last_updated"] = self.last_updated.isoformat()
        return d
    
    @classmethod
    def from_entity_snapshot(
        cls,
        zone_id: str,
        zone_name: str,
        entity_snapshot: Dict[str, Any],
    ) -> "ZoneHealthMetrics":
        """Create metrics from an entity snapshot dict.
        
        Args:
            zone_id: Zone identifier
            zone_name: Human-readable zone name
            entity_snapshot: Dict of entity_id -> entity state dict
                e.g. {"sensor.living_room_temp": {"state": "21.5", "attributes": {"device_class": "temperature"}}}
        """
        metrics = cls(zone_id=zone_id, zone_name=zone_name)
        
        temp_values: List[float] = []
        humidity_values: List[float] = []
        co2_values: List[float] = []
        lux_values: List[float] = []
        
        for entity_id, entity_data in entity_snapshot.items():
            state = entity_data.get("state", "")
            attrs = entity_data.get("attributes", {})
            device_class = attrs.get("device_class", "")
            entity_id_lower = entity_id.lower()
            
            # Temperature
            if device_class == SensorDeviceClass.TEMPERATURE.value or \
               "temperature" in entity_id_lower or "temp" in entity_id_lower:
                try:
                    temp_values.append(float(state))
                except (ValueError, TypeError):
                    pass
            
            # Humidity
            if device_class == SensorDeviceClass.HUMIDITY.value or \
               "humidity" in entity_id_lower or "humid" in entity_id_lower:
                try:
                    humidity_values.append(float(state))
                except (ValueError, TypeError):
                    pass
            
            # CO2
            if device_class == SensorDeviceClass.CO2.value or \
               "co2" in entity_id_lower or "carbon_dioxide" in entity_id_lower:
                try:
                    co2_values.append(float(state))
                except (ValueError, TypeError):
                    pass
            
            # Illuminance
            if device_class == SensorDeviceClass.ILLUMINANCE.value or \
               "illuminance" in entity_id_lower or "lux" in entity_id_lower:
                try:
                    lux_values.append(float(state))
                except (ValueError, TypeError):
                    pass
        
        # Aggregate temperature
        if temp_values:
            metrics.temperature = sum(temp_values) / len(temp_values)
            metrics.temperature_min = min(temp_values)
            metrics.temperature_max = max(temp_values)
            metrics.temperature_comfort = TEMP_COMFORT_MIN <= metrics.temperature <= TEMP_COMFORT_MAX
        
        # Aggregate humidity
        if humidity_values:
            metrics.humidity = sum(humidity_values) / len(humidity_values)
            metrics.humidity_min = min(humidity_values)
            metrics.humidity_max = max(humidity_values)
            metrics.humidity_comfort = HUMIDITY_COMFORT_MIN <= metrics.humidity <= HUMIDITY_COMFORT_MAX
        
        # Aggregate CO2 (worst case)
        if co2_values:
            metrics.co2 = max(co2_values)
            metrics.air_quality = _get_air_quality(metrics.co2)
        
        # Aggregate lux (brightest)
        if lux_values:
            metrics.lux = max(lux_values)
        
        # Calculate health score
        metrics.health_score = _calculate_health_score(metrics)
        metrics.last_updated = datetime.now(tz=timezone.utc)
        
        return metrics


def _get_air_quality(co2: float | None) -> str:
    """Determine air quality from CO2 level."""
    if co2 is None:
        return "unknown"
    if co2 <= CO2_GOOD_MAX:
        return "good"
    if co2 <= CO2_MODERATE_MAX:
        return "moderate"
    return "poor"


def _calculate_health_score(metrics: ZoneHealthMetrics) -> float:
    """Calculate overall health score (0-100).
    
    Applies penalties for out-of-range metrics.
    """
    score = 100.0
    
    # Temperature penalty
    if metrics.temperature is not None:
        if metrics.temperature < TEMP_COMFORT_MIN:
            delta = TEMP_COMFORT_MIN - metrics.temperature
            score -= min(TEMP_PENALTY_MAX, delta * 2)
        elif metrics.temperature > TEMP_COMFORT_MAX:
            delta = metrics.temperature - TEMP_COMFORT_MAX
            score -= min(TEMP_PENALTY_MAX, delta * 2)
    
    # Humidity penalty
    if metrics.humidity is not None:
        if metrics.humidity < HUMIDITY_COMFORT_MIN:
            delta = HUMIDITY_COMFORT_MIN - metrics.humidity
            score -= min(HUMIDITY_PENALTY_MAX, delta * 0.5)
        elif metrics.humidity > HUMIDITY_COMFORT_MAX:
            delta = metrics.humidity - HUMIDITY_COMFORT_MAX
            score -= min(HUMIDITY_PENALTY_MAX, delta * 0.5)
    
    # CO2 penalty
    if metrics.co2 is not None:
        if metrics.co2 > CO2_MODERATE_MAX:
            score -= CO2_PENALTY_MAX
        elif metrics.co2 > CO2_GOOD_MAX:
            penalty = (metrics.co2 - CO2_GOOD_MAX) * 0.05
            score -= min(15.0, penalty)
    
    return max(0.0, min(100.0, score))


class ZoneHealthStore:
    """In-memory store for zone health metrics.
    
    Thread-safe singleton that persists health snapshots.
    """
    
    _instance: Optional["ZoneHealthStore"] = None
    _lock = __import__("threading").Lock()
    
    def __init__(self):
        self._metrics: Dict[str, ZoneHealthMetrics] = {}
        self._history: List[Dict[str, Any]] = []  # Last N snapshots
        self._max_history = 100
    
    @classmethod
    def get_instance(cls) -> "ZoneHealthStore":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def update(self, zone_id: str, metrics: ZoneHealthMetrics) -> None:
        """Update metrics for a zone."""
        with self._lock:
            self._metrics[zone_id] = metrics
            self._history.append({
                "zone_id": zone_id,
                "timestamp": metrics.last_updated.isoformat(),
                "health_score": metrics.health_score,
            })
            # Trim history
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
    
    def get(self, zone_id: str) -> Optional[ZoneHealthMetrics]:
        """Get current metrics for a zone."""
        return self._metrics.get(zone_id)
    
    def get_all(self) -> Dict[str, ZoneHealthMetrics]:
        """Get all zone metrics."""
        with self._lock:
            return dict(self._metrics)
    
    def get_average_score(self) -> float:
        """Get average health score across all zones."""
        if not self._metrics:
            return 0.0
        return sum(m.health_score for m in self._metrics.values()) / len(self._metrics)
    
    def get_trend(self, zone_id: str, hours: int = 24) -> str:
        """Get health trend for a zone over N hours.
        
        Returns: "improving", "stable", "declining", or "unknown"
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        relevant = [
            h for h in self._history
            if h["zone_id"] == zone_id and datetime.fromisoformat(h["timestamp"]).timestamp() > cutoff
        ]
        if len(relevant) < 2:
            return "unknown"
        
        scores = [h["health_score"] for h in relevant]
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        delta = avg_second - avg_first
        if delta > 5:
            return "improving"
        elif delta < -5:
            return "declining"
        return "stable"


# Module state
_store = ZoneHealthStore.get_instance()


def get_store() -> ZoneHealthStore:
    """Get the zone health store."""
    return _store


__all__ = [
    "ZoneHealthMetrics",
    "ZoneHealthStore",
    "TEMP_COMFORT_MIN",
    "TEMP_COMFORT_MAX",
    "HUMIDITY_COMFORT_MIN",
    "HUMIDITY_COMFORT_MAX",
    "CO2_GOOD_MAX",
    "CO2_MODERATE_MAX",
    "get_store",
]
