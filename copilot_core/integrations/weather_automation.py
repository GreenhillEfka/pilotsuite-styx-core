"""PilotSuite Weather-based Automations — Weather triggers and actions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# WEATHER CONDITIONS
# =============================================================================

class WeatherCondition(Enum):
    """Weather conditions."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    PARTLY_CLOUDY = "partly_cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    WINDY = "windy"
    EXTREME_HEAT = "extreme_heat"
    EXTREME_COLD = "extreme_cold"


@dataclass
class WeatherState:
    """Current weather state."""
    temperature: float  # Celsius
    humidity: float  # Percent
    pressure: float  # hPa
    wind_speed: float  # km/h
    wind_direction: Optional[str] = None
    condition: WeatherCondition = WeatherCondition.CLEAR
    visibility: Optional[float] = None  # km
    uv_index: Optional[float] = None
    precipitation: Optional[float] = None  # mm
    cloud_cover: Optional[float] = None  # Percent


@dataclass
class WeatherForecast:
    """Weather forecast entry."""
    datetime: datetime
    temperature: float
    condition: WeatherCondition
    precipitation_probability: float = 0.0
    wind_speed: Optional[float] = None
    humidity: Optional[float] = None


# =============================================================================
# WEATHER AUTOMATION RULES
# =============================================================================

@dataclass
class WeatherAutomationRule:
    """Weather-based automation rule."""
    name: str
    trigger_conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    priority: int = 0  # Higher = more important
    cooldown_minutes: int = 0  # Prevent rapid re-triggering
    last_triggered: Optional[datetime] = None


class WeatherAutomationEngine:
    """
    Weather-based Automation Engine
    
    Features:
    - Multi-condition triggers
    - Action chaining
    - Cooldown management
    - Priority-based execution
    
    Example Rules:
    ```python
    # Close blinds when too sunny
    {
        "name": "Close Blinds - Sunny",
        "trigger_conditions": {
            "condition": WeatherCondition.CLEAR,
            "temperature_min": 25,
            "uv_index_min": 6,
        },
        "actions": [
            {"service": "cover.close_cover", "entity_id": "cover.living_room_blinds"},
        ],
    }
    
    # Start irrigation when dry
    {
        "name": "Irrigation - Dry",
        "trigger_conditions": {
            "humidity_max": 30,
            "temperature_min": 20,
            "condition": WeatherCondition.CLEAR,
        },
        "actions": [
            {"service": "switch.turn_on", "entity_id": "switch.garden_irrigation"},
        ],
    }
    ```
    """

    def __init__(self, hass):
        self.hass = hass
        self._rules: List[WeatherAutomationRule] = []
        self._current_weather: Optional[WeatherState] = None
        self._forecast: List[WeatherForecast] = []

    def add_rule(self, rule: WeatherAutomationRule):
        """Add automation rule."""
        self._rules.append(rule)
        logger.info(f"Added weather automation rule: {rule.name}")

    def remove_rule(self, name: str):
        """Remove automation rule by name."""
        self._rules = [r for r in self._rules if r.name != name]

    def update_weather(self, weather: WeatherState):
        """Update current weather state."""
        self._current_weather = weather
        logger.debug(f"Weather updated: {weather.temperature}°C, {weather.condition.value}")

    def update_forecast(self, forecast: List[WeatherForecast]):
        """Update weather forecast."""
        self._forecast = forecast

    async def evaluate_rules(self) -> List[Dict[str, Any]]:
        """Evaluate all rules against current weather."""
        if not self._current_weather:
            logger.warning("No weather data available for evaluation")
            return []
        
        triggered = []
        now = datetime.now()
        
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue
            
            # Check cooldown
            if rule.last_triggered:
                cooldown_end = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
                if now < cooldown_end:
                    continue
            
            # Check trigger conditions
            if self._check_trigger(rule.trigger_conditions):
                # Execute actions
                for action in rule.actions:
                    await self._execute_action(action)
                
                rule.last_triggered = now
                triggered.append({
                    "rule": rule.name,
                    "actions_executed": len(rule.actions),
                })
                
                logger.info(f"Weather automation triggered: {rule.name}")
        
        return triggered

    def _check_trigger(self, conditions: Dict[str, Any]) -> bool:
        """Check if weather matches trigger conditions."""
        weather = self._current_weather
        if not weather:
            return False
        
        # Check condition
        if "condition" in conditions:
            if weather.condition != conditions["condition"]:
                return False
        
        # Check temperature
        if "temperature_min" in conditions:
            if weather.temperature < conditions["temperature_min"]:
                return False
        
        if "temperature_max" in conditions:
            if weather.temperature > conditions["temperature_max"]:
                return False
        
        # Check humidity
        if "humidity_min" in conditions:
            if weather.humidity < conditions["humidity_min"]:
                return False
        
        if "humidity_max" in conditions:
            if weather.humidity > conditions["humidity_max"]:
                return False
        
        # Check wind
        if "wind_speed_min" in conditions:
            if weather.wind_speed < conditions["wind_speed_min"]:
                return False
        
        # Check UV
        if "uv_index_min" in conditions:
            if weather.uv_index and weather.uv_index < conditions["uv_index_min"]:
                return False
        
        # Check precipitation
        if "precipitation_min" in conditions:
            if weather.precipitation and weather.precipitation < conditions["precipitation_min"]:
                return False
        
        return True

    async def _execute_action(self, action: Dict[str, Any]):
        """Execute automation action."""
        service = action.get("service")
        entity_id = action.get("entity_id")
        data = action.get("data", {})
        
        if not service or not entity_id:
            logger.warning(f"Invalid action: {action}")
            return
        
        try:
            await self.hass.services.async_call(
                service.split(".")[0],
                service.split(".")[1],
                {"entity_id": entity_id, **data},
                blocking=False,
            )
        except Exception as e:
            logger.error(f"Error executing weather action {service}: {e}")


