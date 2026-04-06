"""Zone-Aware Presence Module — Slice 70.

Präsenzerkennung pro Habituszone mit Timer/Timeout.

Features:
- Multi-Sensor Fusion (mmWave, PIR, Device Tracker, Person)
- Zone Presence State (present, absent, uncertain)
- Presence Timer (on-delay, off-delay)
- Absence Timeout
- Confidence Scoring
- Presence History
- Zone Occupancy Events
- Slice 40: Zone Presence Hold Integration
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import math
import threading
import uuid

logger = logging.getLogger(__name__)

# Slice 40: Import hold state for integration
try:
    from copilot_core.core.zone_presence_hold import ZoneHoldState, get_zone_presence_hold_store
    HOLD_INTEGRATION_AVAILABLE = True
except ImportError:
    # Fallback for environments without hold module
    class ZoneHoldState(Enum):  # type: ignore
        AUTO = "auto"
        FORCE_ON = "force_on"
        FORCE_OFF = "force_off"
    
    def get_zone_presence_hold_store():  # type: ignore
        return None
    
    HOLD_INTEGRATION_AVAILABLE = False


class PresenceState(Enum):
    """Presence states."""
    PRESENT = "present"
    ABSENT = "absent"
    UNCERTAIN = "uncertain"
    EXTENDED_ABSENT = "extended_absent"  # Long-term absence


class PresenceSensorType(Enum):
    """Presence sensor types."""
    MMWAVE = "mmwave"  # High accuracy, static detection
    PIR = "pir"  # Motion only
    DEVICE_TRACKER = "device_tracker"  # Phone BT/WiFi
    PERSON = "person"  # HA person entity
    CAMERA = "camera"  # Vision-based
    CUSTOM = "custom"


@dataclass
class PresenceSensor:
    """Presence sensor configuration."""
    sensor_id: str
    zone_id: str
    sensor_type: PresenceSensorType
    entity_id: str
    name: str
    enabled: bool = True
    priority: int = 50  # 0-100, higher = more weight
    confidence: float = 1.0  # Sensor reliability
    last_trigger: Optional[str] = None
    
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
            "last_trigger": self.last_trigger,
        }


@dataclass
class PresenceConfig:
    """Presence configuration for a zone."""
    zone_id: str
    on_delay_seconds: int = 0  # Delay before marking present
    off_delay_seconds: int = 300  # Delay before marking absent (5 min default)
    extended_absence_threshold_seconds: int = 86400  # 24 hours
    require_multiple_sensors: bool = False  # Need 2+ sensors for present
    min_confidence_threshold: float = 0.5  # Min confidence for present
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "on_delay_seconds": self.on_delay_seconds,
            "off_delay_seconds": self.off_delay_seconds,
            "extended_absence_threshold_seconds": self.extended_absence_threshold_seconds,
            "require_multiple_sensors": self.require_multiple_sensors,
            "min_confidence_threshold": self.min_confidence_threshold,
        }


@dataclass
class ZonePresenceState:
    """Current presence state for a zone."""
    zone_id: str
    state: PresenceState
    confidence: float
    active_sensors: List[str]  # Sensor IDs currently triggered
    inactive_sensors: List[str]  # Sensor IDs not triggered
    present_since: Optional[str] = None
    absent_since: Optional[str] = None
    last_motion: Optional[str] = None
    last_update: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "state": self.state.value,
            "confidence": self.confidence,
            "active_sensors": self.active_sensors,
            "inactive_sensors": self.inactive_sensors,
            "present_since": self.present_since,
            "absent_since": self.absent_since,
            "last_motion": self.last_motion,
            "last_update": self.last_update,
        }


@dataclass
class PresenceEvent:
    """Presence change event."""
    event_id: str
    zone_id: str
    event_type: str  # "present", "absent", "uncertain", "extended_absent"
    previous_state: PresenceState
    new_state: PresenceState
    confidence: float
    triggered_by: List[str]  # Sensor IDs
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "zone_id": self.zone_id,
            "event_type": self.event_type,
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "confidence": self.confidence,
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp,
        }


@dataclass
class PresenceHistoryEntry:
    """Presence history entry."""
    timestamp: str
    zone_id: str
    state: PresenceState
    confidence: float
    active_sensor_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "zone_id": self.zone_id,
            "state": self.state.value,
            "confidence": self.confidence,
            "active_sensor_count": self.active_sensor_count,
        }


class PresenceModule:
    """Zone-aware presence detection module.
    
    Architecture:
        Normalized States → Sensor Fusion → Timer Logic → Zone Presence State
    
    Usage:
        module = PresenceModule()
        module.add_sensor(sensor_config)
        module.set_zone_config(zone_id, config)
        module.update_sensor_state(sensor_id, is_present)
        presence = module.get_zone_presence(zone_id)
    """
    
    def __init__(self):
        self._thread_lock = threading.RLock()
        self._sensors: Dict[str, PresenceSensor] = {}
        self._zone_sensors: Dict[str, List[str]] = {}  # zone_id -> sensor_ids
        self._zone_configs: Dict[str, PresenceConfig] = {}
        self._zone_states: Dict[str, ZonePresenceState] = {}
        self._sensor_states: Dict[str, bool] = {}  # sensor_id -> is_present
        self._sensor_timers: Dict[str, datetime] = {}  # sensor_id -> last_trigger_time
        self._zone_timers: Dict[str, datetime] = {}  # zone_id -> state_change_time
        self._presence_events: Dict[str, List[PresenceEvent]] = {}  # zone_id -> events
        self._presence_history: Dict[str, List[PresenceHistoryEntry]] = {}  # zone_id -> history
        
        logger.info("PresenceModule initialized")
    
    def add_sensor(self, sensor: PresenceSensor) -> str:
        """Add a presence sensor."""
        with self._lock():
            self._sensors[sensor.sensor_id] = sensor
            
            if sensor.zone_id not in self._zone_sensors:
                self._zone_sensors[sensor.zone_id] = []
            
            self._zone_sensors[sensor.zone_id].append(sensor.sensor_id)
            
            # Initialize sensor state
            self._sensor_states[sensor.sensor_id] = False
            
            # Initialize zone state if needed
            if sensor.zone_id not in self._zone_states:
                self._zone_states[sensor.zone_id] = ZonePresenceState(
                    zone_id=sensor.zone_id,
                    state=PresenceState.ABSENT,
                    confidence=1.0,
                    active_sensors=[],
                    inactive_sensors=[sensor.sensor_id],
                )
        
        logger.info("Sensor added: %s (%s) to %s", sensor.name, sensor.sensor_type.value, sensor.zone_id)
        
        return sensor.sensor_id
    
    def remove_sensor(self, sensor_id: str) -> bool:
        """Remove a presence sensor."""
        if sensor_id not in self._sensors:
            return False
        
        sensor = self._sensors[sensor_id]
        
        with self._lock():
            del self._sensors[sensor_id]
            
            if sensor.zone_id in self._zone_sensors:
                if sensor_id in self._zone_sensors[sensor.zone_id]:
                    self._zone_sensors[sensor.zone_id].remove(sensor_id)
            
            if sensor_id in self._sensor_states:
                del self._sensor_states[sensor_id]
        
        return True
    
    def set_zone_config(self, zone_id: str, config: PresenceConfig) -> bool:
        """Set presence configuration for a zone."""
        with self._lock():
            self._zone_configs[zone_id] = config
        return True
    
    def get_zone_config(self, zone_id: str) -> Optional[PresenceConfig]:
        """Get presence configuration for a zone."""
        return self._zone_configs.get(zone_id)
    
    def update_sensor_state(self, sensor_id: str, is_present: bool,
                           confidence: Optional[float] = None) -> Optional[PresenceEvent]:
        """Update state for a presence sensor."""
        sensor = self._sensors.get(sensor_id)
        
        if not sensor or not sensor.enabled:
            return None
        
        now = datetime.now(timezone.utc)
        
        with self._lock():
            # Update sensor state
            self._sensor_states[sensor_id] = is_present
            
            if is_present:
                sensor.last_trigger = now.isoformat()
                self._sensor_timers[sensor_id] = now
            
            # Update zone state
            event = self._update_zone_state(sensor.zone_id, now)
        
        return event
    
    def _update_zone_state(self, zone_id: str, now: datetime) -> Optional[PresenceEvent]:
        """Update zone presence state based on sensor states."""
        config = self._zone_configs.get(zone_id)
        
        if not config:
            config = PresenceConfig(zone_id=zone_id)
        
        zone_sensors = self._zone_sensors.get(zone_id, [])
        
        if not zone_sensors:
            return None
        
        # Count active sensors and calculate weighted confidence
        active_sensors = []
        inactive_sensors = []
        weighted_confidence = 0.0
        total_weight = 0
        
        # Build sensor readings for Bayesian inference
        sensor_readings = {}
        
        for sensor_id in zone_sensors:
            sensor = self._sensors.get(sensor_id)
            
            if not sensor:
                continue
            
            is_present = self._sensor_states.get(sensor_id, False)
            sensor_readings[sensor_id] = (is_present, sensor.sensor_type.value if hasattr(sensor.sensor_type, 'value') else sensor.sensor_type, sensor.confidence)
            
            if is_present:
                active_sensors.append(sensor_id)
                weighted_confidence += sensor.confidence * sensor.priority
            else:
                inactive_sensors.append(sensor_id)
            
            total_weight += sensor.priority
        
        # Bayesian presence probability (P1-001)
        confidence, evidence_strength = bayesian_presence_probability(sensor_readings)
        
        # Fallback if Bayesian returns 0
        if confidence == 0.0 and total_weight > 0:
            confidence = weighted_confidence / total_weight
        
        # Get previous state
        previous_state = self._zone_states[zone_id].state if zone_id in self._zone_states else PresenceState.ABSENT
        
        # Determine new state based on config (returns tuple of state + confidence)
        new_state, effective_confidence = self._determine_state(
            zone_id, active_sensors, inactive_sensors, confidence, config, now,
        )
        
        # Use effective_confidence when hold-enforced, otherwise use sensor-based confidence
        final_confidence = effective_confidence if effective_confidence == 1.0 else confidence
        
        # Create event if state changed
        event = None
        
        if new_state != previous_state:
            event = self._create_presence_event(
                zone_id, previous_state, new_state, confidence, active_sensors, now,
            )
            
            self._zone_timers[zone_id] = now
        
        # Update zone state
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            zone_state = ZonePresenceState(
                zone_id=zone_id,
                state=new_state,
                confidence=confidence,
                active_sensors=[],
                inactive_sensors=[],
            )
            self._zone_states[zone_id] = zone_state
        
        zone_state.state = new_state
        zone_state.confidence = final_confidence
        zone_state.active_sensors = active_sensors.copy()
        zone_state.inactive_sensors = inactive_sensors.copy()
        zone_state.last_update = now.isoformat()
        
        # Update present/absent timestamps
        if new_state == PresenceState.PRESENT:
            if previous_state != PresenceState.PRESENT:
                zone_state.present_since = now.isoformat()
            zone_state.absent_since = None
        elif new_state in (PresenceState.ABSENT, PresenceState.EXTENDED_ABSENT):
            if previous_state not in (PresenceState.ABSENT, PresenceState.EXTENDED_ABSENT):
                zone_state.absent_since = now.isoformat()
            elif not zone_state.absent_since:
                zone_state.absent_since = now.isoformat()
            zone_state.present_since = None
        
        # Update last motion
        if active_sensors:
            zone_state.last_motion = now.isoformat()
        
        # Record history
        self._record_history(zone_id, zone_state, now)
        
        return event
    
    def _determine_state(self, zone_id: str, active_sensors: List[str],
                        inactive_sensors: List[str], sensor_confidence: float,
                        config: PresenceConfig, now: datetime) -> Tuple[PresenceState, float]:
        """Determine presence state based on sensors and config.
        
        Slice 40: Checks ZonePresenceHold state first before applying sensor logic.
        Hold states (FORCE_ON/FORCE_OFF) override sensor-based detection.
        
        Returns:
            Tuple[PresenceState, float]: (state, confidence) — confidence is 1.0 when hold-enforced,
                                         otherwise returns sensor_confidence for normal logic paths
        """
        # Slice 40: Check hold state first — holds override sensor logic
        hold_state = self._get_effective_hold_state(zone_id)
        if hold_state == ZoneHoldState.FORCE_ON:
            return PresenceState.PRESENT, 1.0
        elif hold_state == ZoneHoldState.FORCE_OFF:
            return PresenceState.ABSENT, 1.0
        # hold_state == AUTO: continue with normal sensor-based detection
        
        # Check for extended absence
        zone_state = self._zone_states.get(zone_id)
        
        if zone_state and zone_state.absent_since:
            absent_time = datetime.fromisoformat(zone_state.absent_since.replace('Z', '+00:00'))
            absent_duration = (now - absent_time).total_seconds()
            
            if absent_duration >= config.extended_absence_threshold_seconds:
                return PresenceState.EXTENDED_ABSENT, sensor_confidence
        
        # Check on-delay
        if active_sensors and config.on_delay_seconds > 0:
            # Check if any sensor has been active for on_delay
            for sensor_id in active_sensors:
                if sensor_id in self._sensor_timers:
                    trigger_time = self._sensor_timers[sensor_id]
                    if (now - trigger_time).total_seconds() >= config.on_delay_seconds:
                        return PresenceState.PRESENT, sensor_confidence
            return PresenceState.UNCERTAIN, sensor_confidence
        
        # Check off-delay
        if not active_sensors and config.off_delay_seconds > 0:
            # Check if all sensors have been inactive for off_delay
            all_inactive_long_enough = True
            
            for sensor_id in inactive_sensors:
                if sensor_id in self._sensor_timers:
                    trigger_time = self._sensor_timers[sensor_id]
                    if (now - trigger_time).total_seconds() < config.off_delay_seconds:
                        all_inactive_long_enough = False
                        break
            
            if not all_inactive_long_enough:
                return PresenceState.UNCERTAIN, sensor_confidence

        # Check require_multiple_sensors only when presence is otherwise active.
        if active_sensors and config.require_multiple_sensors and len(active_sensors) < 2:
            return PresenceState.ABSENT, sensor_confidence

        # Confidence threshold only applies to active detections. When a zone
        # has no active sensors, off-delay / extended-absence semantics must be
        # able to yield UNCERTAIN or EXTENDED_ABSENT instead of short-circuiting
        # to ABSENT due to 0.0 confidence.
        if active_sensors and sensor_confidence < config.min_confidence_threshold:
            return PresenceState.ABSENT, sensor_confidence
        
        # Normal presence detection
        if active_sensors:
            return PresenceState.PRESENT, sensor_confidence
        else:
            return PresenceState.ABSENT, sensor_confidence
    
    def _create_presence_event(self, zone_id: str, previous_state: PresenceState,
                               new_state: PresenceState, confidence: float,
                               triggered_sensors: List[str],
                               now: datetime) -> PresenceEvent:
        """Create presence change event."""
        event_id = f"pevt_{uuid.uuid4().hex[:16]}"
        
        event_type_map = {
            PresenceState.PRESENT: "present",
            PresenceState.ABSENT: "absent",
            PresenceState.UNCERTAIN: "uncertain",
            PresenceState.EXTENDED_ABSENT: "extended_absent",
        }
        
        event = PresenceEvent(
            event_id=event_id,
            zone_id=zone_id,
            event_type=event_type_map[new_state],
            previous_state=previous_state,
            new_state=new_state,
            confidence=confidence,
            triggered_by=triggered_sensors.copy(),
            timestamp=now.isoformat(),
        )
        
        # Store event
        if zone_id not in self._presence_events:
            self._presence_events[zone_id] = []
        
        self._presence_events[zone_id].append(event)
        
        # Limit events (last 100 per zone)
        if len(self._presence_events[zone_id]) > 100:
            self._presence_events[zone_id] = self._presence_events[zone_id][-100:]
        
        logger.info("Presence event: %s → %s in %s", previous_state.value, new_state.value, zone_id)
        
        return event
    
    def _record_history(self, zone_id: str, zone_state: ZonePresenceState,
                       now: datetime) -> None:
        """Record presence state to history."""
        if zone_id not in self._presence_history:
            self._presence_history[zone_id] = []
        
        entry = PresenceHistoryEntry(
            timestamp=now.isoformat(),
            zone_id=zone_id,
            state=zone_state.state,
            confidence=zone_state.confidence,
            active_sensor_count=len(zone_state.active_sensors),
        )
        
        self._presence_history[zone_id].append(entry)
        
        # Limit history (last 1000 per zone)
        if len(self._presence_history[zone_id]) > 1000:
            self._presence_history[zone_id] = self._presence_history[zone_id][-1000:]
    
    def get_zone_presence(self, zone_id: str) -> Optional[ZonePresenceState]:
        """Get current presence state for a zone.
        
        Slice 40: Applies hold state at read time so hold changes are immediately visible
        without requiring a sensor update.
        """
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            return None
        
        # Slice 40: Apply hold state at read time
        hold_state = self._get_effective_hold_state(zone_id)
        
        if hold_state == ZoneHoldState.FORCE_ON:
            # Return a modified state showing PRESENT with hold-enforced confidence
            return ZonePresenceState(
                zone_id=zone_id,
                state=PresenceState.PRESENT,
                confidence=1.0,
                active_sensors=zone_state.active_sensors.copy(),
                inactive_sensors=zone_state.inactive_sensors.copy(),
                present_since=zone_state.present_since,
                absent_since=None,
                last_motion=zone_state.last_motion,
                last_update=datetime.now(timezone.utc).isoformat(),
            )
        elif hold_state == ZoneHoldState.FORCE_OFF:
            # Return a modified state showing ABSENT with hold-enforced confidence
            return ZonePresenceState(
                zone_id=zone_id,
                state=PresenceState.ABSENT,
                confidence=1.0,
                active_sensors=zone_state.active_sensors.copy(),
                inactive_sensors=zone_state.inactive_sensors.copy(),
                present_since=None,
                absent_since=zone_state.absent_since,
                last_motion=zone_state.last_motion,
                last_update=datetime.now(timezone.utc).isoformat(),
            )
        
        # AUTO: return sensor-based state as-is
        return zone_state
    
    def get_all_zone_presence(self) -> Dict[str, ZonePresenceState]:
        """Get presence states for all zones."""
        return self._zone_states.copy()
    
    def get_sensor(self, sensor_id: str) -> Optional[PresenceSensor]:
        """Get sensor by ID."""
        return self._sensors.get(sensor_id)
    
    def get_zone_sensors(self, zone_id: str) -> List[PresenceSensor]:
        """Get all sensors for a zone."""
        sensor_ids = self._zone_sensors.get(zone_id, [])
        return [self._sensors[sid] for sid in sensor_ids if sid in self._sensors]
    
    def get_presence_events(self, zone_id: str,
                           limit: int = 50) -> List[PresenceEvent]:
        """Get presence events for a zone."""
        events = self._presence_events.get(zone_id, [])
        return events[-limit:]
    
    def get_presence_history(self, zone_id: str,
                            hours: int = 24,
                            limit: int = 100) -> List[PresenceHistoryEntry]:
        """Get presence history for a zone."""
        if zone_id not in self._presence_history:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        history = self._presence_history[zone_id]
        
        # Filter by time
        filtered = [
            entry for entry in history
            if datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00')) > cutoff
        ]
        
        return filtered[-limit:]
    
    def get_occupancy_duration(self, zone_id: str) -> Optional[float]:
        """Get current occupancy duration in seconds."""
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state or zone_state.state != PresenceState.PRESENT:
            return None
        
        if not zone_state.present_since:
            return None
        
        present_time = datetime.fromisoformat(zone_state.present_since.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        return (now - present_time).total_seconds()
    
    def get_absence_duration(self, zone_id: str) -> Optional[float]:
        """Get current absence duration in seconds."""
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state or zone_state.state not in (PresenceState.ABSENT, PresenceState.EXTENDED_ABSENT):
            return None
        
        if not zone_state.absent_since:
            return None
        
        absent_time = datetime.fromisoformat(zone_state.absent_since.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        return (now - absent_time).total_seconds()
    
    def is_present(self, zone_id: str) -> bool:
        """Check if zone is currently present."""
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            return False
        
        return zone_state.state == PresenceState.PRESENT
    
    def is_absent(self, zone_id: str) -> bool:
        """Check if zone is currently absent."""
        zone_state = self._zone_states.get(zone_id)
        
        if not zone_state:
            return False
        
        return zone_state.state in (PresenceState.ABSENT, PresenceState.EXTENDED_ABSENT)
    
    def enable_sensor(self, sensor_id: str) -> bool:
        """Enable a sensor."""
        sensor = self._sensors.get(sensor_id)
        
        if not sensor:
            return False
        
        sensor.enabled = True
        
        return True
    
    def disable_sensor(self, sensor_id: str) -> bool:
        """Disable a sensor."""
        sensor = self._sensors.get(sensor_id)
        
        if not sensor:
            return False
        
        sensor.enabled = False
        
        return True
    
    def set_sensor_priority(self, sensor_id: str, priority: int) -> bool:
        """Set sensor priority."""
        sensor = self._sensors.get(sensor_id)
        
        if not sensor:
            return False
        
        sensor.priority = max(0, min(100, priority))
        
        return True
    
    def set_sensor_confidence(self, sensor_id: str, confidence: float) -> bool:
        """Set sensor confidence."""
        sensor = self._sensors.get(sensor_id)
        
        if not sensor:
            return False
        
        sensor.confidence = max(0.0, min(1.0, confidence))
        
        return True
    
    def reset_zone(self, zone_id: str) -> bool:
        """Reset zone presence state."""
        if zone_id not in self._zone_states:
            return False
        
        zone_state = self._zone_states[zone_id]
        
        zone_state.state = PresenceState.ABSENT
        zone_state.confidence = 1.0
        zone_state.active_sensors = []
        zone_state.present_since = None
        zone_state.absent_since = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get presence module statistics."""
        total_sensors = len(self._sensors)
        enabled_sensors = len([s for s in self._sensors.values() if s.enabled])
        present_zones = len([z for z in self._zone_states.values() if z.state == PresenceState.PRESENT])
        absent_zones = len([z for z in self._zone_states.values() if z.state in (PresenceState.ABSENT, PresenceState.EXTENDED_ABSENT)])
        
        return {
            "total_sensors": total_sensors,
            "enabled_sensors": enabled_sensors,
            "disabled_sensors": total_sensors - enabled_sensors,
            "total_zones": len(self._zone_states),
            "present_zones": present_zones,
            "absent_zones": absent_zones,
            "uncertain_zones": len([z for z in self._zone_states.values() if z.state == PresenceState.UNCERTAIN]),
            "total_events": sum(len(e) for e in self._presence_events.values()),
            "total_history_entries": sum(len(h) for h in self._presence_history.values()),
        }
    
    def _get_effective_hold_state(self, zone_id: str) -> ZoneHoldState:
        """Slice 40: Get effective hold state for a zone.
        
        Returns ZoneHoldState.FORCE_ON, FORCE_OFF, or AUTO based on
        active hold records. Hold states override sensor-based detection.
        
        Returns:
            ZoneHoldState: Current effective hold state (AUTO if no hold or hold integration unavailable)
        """
        if not HOLD_INTEGRATION_AVAILABLE:
            return ZoneHoldState.AUTO
        
        try:
            store = get_zone_presence_hold_store()
            if store is None:
                return ZoneHoldState.AUTO
            
            hold_state = store.get_active_hold_state(zone_id)
            return hold_state
        except Exception:
            # Graceful degradation: if hold store fails, fall back to AUTO
            logger.warning("Failed to get hold state for zone %s, defaulting to AUTO", zone_id)
            return ZoneHoldState.AUTO
    
    def get_hold_state(self, zone_id: str) -> str:
        """Slice 40: Get human-readable hold state for a zone.
        
        Returns:
            str: 'force_on', 'force_off', or 'auto'
        """
        hold_state = self._get_effective_hold_state(zone_id)
        return hold_state.value
    
    def is_hold_enforced(self, zone_id: str) -> bool:
        """Slice 40: Check if hold is currently enforced for a zone.
        
        Returns:
            bool: True if hold state is FORCE_ON or FORCE_OFF
        """
        hold_state = self._get_effective_hold_state(zone_id)
        return hold_state in (ZoneHoldState.FORCE_ON, ZoneHoldState.FORCE_OFF)
    
    def get_summary(self) -> Dict[str, Any]:
        """Slice 136: Return module summary for Backend-UI read model.
        
        Design Contract: summary, detailed_states, active_features, anomalies
        """
        now = datetime.now(timezone.utc)
        
        # Build detailed states for all zones
        detailed_states = []
        for zone_id, zone_state in self._zone_states.items():
            detailed_states.append({
                "entity_id": f"presence.{zone_id}",
                "state": zone_state.state.value,
                "attributes": {
                    "confidence": zone_state.confidence,
                    "last_changed": zone_state.last_changed.isoformat() if zone_state.last_changed else None,
                    "active_sensors": zone_state.active_sensors,
                    "hold_state": self.get_hold_state(zone_id),
                    "is_hold_enforced": self.is_hold_enforced(zone_id),
                }
            })
        
        # Count present zones
        present_count = sum(
            1 for zs in self._zone_states.values()
            if zs.state == PresenceState.PRESENT
        )
        
        return {
            "summary": f"{present_count}/{len(self._zone_states)} zones occupied",
            "detailed_states": detailed_states,
            "active_features": ["Multi-Sensor Fusion", "Zone Timers", "Hold Integration"],
            "anomalies": [],  # Could be populated with low-confidence detections
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        return self._thread_lock


def create_presence_module() -> PresenceModule:
    """Factory function to create presence module."""
    return PresenceModule()


class ZonePresenceEngine:
    """Compatibility facade for legacy integration tests.

    Keeps the richer ``PresenceModule`` intact but restores the small event-driven
    surface expected by Slice 67-82 integration tests.
    """

    def __init__(self, event_bus: Any = None, zone_registry: Any = None):
        self.event_bus = event_bus
        self.zone_registry = zone_registry
        self._occupants: Dict[str, Set[str]] = {}

    def _zone_exists(self, zone_id: str) -> bool:
        if not self.zone_registry or not hasattr(self.zone_registry, "get_zone"):
            return True
        return self.zone_registry.get_zone(zone_id) is not None

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if self.event_bus and hasattr(self.event_bus, "publish"):
            self.event_bus.publish(topic, payload)

    def _emit(self, topic: str, payload: Dict[str, Any]) -> None:
        if self.event_bus and hasattr(self.event_bus, "emit"):
            self.event_bus.emit(topic, payload)

    def on_person_entered(self, zone_id: str, person_id: str) -> None:
        if not self._zone_exists(zone_id):
            self._publish("presence_error", {
                "zone_id": zone_id,
                "person_id": person_id,
                "error": "unknown_zone",
            })
            return

        occupants = self._occupants.setdefault(zone_id, set())
        occupants.add(person_id)

        payload = {
            "zone_id": zone_id,
            "person_id": person_id,
            "occupancy": len(occupants),
            "state": "occupied",
        }
        self._emit("zone_state_updated", payload)
        self._publish("light_automation", {**payload, "action": "turn_on"})
        self._publish("climate_presence_sync", {**payload, "mode": "comfort"})

    def on_person_left(self, zone_id: str, person_id: str) -> None:
        occupants = self._occupants.setdefault(zone_id, set())
        occupants.discard(person_id)
        occupied = bool(occupants)
        payload = {
            "zone_id": zone_id,
            "person_id": person_id,
            "occupancy": len(occupants),
            "state": "occupied" if occupied else "vacant",
        }
        self._emit("zone_state_updated", payload)

        if occupied:
            self._publish("presence_update", payload)
            return

        self._publish("cleanup", {**payload, "action": "cleanup"})
        self._publish("light_cleanup", {**payload, "action": "turn_off"})
        self._publish("climate_eco", {**payload, "mode": "eco"})
        self._publish("energy_optimization", {**payload, "profile": "away"})


SENSOR_TYPE_PRIORS = {
    "mmwave": (8.0, 2.0), "pir": (3.0, 4.0), "device_tracker": (4.0, 5.0),
    "person": (6.0, 2.0), "camera": (5.0, 3.0), "custom": (2.0, 3.0),
}

def bayesian_presence_probability(sensor_readings):
    """Bayesian P(present) via Beta-Binomial conjugate model.
    
    Prior: historical base rate per sensor type (Beta distribution).
    Likelihood: sensor triggered/confirmed.
    Confidence: scales alpha of prior (reliability weight).
    """
    if not sensor_readings: return 0.0, "none"
    total_log_odds = 0.0; total_weight = 0.0
    for sid, (triggered, stype, reliability) in sensor_readings.items():
        base_a, base_b = SENSOR_TYPE_PRIORS.get(stype, (2.0, 3.0))
        # Scale prior by sensor confidence (reliability prior modifier)
        a = base_a * reliability
        b = base_b * reliability
        # Posterior after observing evidence
        if triggered:
            post_a = a + 1.0; post_b = b
        else:
            post_a = a; post_b = b + 1.0
        # Posterior mean
        eps = 1e-9
        pm = (post_a + eps) / (post_a + post_b + 2*eps)
        # Weight = informativeness of prior (sqrt of sample size)
        weight = math.sqrt(a + b)
        odds = (pm + eps) / (1 - pm + eps)
        total_log_odds += weight * math.log(odds)
        total_weight += weight
    if total_weight == 0: return 0.0, "none"
    prob = 1 / (1 + math.exp(-total_log_odds / total_weight))
    strength = "strong" if total_weight > 15 else "moderate" if total_weight > 8 else "weak" if total_weight > 2 else "none"
    return min(1.0, max(0.0, prob)), strength
    
def wilson_confidence(n_present, n_total):
    if n_total == 0: return 0.0
    p_hat = n_present / n_total; z = 1.645
    denom = 1 + z*z / n_total
    center = (p_hat + z*z/(2*n_total)) / denom
    margin = z * math.sqrt((p_hat*(1-p_hat) + z*z/(4*n_total)) / n_total) / denom
    return max(0.0, center - margin)
