"""Live Mood Engine with 3D Scoring for PilotSuite.

Extends the base mood engine with:
- Live mood streaming
- 3D scoring (Comfort/Joy/Frugality)
- Real-time mood transitions
- WebSocket-ready event emission
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import math

_LOGGER = logging.getLogger(__name__)


class MoodDimension(str, Enum):
    """Three dimensions for 3D mood scoring."""
    COMFORT = "comfort"      # Physical comfort and ease
    JOY = "joy"             # Emotional happiness and satisfaction
    FRUGALITY = "frugality"  # Resource efficiency and conservation


@dataclass
class MoodScore3D:
    """3D mood score vector.
    
    Attributes:
        comfort: Comfort score (0.0-1.0)
        joy: Joy score (0.0-1.0)
        frugality: Frugality score (0.0-1.0)
        timestamp: When this score was calculated
    """
    comfort: float = 0.5
    joy: float = 0.5
    frugality: float = 0.5
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "comfort": round(self.comfort, 3),
            "joy": round(self.joy, 3),
            "frugality": round(self.frugality, 3),
            "timestamp": self.timestamp.isoformat(),
            "vector": [round(self.comfort, 3), round(self.joy, 3), round(self.frugality, 3)]
        }
    
    def magnitude(self) -> float:
        """Calculate magnitude of the 3D vector."""
        return math.sqrt(self.comfort**2 + self.joy**2 + self.frugality**2)
    
    def normalize(self) -> "MoodScore3D":
        """Return normalized vector."""
        mag = self.magnitude()
        if mag > 0:
            return MoodScore3D(
                comfort=self.comfort / mag,
                joy=self.joy / mag,
                frugality=self.frugality / mag,
                timestamp=self.timestamp
            )
        return MoodScore3D(timestamp=self.timestamp)
    
    def distance_to(self, other: "MoodScore3D") -> float:
        """Calculate Euclidean distance to another score."""
        return math.sqrt(
            (self.comfort - other.comfort)**2 +
            (self.joy - other.joy)**2 +
            (self.frugality - other.frugality)**2
        )


@dataclass
class LiveMoodState:
    """Live mood state with 3D scoring.
    
    Attributes:
        mood: Current mood label
        confidence: Confidence in the mood (0.0-1.0)
        score_3d: 3D mood score vector
        previous_mood: Previous mood (for transition detection)
        transition_progress: How far through transition (0.0-1.0)
        reasons: List of reasons for current mood
        metadata: Additional metadata
    """
    mood: str = "neutral"
    confidence: float = 0.5
    score_3d: MoodScore3D = field(default_factory=MoodScore3D)
    previous_mood: Optional[str] = None
    transition_progress: float = 0.0
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "mood": self.mood,
            "confidence": round(self.confidence, 3),
            "score_3d": self.score_3d.to_dict(),
            "previous_mood": self.previous_mood,
            "transition_progress": round(self.transition_progress, 3),
            "reasons": self.reasons,
            "metadata": self.metadata,
            "is_transitioning": self.transition_progress > 0 and self.transition_progress < 1.0
        }


@dataclass
class MoodTransition:
    """Represents a mood transition in progress.
    
    Attributes:
        from_mood: Starting mood
        to_mood: Target mood
        start_time: When transition started
        duration_seconds: Expected duration
        progress: Current progress (0.0-1.0)
    """
    from_mood: str
    to_mood: str
    start_time: datetime
    duration_seconds: float = 30.0  # 30 second smooth transitions
    progress: float = 0.0
    
    def update(self) -> float:
        """Update progress and return current value.
        
        Returns:
            Current progress (0.0-1.0)
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self.start_time).total_seconds()
        self.progress = min(1.0, elapsed / self.duration_seconds)
        return self.progress
    
    def is_complete(self) -> bool:
        """Check if transition is complete."""
        return self.progress >= 1.0


