"""Zone Presence Module — Slice 70.

Zone-aware presence tracking with multi-sensor fusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class PresenceState(str, Enum):
    """Presence states."""
    PRESENT = "present"
    ABSENT = "absent"
    UNCERTAIN = "uncertain"
    EXTENDED_ABSENT = "extended_absent"


class PresenceSensorType(str, Enum):
    """Presence sensor types."""
    MMWAVE = "mmwave"
    PIR = "pir"
    DEVICE_TRACKER = "device_tracker"
    PERSON = "person"
    BLE = "ble"
    WIFI = "wifi"


@dataclass
class PresenceSensor:
    """Presence sensor configuration."""
    sensor_id: str
    zone_id: str
    sensor_type: PresenceSensorType
    name: str
    is_enabled: bool = True
    confidence_weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "zone_id": self.zone_id,
            "sensor_type": self.sensor_type.value,
            "name": self.name,
            "is_enabled": self.is_enabled,
            "confidence_weight": self.confidence_weight,
        }


@dataclass
class PresenceConfig:
    """Presence configuration for a zone."""
    zone_id: str
    auto_away_delay_seconds: int = 300
    extended_absent_threshold_hours: int = 24
    min_sensors_for_confidence: int = 2
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "auto_away_delay_seconds": self.auto_away_delay_seconds,
            "extended_absent_threshold_hours": self.extended_absent_threshold_hours,
            "min_sensors_for_confidence": self.min_sensors_for_confidence,
        }


@dataclass
class ZonePresenceState:
    """Current presence state for a zone."""
    zone_id: str
    state: PresenceState = PresenceState.ABSENT
    person_count: int = 0
    confidence: float = 0.0
    last_detected: Optional[datetime] = None
    sensors_active: int = 0
    hold_active: bool = False
    hold_until: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "state": self.state.value,
            "person_count": self.person_count,
            "confidence": self.confidence,
            "last_detected": self.last_detected.isoformat() if self.last_detected else None,
            "sensors_active": self.sensors_active,
            "hold_active": self.hold_active,
            "hold_until": self.hold_until.isoformat() if self.hold_until else None,
        }


@dataclass
class PresenceEvent:
    """Presence event."""
    event_id: str
    zone_id: str
    sensor_id: str
    event_type: str  # detected, cleared, hold_set, hold_cleared
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "zone_id": self.zone_id,
            "sensor_id": self.sensor_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
        }


@dataclass
class PresenceHistoryEntry:
    """Presence history entry."""
    zone_id: str
    state: PresenceState
    timestamp: datetime
    duration_seconds: int = 0
    person_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "person_count": self.person_count,
        }


class PresenceModule:
    """Presence management module."""
    
    def __init__(self):
        self._sensors: Dict[str, PresenceSensor] = {}
        self._configs: Dict[str, PresenceConfig] = {}
        self._states: Dict[str, ZonePresenceState] = {}
        self._events: List[PresenceEvent] = []
        self._history: List[PresenceHistoryEntry] = []
    
    def register_sensor(self, sensor: PresenceSensor) -> bool:
        """Register a presence sensor."""
        self._sensors[sensor.sensor_id] = sensor
        return True
    
    def get_sensor(self, sensor_id: str) -> Optional[PresenceSensor]:
        """Get sensor by ID."""
        return self._sensors.get(sensor_id)
    
    def set_config(self, config: PresenceConfig) -> bool:
        """Set configuration for a zone."""
        self._configs[config.zone_id] = config
        return True
    
    def get_config(self, zone_id: str) -> Optional[PresenceConfig]:
        """Get configuration for a zone."""
        return self._configs.get(zone_id)
    
    def update_state(self, state: ZonePresenceState) -> bool:
        """Update presence state for a zone."""
        self._states[state.zone_id] = state
        return True
    
    def get_state(self, zone_id: str) -> Optional[ZonePresenceState]:
        """Get presence state for a zone."""
        return self._states.get(zone_id)
    
    def record_event(self, event: PresenceEvent) -> bool:
        """Record a presence event."""
        self._events.append(event)
        return True
    
    def get_events(self, zone_id: Optional[str] = None, limit: int = 100) -> List[PresenceEvent]:
        """Get recent presence events."""
        events = self._events
        if zone_id:
            events = [e for e in events if e.zone_id == zone_id]
        return events[-limit:]


def create_presence_module() -> PresenceModule:
    """Factory function."""
    return PresenceModule()
