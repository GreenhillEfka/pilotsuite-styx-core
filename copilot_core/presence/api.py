"""Presence API v2 — Bayesian Presence Detection with Wilson Score."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class PresenceState:
    """Current presence state."""
    is_present: bool
    confidence: float
    wilson_lower: float
    wilson_upper: float
    sensor_count: int
    last_motion: float
    updated_at: float = field(default_factory=lambda: time.time())


class PresenceAPI:
    """
    Bayesian Presence Detection API v2.
    
    Combines:
    - Wilson Score Interval for confidence estimation
    - Multi-sensor fusion (PIR, Radar, WiFi, BLE)
    - Bayesian priors for temporal reasoning
    """

    def __init__(self):
        from copilot_core.presence.wilson_score import WilsonScoreInterval
        from copilot_core.presence.sensor_fusion import MultiSensorFusion
        from copilot_core.presence.bayesian_fusion import BayesianFusion
        
        self._wilson = WilsonScoreInterval(confidence_level=0.95)
        self._sensor_fusion = MultiSensorFusion()
        self._bayesian = BayesianFusion()
        
        self._presence_history: List[Dict] = []
        self._observation_counts: Dict[str, int] = {}

    def update_sensor(
        self,
        sensor_type: str,
        sensor_id: str,
        value: float,
        metadata: Optional[Dict] = None,
    ) -> PresenceState:
        """
        Update sensor reading and recalculate presence.
        
        Args:
            sensor_type: Type of sensor (pir, radar, wifi, ble)
            sensor_id: Unique sensor identifier
            value: Sensor confidence (0.0-1.0)
            metadata: Optional sensor metadata
        
        Returns:
            Updated presence state
        """
        from copilot_core.presence.sensor_fusion import SensorReading, SensorType
        
        # Add sensor reading
        reading = SensorReading(
            sensor_type=SensorType(sensor_type),
            sensor_id=sensor_id,
            value=value,
            metadata=metadata or {},
        )
        self._sensor_fusion.add_reading(reading)
        
        # Track observations for Wilson score
        obs_key = f"{sensor_type}:{sensor_id}"
        self._observation_counts[obs_key] = self._observation_counts.get(obs_key, 0) + 1
        
        # Fuse sensors
        fused = self._sensor_fusion.fuse()
        
        # Calculate Wilson interval
        successes = sum(1 for r in self._sensor_fusion._recent_readings if r.value > 0.5)
        trials = len(self._sensor_fusion._recent_readings)
        wilson = self._wilson.calculate(successes, trials)
        
        # Bayesian update with priors
        posterior = self._bayesian.update_with_prior(
            prior_alpha=1.0,
            prior_beta=1.0,
            successes=fused.confidence * trials,
            trials=trials,
        )
        
        state = PresenceState(
            is_present=fused.is_present,
            confidence=fused.confidence,
            wilson_lower=wilson.lower_bound,
            wilson_upper=wilson.upper_bound,
            sensor_count=len(self._sensor_fusion._recent_readings),
            last_motion=time.time() if fused.is_present else self._get_last_motion(),
        )
        
        self._presence_history.append({
            "timestamp": time.time(),
            "state": state.is_present,
            "confidence": state.confidence,
        })
        
        logger.info(f"Presence updated: {state.is_present} (conf: {state.confidence:.2f})")
        
        return state

    def _get_last_motion(self) -> float:
        """Get timestamp of last motion detection."""
        for event in reversed(self._presence_history[-100:]):
            if event["state"]:
                return event["timestamp"]
        return 0.0

    def get_current_state(self) -> PresenceState:
        """Get current presence state."""
        fused = self._sensor_fusion.fuse()
        
        successes = sum(1 for r in self._sensor_fusion._recent_readings if r.value > 0.5)
        trials = len(self._sensor_fusion._recent_readings)
        wilson = self._wilson.calculate(successes, trials) if trials > 0 else None
        
        return PresenceState(
            is_present=fused.is_present,
            confidence=fused.confidence,
            wilson_lower=wilson.lower_bound if wilson else 0.0,
            wilson_upper=wilson.upper_bound if wilson else 1.0,
            sensor_count=len(self._sensor_fusion._recent_readings),
            last_motion=self._get_last_motion(),
        )

    def get_presence_probability(self) -> float:
        """Get current presence probability."""
        return self._sensor_fusion.get_presence_probability()

    def get_sensor_health(self) -> Dict[str, Dict]:
        """Get health status of all sensors."""
        return self._sensor_fusion.get_sensor_health()

    def get_presence_history(
        self,
        limit: int = 100,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict]:
        """Get presence history."""
        history = self._presence_history
        
        if start_time:
            history = [h for h in history if h["timestamp"] >= start_time]
        if end_time:
            history = [h for h in history if h["timestamp"] <= end_time]
        
        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get presence API statistics."""
        return {
            "total_updates": len(self._presence_history),
            "sensor_types": self._sensor_fusion.get_stats().get("sensor_types_active", 0),
            "current_presence": self.get_current_state().is_present,
            "observation_counts": self._observation_counts,
        }


# Global default presence API
default_presence_api: Optional[PresenceAPI] = None


def init_presence_api_v2() -> PresenceAPI:
    """Initialize global presence API v2."""
    global default_presence_api
    default_presence_api = PresenceAPI()
    return default_presence_api