# =============================================================================
# PREDEFINED AUTOMATION TEMPLATES
# =============================================================================

def get_predefined_automations() -> List[WeatherAutomationRule]:
    """Get library of predefined weather automations."""
    return [
        # Blinds control
        WeatherAutomationRule(
            name="Blinds - Too Sunny",
            trigger_conditions={
                "condition": WeatherCondition.CLEAR,
                "temperature_min": 25,
                "uv_index_min": 6,
            },
            actions=[
                {"service": "cover.close_cover", "entity_id": "cover.living_room_blinds"},
            ],
            cooldown_minutes=60,
        ),
        
        # Irrigation
        WeatherAutomationRule(
            name="Irrigation - Dry & Hot",
            trigger_conditions={
                "humidity_max": 40,
                "temperature_min": 22,
                "condition": WeatherCondition.CLEAR,
            },
            actions=[
                {"service": "switch.turn_on", "entity_id": "switch.garden_irrigation"},
            ],
            cooldown_minutes=120,
        ),
        
        # Heating
        WeatherAutomationRule(
            name="Heating - Cold",
            trigger_conditions={
                "temperature_max": 15,
            },
            actions=[
                {"service": "climate.set_temperature", "entity_id": "climate.living_room", "data": {"temperature": 21}},
            ],
            cooldown_minutes=30,
        ),
        
        # Windows
        WeatherAutomationRule(
            name="Windows - Rain Coming",
            trigger_conditions={
                "condition": WeatherCondition.RAINY,
            },
            actions=[
                {"service": "cover.close_cover", "entity_id": "cover.all_windows"},
            ],
            cooldown_minutes=10,
        ),
        
        # Ventilation
        WeatherAutomationRule(
            name="Ventilation - Good Weather",
            trigger_conditions={
                "condition": WeatherCondition.CLEAR,
                "temperature_min": 18,
                "temperature_max": 26,
                "humidity_min": 30,
                "humidity_max": 70,
            },
            actions=[
                {"service": "cover.open_cover", "entity_id": "cover.living_room_window"},
            ],
            cooldown_minutes=60,
        ),
    ]


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_weather_automations(hass, config: Dict[str, Any]):
    """Set up weather automations in Home Assistant."""
    engine = WeatherAutomationEngine(hass)
    
    # Add predefined automations
    predefined = get_predefined_automations()
    for rule in predefined:
        engine.add_rule(rule)
    
    # Add custom automations from config
    custom_rules = config.get("custom_rules", [])
    for rule_config in custom_rules:
        rule = WeatherAutomationRule(
            name=rule_config["name"],
            trigger_conditions=rule_config["trigger_conditions"],
            actions=rule_config["actions"],
            enabled=rule_config.get("enabled", True),
            priority=rule_config.get("priority", 0),
            cooldown_minutes=rule_config.get("cooldown_minutes", 0),
        )
        engine.add_rule(rule)
    
    # Store engine in hass.data
    hass.data["pilotsuite_weather_engine"] = engine
    
    # Set up periodic evaluation
    async def evaluate_weather():
        """Periodically evaluate weather rules."""
        # Get current weather
        weather_entity = config.get("weather_entity", "weather.home")
        state = hass.states.get(weather_entity)
        
        if state:
            weather = WeatherState(
                temperature=float(state.attributes.get("temperature", 0)),
                humidity=float(state.attributes.get("humidity", 0)),
                pressure=float(state.attributes.get("pressure", 0)),
                wind_speed=float(state.attributes.get("wind_speed", 0)),
                condition=WeatherCondition(state.state),
            )
            engine.update_weather(weather)
            
            # Evaluate rules
            triggered = await engine.evaluate_rules()
            
            if triggered:
                logger.info(f"Weather automations triggered: {triggered}")
    
    # Schedule evaluation every 5 minutes
    from homeassistant.helpers.event import async_track_time_interval
    async_track_time_interval(hass, lambda now: evaluate_weather(), timedelta(minutes=5))
    
    logger.info("Weather automations set up successfully")
