"""State Neurons for PilotSuite neural orchestration.

State neurons maintain smoothed, inertial values that represent
the user's internal state. Unlike context neurons (which are
immediate and objective), state neurons integrate over time.

State Neurons:
- EnergyLevel: Physical/mental energy (0=exhausted, 1=energized)
- StressIndex: Stress/tension level (0=relaxed, 1=stressed)
- RoutineStability: How stable the routine is (0=chaotic, 1=stable)
- SleepDebt: Accumulated sleep deficit (0=well-rested, 1=sleep-deprived)
- AttentionLoad: Cognitive load (0=unfocused, 1=deep-focus)
- ComfortIndex: Physical comfort (0=uncomfortable, 1=comfortable)

These values change slowly and are influenced by:
- Time of day patterns
- Activity history
- Environmental factors
- Explicit user feedback
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone, time
from typing import Any, Dict, List, Optional

from .base import BaseNeuron, NeuronConfig, NeuronState, NeuronType, StateNeuron

_LOGGER = logging.getLogger(__name__)


# Default configurations for state neurons
DEFAULT_CONFIGS = {
    "energy_level": {
        "threshold": 0.5,
        "decay_rate": 0.05,  # Slow decay
        "smoothing_factor": 0.1,  # Very smooth
        "weights": {
            "time_of_day": 0.3,
            "activity_duration": 0.2,
            "sleep_quality": 0.3,
            "exercise": 0.2,
        }
    },
    "stress_index": {
        "threshold": 0.6,
        "decay_rate": 0.08,
        "smoothing_factor": 0.15,
        "weights": {
            "calendar_load": 0.25,
            "notification_frequency": 0.2,
            "routine_disruption": 0.25,
            "time_pressure": 0.3,
        }
    },
    "routine_stability": {
        "threshold": 0.7,
        "decay_rate": 0.03,  # Very slow decay
        "smoothing_factor": 0.05,  # Very smooth
        "weights": {
            "schedule_variance": 0.4,
            "location_stability": 0.3,
            "activity_consistency": 0.3,
        }
    },
    "sleep_debt": {
        "threshold": 0.5,
        "decay_rate": 0.02,  # Extremely slow decay
        "smoothing_factor": 0.05,
        "weights": {
            "sleep_duration": 0.5,
            "sleep_quality": 0.3,
            "time_since_sleep": 0.2,
        }
    },
    "attention_load": {
        "threshold": 0.5,
        "decay_rate": 0.15,  # Faster decay
        "smoothing_factor": 0.2,
        "weights": {
            "focus_time": 0.3,
            "interruptions": 0.25,
            "task_complexity": 0.25,
            "media_activity": 0.2,
        }
    },
    "comfort_index": {
        "threshold": 0.6,
        "decay_rate": 0.1,
        "smoothing_factor": 0.15,
        "weights": {
            "temperature": 0.3,
            "humidity": 0.15,
            "light_level": 0.2,
            "noise_level": 0.2,
            "air_quality": 0.15,
        }
    }
}


class EnergyLevelNeuron(StateNeuron):
    """Evaluates physical/mental energy level.
    
    Energy is high when:
    - Well-rested (low sleep debt)
    - During active hours
    - After exercise
    - Morning/afternoon
    
    Energy is low when:
    - Sleep deprived
    - Late night/early morning
    - After prolonged activity
    - During recovery
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="energy_level",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["energy_level"]
            )
        super().__init__(config)
        self._activity_start: Optional[datetime] = None
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate energy level from context."""
        states = context.get("states", {})
        now = context.get("now", datetime.now(timezone.utc))
        
        # Time of day factor (circadian rhythm)
        hour = now.hour
        if 6 <= hour < 10:  # Morning
            time_factor = 0.8
        elif 10 <= hour < 14:  # Late morning/noon
            time_factor = 0.9
        elif 14 <= hour < 18:  # Afternoon
            time_factor = 0.7
        elif 18 <= hour < 22:  # Evening
            time_factor = 0.5
        else:  # Night
            time_factor = 0.2
        
        # Sleep quality factor (if available)
        sleep_factor = 0.5
        sleep_entity = states.get("sensor.sleep_quality")
        if sleep_entity:
            try:
                sleep_factor = float(sleep_entity.get("state", 0.5)) / 100.0
            except (ValueError, TypeError):
                pass
        
        # Activity duration factor (energy depletion)
        activity_factor = 0.7
        if self._activity_start:
            duration = (now - self._activity_start).total_seconds() / 3600
            # Energy depletes over time during activity
            activity_factor = max(0.3, 0.9 - (duration * 0.05))
        
        # Exercise boost factor
        exercise_factor = 0.5
        exercise_entity = states.get("sensor.exercise_today")
        if exercise_entity:
            try:
                # If exercised today, slight boost
                exercise_factor = 0.7 if exercise_entity.get("state") == "on" else 0.5
            except (ValueError, TypeError):
                pass
        
        # Weighted average
        weights = self.config.weights
        value = (
            time_factor * weights.get("time_of_day", 0.3) +
            activity_factor * weights.get("activity_duration", 0.2) +
            sleep_factor * weights.get("sleep_quality", 0.3) +
            exercise_factor * weights.get("exercise", 0.2)
        )
        
        return min(1.0, max(0.0, value))
    
    def set_activity_start(self, start_time: datetime):
        """Mark the start of an activity period."""
        self._activity_start = start_time
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "EnergyLevelNeuron":
        return cls(config)


class StressIndexNeuron(StateNeuron):
    """Evaluates stress/tension level.
    
    High stress when:
    - Calendar overloaded
    - Frequent notifications/interruptions
    - Routine disrupted
    - Time pressure (upcoming deadlines)
    
    Low stress when:
    - Schedule clear
    - Quiet environment
    - Routine stable
    - No immediate deadlines
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="stress_index",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["stress_index"]
            )
        super().__init__(config)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate stress level from context."""
        states = context.get("states", {})
        now = context.get("now", datetime.now(timezone.utc))
        
        # Calendar load factor
        calendar_factor = 0.3
        calendar_entity = states.get("calendar.main")
        if calendar_entity:
            events = calendar_entity.get("attributes", {}).get("events_today", 0)
            # More events = more stress (capped at 10 events)
            calendar_factor = min(1.0, events / 10.0)
        
        # Notification frequency factor
        notification_factor = 0.3
        notification_entity = states.get("sensor.notification_rate")
        if notification_entity:
            try:
                # Rate per hour, normalize to 0-1
                rate = float(notification_entity.get("state", 0))
                notification_factor = min(1.0, rate / 20.0)  # 20/hr = max
            except (ValueError, TypeError):
                pass
        
        # Routine disruption factor
        routine_factor = 0.3
        routine_entity = states.get("sensor.routine_deviation")
        if routine_entity:
            try:
                routine_factor = float(routine_entity.get("state", 0.3))
            except (ValueError, TypeError):
                pass
        
        # Time pressure factor (upcoming events/deadlines)
        time_pressure_factor = 0.3
        next_event = states.get("calendar.next_event")
        if next_event:
            try:
                # Check if event is within 30 minutes
                event_time_str = next_event.get("attributes", {}).get("start_time")
                if event_time_str:
                    event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                    minutes_until = (event_time - now).total_seconds() / 60
                    if minutes_until < 30:
                        time_pressure_factor = min(1.0, minutes_until / 30.0)
                    elif minutes_until < 60:
                        time_pressure_factor = 0.6
                    else:
                        time_pressure_factor = 0.3
            except (ValueError, TypeError):
                pass
        
        # Weighted average
        weights = self.config.weights
        value = (
            calendar_factor * weights.get("calendar_load", 0.25) +
            notification_factor * weights.get("notification_frequency", 0.2) +
            routine_factor * weights.get("routine_disruption", 0.25) +
            time_pressure_factor * weights.get("time_pressure", 0.3)
        )
        
        return min(1.0, max(0.0, value))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "StressIndexNeuron":
        return cls(config)


class RoutineStabilityNeuron(StateNeuron):
    """Evaluates how stable/routine the current state is.
    
    High stability when:
    - Consistent schedule
    - Location stable (home/work)
    - Activities predictable
    - Time patterns match history
    
    Low stability when:
    - Unusual schedule
    - Location changes frequently
    - Activities unexpected
    - Deviations from patterns
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="routine_stability",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["routine_stability"]
            )
        super().__init__(config)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate routine stability from context."""
        states = context.get("states", {})
        history = context.get("history", {})
        
        # Schedule variance factor
        schedule_factor = 0.7
        schedule_entity = states.get("sensor.schedule_variance")
        if schedule_entity:
            try:
                # Lower variance = higher stability
                variance = float(schedule_entity.get("state", 0.3))
                schedule_factor = 1.0 - min(1.0, variance)
            except (ValueError, TypeError):
                pass
        
        # Location stability factor
        location_factor = 0.7
        location_entity = states.get("sensor.location_changes_today")
        if location_entity:
            try:
                changes = float(location_entity.get("state", 0))
                # Fewer changes = more stable
                location_factor = max(0.2, 1.0 - (changes * 0.1))
            except (ValueError, TypeError):
                pass
        
        # Activity consistency factor
        activity_factor = 0.7
        activity_entity = states.get("sensor.activity_consistency")
        if activity_entity:
            try:
                activity_factor = float(activity_entity.get("state", 0.7))
            except (ValueError, TypeError):
                pass
        
        # Historical pattern match
        pattern_factor = 0.7
        hour = context.get("now", datetime.now(timezone.utc)).hour
        typical_activity = history.get("typical_activity", {}).get(str(hour))
        current_activity = context.get("current_activity")
        if typical_activity and current_activity:
            pattern_factor = 1.0 if typical_activity == current_activity else 0.5
        
        # Weighted average
        weights = self.config.weights
        value = (
            schedule_factor * weights.get("schedule_variance", 0.4) +
            location_factor * weights.get("location_stability", 0.3) +
            activity_factor * weights.get("activity_consistency", 0.3)
        )
        
        return min(1.0, max(0.0, value))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "RoutineStabilityNeuron":
        return cls(config)


class SleepDebtNeuron(StateNeuron):
    """Evaluates accumulated sleep deficit.
    
    Low debt when:
    - Full sleep last night (7-9 hours)
    - Consistent sleep schedule
    - Recent nap/rest
    - Good sleep quality
    
    High debt when:
    - Short sleep duration
    - Irregular sleep times
    - Multiple nights of poor sleep
    - Long time since sleep
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="sleep_debt",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["sleep_debt"]
            )
        super().__init__(config)
        self._last_sleep_duration: float = 7.0  # Default 7 hours
        self._accumulated_debt: float = 0.0
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate sleep debt from context."""
        states = context.get("states", {})
        now = context.get("now", datetime.now(timezone.utc))
        
        # Sleep duration factor
        duration_factor = 0.5  # Neutral
        sleep_entity = states.get("sensor.sleep_duration")
        if sleep_entity:
            try:
                hours = float(sleep_entity.get("state", 7))
                self._last_sleep_duration = hours
                # Optimal: 7-9 hours
                # <6 = high debt, >9 = oversleeping (also not ideal)
                if 7 <= hours <= 9:
                    duration_factor = 0.1  # Low debt
                elif hours >= 6:
                    duration_factor = 0.3  # Moderate
                else:
                    duration_factor = min(1.0, (9 - hours) / 4)  # High debt
            except (ValueError, TypeError):
                pass
        
        # Sleep quality factor
        quality_factor = 0.5
        quality_entity = states.get("sensor.sleep_quality_score")
        if quality_entity:
            try:
                quality = float(quality_entity.get("state", 50)) / 100.0
                quality_factor = 1.0 - quality  # Low quality = high debt
            except (ValueError, TypeError):
                pass
        
        # Time since sleep factor
        time_factor = 0.5
        last_sleep = states.get("sensor.last_sleep_end")
        if last_sleep:
            try:
                end_time_str = last_sleep.get("state")
                if end_time_str:
                    end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    hours_awake = (now - end_time).total_seconds() / 3600
                    # Debt increases with hours awake
                    if hours_awake < 8:
                        time_factor = 0.1
                    elif hours_awake < 12:
                        time_factor = 0.3
                    elif hours_awake < 16:
                        time_factor = 0.5
                    elif hours_awake < 20:
                        time_factor = 0.7
                    else:
                        time_factor = min(1.0, hours_awake / 24.0)
            except (ValueError, TypeError):
                pass
        
        # Accumulated debt from previous nights
        accumulated_factor = min(1.0, self._accumulated_debt / 10.0)
        
        # Update accumulated debt
        if duration_factor > 0.5:
            self._accumulated_debt += (duration_factor - 0.5) * 2
        else:
            self._accumulated_debt = max(0, self._accumulated_debt - 1)
        
        # Weighted average
        weights = self.config.weights
        value = (
            duration_factor * weights.get("sleep_duration", 0.5) +
            quality_factor * weights.get("sleep_quality", 0.3) +
            time_factor * weights.get("time_since_sleep", 0.2)
        )
        
        return min(1.0, max(0.0, value))
    
    def record_sleep(self, duration_hours: float, quality: float = 0.8):
        """Manually record sleep data."""
        self._last_sleep_duration = duration_hours
        if duration_hours >= 7:
            self._accumulated_debt = max(0, self._accumulated_debt - 2)
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "SleepDebtNeuron":
        return cls(config)


class AttentionLoadNeuron(StateNeuron):
    """Evaluates cognitive load / focus state.
    
    High load when:
    - Deep work session active
    - Complex tasks ongoing
    - Minimal interruptions
    - Focus-mode media state
    
    Low load when:
    - No active tasks
    - Media consumption
    - Frequent interruptions
    - Casual/browsing mode
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="attention_load",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["attention_load"]
            )
        super().__init__(config)
        self._focus_start: Optional[datetime] = None
        self._interruptions: int = 0
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate attention load from context."""
        states = context.get("states", {})
        now = context.get("now", datetime.now(timezone.utc))
        
        # Focus time factor
        focus_factor = 0.3
        if self._focus_start:
            duration = (now - self._focus_start).total_seconds() / 60
            # Focus increases over time, caps at ~90 min
            focus_factor = min(1.0, duration / 90.0)
        
        # Interruption factor (inverted - more interruptions = lower load)
        interruption_factor = 0.5
        interruption_entity = states.get("sensor.interruptions_today")
        if interruption_entity:
            try:
                count = float(interruption_entity.get("state", 0))
                # More interruptions = lower attention
                interruption_factor = max(0.1, 1.0 - (count * 0.05))
            except (ValueError, TypeError):
                pass
        
        # Task complexity factor
        complexity_factor = 0.5
        task_entity = states.get("sensor.current_task_complexity")
        if task_entity:
            try:
                complexity_factor = float(task_entity.get("state", 0.5))
            except (ValueError, TypeError):
                pass
        
        # Media activity factor (inverted - media = lower attention)
        media_factor = 0.5
        media_entity = states.get("media_player.main")
        if media_entity:
            state = media_entity.get("state", "off")
            if state == "playing":
                # Media playing = lower attention load
                media_factor = 0.2
        
        # Weighted average
        weights = self.config.weights
        value = (
            focus_factor * weights.get("focus_time", 0.3) +
            interruption_factor * weights.get("interruptions", 0.25) +
            complexity_factor * weights.get("task_complexity", 0.25) +
            media_factor * weights.get("media_activity", 0.2)
        )
        
        return min(1.0, max(0.0, value))
    
    def start_focus(self):
        """Mark start of focus session."""
        self._focus_start = datetime.now(timezone.utc)
        self._interruptions = 0
    
    def end_focus(self):
        """End focus session."""
        self._focus_start = None
    
    def add_interruption(self):
        """Record an interruption."""
        self._interruptions += 1
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "AttentionLoadNeuron":
        return cls(config)


class ComfortIndexNeuron(StateNeuron):
    """Evaluates physical comfort level.
    
    High comfort when:
    - Temperature in range (20-24°C)
    - Humidity moderate (40-60%)
    - Good lighting
    - Quiet environment
    - Good air quality
    
    Low comfort when:
    - Temperature extreme
    - Humidity high/low
    - Bright/dark conditions
    - Noisy environment
    - Poor air quality
    """
    
    def __init__(self, config: Optional[NeuronConfig] = None):
        if config is None:
            config = NeuronConfig(
                name="comfort_index",
                neuron_type=NeuronType.STATE,
                **DEFAULT_CONFIGS["comfort_index"]
            )
        super().__init__(config)
        # Comfort preferences (can be customized)
        self._temp_range = (20.0, 24.0)  # Celsius
        self._humidity_range = (40.0, 60.0)  # Percent
        self._noise_max = 60.0  # dB
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate comfort from context."""
        states = context.get("states", {})
        
        # Temperature comfort (Gaussian centered on ideal range)
        temp_factor = 0.7
        temp_entity = states.get("sensor.temperature")
        if temp_entity:
            try:
                temp = float(temp_entity.get("state", 22))
                min_t, max_t = self._temp_range
                mid = (min_t + max_t) / 2
                # Gaussian: peak at mid, drops off outside range
                temp_factor = math.exp(-((temp - mid) ** 2) / (2 * 3 ** 2))
            except (ValueError, TypeError):
                pass
        
        # Humidity comfort
        humidity_factor = 0.7
        humidity_entity = states.get("sensor.humidity")
        if humidity_entity:
            try:
                humidity = float(humidity_entity.get("state", 50))
                min_h, max_h = self._humidity_range
                mid = (min_h + max_h) / 2
                humidity_factor = math.exp(-((humidity - mid) ** 2) / (2 * 15 ** 2))
            except (ValueError, TypeError):
                pass
        
        # Light level comfort (depends on time of day)
        light_factor = 0.7
        light_entity = states.get("sensor.illuminance")
        if light_entity:
            try:
                lux = float(light_entity.get("state", 300))
                # Ideal ranges: 300-500 lux for normal activities
                # Lower for relaxation, higher for work
                if 300 <= lux <= 500:
                    light_factor = 1.0
                elif 100 <= lux < 300:
                    light_factor = 0.8
                elif 500 < lux <= 800:
                    light_factor = 0.8
                else:
                    light_factor = max(0.3, 1.0 - abs(lux - 400) / 1000)
            except (ValueError, TypeError):
                pass
        
        # Noise level comfort (inverted)
        noise_factor = 0.7
        noise_entity = states.get("sensor.noise_level")
        if noise_entity:
            try:
                noise_db = float(noise_entity.get("state", 30))
                # Lower is better, cap at 60dB
                noise_factor = max(0.1, 1.0 - (noise_db / self._noise_max))
            except (ValueError, TypeError):
                pass
        
        # Air quality comfort
        air_factor = 0.7
        air_entity = states.get("sensor.air_quality")
        if air_entity:
            try:
                aqi = float(air_entity.get("state", 50))
                # AQI: 0-50 good, 50-100 moderate, 100+ unhealthy
                if aqi <= 50:
                    air_factor = 1.0
                elif aqi <= 100:
                    air_factor = 0.7
                else:
                    air_factor = max(0.2, 1.0 - (aqi / 200))
            except (ValueError, TypeError):
                pass
        
        # Weighted average
        weights = self.config.weights
        value = (
            temp_factor * weights.get("temperature", 0.3) +
            humidity_factor * weights.get("humidity", 0.15) +
            light_factor * weights.get("light_level", 0.2) +
            noise_factor * weights.get("noise_level", 0.2) +
            air_factor * weights.get("air_quality", 0.15)
        )
        
        return min(1.0, max(0.0, value))
    
    def set_comfort_preferences(
        self,
        temp_range: tuple = (20.0, 24.0),
        humidity_range: tuple = (40.0, 60.0),
        noise_max: float = 60.0
    ):
        """Customize comfort preferences."""
        self._temp_range = temp_range
        self._humidity_range = humidity_range
        self._noise_max = noise_max
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "ComfortIndexNeuron":
        return cls(config)


