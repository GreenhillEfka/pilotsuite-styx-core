"""Mood inference engine for Home Assistant sensor data.

Implements the mood_module v0.1 spec: local-only mood inference from HA sensors.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


class MoodState(str, Enum):
    """Mood states as defined in mood_module v0.1 spec."""
    
    AWAY = "away"
    NIGHT = "night"
    RELAX = "relax"
    FOCUS = "focus"
    ACTIVE = "active"
    NEUTRAL = "neutral"  # fallback


@dataclass
class ZoneFeatures:
    """Derived features for a zone."""

    last_motion_ts: Optional[datetime] = None
    motion_recent: bool = False
    ambient_dark: bool = False
    media_playing: bool = False
    quiet_hours: bool = False
    user_override: bool = False

    # Derived indices (0.0 .. 1.0)
    stress_index: float = 0.0
    comfort_index: float = 0.5
    energy_level: float = 0.5

    # Raw sensor values for debugging
    motion_entities: Dict[str, bool] = field(default_factory=dict)
    illuminance_value: Optional[float] = None
    media_state: Optional[str] = None


@dataclass
class MoodResult:
    """Result of mood inference for a zone."""
    
    mood: MoodState
    confidence: float
    reasons: List[str]
    features: ZoneFeatures
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood": self.mood.value,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "timestamp": self.timestamp.isoformat(),
            "features": {
                "last_motion_ts": self.features.last_motion_ts.isoformat() if self.features.last_motion_ts else None,
                "motion_recent": self.features.motion_recent,
                "ambient_dark": self.features.ambient_dark,
                "media_playing": self.features.media_playing,
                "quiet_hours": self.features.quiet_hours,
                "user_override": self.features.user_override,
                "illuminance_value": self.features.illuminance_value,
                "media_state": self.features.media_state,
                "stress_index": round(self.features.stress_index, 3),
                "comfort_index": round(self.features.comfort_index, 3),
                "energy_level": round(self.features.energy_level, 3),
            }
        }


@dataclass
class ZoneConfig:
    """Configuration for a zone."""
    
    name: str
    motion_entities: List[str] = field(default_factory=list)
    light_entities: List[str] = field(default_factory=list)
    media_entities: List[str] = field(default_factory=list)
    illuminance_entity: Optional[str] = None
    
    # Thresholds
    motion_recent_minutes: int = 5
    dark_lux_threshold: float = 40.0
    away_no_motion_minutes: int = 30
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:00"


@dataclass
class MoodConfig:
    """Global mood configuration."""
    
    zones: Dict[str, ZoneConfig] = field(default_factory=dict)
    min_dwell_time_seconds: int = 600  # 10 minutes
    action_cooldown_seconds: int = 120  # 2 minutes


class MoodEngine:
    """Core mood inference engine."""
    
    def __init__(self, config: MoodConfig):
        self.config = config
        self._zone_states: Dict[str, MoodResult] = {}
        self._zone_dwell_start: Dict[str, datetime] = {}
    
    def compute_zone_features(self, zone_name: str, sensor_data: Dict[str, Any]) -> ZoneFeatures:
        """Extract features for a zone from sensor data."""
        
        if zone_name not in self.config.zones:
            raise ValueError(f"Unknown zone: {zone_name}")
        
        zone_config = self.config.zones[zone_name]
        features = ZoneFeatures()
        now = datetime.now(timezone.utc)
        
        # Motion analysis
        motion_states = {}
        latest_motion = None
        any_motion = False
        
        for entity_id in zone_config.motion_entities:
            state = sensor_data.get(entity_id, {}).get("state")
            is_on = state in ("on", "True", True, 1)
            motion_states[entity_id] = is_on
            
            if is_on:
                any_motion = True
                last_changed = sensor_data.get(entity_id, {}).get("last_changed")
                if last_changed:
                    try:
                        if isinstance(last_changed, str):
                            motion_time = datetime.fromisoformat(last_changed.replace('Z', '+00:00'))
                        else:
                            motion_time = last_changed
                        
                        if latest_motion is None or motion_time > latest_motion:
                            latest_motion = motion_time
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not parse last_changed for %s: %s", entity_id, last_changed)
        
        features.motion_entities = motion_states
        features.last_motion_ts = latest_motion
        
        # Recent motion check
        if latest_motion:
            motion_age = (now - latest_motion).total_seconds() / 60
            features.motion_recent = motion_age <= zone_config.motion_recent_minutes
        else:
            features.motion_recent = any_motion
        
        # Illuminance
        if zone_config.illuminance_entity:
            illuminance_data = sensor_data.get(zone_config.illuminance_entity, {})
            try:
                lux_value = float(illuminance_data.get("state", 0))
                features.illuminance_value = lux_value
                features.ambient_dark = lux_value < zone_config.dark_lux_threshold
            except (ValueError, TypeError):
                _LOGGER.warning("Could not parse illuminance for %s", zone_config.illuminance_entity)
                features.ambient_dark = self._is_night_hours(now, zone_config)
        else:
            # Fallback to time-based dark detection
            features.ambient_dark = self._is_night_hours(now, zone_config)
        
        # Media playing
        for entity_id in zone_config.media_entities:
            media_data = sensor_data.get(entity_id, {})
            state = media_data.get("state", "").lower()
            features.media_state = state
            
            if state in ("playing", "on"):
                features.media_playing = True
                break
        
        # Quiet hours
        features.quiet_hours = self._is_quiet_hours(now, zone_config)
        
        # User override (simplified - could be expanded)
        override_entity = f"input_boolean.mood_manual_override_{zone_name}"
        if override_entity in sensor_data:
            override_state = sensor_data[override_entity].get("state")
            features.user_override = override_state in ("on", "True", True, 1)

        # --- Derived indices ---

        # Comfort index (0..1): high when appropriate light + media + not quiet hours
        comfort = 0.5
        if features.illuminance_value is not None:
            # Optimal lux range ~100-400 for living areas
            if 100 <= features.illuminance_value <= 400:
                comfort += 0.2
            elif features.illuminance_value < 20:
                comfort -= 0.15
        if features.media_playing:
            comfort += 0.15
        if features.quiet_hours:
            comfort -= 0.1
        features.comfort_index = max(0.0, min(1.0, comfort))

        # Energy level (0..1): high during daytime with recent motion
        energy = 0.5
        if features.motion_recent:
            energy += 0.25
        if not features.ambient_dark:
            energy += 0.15
        if features.quiet_hours:
            energy -= 0.3
        features.energy_level = max(0.0, min(1.0, energy))

        # Stress index (0..1): elevated when many sensors active + rapid changes
        stress = 0.0
        active_motion = sum(1 for v in features.motion_entities.values() if v)
        total_motion = max(1, len(features.motion_entities))
        if active_motion / total_motion > 0.7 and total_motion > 1:
            stress += 0.3
        if features.ambient_dark and features.motion_recent:
            stress += 0.15  # unexpected activity in dark
        features.stress_index = max(0.0, min(1.0, stress))

        return features
    
    def infer_mood(self, zone_name: str, features: ZoneFeatures) -> MoodResult:
        """Infer mood for a zone based on features."""
        
        reasons = []
        scores = {}
        
        # Rule-based scoring (as per spec)
        
        # AWAY: no motion for extended period
        if not features.motion_recent:
            if features.last_motion_ts:
                no_motion_minutes = (datetime.now(timezone.utc) - features.last_motion_ts).total_seconds() / 60
                if no_motion_minutes >= self.config.zones[zone_name].away_no_motion_minutes:
                    scores[MoodState.AWAY] = 1.0
                    reasons.append(f"No motion for {no_motion_minutes:.1f} minutes")
            else:
                # No motion detected at all
                scores[MoodState.AWAY] = 0.8
                reasons.append("No motion sensors active")
        
        # NIGHT: quiet hours and dark
        if features.quiet_hours and features.ambient_dark:
            scores[MoodState.NIGHT] = 0.9
            reasons.append("Quiet hours and dark")
        elif features.quiet_hours:
            scores[MoodState.NIGHT] = 0.6
            reasons.append("Quiet hours")
        elif features.ambient_dark and not features.media_playing:
            scores[MoodState.NIGHT] = 0.4
            reasons.append("Dark environment")
        
        # RELAX: media playing in dark/evening
        if features.media_playing and features.ambient_dark:
            scores[MoodState.RELAX] = 0.8
            reasons.append("Media playing in dark environment")
        elif features.media_playing:
            scores[MoodState.RELAX] = 0.5
            reasons.append("Media playing")
        
        # FOCUS: motion recent, not quiet hours, no media
        if (features.motion_recent and 
            not features.quiet_hours and 
            not features.media_playing and
            not features.ambient_dark):
            scores[MoodState.FOCUS] = 0.7
            reasons.append("Active presence, no media, daylight hours")
        
        # ACTIVE: motion + bright + not quiet
        if (features.motion_recent and 
            not features.ambient_dark and 
            not features.quiet_hours):
            scores[MoodState.ACTIVE] = 0.6
            reasons.append("Active with good lighting")
        
        # User override
        if features.user_override:
            scores = {}  # Clear automatic scores
            reasons = ["User manual override"]
        
        # Determine winning mood
        if not scores:
            mood = MoodState.NEUTRAL
            confidence = 0.5
            reasons = ["No clear mood indicators"]
        else:
            mood = max(scores, key=scores.get)
            confidence = scores[mood]
        
        # Apply hysteresis for stability
        current_mood = self._zone_states.get(zone_name)
        if current_mood and current_mood.mood != mood:
            # Check dwell time
            dwell_start = self._zone_dwell_start.get(zone_name, datetime.now(timezone.utc))
            dwell_seconds = (datetime.now(timezone.utc) - dwell_start).total_seconds()
            
            if dwell_seconds < self.config.min_dwell_time_seconds:
                # Keep current mood, but reduce confidence
                mood = current_mood.mood
                confidence = confidence * 0.8
                reasons.append(f"Hysteresis: keeping {mood.value} (dwell: {dwell_seconds:.0f}s)")
            else:
                # Allow transition
                self._zone_dwell_start[zone_name] = datetime.now(timezone.utc)
        else:
            # Same mood or first inference
            if zone_name not in self._zone_dwell_start:
                self._zone_dwell_start[zone_name] = datetime.now(timezone.utc)
        
        result = MoodResult(
            mood=mood,
            confidence=confidence,
            reasons=reasons,
            features=features
        )
        
        self._zone_states[zone_name] = result
        return result
    
    def _is_night_hours(self, dt: datetime, zone_config: ZoneConfig) -> bool:
        """Check if current time is in night hours (rough approximation)."""
        # Simplified: assume always dark during typical sleep hours
        hour = dt.hour
        return hour < 7 or hour > 22
    
    def _is_quiet_hours(self, dt: datetime, zone_config: ZoneConfig) -> bool:
        """Check if current time is in quiet hours."""
        try:
            # Parse quiet hours (simplified)
            start_hour, start_min = map(int, zone_config.quiet_hours_start.split(':'))
            end_hour, end_min = map(int, zone_config.quiet_hours_end.split(':'))
            
            current_minutes = dt.hour * 60 + dt.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            if start_minutes > end_minutes:
                # Crosses midnight
                return current_minutes >= start_minutes or current_minutes <= end_minutes
            else:
                return start_minutes <= current_minutes <= end_minutes
                
        except (ValueError, IndexError):
            _LOGGER.warning("Could not parse quiet hours: %s - %s", 
                           zone_config.quiet_hours_start, zone_config.quiet_hours_end)
            return False
    
    def get_zone_mood(self, zone_name: str) -> Optional[MoodResult]:
        """Get current mood for a zone."""
        return self._zone_states.get(zone_name)
    
    def list_zones(self) -> List[str]:
        """Get list of configured zones."""
        return list(self.config.zones.keys())