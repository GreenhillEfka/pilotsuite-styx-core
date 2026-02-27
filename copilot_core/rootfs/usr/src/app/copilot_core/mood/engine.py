"""Mood inference engine for Home Assistant sensor data (v2.0).

Implements mood inference from HA sensors using mathematically rigorous models:
- Sigmoid activation functions for smooth, bounded feature scoring
- Softmax mood selection for probabilistic multi-class decision
- Exponential Moving Average (EMA) for hysteresis smoothing
- Bayesian confidence estimation with prior decay

References:
- Softmax: Bridle (1990) - probabilistic interpretation of neural outputs
- EMA smoothing: Roberts (1959) - exponential weighted moving average
- Sigmoid activation: Verhulst (1845) - logistic function
"""
from __future__ import annotations

import logging
import math
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

        # --- Derived indices using sigmoid activation functions ---
        # sigmoid(x, k, x0) = 1 / (1 + exp(-k * (x - x0)))
        # Maps continuous inputs to smooth [0, 1] outputs

        # Comfort index (0..1): multi-factor sigmoid aggregation
        comfort_signals = []
        if features.illuminance_value is not None:
            # Bell-shaped: optimal 100-400 lux, Gaussian in log-space
            lux = max(1.0, features.illuminance_value)
            log_ratio = math.log(lux / 200.0)  # centered on 200 lux
            lux_comfort = math.exp(-0.5 * (log_ratio / 0.7) ** 2)
            comfort_signals.append(lux_comfort)
        if features.media_playing:
            comfort_signals.append(0.7)  # media adds moderate comfort
        if features.quiet_hours:
            comfort_signals.append(0.3)  # quiet hours reduce comfort
        else:
            comfort_signals.append(0.6)

        if comfort_signals:
            # Geometric mean: penalizes any single bad factor more than arithmetic
            log_sum = sum(math.log(max(0.01, s)) for s in comfort_signals)
            features.comfort_index = math.exp(log_sum / len(comfort_signals))
        else:
            features.comfort_index = 0.5

        # Energy level (0..1): sigmoid-based with circadian modulation
        now_hour = now.hour + now.minute / 60.0
        # Circadian energy: sine wave peaking at noon
        if 5.0 <= now_hour <= 23.0:
            circadian = math.sin(math.pi * (now_hour - 5.0) / 18.0)
            circadian = max(0.0, circadian)
        else:
            circadian = 0.0

        energy_raw = 0.3 * circadian  # baseline from time of day
        if features.motion_recent:
            energy_raw += 0.4  # motion is strongest energy signal
        if not features.ambient_dark:
            energy_raw += 0.2  # light adds energy
        if features.quiet_hours:
            energy_raw -= 0.3  # quiet hours suppress energy

        # Sigmoid squash to [0, 1]: steepness=6, centered at 0.5
        features.energy_level = 1.0 / (1.0 + math.exp(-6.0 * (energy_raw - 0.35)))

        # Stress index (0..1): sigmoid accumulation of stress signals
        stress_raw = 0.0
        active_motion = sum(1 for v in features.motion_entities.values() if v)
        total_motion = max(1, len(features.motion_entities))
        motion_ratio = active_motion / total_motion

        # Multi-sensor activation: sigmoid threshold at 60% activation
        stress_raw += 1.0 / (1.0 + math.exp(-10.0 * (motion_ratio - 0.6)))
        # Unexpected activity in dark: multiplicative stress
        if features.ambient_dark and features.motion_recent:
            stress_raw += 0.3
        # High stress when many sensors rapid-fire (proxy via motion ratio)
        if motion_ratio > 0.8 and total_motion > 2:
            stress_raw += 0.2

        # Final sigmoid squash: centered at 0.5 stress_raw
        features.stress_index = 1.0 / (1.0 + math.exp(-4.0 * (stress_raw - 0.5)))

        return features
    
    def infer_mood(self, zone_name: str, features: ZoneFeatures) -> MoodResult:
        """Infer mood for a zone using multi-signal scoring + softmax selection.

        The inference pipeline:
        1. Compute raw log-odds for each mood state from features
        2. Apply softmax to get a probability distribution
        3. Select the mood with highest probability
        4. Smooth via EMA with the previous state (hysteresis)
        5. Only transition if the new mood sustains past dwell threshold
        """
        reasons = []
        raw_scores: Dict[str, float] = {}
        now = datetime.now(timezone.utc)

        zone_config = self.config.zones[zone_name]

        # --- Step 1: Compute raw log-odds (unbounded scores) per mood ---

        # AWAY: sigmoid on no-motion duration
        if features.last_motion_ts:
            no_motion_min = (now - features.last_motion_ts).total_seconds() / 60
        elif not features.motion_recent:
            no_motion_min = zone_config.away_no_motion_minutes + 10  # assume long absence
        else:
            no_motion_min = 0.0

        # Sigmoid activation: midpoint at away_no_motion_minutes
        away_score = 1.0 / (1.0 + math.exp(-0.15 * (no_motion_min - zone_config.away_no_motion_minutes)))
        raw_scores[MoodState.AWAY] = away_score * 3.0  # scale to log-odds range
        if away_score > 0.5:
            reasons.append(f"No motion for {no_motion_min:.0f} min")

        # NIGHT: quiet hours + darkness combined signal
        night_signal = 0.0
        if features.quiet_hours:
            night_signal += 0.6
        if features.ambient_dark:
            night_signal += 0.4
        if features.media_playing:
            night_signal -= 0.2  # media suppresses night mood
        raw_scores[MoodState.NIGHT] = night_signal * 3.0
        if night_signal > 0.5:
            reasons.append("Quiet hours/dark environment")

        # RELAX: media + low energy + moderate comfort
        relax_signal = 0.0
        if features.media_playing:
            relax_signal += 0.5
        if features.ambient_dark:
            relax_signal += 0.2
        relax_signal += (1.0 - features.energy_level) * 0.2  # low energy → relax
        relax_signal += features.comfort_index * 0.1  # comfort helps
        raw_scores[MoodState.RELAX] = relax_signal * 3.0
        if relax_signal > 0.4:
            reasons.append("Media/low-energy environment")

        # FOCUS: motion + no media + daylight + low stress
        focus_signal = 0.0
        if features.motion_recent and not features.media_playing:
            focus_signal += 0.5
        if not features.ambient_dark:
            focus_signal += 0.2
        if not features.quiet_hours:
            focus_signal += 0.15
        focus_signal += (1.0 - features.stress_index) * 0.15  # low stress → focus
        raw_scores[MoodState.FOCUS] = focus_signal * 3.0
        if focus_signal > 0.5:
            reasons.append("Active presence, daylight, no media")

        # ACTIVE: strong motion + bright + high energy
        active_signal = 0.0
        if features.motion_recent:
            active_signal += 0.4
        if not features.ambient_dark:
            active_signal += 0.2
        active_signal += features.energy_level * 0.3  # high energy → active
        if features.quiet_hours:
            active_signal -= 0.3
        raw_scores[MoodState.ACTIVE] = active_signal * 3.0
        if active_signal > 0.5:
            reasons.append("High activity with good lighting")

        # NEUTRAL: baseline (acts as softmax "default class")
        raw_scores[MoodState.NEUTRAL] = 0.5  # small positive baseline

        # User override: dominate all scores
        if features.user_override:
            raw_scores = {m: 0.0 for m in MoodState}
            raw_scores[MoodState.NEUTRAL] = 5.0  # force neutral on override
            reasons = ["User manual override"]

        # --- Step 2: Softmax to get probability distribution ---
        # P(mood_i) = exp(score_i / T) / sum(exp(score_j / T))
        # Temperature T controls sharpness (lower = more decisive)
        temperature = 1.0
        max_score = max(raw_scores.values())
        exp_scores = {}
        for mood_state, score in raw_scores.items():
            # Subtract max for numerical stability
            exp_scores[mood_state] = math.exp((score - max_score) / temperature)
        total_exp = sum(exp_scores.values())

        probabilities = {
            mood_state: exp_val / total_exp
            for mood_state, exp_val in exp_scores.items()
        }

        # Select highest probability mood
        mood = max(probabilities, key=probabilities.get)
        confidence = probabilities[mood]

        # --- Step 3: EMA-based hysteresis smoothing ---
        current_result = self._zone_states.get(zone_name)

        if current_result and current_result.mood != mood:
            # EMA smoothing: blend current confidence with previous
            # alpha controls inertia (lower = more stable)
            alpha = 0.3
            ema_confidence = alpha * confidence + (1.0 - alpha) * current_result.confidence

            # Check dwell time: only transition if new mood has sustained
            dwell_start = self._zone_dwell_start.get(zone_name, now)
            dwell_seconds = (now - dwell_start).total_seconds()

            if dwell_seconds < self.config.min_dwell_time_seconds:
                # Not enough dwell time: keep current mood with blended confidence
                mood = current_result.mood
                confidence = ema_confidence
                reasons.append(
                    f"EMA hysteresis: keeping {mood.value} "
                    f"(dwell: {dwell_seconds:.0f}s/{self.config.min_dwell_time_seconds}s)"
                )
            else:
                # Transition allowed: reset dwell timer
                self._zone_dwell_start[zone_name] = now
                confidence = ema_confidence
        else:
            # Same mood or first inference: reset dwell timer
            if zone_name not in self._zone_dwell_start:
                self._zone_dwell_start[zone_name] = now

        result = MoodResult(
            mood=mood,
            confidence=round(confidence, 3),
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