"""Bayesian Fusion for multi-sensor presence detection.

Combines evidence from multiple sensors using Bayesian inference:
- Incorporates prior probabilities (temporal, historical, contextual)
- Fuses sensor readings with different reliability weights
- Calculates posterior probability of presence
- Handles sensor conflicts and uncertainties
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import math
import logging

from .wilson_interval import WilsonScoreInterval, WilsonInterval
from .priors import PriorManager, PresencePrior

logger = logging.getLogger(__name__)


class SensorType(Enum):
    """Types of presence sensors."""
    MOTION = "motion"  # PIR motion sensors
    CONTACT = "contact"  # Door/window contacts
    CAMERA = "camera"  # Computer vision detection
    AUDIO = "audio"  # Sound-based detection
    WIFI = "wifi"  # WiFi device presence
    BLUETOOTH = "bluetooth"  # Bluetooth device presence
    POWER = "power"  # Power consumption patterns
    MANUAL = "manual"  # Manual override
    SCHEDULE = "schedule"  # Schedule-based


class SensorReliability(Enum):
    """Sensor reliability levels."""
    VERY_LOW = 0.3
    LOW = 0.5
    MEDIUM = 0.7
    HIGH = 0.85
    VERY_HIGH = 0.95


@dataclass
class SensorReading:
    """Single sensor reading with metadata.
    
    Attributes:
        sensor_id: Unique sensor identifier
        sensor_type: Type of sensor
        detected: Whether sensor detected presence (True/False)
        confidence: Sensor's own confidence (0-1)
        timestamp: When reading was taken
        reliability: Sensor reliability rating
        wilson_interval: Optional pre-computed Wilson interval
    """
    sensor_id: str
    sensor_type: SensorType
    detected: bool
    confidence: float = 1.0
    timestamp: Optional[datetime] = None
    reliability: SensorReliability = SensorReliability.MEDIUM
    wilson_interval: Optional[WilsonInterval] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
    
    @property
    def effective_confidence(self) -> float:
        """Combine sensor confidence with reliability."""
        return self.confidence * self.reliability.value
    
    def to_evidence(self) -> float:
        """Convert reading to evidence value for Bayesian update.
        
        Returns value in (0, 1) where:
        - > 0.5 supports presence
        - < 0.5 supports absence
        - = 0.5 is neutral
        """
        base = 0.5 + (0.5 if self.detected else -0.5)
        return base * self.effective_confidence + 0.5 * (1 - self.effective_confidence)


@dataclass
class PresenceState:
    """Current presence state estimation.
    
    Attributes:
        zone_id: Zone identifier
        probability_present: Posterior P(present | evidence)
        probability_absent: Posterior P(absent | evidence) = 1 - probability_present
        confidence: Confidence in the estimation
        last_updated: Last update timestamp
        contributing_sensors: Number of sensors contributing
        prior_used: Prior probability used
        evidence_strength: Combined evidence strength
    """
    zone_id: str
    probability_present: float
    probability_absent: float = field(init=False)
    confidence: float
    last_updated: datetime
    contributing_sensors: int
    prior_used: float
    evidence_strength: float
    
    def __post_init__(self):
        self.probability_absent = 1.0 - self.probability_present
    
    @property
    def is_present(self) -> bool:
        """Binary decision: presence detected."""
        return self.probability_present >= 0.5
    
    @property
    def is_confident(self) -> bool:
        """Check if estimation is confident enough for automation."""
        # Confident if probability is far from 0.5
        return abs(self.probability_present - 0.5) > 0.3
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "zone_id": self.zone_id,
            "probability_present": self.probability_present,
            "probability_absent": self.probability_absent,
            "confidence": self.confidence,
            "is_present": self.is_present,
            "is_confident": self.is_confident,
            "last_updated": self.last_updated.isoformat(),
            "contributing_sensors": self.contributing_sensors,
            "prior_used": self.prior_used,
            "evidence_strength": self.evidence_strength,
        }


class BayesianPresenceFusion:
    """Bayesian fusion engine for multi-sensor presence detection.
    
    Implements:
    1. Bayesian update: P(H|E) = P(E|H) * P(H) / P(E)
    2. Multi-sensor fusion with reliability weighting
    3. Wilson Score Interval for sensor confidence bounding
    4. Temporal smoothing for state stability
    5. Conflict detection and resolution
    
    Usage:
        fusion = BayesianPresenceFusion(zone_id="living_room")
        fusion.set_prior(0.3)  # 30% prior probability of presence
        
        # Add sensor readings
        fusion.add_reading(SensorReading(...))
        fusion.add_reading(SensorReading(...))
        
        # Get fused state
        state = fusion.compute_state()
        print(f"Presence probability: {state.probability_present:.2%}")
    """
    
    # Likelihood ratios for sensor types
    # P(detection | present) / P(detection | absent)
    LIKELIHOOD_RATIOS = {
        SensorType.MOTION: 8.0,  # Strong evidence when triggered
        SensorType.CONTACT: 10.0,  # Very strong (doors/windows)
        SensorType.CAMERA: 15.0,  # Very strong (visual confirmation)
        SensorType.AUDIO: 4.0,  # Moderate (could be false alarms)
        SensorType.WIFI: 6.0,  # Good (phone presence)
        SensorType.BLUETOOTH: 7.0,  # Good (wearable/device)
        SensorType.POWER: 3.0,  # Weak (could be appliances)
        SensorType.MANUAL: 20.0,  # Very strong (user override)
        SensorType.SCHEDULE: 2.0,  # Weak (just a hint)
    }
    
    def __init__(
        self,
        zone_id: str,
        prior_manager: Optional[PriorManager] = None,
        wilson_confidence: float = 0.95
    ):
        """Initialize Bayesian fusion engine.
        
        Args:
            zone_id: Zone identifier
            prior_manager: Optional prior manager for adaptive priors
            wilson_confidence: Confidence level for Wilson intervals
        """
        self.zone_id = zone_id
        self._prior_manager = prior_manager
        self._wilson = WilsonScoreInterval(confidence_level=wilson_confidence)
        
        self._readings: List[SensorReading] = []
        self._prior_probability = 0.5
        self._last_state: Optional[PresenceState] = None
        
        # Temporal smoothing
        self._smoothing_factor = 0.7  # Weight for previous state
        self._temporal_window_seconds = 60
    
    def set_prior(self, probability: float, confidence: float = 0.5):
        """Set prior probability manually.
        
        Args:
            probability: Prior P(present)
            confidence: Confidence in this prior
        """
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        self._prior_probability = probability
        logger.debug(f"Prior set for {self.zone_id}: {probability:.3f}")
    
    def load_prior_from_manager(self, context: Optional[List[str]] = None):
        """Load prior from prior manager (if available)."""
        if self._prior_manager:
            self._prior_probability = self._prior_manager.get_prior(
                self.zone_id,
                context=context
            )
    
    def add_reading(self, reading: SensorReading):
        """Add a sensor reading to the fusion engine.
        
        Args:
            reading: Sensor reading to add
        """
        # Compute Wilson interval if we have historical data for this sensor
        # (This would require tracking per-sensor history - simplified here)
        self._readings.append(reading)
        logger.debug(
            f"Added reading from {reading.sensor_id}: "
            f"detected={reading.detected}, eff_conf={reading.effective_confidence:.2f}"
        )
    
    def clear_readings(self):
        """Clear all readings (for fresh computation)."""
        self._readings = []
    
    def compute_bayes_factor(self, reading: SensorReading) -> float:
        """Compute Bayes factor for a single reading.
        
        Bayes factor = P(E | present) / P(E | absent)
        
        For a detection:
            BF = likelihood_ratio * confidence
        
        For no detection:
            BF = 1 / (likelihood_ratio * confidence)
        
        Args:
            reading: Sensor reading
            
        Returns:
            Bayes factor (>1 supports presence, <1 supports absence)
        """
        base_lr = self.LIKELIHOOD_RATIOS.get(reading.sensor_type, 1.0)
        adjusted_lr = base_lr * reading.effective_confidence
        
        if reading.detected:
            return adjusted_lr
        else:
            # No detection is evidence against presence
            # But less strong than a positive detection
            return 1.0 / (adjusted_lr ** 0.7)
    
    def compute_combined_bayes_factor(self) -> Tuple[float, List[float]]:
        """Compute combined Bayes factor from all readings.
        
        Uses logarithmic pooling to combine evidence:
            log(BF_combined) = sum(w_i * log(BF_i)) / sum(w_i)
        
        Returns:
            Tuple of (combined_bayes_factor, individual_factors)
        """
        if not self._readings:
            return 1.0, []
        
        log_bf_sum = 0.0
        weight_sum = 0.0
        individual_factors = []
        
        for reading in self._readings:
            bf = self.compute_bayes_factor(reading)
            individual_factors.append(bf)
            
            # Weight by effective confidence
            weight = reading.effective_confidence
            log_bf_sum += weight * math.log(bf)
            weight_sum += weight
        
        if weight_sum == 0:
            return 1.0, individual_factors
        
        # Exponentiate to get combined BF
        combined_log_bf = log_bf_sum / weight_sum
        combined_bf = math.exp(combined_log_bf)
        
        logger.debug(
            f"Combined Bayes factor: {combined_bf:.3f} "
            f"(from {len(self._readings)} readings)"
        )
        
        return combined_bf, individual_factors
    
    def compute_posterior(self, bayes_factor: float) -> float:
        """Compute posterior probability from prior and Bayes factor.
        
        P(present | E) = BF * P(present) / [BF * P(present) + P(absent)]
        
        Args:
            bayes_factor: Combined Bayes factor
            
        Returns:
            Posterior probability of presence
        """
        prior = self._prior_probability
        if bayes_factor <= 0:
            return 0.0
        
        numerator = bayes_factor * prior
        denominator = bayes_factor * prior + (1 - prior)
        
        if denominator == 0:
            return 0.5
        
        posterior = numerator / denominator
        return max(0.0, min(1.0, posterior))
    
    def apply_temporal_smoothing(self, new_probability: float) -> float:
        """Apply temporal smoothing to reduce oscillations.
        
        Uses exponential moving average:
            P_smoothed = alpha * P_new + (1 - alpha) * P_previous
        
        Args:
            new_probability: New computed probability
            
        Returns:
            Smoothed probability
        """
        if self._last_state is None:
            return new_probability
        
        alpha = self._smoothing_factor
        previous = self._last_state.probability_present
        
        smoothed = alpha * new_probability + (1 - alpha) * previous
        logger.debug(
            f"Temporal smoothing: {previous:.3f} → {new_probability:.3f} → {smoothed:.3f}"
        )
        
        return smoothed
    
    def compute_state(
        self,
        apply_smoothing: bool = True,
        context: Optional[List[str]] = None
    ) -> PresenceState:
        """Compute fused presence state.
        
        Args:
            apply_smoothing: Whether to apply temporal smoothing
            context: Optional context for prior loading
            
        Returns:
            PresenceState with fused probability and metadata
        """
        # Load prior if manager available
        if self._prior_manager:
            self.load_prior_from_manager(context)
        
        # Compute combined evidence
        combined_bf, individual_bfs = self.compute_combined_bayes_factor()
        
        # Compute posterior
        posterior = self.compute_posterior(combined_bf)
        
        # Apply smoothing
        if apply_smoothing:
            posterior = self.apply_temporal_smoothing(posterior)
        
        # Calculate confidence based on:
        # - Number of sensors
        # - Agreement between sensors
        # - Distance from 0.5
        sensor_confidence = min(1.0, len(self._readings) / 5.0)
        
        # Check agreement (variance of individual Bayes factors)
        if len(individual_bfs) > 1:
            log_bfs = [math.log(bf) for bf in individual_bfs]
            mean_log_bf = sum(log_bfs) / len(log_bfs)
            variance = sum((x - mean_log_bf) ** 2 for x in log_bfs) / len(log_bfs)
            agreement = max(0.0, 1.0 - variance / 4.0)  # Normalize
        else:
            agreement = 1.0
        
        # Final confidence
        confidence = sensor_confidence * agreement * (0.5 + abs(posterior - 0.5))
        
        # Evidence strength (log of combined BF)
        evidence_strength = math.log(combined_bf) if combined_bf > 0 else 0.0
        
        state = PresenceState(
            zone_id=self.zone_id,
            probability_present=posterior,
            confidence=confidence,
            last_updated=datetime.now(),
            contributing_sensors=len(self._readings),
            prior_used=self._prior_probability,
            evidence_strength=evidence_strength,
        )
        
        self._last_state = state
        
        logger.info(
            f"Presence state for {self.zone_id}: "
            f"P={posterior:.3f}, conf={confidence:.3f}, BF={combined_bf:.2f}"
        )
        
        return state
    
    def get_wilson_summary(self) -> Optional[WilsonInterval]:
        """Get Wilson interval summary of all positive detections.
        
        Returns:
            WilsonInterval for the aggregate detection rate, or None if no readings
        """
        if not self._readings:
            return None
        
        # Count detections weighted by confidence
        effective_trials = sum(r.effective_confidence for r in self._readings)
        effective_successes = sum(
            r.effective_confidence for r in self._readings if r.detected
        )
        
        if effective_trials < 1:
            return None
        
        return self._wilson.calculate(
            successes=round(effective_successes),
            trials=round(effective_trials),
        )
    
    def detect_conflicts(self, threshold: float = 0.5) -> List[Tuple[SensorReading, SensorReading]]:
        """Detect conflicting sensor readings.
        
        Args:
            threshold: Probability threshold for conflict detection
            
        Returns:
            List of conflicting reading pairs
        """
        conflicts = []
        positive = [r for r in self._readings if r.detected and r.effective_confidence > 0.5]
        negative = [r for r in self._readings if not r.detected and r.effective_confidence > 0.5]
        
        # Check for conflicts between high-confidence readings
        for pos in positive:
            for neg in negative:
                # Conflict if both have high confidence but opposite readings
                if pos.effective_confidence > 0.7 and neg.effective_confidence > 0.7:
                    # Check if sensors are of different types (expected conflicts)
                    if pos.sensor_type != neg.sensor_type:
                        conflicts.append((pos, neg))
        
        if conflicts:
            logger.warning(
                f"Detected {len(conflicts)} sensor conflicts in {self.zone_id}"
            )
        
        return conflicts
