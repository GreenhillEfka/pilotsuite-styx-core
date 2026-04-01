"""Weather Integration — Slice 20.

Weather integration for PilotSuite Core.

Features:
- Weather data ingestion (HA, OpenWeatherMap, etc.)
- Weather-based automations
- Forecast-aware routines
- Seasonal adjustments
- Weather alerts
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WeatherCondition(Enum):
    """Weather condition."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    PARTLY_CLOUDY = "partly_cloudy"
    RAINY = "rainy"
    HEAVY_RAIN = "heavy_rain"
    SNOWY = "snowy"
    HEAVY_SNOW = "heavy_snow"
    STORM = "storm"
    FOG = "fog"
    WINDY = "windy"
    UNKNOWN = "unknown"


class WeatherAlertType(Enum):
    """Type of weather alert."""
    STORM_WARNING = "storm_warning"
    HEAVY_RAIN = "heavy_rain"
    HEAVY_SNOW = "heavy_snow"
    EXTREME_COLD = "extreme_cold"
    EXTREME_HEAT = "extreme_heat"
    FOG_WARNING = "fog_warning"
    WIND_WARNING = "wind_warning"


@dataclass
class WeatherData:
    """Current weather data."""
    source_id: str
    temperature: float  # Celsius
    temperature_unit: str = "°C"
    humidity: float = 0.0  # Percentage
    pressure: float = 0.0  # hPa
    wind_speed: float = 0.0  # km/h
    wind_direction: Optional[str] = None
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    visibility: Optional[float] = None  # km
    uv_index: float = 0.0
    precipitation: float = 0.0  # mm
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "temperature": self.temperature,
            "temperature_unit": self.temperature_unit,
            "humidity": self.humidity,
            "pressure": self.pressure,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "condition": self.condition.value,
            "visibility": self.visibility,
            "uv_index": self.uv_index,
            "precipitation": self.precipitation,
            "timestamp": self.timestamp,
        }


@dataclass
class WeatherForecast:
    """Weather forecast for a time period."""
    forecast_id: str
    source_id: str
    start: datetime
    end: datetime
    temperature_min: float
    temperature_max: float
    condition: WeatherCondition
    precipitation_probability: float = 0.0
    precipitation_amount: float = 0.0
    wind_speed_max: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "source_id": self.source_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "condition": self.condition.value,
            "precipitation_probability": self.precipitation_probability,
            "precipitation_amount": self.precipitation_amount,
            "wind_speed_max": self.wind_speed_max,
        }


@dataclass
class WeatherAlert:
    """Weather alert."""
    alert_id: str
    alert_type: WeatherAlertType
    severity: str  # "minor", "moderate", "severe", "extreme"
    title: str
    description: str
    start: datetime
    end: Optional[datetime]
    acknowledged: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at,
        }


@dataclass
class WeatherAutomation:
    """Weather-based automation."""
    automation_id: str
    condition_trigger: Optional[WeatherCondition]
    temperature_threshold: Optional[float]
    temperature_operator: Optional[str]  # "above", "below"
    alert_trigger: Optional[WeatherAlertType]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    last_triggered: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "condition_trigger": self.condition_trigger.value if self.condition_trigger else None,
            "temperature_threshold": self.temperature_threshold,
            "temperature_operator": self.temperature_operator,
            "alert_trigger": self.alert_trigger.value if self.alert_trigger else None,
            "actions": self.actions,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
        }


