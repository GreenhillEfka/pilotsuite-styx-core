"""Multi-Sensor Fusion — Bayesian fusion of PIR, Radar, WiFi, BLE."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time

logger = logging.getLogger(__name__)


class SensorType(Enum):
    """Sensor types for presence detection."""
    PIR = "pir"  # Passive Infrared
    RADAR = "radar"  # mmWave radar
    WIFI = "wifi"  # WiFi fingerprinting
    BLE = "ble"  # Bluetooth Low Energy
    CAMERA = "camera"  # Visual detection
    AUDIO = "audio"  # Sound detection


@dataclass
class SensorReading:
    """Reading from a sensor."""
    sensor_type: SensorType
    sensor_id: str
    value: float  # 0.0-1.0 confidence
    timestamp: float = field(default_factory=lambda: time.time())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedPresence:
    """Fused presence detection result."""
    is_present: bool
    confidence: float
    sensor_contributions: Dict[str, float]
    timestamp: float = field(default_factory=lambda: time.time())


class MultiSensorFusion:
    """
    Bayesian multi-sensor fusion for presence detection.
    
    Combines multiple sensor types with weighted confidence:
    - PIR: Motion detection (fast, prone to false negatives)
    - Radar: Micro-motion (accurate, always-on)
    - WiFi: Device fingerprinting (good for multi-person)
    - BLE: Proximity (high accuracy when available)
    """

    def __init__(self):
        self._sensor_weights: Dict[SensorType, float] = {
            SensorType.PIR: 0.6,
            SensorType.RADAR: 0.9,
            SensorType.WIFI: 0.7,
            SensorType.BLE: 0.8,
            SensorType.CAMERA: 0.95,
            SensorType.AUDIO: 0.5,
        }
        self._recent_readings: List[SensorReading] = []
        self._presence_history: List[FusedPresence] = []
        self._decay_rate = 0.1  # Confidence decay per second

    def add_reading(self, reading: SensorReading):
        """Add sensor reading."""
        self._recent_readings.append(reading)
        
        # Keep last 60 seconds
        cutoff = time.time() - 60.0
        self._recent_readings = [r for r in self._recent_readings if r.timestamp >= cutoff]

    def fuse(self) -> FusedPresence:
        """Fuse recent sensor readings into presence decision."""
        if not self._recent_readings:
            return FusedPresence(
                is_present=False,
                confidence=0.0,
                sensor_contributions={},
            )
        
        # Group by sensor type
        by_type: Dict[SensorType, List[SensorReading]] = {}
        for reading in self._recent_readings:
            if reading.sensor_type not in by_type:
                by_type[reading.sensor_type] = []
            by_type[reading.sensor_type].append(reading)
        
        # Calculate weighted confidence per sensor type
        type_confidences = {}
        for sensor_type, readings in by_type.items():
            # Average reading value
            avg_value = sum(r.value for r in readings) / len(readings)
            # Apply time decay
            newest = max(r.timestamp for r in readings)
            age_seconds = time.time() - newest
            decay = math.exp(-self._decay_rate * age_seconds)
            # Weighted confidence
            weight = self._sensor_weights[sensor_type]
            type_confidences[sensor_type.value] = avg_value * weight * decay
        
        # Bayesian fusion: P(present|sensors) = 1 - P(not present|all sensors)
        # Assuming independence: P(not present|all) = ∏(1 - p_i)
        p_not_present = 1.0
        for conf in type_confidences.values():
            p_not_present *= (1.0 - conf)
        
        fused_confidence = 1.0 - p_not_present
        is_present = fused_confidence > 0.5
        
        result = FusedPresence(
            is_present=is_present,
            confidence=fused_confidence,
            sensor_contributions=type_confidences,
        )
        
        self._presence_history.append(result)
        logger.info(f"Fused presence: {is_present} (conf: {fused_confidence:.2f})")
        
        return result

    def get_presence_probability(self) -> float:
        """Get current presence probability."""
        result = self.fuse()
        return result.confidence

    def get_sensor_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all sensors."""
        health = {}
        for sensor_type in SensorType:
            readings = [r for r in self._recent_readings if r.sensor_type == sensor_type]
            if readings:
                health[sensor_type.value] = {
                    "reading_count": len(readings),
                    "avg_confidence": sum(r.value for r in readings) / len(readings),
                    "last_reading": max(r.timestamp for r in readings),
                    "weight": self._sensor_weights[sensor_type],
                }
            else:
                health[sensor_type.value] = {
                    "reading_count": 0,
                    "status": "no_data",
                }
        return health

    def calibrate_sensor(self, sensor_type: SensorType, new_weight: float):
        """Recalibrate sensor weight."""
        if 0.0 <= new_weight <= 1.0:
            self._sensor_weights[sensor_type] = new_weight
            logger.info(f"Sensor {sensor_type.value} weight: {new_weight}")

    def get_stats(self) -> Dict[str, Any]:
        """Get fusion statistics."""
        return {
            "recent_readings": len(self._recent_readings),
            "presence_events": len(self._presence_history),
            "sensor_types_active": len(set(r.sensor_type for r in self._recent_readings)),
            "last_presence": self._presence_history[-1].is_present if self._presence_history else None,
        }


import math

# Global default fusion engine
default_sensor_fusion: Optional[MultiSensorFusion] = None


def init_multi_sensor_fusion() -> MultiSensorFusion:
    """Initialize global multi-sensor fusion."""
    global default_sensor_fusion
    default_sensor_fusion = MultiSensorFusion()
    return default_sensor_fusion
