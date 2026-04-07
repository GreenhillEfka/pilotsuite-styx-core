"""Context Neurons - Objective environmental factors.

Context neurons evaluate objective data from Home Assistant states.
They represent measurable, non-subjective aspects of the environment.
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, Optional
from enum import Enum

from .base import BaseNeuron, NeuronConfig, NeuronType, ContextNeuron

_LOGGER = logging.getLogger(__name__)


class DayType(str, Enum):
    """Types of days for time-based context."""
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class PresenceNeuron(ContextNeuron):
    """Evaluates presence in a zone or the house.
    
    Inputs:
        - Person entity states (home/away)
        - Room presence sensors
        - Device tracker states
    
    Output: 0.0 (no presence) to 1.0 (definite presence)
    """
    
    def __init__(self, config: NeuronConfig, zone: str = "house"):
        super().__init__(config)
        self.zone = zone
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate presence based on person and sensor states."""
        states = context.get("states", {})
        presence_data = context.get("presence", {})
        
        # Check person entities
        person_entities = [
            eid for eid in self.config.entity_ids 
            if eid.startswith("person.")
        ]
        
        if person_entities:
            home_count = 0
            for entity_id in person_entities:
                state = states.get(entity_id, {})
                if state.get("state") == "home":
                    home_count += 1
            
            if home_count > 0:
                return min(1.0, home_count / max(len(person_entities), 1))
        
        # Check presence sensors for zone
        zone_sensors = presence_data.get(self.zone, [])
        for sensor_id in zone_sensors:
            state = states.get(sensor_id, {})
            if state.get("state") == "on":
                return 1.0
        
        # Check binary sensors
        for entity_id in self.config.entity_ids:
            if entity_id.startswith("binary_sensor."):
                state = states.get(entity_id, {})
                if state.get("state") == "on":
                    return 1.0
        
        return 0.0
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "PresenceNeuron":
        zone = config.weights.get("zone", "house")
        return cls(config, zone=zone)


