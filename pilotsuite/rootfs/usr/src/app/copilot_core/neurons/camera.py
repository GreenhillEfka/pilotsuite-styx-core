"""Camera Context Neuron for security and vision integration.

Implements context neurons for camera-based presence and activity detection:
- CameraPresenceNeuron: Detect presence from camera events
- CameraActivityNeuron: Detect activity level from motion events
- SecurityAlertNeuron: Security-focused context from camera alerts

HA 2025.8+ supports AI Tasks for camera analysis.
This module integrates camera events into the neural system.

See: Industry research from Perplexity audit (2026-02-15)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base import ContextNeuron, NeuronConfig, NeuronType

_LOGGER = logging.getLogger(__name__)


@dataclass
class CameraState:
    """State for camera detection."""
    last_motion: Optional[datetime] = None
    last_person: Optional[datetime] = None
    last_vehicle: Optional[datetime] = None
    last_animal: Optional[datetime] = None
    motion_count: int = 0
    person_count: int = 0
    confidence: float = 0.0
    zone: str = "unknown"


class CameraPresenceNeuron(ContextNeuron):
    """Presence detection from camera events.
    
    Integrates with HA camera entities and image processing:
    - Motion detection events
    - Person detection (frigate, deepstack, etc.)
    - Zone-based presence
    
    Compatible with:
    - Frigate NVR
    - DeepStack / CodeProject.AI
    - HA image_processing entities
    - ONVIF cameras with motion detection
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        # Camera entities
        self.camera_entities: List[str] = config.extra.get("camera_entities", [])
        self.motion_entities: List[str] = config.extra.get("motion_entities", [])
        self.image_processing_entities: List[str] = config.extra.get("image_processing_entities", [])
        
        # Detection thresholds
        self.presence_timeout_seconds: int = config.extra.get("presence_timeout", 120)
        self.min_confidence: float = config.extra.get("min_confidence", 0.6)
        
        # State
        self._camera_states: Dict[str, CameraState] = {}
        self._last_update: Optional[datetime] = None
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate camera-based presence.
        
        Returns:
            Presence confidence (0.0 - 1.0)
        """
        ha_states = context.get("ha_states", {})
        now = datetime.now(timezone.utc)
        
        total_presence = 0.0
        active_cameras = 0
        
        # Process motion sensors
        for entity_id in self.motion_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            state_value = str(state.state).lower()
            is_motion = state_value in ("on", "detected", "motion")
            
            if is_motion:
                active_cameras += 1
                
                # Get last changed time
                last_changed = state.last_changed
                if isinstance(last_changed, str):
                    try:
                        last_changed = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                    except Exception:
                        last_changed = now
                
                # Calculate presence factor based on recency
                elapsed = (now - last_changed).total_seconds() if last_changed else 0
                if elapsed < self.presence_timeout_seconds:
                    presence_factor = 1.0 - (elapsed / self.presence_timeout_seconds)
                    total_presence += presence_factor
        
        # Process image_processing entities (Frigate, DeepStack)
        for entity_id in self.image_processing_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            # Check for person detection
            attrs = state.attributes or {}
            
            # Frigate format
            if "person" in attrs:
                person_count = int(attrs.get("person", 0))
                if person_count > 0:
                    active_cameras += 1
                    total_presence += min(1.0, person_count / 2)
            
            # Generic format
            if "count" in attrs:
                count = int(attrs.get("count", 0))
                if count > 0:
                    active_cameras += 1
                    total_presence += min(1.0, count / 2)
        
        # Normalize
        if active_cameras == 0:
            return 0.0
        
        return min(1.0, total_presence / active_cameras)
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "CameraPresenceNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "active_cameras": len([s for s in self._camera_states.values() if s.last_motion]),
            "last_motion": max(
                [s.last_motion for s in self._camera_states.values() if s.last_motion],
                default=None
            ),
            "presence_detected": any(
                s.confidence > self.min_confidence 
                for s in self._camera_states.values()
            ),
        }


class CameraActivityNeuron(ContextNeuron):
    """Activity level detection from camera motion frequency.
    
    Measures activity intensity based on:
    - Motion event frequency
    - Duration of activity
    - Zone transitions
    
    Useful for:
    - Detecting high-activity periods
    - Calibrating motion sensitivity
    - Activity-based automation
    """
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        self.motion_entities: List[str] = config.extra.get("motion_entities", [])
        self.activity_window_seconds: int = config.extra.get("activity_window", 300)  # 5 min
        
        self._motion_history: List[datetime] = []
        self._max_history = 100
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate activity level.
        
        Returns:
            Activity score (0.0 - 1.0)
        """
        ha_states = context.get("ha_states", {})
        now = datetime.now(timezone.utc)
        
        # Count recent motion events
        recent_motions = 0
        
        for entity_id in self.motion_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            state_value = str(state.state).lower()
            if state_value in ("on", "detected", "motion"):
                recent_motions += 1
                
                # Track motion time
                self._motion_history.append(now)
        
        # Trim history
        self._motion_history = self._motion_history[-self._max_history:]
        
        # Count motions in window
        window_start = now - timedelta(seconds=self.activity_window_seconds)
        motions_in_window = sum(
            1 for t in self._motion_history 
            if t >= window_start
        )
        
        # Calculate activity score
        # Scale: 0 motions = 0.0, 10+ motions in 5min = 1.0
        max_expected_motions = 10
        activity_score = min(1.0, motions_in_window / max_expected_motions)
        
        return activity_score
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "CameraActivityNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.activity_window_seconds)
        recent_count = sum(1 for t in self._motion_history if t >= window_start)
        
        return {
            "motion_count_5min": recent_count,
            "activity_level": "high" if recent_count > 5 else "medium" if recent_count > 2 else "low",
        }