class LiveMoodEngine:
    """Live mood engine with 3D scoring and real-time updates.
    
    Features:
    - Continuous mood evaluation
    - 3D scoring (Comfort/Joy/Frugality)
    - Smooth transitions between moods
    - Event emission for WebSocket updates
    - Historical tracking
    """
    
    def __init__(self, update_interval_seconds: float = 5.0):
        """Initialize the live mood engine.
        
        Args:
            update_interval_seconds: How often to update mood (default 5s)
        """
        self.update_interval = update_interval_seconds
        self._current_state = LiveMoodState()
        self._transition: Optional[MoodTransition] = None
        self._history: List[LiveMoodState] = []
        self._max_history = 100
        self._callbacks: List[Callable[[LiveMoodState], None]] = []
        self._last_update: Optional[datetime] = None
        
        # Scoring weights
        self._weights = {
            MoodDimension.COMFORT: 0.4,
            MoodDimension.JOY: 0.4,
            MoodDimension.FRUGALITY: 0.2
        }
        
        _LOGGER.info("LiveMoodEngine initialized (interval=%.1fs)", update_interval_seconds)
    
    def update(self, sensor_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> LiveMoodState:
        """Update mood based on sensor data.
        
        Args:
            sensor_data: Home Assistant sensor data
            context: Additional context (time, weather, etc.)
        
        Returns:
            Updated LiveMoodState
        """
        now = datetime.now(timezone.utc)
        self._last_update = now
        
        # Ensure context is never None
        if context is None:
            context = {}
        
        # Calculate 3D scores
        score_3d = self._calculate_3d_score(sensor_data, context)
        
        # Determine mood from scores
        mood, confidence, reasons = self._infer_mood_from_scores(score_3d, context)
        
        # Handle transitions
        if mood != self._current_state.mood:
            self._start_transition(mood)
        
        # Update transition progress
        if self._transition:
            progress = self._transition.update()
            
            # Interpolate scores during transition
            if not self._transition.is_complete():
                score_3d = self._interpolate_scores(
                    self._current_state.score_3d,
                    score_3d,
                    progress
                )
            
            if self._transition.is_complete():
                self._transition = None
        
        # Create new state
        new_state = LiveMoodState(
            mood=mood,
            confidence=confidence,
            score_3d=score_3d,
            previous_mood=self._current_state.mood if self._current_state.mood != mood else self._current_state.previous_mood,
            transition_progress=self._transition.progress if self._transition else 0.0,
            reasons=reasons,
            metadata={
                "sensor_count": len(sensor_data),
                "update_time": now.isoformat(),
                "update_interval": self.update_interval
            }
        )
        
        # Store in history
        self._add_to_history(new_state)
        
        # Update current state
        self._current_state = new_state
        
        # Notify callbacks
        self._notify_callbacks(new_state)
        
        return new_state
    
    def _calculate_3d_score(self, sensor_data: Dict[str, Any], context: Dict[str, Any]) -> MoodScore3D:
        """Calculate 3D mood scores from sensor data.
        
        Args:
            sensor_data: HA sensor data
            context: Additional context
        
        Returns:
            MoodScore3D with calculated scores
        """
        # Comfort score factors:
        # - Temperature in comfort range (20-24°C)
        # - Good lighting (100-400 lux)
        # - Low noise
        # - Media playing (relaxation)
        comfort = 0.5
        
        # Temperature comfort (assuming temperature sensor)
        temp_entity = next((k for k in sensor_data.keys() if "temperature" in k.lower()), None)
        if temp_entity:
            try:
                temp = float(sensor_data[temp_entity].get("state", 20))
                # Comfort range: 20-24°C
                if 20 <= temp <= 24:
                    comfort += 0.2
                elif temp < 18 or temp > 26:
                    comfort -= 0.2
            except (ValueError, TypeError):
                pass
        
        # Lighting comfort
        lux_entity = next((k for k in sensor_data.keys() if "illuminance" in k.lower() or "lux" in k.lower()), None)
        if lux_entity:
            try:
                lux = float(sensor_data[lux_entity].get("state", 200))
                if 100 <= lux <= 400:
                    comfort += 0.15
                elif lux < 50:
                    comfort -= 0.1
            except (ValueError, TypeError):
                pass
        
        # Media playing increases comfort
        media_playing = any(
            sensor_data.get(k, {}).get("state", "").lower() in ("playing", "on")
            for k in sensor_data.keys() if "media" in k.lower()
        )
        if media_playing:
            comfort += 0.1
        
        # Joy score factors:
        # - Presence of people
        # - Social activity
        # - Positive calendar events
        # - Good weather
        joy = 0.5
        
        # Presence increases joy
        presence_detected = any(
            sensor_data.get(k, {}).get("state", "").lower() in ("home", "yes", "on", "true")
            for k in sensor_data.keys() if "presence" in k.lower() or "motion" in k.lower()
        )
        if presence_detected:
            joy += 0.2
        
        # Weather impact on joy
        weather_entity = next((k for k in sensor_data.keys() if "weather" in k.lower()), None)
        if weather_entity:
            weather_state = sensor_data[weather_entity].get("state", "").lower()
            if weather_state in ("sunny", "clear"):
                joy += 0.15
            elif weather_state in ("rainy", "stormy"):
                joy -= 0.1
        
        # Time of day (higher joy during daytime/evening)
        hour = context.get("hour", 12)
        if 9 <= hour <= 21:
            joy += 0.1
        
        # Frugality score factors:
        # - Low energy consumption
        # - Solar production
        # - Efficient appliance usage
        # - Away mode (saving energy)
        frugality = 0.5
        
        # Energy consumption (lower is more frugal)
        power_entity = next((k for k in sensor_data.keys() if "power" in k.lower() or "consumption" in k.lower()), None)
        if power_entity:
            try:
                power = float(sensor_data[power_entity].get("state", 500))
                if power < 300:  # Low consumption
                    frugality += 0.25
                elif power > 1000:  # High consumption
                    frugality -= 0.15
            except (ValueError, TypeError):
                pass
        
        # Solar production (higher is more frugal)
        solar_entity = next((k for k in sensor_data.keys() if "solar" in k.lower() or "pv" in k.lower()), None)
        if solar_entity:
            try:
                solar = float(sensor_data[solar_entity].get("state", 0))
                if solar > 500:
                    frugality += 0.2
            except (ValueError, TypeError):
                pass
        
        # Away mode is frugal
        away_mode = any(
            (sensor_data.get(k, {}) or {}).get("state", "")
            and (sensor_data.get(k, {}) or {}).get("state", "").lower() in ("away", "eco")
            for k in sensor_data.keys()
        )
        if away_mode:
            frugality += 0.15
        
        # Clamp all scores to [0, 1]
        comfort = max(0.0, min(1.0, comfort))
        joy = max(0.0, min(1.0, joy))
        frugality = max(0.0, min(1.0, frugality))
        
        return MoodScore3D(
            comfort=comfort,
            joy=joy,
            frugality=frugality,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _infer_mood_from_scores(self, score_3d: MoodScore3D, context: Dict[str, Any]) -> Tuple[str, float, List[str]]:
        """Infer mood label from 3D scores.
        
        Args:
            score_3d: 3D mood scores
            context: Additional context
        
        Returns:
            Tuple of (mood_label, confidence, reasons)
        """
        reasons = []
        scores = {}
        
        # RELAX: High comfort, moderate joy
        if score_3d.comfort > 0.6 and score_3d.joy > 0.4:
            scores["relax"] = 0.5 * score_3d.comfort + 0.5 * score_3d.joy
            reasons.append(f"High comfort ({score_3d.comfort:.2f}) and joy ({score_3d.joy:.2f})")
        
        # FOCUS: Moderate comfort, lower joy, high frugality
        if score_3d.comfort > 0.4 and score_3d.frugality > 0.6:
            scores["focus"] = 0.4 * score_3d.comfort + 0.3 * score_3d.frugality + 0.3 * (1 - score_3d.joy)
            reasons.append(f"Efficient mode (frugality={score_3d.frugality:.2f})")
        
        # ACTIVE: High joy, moderate comfort
        if score_3d.joy > 0.6 and score_3d.comfort > 0.4:
            scores["active"] = 0.6 * score_3d.joy + 0.4 * score_3d.comfort
            reasons.append(f"High energy (joy={score_3d.joy:.2f})")
        
        # AWAY: Low everything, high frugality
        if score_3d.frugality > 0.7 and score_3d.comfort < 0.4 and score_3d.joy < 0.4:
            scores["away"] = 0.7 * score_3d.frugality + 0.3 * (1 - score_3d.comfort)
            reasons.append("Away mode detected")
        
        # SLEEP: Very low joy and comfort, nighttime
        hour = context.get("hour", 12) if context else 12
        if hour >= 22 or hour <= 6:
            if score_3d.comfort < 0.5 and score_3d.joy < 0.3:
                scores["sleep"] = 0.6 * (1 - score_3d.joy) + 0.4 * (1 - score_3d.comfort)
                reasons.append("Nighttime with low activity")
        
        # ALERT: Low comfort (discomfort detected)
        if score_3d.comfort < 0.3:
            scores["alert"] = 1 - score_3d.comfort
            reasons.append(f"Discomfort detected (comfort={score_3d.comfort:.2f})")
        
        # Determine winner
        if not scores:
            return "neutral", 0.5, ["No clear mood indicators"]
        
        mood = max(scores, key=scores.get)
        confidence = min(0.95, scores[mood] + 0.2)  # Boost confidence slightly
        
        return mood, confidence, reasons
    
    def _start_transition(self, target_mood: str) -> None:
        """Start a mood transition.
        
        Args:
            target_mood: Target mood to transition to
        """
        self._transition = MoodTransition(
            from_mood=self._current_state.mood,
            to_mood=target_mood,
            start_time=datetime.now(timezone.utc),
            duration_seconds=30.0  # Smooth 30s transition
        )
        _LOGGER.info(
            "Mood transition: %s -> %s",
            self._current_state.mood, target_mood
        )
    
    def _interpolate_scores(self, from_score: MoodScore3D, to_score: MoodScore3D, t: float) -> MoodScore3D:
        """Interpolate between two 3D scores.
        
        Args:
            from_score: Starting score
            to_score: Target score
            t: Interpolation factor (0.0-1.0)
        
        Returns:
            Interpolated MoodScore3D
        """
        # Smooth easing (ease-in-out)
        t_smooth = t * t * (3 - 2 * t)
        
        return MoodScore3D(
            comfort=from_score.comfort + (to_score.comfort - from_score.comfort) * t_smooth,
            joy=from_score.joy + (to_score.joy - from_score.joy) * t_smooth,
            frugality=from_score.frugality + (to_score.frugality - from_score.frugality) * t_smooth,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _add_to_history(self, state: LiveMoodState) -> None:
        """Add state to history.
        
        Args:
            state: State to add
        """
        self._history.append(state)
        
        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def _notify_callbacks(self, state: LiveMoodState) -> None:
        """Notify registered callbacks.
        
        Args:
            state: New state
        """
        for callback in self._callbacks:
            try:
                callback(state)
            except Exception as e:
                _LOGGER.error("Callback error in LiveMoodEngine: %s", e)
    
    def on_update(self, callback: Callable[[LiveMoodState], None]) -> None:
        """Register a callback for mood updates.
        
        Args:
            callback: Function to call with new LiveMoodState
        """
        self._callbacks.append(callback)
    
    def get_current_state(self) -> LiveMoodState:
        """Get current mood state.
        
        Returns:
            Current LiveMoodState
        """
        return self._current_state
    
    def get_history(self, limit: int = 10) -> List[LiveMoodState]:
        """Get mood history.
        
        Args:
            limit: Number of entries to return
        
        Returns:
            List of LiveMoodState, most recent first
        """
        return list(reversed(self._history[-limit:]))
    
    def get_3d_score(self) -> MoodScore3D:
        """Get current 3D score.
        
        Returns:
            Current MoodScore3D
        """
        return self._current_state.score_3d
    
    def reset(self) -> None:
        """Reset the engine to initial state."""
        self._current_state = LiveMoodState()
        self._transition = None
        self._history = []
        self._last_update = None
        _LOGGER.info("LiveMoodEngine reset")


# Singleton instance
_live_mood_engine: Optional[LiveMoodEngine] = None


def get_live_mood_engine() -> LiveMoodEngine:
    """Get the singleton LiveMoodEngine instance.
    
    Returns:
        LiveMoodEngine instance
    """
    global _live_mood_engine
    if _live_mood_engine is None:
        _live_mood_engine = LiveMoodEngine()
    return _live_mood_engine


__all__ = [
    "MoodDimension",
    "MoodScore3D",
    "LiveMoodState",
    "MoodTransition",
    "LiveMoodEngine",
    "get_live_mood_engine"
]