class TimeOfDayNeuron(ContextNeuron):
    """Evaluates time of day context.
    
    Maps time to a continuous value representing:
        - Night (22:00-06:00): 0.0-0.2
        - Morning (06:00-09:00): 0.2-0.4
        - Day (09:00-17:00): 0.4-0.6
        - Evening (17:00-22:00): 0.6-0.8
    
    Also considers day type (weekday/weekend/holiday).
    """
    
    # Time ranges in hours
    NIGHT_START = 22
    NIGHT_END = 6
    MORNING_START = 6
    MORNING_END = 9
    DAY_START = 9
    DAY_END = 17
    EVENING_START = 17
    EVENING_END = 22
    
    def __init__(self, config: NeuronConfig, timezone_name: str = "Europe/Berlin"):
        super().__init__(config)
        self.timezone_name = timezone_name
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate time of day."""
        import zoneinfo
        try:
            tz = zoneinfo.ZoneInfo(self.timezone_name)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now()
        
        hour = now.hour + now.minute / 60
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Check for holiday (from context)
        holidays = context.get("holidays", [])
        is_holiday = now.strftime("%Y-%m-%d") in holidays
        is_weekend = weekday >= 5
        
        # Base value from time
        if self.NIGHT_START <= hour or hour < self.NIGHT_END:
            # Night: 0.0-0.2
            if hour >= self.NIGHT_START:
                normalized = (hour - self.NIGHT_START) / (24 - self.NIGHT_START + self.NIGHT_END)
            else:
                normalized = hour / self.NIGHT_END
            value = 0.0 + normalized * 0.2
        
        elif self.MORNING_START <= hour < self.MORNING_END:
            # Morning: 0.2-0.4
            normalized = (hour - self.MORNING_START) / (self.MORNING_END - self.MORNING_START)
            value = 0.2 + normalized * 0.2
        
        elif self.DAY_START <= hour < self.DAY_END:
            # Day: 0.4-0.6
            normalized = (hour - self.DAY_START) / (self.DAY_END - self.DAY_START)
            value = 0.4 + normalized * 0.2
        
        else:
            # Evening: 0.6-0.8
            normalized = (hour - self.EVENING_START) / (self.EVENING_END - self.EVENING_START)
            value = 0.6 + normalized * 0.2
        
        # Adjust for weekend/holiday (shift morning later)
        if is_weekend or is_holiday:
            # Morning starts later on weekends
            if self.MORNING_START <= hour < self.MORNING_START + 2:
                value = max(0.2, value - 0.1)  # Delay morning recognition
        
        return round(value, 3)
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "TimeOfDayNeuron":
        tz = config.weights.get("timezone", "Europe/Berlin")
        return cls(config, timezone_name=tz)


class LightLevelNeuron(ContextNeuron):
    """Evaluates ambient light level.
    
    Inputs:
        - Lux sensors
        - Sun position (elevation)
        - Light entity states (on/off)
    
    Output: 0.0 (dark) to 1.0 (bright)
    """
    
    # Lux thresholds
    DARK_THRESHOLD = 10      # Very dark
    DIM_THRESHOLD = 100      # Dim interior
    NORMAL_THRESHOLD = 300   # Normal interior
    BRIGHT_THRESHOLD = 1000  # Bright / near window
    
    def __init__(self, config: NeuronConfig, use_sun_position: bool = True):
        super().__init__(config)
        self.use_sun_position = use_sun_position
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate light level from sensors and sun position."""
        states = context.get("states", {})
        sun_data = context.get("sun", {})
        
        # Try lux sensor first
        lux_entities = [
            eid for eid in self.config.entity_ids
            if "illuminance" in eid or "lux" in eid or "light_level" in eid
        ]
        
        if lux_entities:
            for entity_id in lux_entities:
                state = states.get(entity_id, {})
                try:
                    lux = float(state.get("state", 0))
                    return self._lux_to_value(lux)
                except (ValueError, TypeError):
                    continue
        
        # Fallback to sun position
        if self.use_sun_position and sun_data:
            elevation = sun_data.get("elevation", 0)
            if elevation < -18:  # Night
                return 0.0
            elif elevation < -6:  # Astronomical twilight
                return 0.1
            elif elevation < 0:  # Civil twilight
                return 0.2
            elif elevation < 10:  # Low sun
                return 0.4
            elif elevation < 30:  # Medium sun
                return 0.6
            else:  # High sun
                return 0.9
        
        # Check if lights are on (implies dark)
        light_entities = [
            eid for eid in self.config.entity_ids
            if eid.startswith("light.")
        ]
        
        if light_entities:
            lights_on = sum(
                1 for eid in light_entities
                if states.get(eid, {}).get("state") == "on"
            )
            # If lights are on, it's probably somewhat dark
            if lights_on > 0:
                return 0.3
        
        # Default to moderate
        return 0.5
    
    def _lux_to_value(self, lux: float) -> float:
        """Convert lux to normalized value."""
        if lux <= self.DARK_THRESHOLD:
            return 0.0
        elif lux <= self.DIM_THRESHOLD:
            return 0.1 + 0.2 * (lux - self.DARK_THRESHOLD) / (self.DIM_THRESHOLD - self.DARK_THRESHOLD)
        elif lux <= self.NORMAL_THRESHOLD:
            return 0.3 + 0.3 * (lux - self.DIM_THRESHOLD) / (self.NORMAL_THRESHOLD - self.DIM_THRESHOLD)
        elif lux <= self.BRIGHT_THRESHOLD:
            return 0.6 + 0.3 * (lux - self.NORMAL_THRESHOLD) / (self.BRIGHT_THRESHOLD - self.NORMAL_THRESHOLD)
        else:
            return min(1.0, 0.9 + 0.1 * min(lux / self.BRIGHT_THRESHOLD - 1, 1))
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "LightLevelNeuron":
        use_sun = config.weights.get("use_sun_position", True)
        return cls(config, use_sun_position=use_sun)


class WeatherNeuron(ContextNeuron):
    """Evaluates weather conditions.
    
    Inputs:
        - Weather entity states
        - Temperature sensors
        - Humidity sensors
    
    Output: 0.0 (bad weather) to 1.0 (good weather)
    """
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate weather conditions."""
        states = context.get("states", {})
        weather_data = context.get("weather", {})
        
        # Check weather entity
        weather_entities = [
            eid for eid in self.config.entity_ids
            if eid.startswith("weather.")
        ]
        
        if weather_entities:
            for entity_id in weather_entities:
                state = states.get(entity_id, {})
                condition = state.get("state", "").lower()
                
                # Map weather conditions to values
                good_conditions = ["sunny", "clear", "clear-night"]
                moderate_conditions = ["partlycloudy", "cloudy", "fog"]
                poor_conditions = ["rainy", "snowy", "lightning", "hail", "windy"]
                
                if condition in good_conditions:
                    return 0.9
                elif condition in moderate_conditions:
                    return 0.5
                elif condition in poor_conditions:
                    return 0.2
        
        # Fallback to basic assessment
        return 0.5
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "WeatherNeuron":
        return cls(config)


# Register all context neurons
CONTEXT_NEURON_CLASSES = {
    "presence": PresenceNeuron,
    "time_of_day": TimeOfDayNeuron,
    "light_level": LightLevelNeuron,
    "weather": WeatherNeuron,
}


def create_context_neuron(name: str, config: NeuronConfig) -> ContextNeuron:
    """Factory function to create context neurons by name."""
    neuron_class = CONTEXT_NEURON_CLASSES.get(name)
    if neuron_class:
        return neuron_class.from_config(config)
    raise ValueError(f"Unknown context neuron type: {name}")