"""High-level presence detector combining Wilson intervals and Bayesian fusion.

Provides a simple API for presence detection with:
- Automatic prior management
- Multi-sensor fusion
- Configurable thresholds and smoothing
- State persistence and learning
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from .bayesian_fusion import (
    BayesianPresenceFusion,
    PresenceState,
    SensorReading,
    SensorType,
    SensorReliability,
)
from .priors import PriorManager, PresencePrior, TimeRange
from .wilson_interval import WilsonScoreInterval

logger = logging.getLogger(__name__)


@dataclass
class PresenceConfig:
    """Configuration for presence detector.
    
    Attributes:
        zone_id: Zone identifier
        prior_probability: Default prior P(present)
        smoothing_factor: Temporal smoothing (0-1, higher = more smoothing)
        presence_threshold: Threshold for declaring presence (default 0.5)
        confidence_threshold: Minimum confidence for automation triggers
        wilson_confidence: Confidence level for Wilson intervals
        sensor_reliabilities: Custom reliability overrides per sensor
        temporal_priors: Time-based prior adjustments
        persistence_path: Path for state persistence
    """
    zone_id: str
    prior_probability: float = 0.3
    smoothing_factor: float = 0.7
    presence_threshold: float = 0.5
    confidence_threshold: float = 0.6
    wilson_confidence: float = 0.95
    sensor_reliabilities: Dict[str, SensorReliability] = field(default_factory=dict)
    temporal_priors: Dict[str, Tuple[float, TimeRange]] = field(default_factory=dict)
    persistence_path: Optional[Path] = None
    
    def __post_init__(self):
        if not 0.0 <= self.prior_probability <= 1.0:
            raise ValueError("prior_probability must be in [0, 1]")
        if not 0.0 <= self.smoothing_factor <= 1.0:
            raise ValueError("smoothing_factor must be in [0, 1]")


@dataclass
class DetectionEvent:
    """A presence detection event.
    
    Attributes:
        timestamp: When detection occurred
        zone_id: Zone identifier
        state: Presence state at time of event
        event_type: Type of event (presence_detected, absence_detected, state_change)
        trigger_sensor: Sensor that triggered the event (if applicable)
    """
    timestamp: datetime
    zone_id: str
    state: PresenceState
    event_type: str
    trigger_sensor: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "zone_id": self.zone_id,
            "state": self.state.to_dict(),
            "event_type": self.event_type,
            "trigger_sensor": self.trigger_sensor,
        }


class PresenceDetector:
    """Main presence detection engine.
    
    Combines Wilson Score Intervals and Bayesian Fusion for robust
    multi-sensor presence detection with adaptive priors.
    
    Usage:
        config = PresenceConfig(zone_id="living_room")
        detector = PresenceDetector(config)
        
        # Add sensor readings
        detector.add_reading("motion_living", SensorType.MOTION, True)
        detector.add_reading("wifi_phone", SensorType.WIFI, True)
        
        # Get detection state
        state = detector.get_state()
        if state.is_present and state.is_confident:
            print("Someone is home!")
        
        # Save/load state
        detector.save()
        detector.load()
    """
    
    def __init__(self, config: PresenceConfig):
        """Initialize presence detector.
        
        Args:
            config: Detector configuration
        """
        self.config = config
        self.zone_id = config.zone_id
        
        # Initialize prior manager
        prior_path = config.persistence_path.parent / f"{config.zone_id}_priors.json" if config.persistence_path else None
        self._prior_manager = PriorManager(storage_path=prior_path)
        
        # Initialize Bayesian fusion engine
        self._fusion = BayesianPresenceFusion(
            zone_id=config.zone_id,
            prior_manager=self._prior_manager,
            wilson_confidence=config.wilson_confidence,
        )
        self._fusion._smoothing_factor = config.smoothing_factor
        
        # Set initial prior
        self._fusion.set_prior(config.prior_probability)
        
        # State tracking
        self._last_state: Optional[PresenceState] = None
        self._event_history: List[DetectionEvent] = []
        self._sensor_history: Dict[str, List[SensorReading]] = {}
        
        # Load persisted state if available
        if config.persistence_path and config.persistence_path.exists():
            self.load(config.persistence_path)
    
    def add_reading(
        self,
        sensor_id: str,
        sensor_type: SensorType,
        detected: bool,
        confidence: float = 1.0,
        reliability: Optional[SensorReliability] = None
    ) -> SensorReading:
        """Add a sensor reading.
        
        Args:
            sensor_id: Unique sensor identifier
            sensor_type: Type of sensor
            detected: Whether presence was detected
            confidence: Sensor's confidence (0-1)
            reliability: Override reliability (uses config default if None)
            
        Returns:
            The created SensorReading
        """
        # Use configured reliability or default
        if reliability is None:
            reliability = self.config.sensor_reliabilities.get(
                sensor_id,
                SensorReliability.MEDIUM
            )
        
        reading = SensorReading(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            detected=detected,
            confidence=confidence,
            reliability=reliability,
        )
        
        # Track sensor history
        if sensor_id not in self._sensor_history:
            self._sensor_history[sensor_id] = []
        self._sensor_history[sensor_id].append(reading)
        
        # Keep last 100 readings per sensor
        if len(self._sensor_history[sensor_id]) > 100:
            self._sensor_history[sensor_id] = self._sensor_history[sensor_id][-100:]
        
        # Add to fusion engine
        self._fusion.add_reading(reading)
        
        logger.debug(
            f"Reading added: {sensor_id} ({sensor_type.value}) = {detected}"
        )
        
        return reading
    
    def get_state(
        self,
        force_recompute: bool = False,
        context: Optional[List[str]] = None
    ) -> PresenceState:
        """Get current presence state.
        
        Args:
            force_recompute: Force recomputation even if recent
            context: Optional context tags for prior adjustment
            
        Returns:
            Current PresenceState
        """
        state = self._fusion.compute_state(context=context)
        
        # Check for state change events
        if self._last_state is not None:
            was_present = self._last_state.is_present
            is_present = state.is_present
            
            if was_present != is_present:
                # State change detected
                event_type = "presence_detected" if is_present else "absence_detected"
                event = DetectionEvent(
                    timestamp=datetime.now(),
                    zone_id=self.zone_id,
                    state=state,
                    event_type=event_type,
                )
                self._event_history.append(event)
                
                # Keep last 1000 events
                if len(self._event_history) > 1000:
                    self._event_history = self._event_history[-1000:]
                
                # Update priors based on observation
                self._prior_manager.update_from_observation(
                    self.zone_id,
                    observed_present=is_present,
                    predicted_present=was_present,
                    weight=0.1,
                )
                
                logger.info(
                    f"State change in {self.zone_id}: {was_present} → {is_present}"
                )
        
        self._last_state = state
        return state
    
    def is_present(self, min_confidence: Optional[float] = None) -> bool:
        """Check if presence is detected with optional confidence threshold.
        
        Args:
            min_confidence: Override default confidence threshold
            
        Returns:
            True if presence detected with sufficient confidence
        """
        threshold = min_confidence or self.config.confidence_threshold
        state = self.get_state()
        return state.is_present and state.confidence >= threshold
    
    def get_wilson_summary(self) -> Optional[Dict]:
        """Get Wilson interval summary for all sensors.
        
        Returns:
            Dictionary with Wilson interval statistics, or None
        """
        interval = self._fusion.get_wilson_summary()
        if interval is None:
            return None
        
        return {
            "center": interval.center,
            "lower_bound": interval.lower_bound,
            "upper_bound": interval.upper_bound,
            "width": interval.width,
            "is_reliable": interval.is_reliable,
            "successes": interval.successes,
            "trials": interval.trials,
            "confidence_level": interval.confidence_level,
        }
    
    def detect_conflicts(self) -> List[Dict]:
        """Detect sensor conflicts.
        
        Returns:
            List of conflict descriptions
        """
        conflicts = self._fusion.detect_conflicts()
        return [
            {
                "sensor1": c[0].sensor_id,
                "sensor2": c[1].sensor_id,
                "sensor1_type": c[0].sensor_type.value,
                "sensor2_type": c[1].sensor_type.value,
                "sensor1_confidence": c[0].effective_confidence,
                "sensor2_confidence": c[1].effective_confidence,
            }
            for c in conflicts
        ]
    
    def clear_readings(self, older_than: Optional[timedelta] = None):
        """Clear sensor readings.
        
        Args:
            older_than: If set, only clear readings older than this timedelta
        """
        if older_than is None:
            self._fusion.clear_readings()
        else:
            # Filter out old readings (not implemented in fusion engine)
            # Would require timestamp tracking in fusion
            self._fusion.clear_readings()
        
        logger.debug(f"Readings cleared for {self.zone_id}")
    
    def save(self, path: Optional[Path] = None):
        """Save detector state to file.
        
        Args:
            path: Override persistence path
        """
        path = path or self.config.persistence_path
        if not path:
            raise ValueError("No persistence path available")
        
        data = {
            "zone_id": self.zone_id,
            "config": {
                "prior_probability": self.config.prior_probability,
                "smoothing_factor": self.config.smoothing_factor,
                "presence_threshold": self.config.presence_threshold,
                "confidence_threshold": self.config.confidence_threshold,
            },
            "last_state": self._last_state.to_dict() if self._last_state else None,
            "event_count": len(self._event_history),
            "sensor_count": len(self._sensor_history),
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Save priors separately
        self._prior_manager.save()
        
        logger.info(f"Detector state saved to {path}")
    
    def load(self, path: Optional[Path] = None):
        """Load detector state from file.
        
        Args:
            path: Override persistence path
        """
        path = path or self.config.persistence_path
        if not path or not path.exists():
            logger.warning(f"No state file at {path}")
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Restore config
        if "config" in data:
            cfg = data["config"]
            self.config.prior_probability = cfg.get("prior_probability", 0.3)
            self.config.smoothing_factor = cfg.get("smoothing_factor", 0.7)
            self.config.presence_threshold = cfg.get("presence_threshold", 0.5)
            self.config.confidence_threshold = cfg.get("confidence_threshold", 0.6)
        
        # Restore prior
        self._fusion.set_prior(self.config.prior_probability)
        
        # Load priors
        self._prior_manager.load()
        
        logger.info(f"Detector state loaded from {path}")
    
    def get_stats(self) -> Dict:
        """Get detector statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "zone_id": self.zone_id,
            "sensor_count": len(self._sensor_history),
            "total_readings": sum(len(readings) for readings in self._sensor_history.values()),
            "event_count": len(self._event_history),
            "prior_manager_stats": self._prior_manager.get_stats(),
            "last_state": self._last_state.to_dict() if self._last_state else None,
        }
    
    def reset(self):
        """Reset detector to initial state."""
        self._fusion.clear_readings()
        self._sensor_history.clear()
        self._event_history.clear()
        self._last_state = None
        self._fusion.set_prior(self.config.prior_probability)
        
        logger.info(f"Detector reset for {self.zone_id}")


# Convenience factory function
def create_presence_detector(
    zone_id: str,
    prior: float = 0.3,
    persistence_path: Optional[str] = None,
    **kwargs
) -> PresenceDetector:
    """Create a presence detector with sensible defaults.
    
    Args:
        zone_id: Zone identifier
        prior: Default prior probability
        persistence_path: Optional path for state persistence
        **kwargs: Additional config options
        
    Returns:
        Configured PresenceDetector
    """
    config = PresenceConfig(
        zone_id=zone_id,
        prior_probability=prior,
        persistence_path=Path(persistence_path) if persistence_path else None,
        **kwargs
    )
    return PresenceDetector(config)