class WeatherIntegrationEngine:
    """Weather integration engine."""
    
    def __init__(self):
        self._sources: Dict[str, Dict[str, Any]] = {}
        self._current_weather: Dict[str, WeatherData] = {}
        self._forecasts: Dict[str, List[WeatherForecast]] = {}
        self._alerts: Dict[str, WeatherAlert] = {}
        self._automations: Dict[str, WeatherAutomation] = {}
        self._alert_counter = 0
        self._automation_counter = 0
        self._forecast_counter = 0
        
        # Condition keyword mapping
        self._condition_keywords = {
            WeatherCondition.CLEAR: ["clear", "sunny", "sonnig", "heiter"],
            WeatherCondition.CLOUDY: ["cloudy", "cloud", "bewölkt", "wolken"],
            WeatherCondition.PARTLY_CLOUDY: ["partly", "teilweise", "wechselhaft"],
            WeatherCondition.RAINY: ["rain", "regen", "rainy"],
            WeatherCondition.HEAVY_RAIN: ["heavy rain", "starkregen", "downpour"],
            WeatherCondition.SNOWY: ["snow", "schnee", "snowy"],
            WeatherCondition.HEAVY_SNOW: ["heavy snow", "schneesturm", "blizzard"],
            WeatherCondition.STORM: ["storm", "gewitter", "thunderstorm"],
            WeatherCondition.FOG: ["fog", "nebel", "foggy"],
            WeatherCondition.WINDY: ["wind", "windig", "windy", "böig"],
        }
    
    def register_weather_source(self, source_id: str, name: str, source_type: str,
                               entity_id: Optional[str] = None) -> str:
        """Register a weather source."""
        self._sources[source_id] = {
            "source_id": source_id,
            "name": name,
            "source_type": source_type,  # "ha", "openweathermap", "metno", etc.
            "entity_id": entity_id,
            "enabled": True,
        }
        
        return source_id
    
    def update_current_weather(self, source_id: str, data: Dict[str, Any]) -> WeatherData:
        """Update current weather from a source."""
        if source_id not in self._sources:
            raise ValueError(f"Unknown weather source: {source_id}")
        
        condition = self._parse_condition(data.get("condition", ""))
        
        weather = WeatherData(
            source_id=source_id,
            temperature=data.get("temperature", 0.0),
            humidity=data.get("humidity", 0.0),
            pressure=data.get("pressure", 0.0),
            wind_speed=data.get("wind_speed", 0.0),
            wind_direction=data.get("wind_direction"),
            condition=condition,
            visibility=data.get("visibility"),
            uv_index=data.get("uv_index", 0.0),
            precipitation=data.get("precipitation", 0.0),
        )
        
        self._current_weather[source_id] = weather
        
        # Check automations
        self._check_weather_automations(weather)
        
        return weather
    
    def import_forecast(self, source_id: str, forecast_data: List[Dict[str, Any]]) -> int:
        """Import weather forecast."""
        if source_id not in self._sources:
            return 0
        
        imported = 0
        for fc_data in forecast_data:
            self._forecast_counter += 1
            
            forecast = WeatherForecast(
                forecast_id=f"fc_{self._forecast_counter}",
                source_id=source_id,
                start=self._parse_datetime(fc_data.get("start")),
                end=self._parse_datetime(fc_data.get("end")),
                temperature_min=fc_data.get("temperature_min", 0.0),
                temperature_max=fc_data.get("temperature_max", 0.0),
                condition=self._parse_condition(fc_data.get("condition", "")),
                precipitation_probability=fc_data.get("precipitation_probability", 0.0),
                precipitation_amount=fc_data.get("precipitation_amount", 0.0),
                wind_speed_max=fc_data.get("wind_speed_max", 0.0),
            )
            
            if source_id not in self._forecasts:
                self._forecasts[source_id] = []
            
            self._forecasts[source_id].append(forecast)
            imported += 1
        
        return imported
    
    def create_automation(self, actions: List[Dict[str, Any]],
                         condition_trigger: Optional[WeatherCondition] = None,
                         temperature_threshold: Optional[float] = None,
                         temperature_operator: Optional[str] = None,
                         alert_trigger: Optional[WeatherAlertType] = None) -> str:
        """Create weather-based automation."""
        self._automation_counter += 1
        
        automation = WeatherAutomation(
            automation_id=f"weather_auto_{self._automation_counter}",
            condition_trigger=condition_trigger,
            temperature_threshold=temperature_threshold,
            temperature_operator=temperature_operator,
            alert_trigger=alert_trigger,
            actions=actions,
        )
        
        self._automations[automation.automation_id] = automation
        return automation.automation_id
    
    def create_alert(self, alert_type: WeatherAlertType, severity: str,
                    title: str, description: str,
                    start: datetime, end: Optional[datetime] = None) -> str:
        """Create weather alert."""
        self._alert_counter += 1
        
        alert = WeatherAlert(
            alert_id=f"alert_{self._alert_counter}",
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            start=start,
            end=end,
        )
        
        self._alerts[alert.alert_id] = alert
        
        # Check alert automations
        self._check_alert_automations(alert)
        
        return alert.alert_id
    
    def get_current_weather(self, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get current weather."""
        if source_id:
            if source_id not in self._current_weather:
                return None
            return self._current_weather[source_id].to_dict()
        
        # Return first available
        if self._current_weather:
            return list(self._current_weather.values())[0].to_dict()
        
        return None
    
    def get_forecast(self, source_id: Optional[str] = None,
                    days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get weather forecast."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        
        forecasts = []
        
        sources = [source_id] if source_id else list(self._forecasts.keys())
        
        for src_id in sources:
            if src_id not in self._forecasts:
                continue
            
            for fc in self._forecasts[src_id]:
                if now <= fc.start <= cutoff:
                    forecasts.append(fc)
        
        # Sort by start time
        forecasts.sort(key=lambda f: f.start)
        
        return [f.to_dict() for f in forecasts]
    
    def get_alerts(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get weather alerts."""
        alerts = list(self._alerts.values())
        
        if active_only:
            now = datetime.now(timezone.utc)
            alerts = [
                a for a in alerts
                if a.start <= now and (a.end is None or a.end > now)
            ]
        
        # Sort by severity
        severity_order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 4))
        
        return [a.to_dict() for a in alerts]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge weather alert."""
        if alert_id not in self._alerts:
            return False
        
        self._alerts[alert_id].acknowledged = True
        return True
    
    def get_weather_summary(self) -> Dict[str, Any]:
        """Get weather integration summary."""
        active_alerts = len(self.get_alerts(active_only=True))
        total_forecasts = sum(len(fcs) for fcs in self._forecasts.values())
        active_automations = len([a for a in self._automations.values() if a.enabled])
        
        return {
            "total_sources": len(self._sources),
            "active_alerts": active_alerts,
            "total_forecasts": total_forecasts,
            "active_automations": active_automations,
        }
    
    def _parse_condition(self, condition_str: str) -> WeatherCondition:
        """Parse weather condition from string."""
        condition_lower = condition_str.lower()

        best_match: Optional[WeatherCondition] = None
        best_length = -1
        for condition, keywords in self._condition_keywords.items():
            for kw in keywords:
                if kw in condition_lower and len(kw) >= best_length:
                    best_match = condition
                    best_length = len(kw)

        return best_match or WeatherCondition.UNKNOWN
    
    def _parse_datetime(self, value: Any) -> datetime:
        """Parse datetime from various formats."""
        if value is None:
            return datetime.now(timezone.utc)
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return datetime.now(timezone.utc)
    
    def _check_weather_automations(self, weather: WeatherData) -> List[Dict[str, Any]]:
        """Check and trigger weather automations."""
        triggered = []
        now = datetime.now(timezone.utc).isoformat()
        
        for automation in self._automations.values():
            if not automation.enabled:
                continue
            
            should_trigger = False
            
            # Check condition trigger
            if automation.condition_trigger and weather.condition == automation.condition_trigger:
                should_trigger = True
            
            # Check temperature trigger
            if automation.temperature_threshold is not None and automation.temperature_operator:
                if automation.temperature_operator == "above" and weather.temperature > automation.temperature_threshold:
                    should_trigger = True
                elif automation.temperature_operator == "below" and weather.temperature < automation.temperature_threshold:
                    should_trigger = True
            
            if should_trigger:
                triggered.append({
                    "automation_id": automation.automation_id,
                    "weather": weather.to_dict(),
                    "actions": automation.actions,
                })
                automation.last_triggered = now
        
        return triggered
    
    def _check_alert_automations(self, alert: WeatherAlert) -> List[Dict[str, Any]]:
        """Check and trigger alert automations."""
        triggered = []
        now = datetime.now(timezone.utc).isoformat()
        
        for automation in self._automations.values():
            if not automation.enabled:
                continue
            
            if automation.alert_trigger and alert.alert_type == automation.alert_trigger:
                triggered.append({
                    "automation_id": automation.automation_id,
                    "alert": alert.to_dict(),
                    "actions": automation.actions,
                })
                automation.last_triggered = now
        
        return triggered


def create_weather_integration_engine() -> WeatherIntegrationEngine:
    """Factory function to create weather integration engine."""
    return WeatherIntegrationEngine()