class SecurityAlertNeuron(ContextNeuron):
    """Security-focused context from camera alerts.
    
    Integrates with:
    - Frigate object detection
    - Doorbell events
    - Security camera alerts
    - Binary sensors (door, window, motion)
    
    Outputs:
    - Security alert level (0.0 - 1.0)
    - Alert type classification
    - Zone information
    """
    
    # Alert severity weights
    ALERT_WEIGHTS = {
        "person": 0.8,      # Person detected
        "vehicle": 0.6,     # Vehicle detected
        "animal": 0.2,      # Pet/wildlife
        "motion": 0.4,      # Generic motion
        "door": 0.7,        # Door opened
        "window": 0.7,      # Window opened
        "glass": 0.9,       # Glass break
        "alarm": 1.0,       # Alarm triggered
    }
    
    def __init__(self, config: NeuronConfig):
        super().__init__(config, NeuronType.CONTEXT)
        
        # Security entities
        self.camera_entities: List[str] = config.extra.get("camera_entities", [])
        self.door_entities: List[str] = config.extra.get("door_entities", [])
        self.window_entities: List[str] = config.extra.get("window_entities", [])
        self.alarm_entities: List[str] = config.extra.get("alarm_entities", [])
        self.image_processing_entities: List[str] = config.extra.get("image_processing_entities", [])
        
        # Alert window
        self.alert_window_seconds: int = config.extra.get("alert_window", 300)
        
        # State
        self._alert_history: List[Dict[str, Any]] = []
        self._last_alert: Optional[datetime] = None
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate security alert level.
        
        Returns:
            Security alert score (0.0 - 1.0)
        """
        ha_states = context.get("ha_states", {})
        now = datetime.now(timezone.utc)
        
        total_alert_score = 0.0
        alert_count = 0
        
        # Check alarm entities
        for entity_id in self.alarm_entities:
            state = ha_states.get(entity_id)
            if state and str(state.state).lower() in ("on", "triggered", "alarm"):
                total_alert_score += self.ALERT_WEIGHTS.get("alarm", 1.0)
                alert_count += 1
                self._record_alert("alarm", entity_id, now)
        
        # Check door entities
        for entity_id in self.door_entities:
            state = ha_states.get(entity_id)
            if state and str(state.state).lower() in ("on", "open"):
                total_alert_score += self.ALERT_WEIGHTS.get("door", 0.7)
                alert_count += 1
                self._record_alert("door", entity_id, now)
        
        # Check window entities
        for entity_id in self.window_entities:
            state = ha_states.get(entity_id)
            if state and str(state.state).lower() in ("on", "open"):
                total_alert_score += self.ALERT_WEIGHTS.get("window", 0.7)
                alert_count += 1
                self._record_alert("window", entity_id, now)
        
        # Check image processing (Frigate, etc.)
        for entity_id in self.image_processing_entities:
            state = ha_states.get(entity_id)
            if not state:
                continue
            
            attrs = state.attributes or {}
            
            # Frigate person detection
            if "person" in attrs and attrs["person"] > 0:
                total_alert_score += self.ALERT_WEIGHTS.get("person", 0.8)
                alert_count += 1
                self._record_alert("person", entity_id, now)
            
            # Vehicle detection
            if "car" in attrs or "vehicle" in attrs:
                count = attrs.get("car", attrs.get("vehicle", 0))
                if count > 0:
                    total_alert_score += self.ALERT_WEIGHTS.get("vehicle", 0.6)
                    alert_count += 1
                    self._record_alert("vehicle", entity_id, now)
        
        # Normalize
        if alert_count == 0:
            return 0.0
        
        alert_score = min(1.0, total_alert_score / alert_count)
        
        # Update last alert time
        if alert_score > 0.3:
            self._last_alert = now
        
        return alert_score
    
    def _record_alert(self, alert_type: str, entity_id: str, timestamp: datetime):
        """Record an alert for history."""
        self._alert_history.append({
            "type": alert_type,
            "entity": entity_id,
            "time": timestamp.isoformat(),
        })
        # Keep only last 50 alerts
        self._alert_history = self._alert_history[-50:]
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "SecurityAlertNeuron":
        return cls(config)
    
    def get_state(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.alert_window_seconds)
        
        recent_alerts = [
            a for a in self._alert_history
            if datetime.fromisoformat(a["time"]) >= window_start
        ]
        
        return {
            "alert_count_5min": len(recent_alerts),
            "last_alert": self._last_alert.isoformat() if self._last_alert else None,
            "alert_types": list(set(a["type"] for a in recent_alerts)),
        }


# Factory functions
def create_camera_presence_neuron(
    motion_entities: List[str],
    image_processing_entities: Optional[List[str]] = None,
    presence_timeout: int = 120,
    name: str = "Camera Presence",
) -> CameraPresenceNeuron:
    """Create camera presence neuron."""
    config = NeuronConfig(
        id="camera_presence",
        name=name,
        extra={
            "motion_entities": motion_entities,
            "image_processing_entities": image_processing_entities or [],
            "presence_timeout": presence_timeout,
        },
    )
    return CameraPresenceNeuron(config)


def create_camera_activity_neuron(
    motion_entities: List[str],
    activity_window: int = 300,
    name: str = "Camera Activity",
) -> CameraActivityNeuron:
    """Create camera activity neuron."""
    config = NeuronConfig(
        id="camera_activity",
        name=name,
        extra={
            "motion_entities": motion_entities,
            "activity_window": activity_window,
        },
    )
    return CameraActivityNeuron(config)


def create_security_alert_neuron(
    door_entities: Optional[List[str]] = None,
    window_entities: Optional[List[str]] = None,
    alarm_entities: Optional[List[str]] = None,
    image_processing_entities: Optional[List[str]] = None,
    name: str = "Security Alert",
) -> SecurityAlertNeuron:
    """Create security alert neuron."""
    config = NeuronConfig(
        id="security_alert",
        name=name,
        extra={
            "door_entities": door_entities or [],
            "window_entities": window_entities or [],
            "alarm_entities": alarm_entities or [],
            "image_processing_entities": image_processing_entities or [],
        },
    )
    return SecurityAlertNeuron(config)


# Register neuron classes
CAMERA_NEURON_CLASSES = {
    "camera_presence": CameraPresenceNeuron,
    "camera_activity": CameraActivityNeuron,
    "security_alert": SecurityAlertNeuron,
}