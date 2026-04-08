"""Weather Context Neuron - Weather-based context for suggestions.

Evaluates weather data for:
- PV production potential
- Energy optimization suggestions
- Comfort adjustments (humidity, temperature)
- Activity recommendations (indoor/outdoor)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum

from .base import BaseNeuron, NeuronConfig, NeuronType, ContextNeuron

_LOGGER = logging.getLogger(__name__)


class WeatherCondition(str, Enum):
    """Weather condition categories."""
    SUNNY = "sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"
    UNKNOWN = "unknown"


class WeatherContextNeuron(ContextNeuron):
    """Evaluates weather conditions for context-aware suggestions.
    
    Inputs:
        - Weather condition (sunny, cloudy, rainy, etc.)
        - Temperature
        - Cloud cover percentage
        - UV index
        - Humidity
    
    Output: 0.0 (poor weather) to 1.0 (optimal weather)
    
    Factors:
        - PV potential (sunny = high, cloudy = low)
        - Comfort impact (extreme temps = low)
        - Activity suitability
    """
    
    # Weather condition scores (PV potential + activity suitability)
    CONDITION_SCORES = {
        WeatherCondition.SUNNY: 1.0,
        WeatherCondition.PARTLY_CLOUDY: 0.7,
        WeatherCondition.CLOUDY: 0.4,
        WeatherCondition.RAINY: 0.2,
        WeatherCondition.STORMY: 0.1,
        WeatherCondition.SNOWY: 0.3,
        WeatherCondition.FOGGY: 0.3,
        WeatherCondition.UNKNOWN: 0.5,
    }
    
    def __init__(
        self,
        config: NeuronConfig,
        pv_mode: bool = True,
        comfort_mode: bool = True,
    ):
        super().__init__(config)
        self.pv_mode = pv_mode  # Prioritize PV production
        self.comfort_mode = comfort_mode  # Consider comfort factors
        self._last_weather: Dict[str, Any] = {}
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate weather conditions."""
        weather_data = context.get("weather", {})
        
        if not weather_data:
            return 0.5  # Neutral when no data
        
        self._last_weather = weather_data
        
        # Parse condition
        condition_str = weather_data.get("condition", "unknown").lower()
        try:
            condition = WeatherCondition(condition_str)
        except ValueError:
            condition = WeatherCondition.UNKNOWN
        
        # Base score from condition
        base_score = self.CONDITION_SCORES.get(condition, 0.5)
        
        # Adjust for cloud cover
        cloud_cover = weather_data.get("cloud_cover_percent", 50)
        cloud_factor = 1.0 - (cloud_cover / 200)  # 0% clouds = 1.0, 100% clouds = 0.5
        
        # Adjust for UV index
        uv_index = weather_data.get("uv_index", 0)
        uv_factor = min(1.0, uv_index / 8)  # UV 8+ = optimal for PV
        
        # Adjust for temperature (comfort range 18-24°C)
        temp = weather_data.get("temperature_c", 20)
        if 18 <= temp <= 24:
            temp_factor = 1.0
        elif 15 <= temp <= 28:
            temp_factor = 0.8
        else:
            temp_factor = 0.5  # Extreme temperatures
        
        # Adjust for humidity (comfort range 40-60%)
        humidity = weather_data.get("humidity_percent", 50)
        if 40 <= humidity <= 60:
            humidity_factor = 1.0
        elif 30 <= humidity <= 70:
            humidity_factor = 0.8
        else:
            humidity_factor = 0.6  # Uncomfortable humidity
        
        # Calculate final score
        if self.pv_mode:
            # Prioritize PV production
            score = (
                base_score * 0.3 +
                cloud_factor * 0.3 +
                uv_factor * 0.3 +
                temp_factor * 0.1
            )
        elif self.comfort_mode:
            # Prioritize comfort
            score = (
                base_score * 0.2 +
                temp_factor * 0.4 +
                humidity_factor * 0.4
            )
        else:
            # Balanced
            score = (
                base_score * 0.3 +
                cloud_factor * 0.2 +
                uv_factor * 0.2 +
                temp_factor * 0.15 +
                humidity_factor * 0.15
            )
        
        self._value = max(0.0, min(1.0, score))
        self._last_evaluation = datetime.now()
        self._update_confidence(weather_data)
        
        return self._value
    
    def _update_confidence(self, weather_data: Dict[str, Any]) -> None:
        """Update confidence based on data quality."""
        # Higher confidence with more data points
        data_points = sum(1 for k in [
            "condition", "temperature_c", "cloud_cover_percent", 
            "uv_index", "humidity_percent"
        ] if k in weather_data and weather_data[k] is not None)
        
        self._confidence = min(1.0, data_points / 5.0 * 0.9 + 0.1)
    
    def get_pv_potential(self) -> float:
        """Get PV production potential (0.0 - 1.0)."""
        if not self._last_weather:
            return 0.5
        
        cloud_cover = self._last_weather.get("cloud_cover_percent", 50)
        uv_index = self._last_weather.get("uv_index", 0)
        condition = self._last_weather.get("condition", "unknown").lower()
        
        # Base from condition
        try:
            base = self.CONDITION_SCORES.get(WeatherCondition(condition), 0.5)
        except ValueError:
            base = 0.5
        
        # Cloud impact
        cloud_factor = 1.0 - (cloud_cover / 100) * 0.6
        
        # UV impact
        uv_factor = min(1.0, uv_index / 8)
        
        return base * 0.5 + cloud_factor * 0.3 + uv_factor * 0.2
    
    def get_comfort_score(self) -> float:
        """Get comfort score (0.0 - 1.0)."""
        if not self._last_weather:
            return 0.5
        
        temp = self._last_weather.get("temperature_c", 20)
        humidity = self._last_weather.get("humidity_percent", 50)
        
        # Temperature comfort
        if 18 <= temp <= 24:
            temp_score = 1.0
        elif 15 <= temp <= 28:
            temp_score = 0.8
        elif 10 <= temp <= 32:
            temp_score = 0.5
        else:
            temp_score = 0.2
        
        # Humidity comfort
        if 40 <= humidity <= 60:
            humidity_score = 1.0
        elif 30 <= humidity <= 70:
            humidity_score = 0.8
        elif 20 <= humidity <= 80:
            humidity_score = 0.5
        else:
            humidity_score = 0.3
        
        return temp_score * 0.6 + humidity_score * 0.4
    
    def should_suppress_outdoor_suggestions(self) -> bool:
        """Check if outdoor activity suggestions should be suppressed."""
        if not self._last_weather:
            return False
        
        condition = self._last_weather.get("condition", "unknown").lower()
        try:
            cond = WeatherCondition(condition)
            return cond in (WeatherCondition.RAINY, WeatherCondition.STORMY, WeatherCondition.SNOWY)
        except ValueError:
            return False
    
    def should_prioritize_pv_usage(self) -> bool:
        """Check if PV surplus usage should be prioritized."""
        return self.get_pv_potential() > 0.7
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "WeatherContextNeuron":
        pv_mode = config.weights.get("pv_mode", True)
        comfort_mode = config.weights.get("comfort_mode", True)
        return cls(config, pv_mode=pv_mode, comfort_mode=comfort_mode)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize neuron state."""
        data = super().to_dict()
        data.update({
            "pv_mode": self.pv_mode,
            "comfort_mode": self.comfort_mode,
            "pv_potential": self.get_pv_potential(),
            "comfort_score": self.get_comfort_score(),
            "last_weather": self._last_weather,
        })
        return data


class PVForecastNeuron(ContextNeuron):
    """Evaluates PV forecast for energy optimization.
    
    Inputs:
        - Forecasted PV production (kWh)
        - Current energy price
        - Grid load
    
    Output: 0.0 (no PV) to 1.0 (high PV surplus expected)
    
    Used for:
        - Energy shifting suggestions
        - EV charging recommendations
        - Appliance scheduling
    """
    
    # PV production thresholds (kWh)
    LOW_PV_THRESHOLD = 5.0
    HIGH_PV_THRESHOLD = 20.0
    
    def __init__(
        self,
        config: NeuronConfig,
        daily_consumption_kwh: float = 15.0,
    ):
        super().__init__(config)
        self.daily_consumption_kwh = daily_consumption_kwh
        self._last_forecast: Dict[str, Any] = {}
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate PV forecast potential."""
        pv_data = context.get("pv_forecast", {})
        
        if not pv_data:
            return 0.5  # Neutral when no data
        
        self._last_forecast = pv_data
        
        # Get forecasted production
        forecast_kwh = pv_data.get("forecast_pv_production_kwh", 0)
        
        # Calculate surplus
        surplus_kwh = max(0, forecast_kwh - self.daily_consumption_kwh)
        surplus_ratio = min(1.0, surplus_kwh / self.HIGH_PV_THRESHOLD)
        
        # Adjust for cloud cover forecast
        cloud_forecast = pv_data.get("cloud_cover_forecast_percent", 50)
        cloud_factor = 1.0 - (cloud_forecast / 200)
        
        # Calculate final score
        self._value = surplus_ratio * 0.7 + cloud_factor * 0.3
        self._last_evaluation = datetime.now()
        self._confidence = min(1.0, surplus_ratio + 0.1)
        
        return self._value
    
    def get_surplus_kwh(self) -> float:
        """Get expected surplus in kWh."""
        if not self._last_forecast:
            return 0.0
        
        forecast = self._last_forecast.get("forecast_pv_production_kwh", 0)
        return max(0, forecast - self.daily_consumption_kwh)
    
    def get_recommendation(self) -> str:
        """Get energy recommendation based on PV forecast."""
        surplus = self.get_surplus_kwh()
        
        if surplus > 10:
            return "optimal_charging"  # Charge EV, run appliances
        elif surplus > 5:
            return "moderate_usage"  # Some surplus available
        elif surplus > 0:
            return "minimal_surplus"  # Small surplus, defer heavy loads
        else:
            return "grid_recommended"  # No surplus, use grid efficiently
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "PVForecastNeuron":
        daily_consumption = config.weights.get("daily_consumption_kwh", 15.0)
        return cls(config, daily_consumption_kwh=daily_consumption)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize neuron state."""
        data = super().to_dict()
        data.update({
            "daily_consumption_kwh": self.daily_consumption_kwh,
            "surplus_kwh": self.get_surplus_kwh(),
            "recommendation": self.get_recommendation(),
            "last_forecast": self._last_forecast,
        })
        return data