# Factory function
def create_state_neuron(name: str, config: Optional[NeuronConfig] = None) -> StateNeuron:
    """Create a state neuron by name.
    
    Args:
        name: Neuron name (energy_level, stress_index, etc.)
        config: Optional custom configuration
    
    Returns:
        StateNeuron instance
    
    Raises:
        ValueError: If neuron name is unknown
    """
    neurons = {
        "energy_level": EnergyLevelNeuron,
        "stress_index": StressIndexNeuron,
        "routine_stability": RoutineStabilityNeuron,
        "sleep_debt": SleepDebtNeuron,
        "attention_load": AttentionLoadNeuron,
        "comfort_index": ComfortIndexNeuron,
    }
    
    if name not in neurons:
        raise ValueError(f"Unknown state neuron: {name}. Available: {list(neurons.keys())}")
    
    return neurons[name](config)


# Export all state neuron classes
STATE_NEURON_CLASSES = {
    "energy_level": EnergyLevelNeuron,
    "stress_index": StressIndexNeuron,
    "routine_stability": RoutineStabilityNeuron,
    "sleep_debt": SleepDebtNeuron,
    "attention_load": AttentionLoadNeuron,
    "comfort_index": ComfortIndexNeuron,
}


__all__ = [
    "EnergyLevelNeuron",
    "StressIndexNeuron", 
    "RoutineStabilityNeuron",
    "SleepDebtNeuron",
    "AttentionLoadNeuron",
    "ComfortIndexNeuron",
    "create_state_neuron",
    "STATE_NEURON_CLASSES",
    "DEFAULT_CONFIGS",
]