"""Prior management for Bayesian presence detection.

Manages prior probabilities for presence detection based on:
- Temporal patterns (time of day, day of week)
- Historical occupancy data
- Contextual factors (holidays, special events)
- User preferences and schedules
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class TimeRange:
    """Time range for temporal priors."""
    start: time
    end: time
    
    def contains(self, t: time) -> bool:
        """Check if time is within range (handles overnight ranges)."""
        if self.start <= self.end:
            return self.start <= t <= self.end
        else:
            # Overnight range (e.g., 22:00 - 06:00)
            return t >= self.start or t <= self.end


@dataclass
class PresencePrior:
    """Prior probability distribution for presence.
    
    Attributes:
        prior_probability: Base prior P(present)
        confidence: Confidence in this prior (0-1)
        source: Source of prior (historical, schedule, manual, etc.)
        temporal_pattern: Time-based pattern if applicable
        day_of_week: Specific days if applicable (0=Mon, 6=Sun)
        context_tags: Contextual tags (holiday, vacation, workday, etc.)
        last_updated: When this prior was last updated
        observation_count: Number of observations supporting this prior
    """
    prior_probability: float = 0.5
    confidence: float = 0.5
    source: str = "default"
    temporal_pattern: Optional[TimeRange] = None
    day_of_week: Optional[List[int]] = None  # 0=Mon, 6=Sun
    context_tags: List[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    observation_count: int = 0
    
    def __post_init__(self):
        if not 0.0 <= self.prior_probability <= 1.0:
            raise ValueError("prior_probability must be in [0, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
    
    def apply_temporal(self, current_time: datetime) -> float:
        """Apply temporal adjustments to prior.
        
        Args:
            current_time: Current datetime
            
        Returns:
            Adjusted prior probability
        """
        base_prior = self.prior_probability
        
        # Check day of week
        if self.day_of_week is not None:
            current_dow = current_time.weekday()
            if current_dow not in self.day_of_week:
                # Different day - reduce confidence
                base_prior *= 0.7
        
        # Check time of day
        if self.temporal_pattern is not None:
            if self.temporal_pattern.contains(current_time.time()):
                # In expected time range - increase confidence
                base_prior = min(1.0, base_prior * 1.2)
            else:
                # Outside expected range - decrease
                base_prior *= 0.8
        
        return max(0.0, min(1.0, base_prior))
    
    def update(self, observation: bool, weight: float = 1.0):
        """Update prior based on new observation.
        
        Uses Bayesian update with fading memory.
        
        Args:
            observation: True if presence observed, False otherwise
            weight: Weight of this observation (0-1)
        """
        # Exponential moving average update
        alpha = weight * self.confidence
        target = 1.0 if observation else 0.0
        
        self.prior_probability = (1 - alpha) * self.prior_probability + alpha * target
        self.observation_count += 1
        self.last_updated = datetime.now()
        
        # Increase confidence with more observations (up to a limit)
        self.confidence = min(0.95, 0.5 + 0.1 * math.log(1 + self.observation_count))
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "prior_probability": self.prior_probability,
            "confidence": self.confidence,
            "source": self.source,
            "temporal_pattern": {
                "start": self.temporal_pattern.start.isoformat() if self.temporal_pattern else None,
                "end": self.temporal_pattern.end.isoformat() if self.temporal_pattern else None,
            } if self.temporal_pattern else None,
            "day_of_week": self.day_of_week,
            "context_tags": self.context_tags,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "observation_count": self.observation_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> PresencePrior:
        """Deserialize from dictionary."""
        temporal = None
        if data.get("temporal_pattern"):
            tp = data["temporal_pattern"]
            if tp.get("start") and tp.get("end"):
                temporal = TimeRange(
                    start=time.fromisoformat(tp["start"]),
                    end=time.fromisoformat(tp["end"]),
                )
        
        last_updated = None
        if data.get("last_updated"):
            last_updated = datetime.fromisoformat(data["last_updated"])
        
        return cls(
            prior_probability=data.get("prior_probability", 0.5),
            confidence=data.get("confidence", 0.5),
            source=data.get("source", "default"),
            temporal_pattern=temporal,
            day_of_week=data.get("day_of_week"),
            context_tags=data.get("context_tags", []),
            last_updated=last_updated,
            observation_count=data.get("observation_count", 0),
        )


class PriorManager:
    """Manage and combine multiple sources of priors.
    
    Responsibilities:
    - Load/save priors from persistent storage
    - Combine multiple prior sources with weighted averaging
    - Adapt priors based on prediction accuracy
    - Provide context-aware prior probabilities
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize prior manager.
        
        Args:
            storage_path: Path to store/load priors (optional)
        """
        self._storage_path = storage_path
        self._priors: Dict[str, PresencePrior] = {}
        self._global_prior = PresencePrior(
            prior_probability=0.3,  # Default: usually not home
            confidence=0.3,
            source="global_default",
        )
        self._accuracy_history: List[bool] = []
        
        # Load existing priors if available
        if storage_path and storage_path.exists():
            self.load(storage_path)
    
    def get_prior(
        self,
        zone_id: str,
        current_time: Optional[datetime] = None,
        context: Optional[List[str]] = None
    ) -> float:
        """Get prior probability for presence in a zone.
        
        Args:
            zone_id: Zone identifier
            current_time: Current datetime (uses now if None)
            context: Optional context tags
            
        Returns:
            Prior probability P(present) in [0, 1]
        """
        current_time = current_time or datetime.now()
        context = context or []
        
        # Start with global prior
        prior = self._global_prior.apply_temporal(current_time)
        weight = 1.0 - self._global_prior.confidence
        
        # Add zone-specific prior if available
        if zone_id in self._priors:
            zone_prior = self._priors[zone_id]
            
            # Check context match
            context_match = all(tag in zone_prior.context_tags for tag in context)
            
            if context_match or not zone_prior.context_tags:
                zone_adjusted = zone_prior.apply_temporal(current_time)
                
                # Weighted combination
                zone_weight = zone_prior.confidence
                prior = (weight * prior + zone_weight * zone_adjusted) / (weight + zone_weight)
                weight += zone_weight
        
        logger.debug(f"Prior for {zone_id}: {prior:.3f} (weight={weight:.2f})")
        return prior
    
    def set_prior(
        self,
        zone_id: str,
        prior: PresencePrior,
        merge: bool = True
    ):
        """Set or update prior for a zone.
        
        Args:
            zone_id: Zone identifier
            prior: Prior to set
            merge: If True, merge with existing prior; if False, replace
        """
        if zone_id in self._priors and merge:
            existing = self._priors[zone_id]
            # Weighted average of priors
            total_weight = existing.confidence + prior.confidence
            if total_weight > 0:
                merged_prior = (
                    existing.prior_probability * existing.confidence +
                    prior.prior_probability * prior.confidence
                ) / total_weight
                
                merged = PresencePrior(
                    prior_probability=merged_prior,
                    confidence=min(0.95, total_weight / 2),
                    source=f"merged:{existing.source},{prior.source}",
                    temporal_pattern=prior.temporal_pattern or existing.temporal_pattern,
                    day_of_week=prior.day_of_week or existing.day_of_week,
                    context_tags=list(set(existing.context_tags + prior.context_tags)),
                )
                self._priors[zone_id] = merged
        else:
            self._priors[zone_id] = prior
        
        logger.info(f"Prior set for {zone_id}: {prior.prior_probability:.3f}")
    
    def update_from_observation(
        self,
        zone_id: str,
        observed_present: bool,
        predicted_present: bool,
        weight: float = 1.0
    ):
        """Update priors based on prediction accuracy.
        
        Args:
            zone_id: Zone where observation occurred
            observed_present: True if presence was actually observed
            predicted_present: True if presence was predicted
            weight: Learning rate (0-1)
        """
        # Track accuracy
        correct = (observed_present == predicted_present)
        self._accuracy_history.append(correct)
        
        # Keep last 1000 observations
        if len(self._accuracy_history) > 1000:
            self._accuracy_history = self._accuracy_history[-1000:]
        
        # Update zone prior if exists
        if zone_id in self._priors:
            self._priors[zone_id].update(observed_present, weight)
        
        # Adjust global prior slightly
        self._global_prior.update(observed_present, weight * 0.1)
    
    def learn_from_schedule(
        self,
        zone_id: str,
        schedule: List[Tuple[time, time, float, List[int]]]
    ):
        """Learn priors from a schedule.
        
        Args:
            zone_id: Zone identifier
            schedule: List of (start_time, end_time, probability, days_of_week)
                     where days_of_week is list of 0-6 (Mon-Sun) or None for all days
        """
        for start, end, prob, days in schedule:
            prior = PresencePrior(
                prior_probability=prob,
                confidence=0.7,
                source="schedule",
                temporal_pattern=TimeRange(start=start, end=end),
                day_of_week=days,
            )
            self.set_prior(zone_id, prior, merge=True)
    
    def save(self, path: Optional[Path] = None):
        """Save priors to file.
        
        Args:
            path: Override storage path
        """
        path = path or self._storage_path
        if not path:
            raise ValueError("No storage path available")
        
        data = {
            "global_prior": self._global_prior.to_dict(),
            "zone_priors": {k: v.to_dict() for k, v in self._priors.items()},
            "accuracy_rate": sum(self._accuracy_history) / len(self._accuracy_history) if self._accuracy_history else 0.5,
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Priors saved to {path}")
    
    def load(self, path: Optional[Path] = None):
        """Load priors from file.
        
        Args:
            path: Override storage path
        """
        path = path or self._storage_path
        if not path or not path.exists():
            logger.warning(f"No prior file at {path}")
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        self._global_prior = PresencePrior.from_dict(data.get("global_prior", {}))
        self._priors = {
            k: PresencePrior.from_dict(v)
            for k, v in data.get("zone_priors", {}).items()
        }
        
        logger.info(f"Priors loaded from {path}: {len(self._priors)} zones")
    
    def get_stats(self) -> Dict:
        """Get statistics about priors."""
        return {
            "global_prior": self._global_prior.prior_probability,
            "global_confidence": self._global_prior.confidence,
            "zone_count": len(self._priors),
            "accuracy_rate": sum(self._accuracy_history) / len(self._accuracy_history) if self._accuracy_history else 0.5,
            "total_observations": sum(p.observation_count for p in self._priors.values()),
        }
