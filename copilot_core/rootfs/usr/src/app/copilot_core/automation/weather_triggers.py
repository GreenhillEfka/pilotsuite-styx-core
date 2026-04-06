"""
Weather Automations for PilotSuite Core.

Weather-based triggers, conditions, and scheduling.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class WeatherCondition(Enum):
    """Weather conditions."""
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    WINDY = "windy"


class WeatherTriggerType(Enum):
    """Weather trigger types."""
    CONDITION_CHANGED = "condition_changed"
    TEMPERATURE_THRESHOLD = "temperature_threshold"
    PRECIPITATION_START = "precipitation_start"
    PRECIPITATION_END = "precipitation_end"
    SUNRISE = "sunrise"
    SUNSET = "sunset"
    WIND_SPEED_THRESHOLD = "wind_speed_threshold"


@dataclass
class WeatherTrigger:
    """Weather-based automation trigger."""
    id: str
    name: str
    trigger_type: WeatherTriggerType
    condition: Optional[WeatherCondition] = None
    temperature_threshold: Optional[float] = None
    wind_speed_threshold: Optional[float] = None
    enabled: bool = True
    actions: List[Dict[str, Any]] = field(default_factory=list)
    last_triggered: Optional[datetime] = None


@dataclass
class WeatherConditionChecker:
    """Weather condition checker."""
    current_temp: float = 0.0
    current_condition: WeatherCondition = WeatherCondition.CLOUDY
    humidity: float = 0.0
    wind_speed: float = 0.0
    precipitation: float = 0.0
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None


class WeatherTriggersEngine:
    """Weather triggers evaluation engine."""

    def __init__(self) -> None:
        """Initialize weather triggers engine."""
        self._triggers: Dict[str, WeatherTrigger] = {}
        self._current_conditions: Optional[WeatherConditionChecker] = None

    def register_trigger(self, trigger: WeatherTrigger) -> None:
        """Register a weather trigger."""
        self._triggers[trigger.id] = trigger
        _LOGGER.info("Weather trigger registered: %s", trigger.name)

    def unregister_trigger(self, trigger_id: str) -> bool:
        """Unregister a trigger."""
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            return True
        return False

    def update_conditions(self, conditions: WeatherConditionChecker) -> List[str]:
        """Update current weather conditions and evaluate triggers."""
        self._current_conditions = conditions
        triggered = []

        for trigger in self._triggers.values():
            if not trigger.enabled:
                continue

            if self._evaluate_trigger(trigger, conditions):
                triggered.append(trigger.id)
                trigger.last_triggered = datetime.now()
                _LOGGER.info("Weather trigger triggered: %s", trigger.name)

        return triggered

    def _evaluate_trigger(self, trigger: WeatherTrigger, conditions: WeatherConditionChecker) -> bool:
        """Evaluate if trigger should fire."""
        if trigger.trigger_type == WeatherTriggerType.CONDITION_CHANGED:
            return conditions.current_condition == trigger.condition

        if trigger.trigger_type == WeatherTriggerType.TEMPERATURE_THRESHOLD:
            if trigger.temperature_threshold is not None:
                return conditions.current_temp >= trigger.temperature_threshold

        if trigger.trigger_type == WeatherTriggerType.WIND_SPEED_THRESHOLD:
            if trigger.wind_speed_threshold is not None:
                return conditions.wind_speed >= trigger.wind_speed_threshold

        if trigger.trigger_type == WeatherTriggerType.PRECIPITATION_START:
            return conditions.precipitation > 0

        if trigger.trigger_type == WeatherTriggerType.PRECIPITATION_END:
            return conditions.precipitation == 0

        return False

    def get_triggers(self) -> List[WeatherTrigger]:
        """Get all registered triggers."""
        return list(self._triggers.values())

    def get_triggered_today(self) -> List[WeatherTrigger]:
        """Get triggers that fired today."""
        today = datetime.now().date()
        return [
            t for t in self._triggers.values()
            if t.last_triggered and t.last_triggered.date() == today
        ]


class WeatherScheduler:
    """Time-based weather scheduling."""

    def __init__(self, triggers_engine: WeatherTriggersEngine) -> None:
        """Initialize weather scheduler."""
        self._engine = triggers_engine
        self._scheduled_actions: List[Dict] = []

    def schedule_sunrise_action(self, action: Dict[str, Any], offset_minutes: int = 0) -> str:
        """Schedule action for sunrise."""
        action_id = f"sunrise_{len(self._scheduled_actions)}"
        self._scheduled_actions.append({
            "id": action_id,
            "type": "sunrise",
            "offset_minutes": offset_minutes,
            "action": action,
        })
        return action_id

    def schedule_sunset_action(self, action: Dict[str, Any], offset_minutes: int = 0) -> str:
        """Schedule action for sunset."""
        action_id = f"sunset_{len(self._scheduled_actions)}"
        self._scheduled_actions.append({
            "id": action_id,
            "type": "sunset",
            "offset_minutes": offset_minutes,
            "action": action,
        })
        return action_id

    def check_scheduled_actions(self, conditions: WeatherConditionChecker) -> List[Dict]:
        """Check and return actions that should run now."""
        now = datetime.now()
        to_run = []

        for scheduled in self._scheduled_actions:
            if scheduled["type"] == "sunrise" and conditions.sunrise:
                trigger_time = conditions.sunrise + timedelta(minutes=scheduled["offset_minutes"])
                if abs((now - trigger_time).total_seconds()) < 60:
                    to_run.append(scheduled["action"])

            if scheduled["type"] == "sunset" and conditions.sunset:
                trigger_time = conditions.sunset + timedelta(minutes=scheduled["offset_minutes"])
                if abs((now - trigger_time).total_seconds()) < 60:
                    to_run.append(scheduled["action"])

        return to_run


# Global instances
_weather_triggers: Optional[WeatherTriggersEngine] = None
_weather_scheduler: Optional[WeatherScheduler] = None


def get_weather_triggers_engine() -> WeatherTriggersEngine:
    """Get weather triggers engine."""
    global _weather_triggers
    if _weather_triggers is None:
        _weather_triggers = WeatherTriggersEngine()
    return _weather_triggers


def get_weather_scheduler() -> WeatherScheduler:
    """Get weather scheduler."""
    global _weather_scheduler
    if _weather_scheduler is None:
        _weather_scheduler = WeatherScheduler(get_weather_triggers_engine())
    return _weather_scheduler


__all__ = [
    "WeatherTriggersEngine",
    "WeatherScheduler",
    "WeatherTrigger",
    "WeatherCondition",
    "WeatherTriggerType",
    "WeatherConditionChecker",
    "get_weather_triggers_engine",
    "get_weather_scheduler",
]
