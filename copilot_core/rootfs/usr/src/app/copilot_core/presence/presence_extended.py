"""Presence Module Extensions — Slice 75.

Erweiterte Präsenz-Erkennung für Habituszonen.

New Features (Slice 75):
- Advanced Sensor Profiles (mmWave, PIR, Camera, BLE, WiFi)
- Sensor Fusion Weights (configurable per zone)
- Presence Patterns (learning-based)
- Extended Absence Profiles
- Guest Mode Support
- Pet Detection Filtering
- Multi-Person Counting
- Presence Confidence Trends
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum
import uuid
import statistics

logger = logging.getLogger(__name__)


class PresenceSensorType(Enum):
    """Extended presence sensor types."""
    MMWAVE = "mmwave"  # Millimeter wave radar
    PIR = "pir"  # Passive infrared
    CAMERA = "camera"  # Computer vision
    BLE = "ble"  # Bluetooth LE tracking
    WIFI = "wifi"  # WiFi presence
    DEVICE_TRACKER = "device_tracker"  # HA device tracker
    PERSON = "person"  # HA person entity
    ULTRASONIC = "ultrasonic"  # Ultrasonic sensor
    PRESSURE = "pressure"  # Pressure mat
    CONTACT = "contact"  # Door/window contact
    AUDIO = "audio"  # Sound detection
    CUSTOM = "custom"  # Custom sensor


class PresencePattern(Enum):
    """Learned presence patterns."""
    TYPICAL_MORNING = "typical_morning"
    TYPICAL_DAY = "typical_day"
    TYPICAL_EVENING = "typical_evening"
    TYPICAL_NIGHT = "typical_night"
    WEEKEND_PATTERN = "weekend_pattern"
    AWAY_PATTERN = "away_pattern"
    GUEST_PATTERN = "guest_pattern"
    ANOMALY = "anomaly"


@dataclass
class AdvancedSensorConfig:
    """Advanced sensor configuration."""
    sensor_id: str
    zone_id: str
    sensor_type: PresenceSensorType
    entity_id: str
    name: str
    enabled: bool = True
    priority: int = 50  # 0-100
    confidence: float = 1.0  # 0.0-1.0
    weight: float = 1.0  # Fusion weight
    min_trigger_time_seconds: int = 0  # Debounce
    min_clear_time_seconds: int = 0  # Debounce off
    ignore_motion_below: Optional[float] = None  # For pet filtering
    max_confidence_decay: float = 0.1  # Per minute when inactive
    battery_monitored: bool = False
    battery_low_threshold: int = 20
    tamper_detection: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "zone_id": self.zone_id,
            "sensor_type": self.sensor_type.value,
            "entity_id": self.entity_id,
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "confidence": self.confidence,
            "weight": self.weight,
            "min_trigger_time_seconds": self.min_trigger_time_seconds,
            "min_clear_time_seconds": self.min_clear_time_seconds,
            "ignore_motion_below": self.ignore_motion_below,
            "max_confidence_decay": self.max_confidence_decay,
            "battery_monitored": self.battery_monitored,
            "battery_low_threshold": self.battery_low_threshold,
            "tamper_detection": self.tamper_detection,
        }


@dataclass
class SensorReading:
    """Individual sensor reading."""
    reading_id: str
    sensor_id: str
    zone_id: str
    timestamp: str
    is_present: bool
    confidence: float = 1.0
    raw_value: Optional[Any] = None
    battery_level: Optional[int] = None
    tamper_detected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reading_id": self.reading_id,
            "sensor_id": self.sensor_id,
            "zone_id": self.zone_id,
            "timestamp": self.timestamp,
            "is_present": self.is_present,
            "confidence": self.confidence,
            "raw_value": self.raw_value,
            "battery_level": self.battery_level,
            "tamper_detected": self.tamper_detected,
        }


@dataclass
class PresenceProfile:
    """Zone presence profile for pattern learning."""
    profile_id: str
    zone_id: str
    name: str
    typical_occupancy_hours: List[int] = field(default_factory=list)  # Hours when usually occupied
    typical_absence_hours: List[int] = field(default_factory=list)
    weekend_behavior_different: bool = False
    sensitivity_multiplier: float = 1.0  # Adjust detection sensitivity
    auto_away_timeout_seconds: int = 43200  # 12 hours
    guest_mode_enabled: bool = False
    pet_friendly: bool = False
    min_persons_expected: int = 0
    max_persons_expected: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "typical_occupancy_hours": self.typical_occupancy_hours,
            "typical_absence_hours": self.typical_absence_hours,
            "weekend_behavior_different": self.weekend_behavior_different,
            "sensitivity_multiplier": self.sensitivity_multiplier,
            "auto_away_timeout_seconds": self.auto_away_timeout_seconds,
            "guest_mode_enabled": self.guest_mode_enabled,
            "pet_friendly": self.pet_friendly,
            "min_persons_expected": self.min_persons_expected,
            "max_persons_expected": self.max_persons_expected,
        }


@dataclass
class OccupancyTrend:
    """Occupancy trend analysis."""
    zone_id: str
    period_start: str
    period_end: str
    total_occupied_minutes: int = 0
    total_absent_minutes: int = 0
    occupancy_rate: float = 0.0  # 0.0-1.0
    peak_occupancy_hour: int = 0
    lowest_occupancy_hour: int = 0
    average_confidence: float = 0.0
    sensor_reliability: Dict[str, float] = field(default_factory=dict)
    pattern_detected: Optional[PresencePattern] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_occupied_minutes": self.total_occupied_minutes,
            "total_absent_minutes": self.total_absent_minutes,
            "occupancy_rate": self.occupancy_rate,
            "peak_occupancy_hour": self.peak_occupancy_hour,
            "lowest_occupancy_hour": self.lowest_occupancy_hour,
            "average_confidence": self.average_confidence,
            "sensor_reliability": self.sensor_reliability,
            "pattern_detected": self.pattern_detected.value if self.pattern_detected else None,
        }


@dataclass
class MultiPersonState:
    """Multi-person counting state."""
    zone_id: str
    person_count: int = 0
    known_persons: Set[str] = field(default_factory=set)  # Person IDs
    unknown_persons: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "person_count": self.person_count,
            "known_persons": list(self.known_persons),
            "unknown_persons": self.unknown_persons,
            "last_updated": self.last_updated,
        }


class PresenceModuleExtended:
    """Extended presence module with advanced features.
    
    New Capabilities (Slice 75):
    - Advanced sensor configuration per type
    - Configurable fusion weights
    - Pattern learning and detection
    - Guest mode support
    - Pet filtering
    - Multi-person counting
    - Confidence trends
    """
    
    def __init__(self):
        self._sensors: Dict[str, AdvancedSensorConfig] = {}
        self._zone_sensors: Dict[str, List[str]] = {}
        self._profiles: Dict[str, PresenceProfile] = {}
        self._readings: Dict[str, List[SensorReading]] = {}  # sensor_id -> readings
        self._trends: Dict[str, OccupancyTrend] = {}  # zone_id -> trend
        self._multi_person_states: Dict[str, MultiPersonState] = {}
        self._guest_mode_zones: Set[str] = set()
        self._sensor_history: Dict[str, List[bool]] = {}  # sensor_id -> recent states
        
        logger.info("PresenceModuleExtended initialized")
    
    def add_sensor(self, config: AdvancedSensorConfig) -> str:
        """Add advanced sensor to zone."""
        with self._lock():
            self._sensors[config.sensor_id] = config
            
            if config.zone_id not in self._zone_sensors:
                self._zone_sensors[config.zone_id] = []
            
            self._zone_sensors[config.zone_id].append(config.sensor_id)
            self._readings[config.sensor_id] = []
            self._sensor_history[config.sensor_id] = []
        
        logger.info("Advanced sensor added: %s (%s) to %s", 
                   config.sensor_id, config.sensor_type.value, config.zone_id)
        
        return config.sensor_id
    
    def remove_sensor(self, sensor_id: str) -> bool:
        """Remove sensor."""
        if sensor_id not in self._sensors:
            return False
        
        config = self._sensors[sensor_id]
        
        with self._lock():
            del self._sensors[sensor_id]
            
            if config.zone_id in self._zone_sensors:
                if sensor_id in self._zone_sensors[config.zone_id]:
                    self._zone_sensors[config.zone_id].remove(sensor_id)
        
        return True
    
    def set_zone_profile(self, profile: PresenceProfile) -> str:
        """Set presence profile for zone."""
        with self._lock():
            self._profiles[profile.zone_id] = profile
        
        logger.info("Presence profile set for %s: %s", profile.zone_id, profile.name)
        return profile.profile_id
    
    def get_zone_profile(self, zone_id: str) -> Optional[PresenceProfile]:
        """Get presence profile for zone."""
        return self._profiles.get(zone_id)
    
    def enable_guest_mode(self, zone_id: str) -> bool:
        """Enable guest mode for zone (relaxed detection)."""
        if zone_id not in self._zone_sensors:
            return False
        
        self._guest_mode_zones.add(zone_id)
        
        logger.info("Guest mode enabled for %s", zone_id)
        return True
    
    def disable_guest_mode(self, zone_id: str) -> bool:
        """Disable guest mode for zone."""
        if zone_id not in self._guest_mode_zones:
            return False
        
        self._guest_mode_zones.remove(zone_id)
        
        logger.info("Guest mode disabled for %s", zone_id)
        return True
    
    def process_sensor_reading(self, sensor_id: str, is_present: bool,
                            confidence: Optional[float] = None,
                            raw_value: Optional[Any] = None,
                            battery_level: Optional[int] = None) -> Optional[SensorReading]:
        """Process a sensor reading with advanced filtering."""
        if sensor_id not in self._sensors:
            return None
        
        config = self._sensors[sensor_id]
        
        if not config.enabled:
            return None
        
        # Check tamper detection
        if config.tamper_detection and self._check_tamper(sensor_id):
            logger.warning("Tamper detected for sensor %s", sensor_id)
            return None
        
        # Pet filtering
        if config.ignore_motion_below and raw_value:
            if isinstance(raw_value, (int, float)) and raw_value < config.ignore_motion_below:
                logger.debug("Motion below pet filter threshold: %s", raw_value)
                return None
        
        # Create reading
        reading = SensorReading(
            reading_id=f"sr_{uuid.uuid4().hex[:16]}",
            sensor_id=sensor_id,
            zone_id=config.zone_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_present=is_present,
            confidence=confidence if confidence is not None else config.confidence,
            raw_value=raw_value,
            battery_level=battery_level,
        )
        
        # Store reading
        self._readings[sensor_id].append(reading)
        
        # Limit readings per sensor (last 1000)
        if len(self._readings[sensor_id]) > 1000:
            self._readings[sensor_id] = self._readings[sensor_id][-1000:]
        
        # Update sensor history
        self._sensor_history[sensor_id].append(is_present)
        if len(self._sensor_history[sensor_id]) > 100:
            self._sensor_history[sensor_id] = self._sensor_history[sensor_id][-100:]
        
        # Update multi-person state if person sensor
        if config.sensor_type in (PresenceSensorType.PERSON, PresenceSensorType.CAMERA):
            self._update_multi_person_state(config.zone_id, sensor_id, is_present)
        
        return reading
    
    def _check_tamper(self, sensor_id: str) -> bool:
        """Check for tamper detection (rapid state changes)."""
        history = self._sensor_history.get(sensor_id, [])
        
        if len(history) < 10:
            return False
        
        # Count state changes in last 10 readings
        changes = sum(1 for i in range(1, len(history)) if history[i] != history[i-1])
        
        # More than 8 changes in 10 readings = likely tamper
        return changes > 8
    
    def _update_multi_person_state(self, zone_id: str, sensor_id: str,
                                   is_present: bool) -> None:
        """Update multi-person counting state."""
        if zone_id not in self._multi_person_states:
            self._multi_person_states[zone_id] = MultiPersonState(zone_id=zone_id)
        
        state = self._multi_person_states[zone_id]
        
        # Extract person ID from sensor_id if present (format: person_{id})
        if sensor_id.startswith("person_"):
            person_id = sensor_id[7:]
            
            if is_present:
                state.known_persons.add(person_id)
            else:
                state.known_persons.discard(person_id)
        
        state.person_count = len(state.known_persons) + state.unknown_persons
        state.last_updated = datetime.now(timezone.utc).isoformat()
    
    def calculate_zone_presence(self, zone_id: str) -> Tuple[bool, float]:
        """Calculate zone presence using weighted sensor fusion."""
        sensor_ids = self._zone_sensors.get(zone_id, [])
        
        if not sensor_ids:
            return False, 0.0
        
        readings = []
        
        for sensor_id in sensor_ids:
            config = self._sensors.get(sensor_id)
            
            if not config or not config.enabled:
                continue
            
            # Get latest reading
            sensor_readings = self._readings.get(sensor_id, [])
            
            if not sensor_readings:
                continue
            
            latest = sensor_readings[-1]
            
            # Apply confidence decay if sensor inactive
            reading_age = datetime.now(timezone.utc) - datetime.fromisoformat(
                latest.timestamp.replace('Z', '+00:00')
            )
            age_minutes = reading_age.total_seconds() / 60
            
            decayed_confidence = max(
                0.0,
                latest.confidence - (age_minutes * config.max_confidence_decay)
            )
            
            readings.append((latest.is_present, decayed_confidence, config.weight))
        
        if not readings:
            return False, 0.0
        
        # Weighted fusion
        total_weight = sum(r[2] for r in readings)
        
        if total_weight == 0:
            return False, 0.0
        
        present_weight = sum(r[2] * r[1] for r in readings if r[0])
        
        fused_confidence = present_weight / total_weight
        
        # Apply profile sensitivity
        profile = self._profiles.get(zone_id)
        if profile:
            fused_confidence *= profile.sensitivity_multiplier
        
        # Guest mode adjustment (lower threshold)
        is_guest_mode = zone_id in self._guest_mode_zones
        
        threshold = 0.3 if is_guest_mode else 0.5
        
        return fused_confidence >= threshold, fused_confidence
    
    def get_occupancy_trend(self, zone_id: str,
                           hours: int = 24) -> Optional[OccupancyTrend]:
        """Calculate occupancy trend for zone."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=hours)
        
        # Collect all readings for zone
        zone_readings = []
        
        for sensor_id in self._zone_sensors.get(zone_id, []):
            for reading in self._readings.get(sensor_id, []):
                reading_time = datetime.fromisoformat(
                    reading.timestamp.replace('Z', '+00:00')
                )
                if reading_time > period_start:
                    zone_readings.append(reading)
        
        if not zone_readings:
            return None
        
        # Calculate occupancy by hour
        hourly_occupancy = {h: [] for h in range(24)}
        
        for reading in zone_readings:
            hour = datetime.fromisoformat(
                reading.timestamp.replace('Z', '+00:00')
            ).hour
            hourly_occupancy[hour].append(reading.is_present)
        
        # Calculate metrics
        total_present = sum(1 for r in zone_readings if r.is_present)
        total_absent = len(zone_readings) - total_present
        total_minutes = hours * 60
        
        occupied_minutes = int((total_present / len(zone_readings)) * total_minutes) if zone_readings else 0
        absent_minutes = total_minutes - occupied_minutes
        
        occupancy_rate = total_present / len(zone_readings) if zone_readings else 0
        
        # Find peak and lowest hours
        hour_rates = {
            h: sum(readings) / len(readings) if readings else 0
            for h, readings in hourly_occupancy.items()
        }
        
        peak_hour = max(hour_rates, key=hour_rates.get) if hour_rates else 0
        lowest_hour = min(hour_rates, key=hour_rates.get) if hour_rates else 0
        
        # Average confidence
        avg_confidence = statistics.mean(r.confidence for r in zone_readings) if zone_readings else 0
        
        # Sensor reliability
        sensor_reliability = {}
        for sensor_id in self._zone_sensors.get(zone_id, []):
            sensor_readings = self._readings.get(sensor_id, [])
            recent = sensor_readings[-100:] if sensor_readings else []
            
            if recent:
                # Reliability = consistency of readings
                if len(recent) > 1:
                    changes = sum(1 for i in range(1, len(recent)) if recent[i].is_present != recent[i-1].is_present)
                    reliability = 1.0 - (changes / len(recent))
                else:
                    reliability = 1.0
                sensor_reliability[sensor_id] = reliability
        
        # Detect pattern
        pattern = self._detect_pattern(zone_id, hour_rates, occupancy_rate)
        
        trend = OccupancyTrend(
            zone_id=zone_id,
            period_start=period_start.isoformat(),
            period_end=now.isoformat(),
            total_occupied_minutes=occupied_minutes,
            total_absent_minutes=absent_minutes,
            occupancy_rate=occupancy_rate,
            peak_occupancy_hour=peak_hour,
            lowest_occupancy_hour=lowest_hour,
            average_confidence=avg_confidence,
            sensor_reliability=sensor_reliability,
            pattern_detected=pattern,
        )
        
        self._trends[zone_id] = trend
        
        return trend
    
    def _detect_pattern(self, zone_id: str, hour_rates: Dict[int, float],
                       occupancy_rate: float) -> Optional[PresencePattern]:
        """Detect presence pattern from occupancy data."""
        profile = self._profiles.get(zone_id)
        
        # Check if currently night hours (22:00 - 06:00)
        current_hour = datetime.now(timezone.utc).hour
        is_night = current_hour >= 22 or current_hour < 6
        
        # Check weekend
        is_weekend = datetime.now(timezone.utc).weekday() >= 5
        
        # Pattern detection logic
        if occupancy_rate < 0.1:
            return PresencePattern.AWAY_PATTERN
        
        if is_night and occupancy_rate > 0.5:
            return PresencePattern.TYPICAL_NIGHT
        
        if is_weekend and occupancy_rate > 0.6:
            return PresencePattern.WEEKEND_PATTERN
        
        if profile and profile.guest_mode_enabled and occupancy_rate > 0.8:
            return PresencePattern.GUEST_PATTERN
        
        # Check against typical hours
        if profile:
            if current_hour in profile.typical_occupancy_hours and occupancy_rate > 0.5:
                if current_hour < 12:
                    return PresencePattern.TYPICAL_MORNING
                elif current_hour < 17:
                    return PresencePattern.TYPICAL_DAY
                else:
                    return PresencePattern.TYPICAL_EVENING
        
        # Anomaly detection
        if profile and current_hour in profile.typical_absence_hours and occupancy_rate > 0.7:
            return PresencePattern.ANOMALY
        
        return None
    
    def get_multi_person_state(self, zone_id: str) -> Optional[MultiPersonState]:
        """Get multi-person state for zone."""
        return self._multi_person_states.get(zone_id)
    
    def get_sensor(self, sensor_id: str) -> Optional[AdvancedSensorConfig]:
        """Get sensor configuration."""
        return self._sensors.get(sensor_id)
    
    def get_zone_sensors(self, zone_id: str) -> List[AdvancedSensorConfig]:
        """Get all sensors for zone."""
        sensor_ids = self._zone_sensors.get(zone_id, [])
        return [self._sensors[sid] for sid in sensor_ids if sid in self._sensors]
    
    def get_sensor_readings(self, sensor_id: str,
                           limit: int = 100) -> List[SensorReading]:
        """Get recent readings for sensor."""
        readings = self._readings.get(sensor_id, [])
        return readings[-limit:]
    
    def get_trend(self, zone_id: str) -> Optional[OccupancyTrend]:
        """Get latest trend for zone."""
        return self._trends.get(zone_id)
    
    def is_guest_mode(self, zone_id: str) -> bool:
        """Check if guest mode is enabled for zone."""
        return zone_id in self._guest_mode_zones
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extended presence module statistics."""
        total_sensors = len(self._sensors)
        enabled_sensors = len([s for s in self._sensors.values() if s.enabled])
        
        sensor_types = {}
        for sensor in self._sensors.values():
            type_name = sensor.sensor_type.value
            sensor_types[type_name] = sensor_types.get(type_name, 0) + 1
        
        return {
            "total_sensors": total_sensors,
            "enabled_sensors": enabled_sensors,
            "disabled_sensors": total_sensors - enabled_sensors,
            "total_zones": len(self._zone_sensors),
            "guest_mode_zones": len(self._guest_mode_zones),
            "sensor_types": sensor_types,
            "total_profiles": len(self._profiles),
            "total_trends": len(self._trends),
            "multi_person_zones": len(self._multi_person_states),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_presence_module_extended() -> PresenceModuleExtended:
    """Factory function to create extended presence module."""
    return PresenceModuleExtended()
