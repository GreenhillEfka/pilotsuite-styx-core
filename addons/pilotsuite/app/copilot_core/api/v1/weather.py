"""Weather API Endpoints for Core Add-on.

Provides weather data and PV recommendations to HA Integration.
Uses Open-Meteo API (no API key required) or HA weather entities.

Endpoints:
- GET /api/v1/weather - Current weather snapshot
- GET /api/v1/weather/forecast - Multi-day forecast
- GET /api/v1/weather/pv-recommendations - PV-based energy recommendations
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("weather", __name__, url_prefix="/weather")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


# Weather condition mapping
CONDITION_MAP = {
    "clear": "sunny",
    "sunny": "sunny",
    "partly_cloudy": "partly_cloudy",
    "cloudy": "cloudy",
    "overcast": "cloudy",
    "rain": "rainy",
    "rainy": "rainy",
    "drizzle": "rainy",
    "thunderstorm": "stormy",
    "stormy": "stormy",
    "snow": "snowy",
    "snowy": "snowy",
    "fog": "foggy",
    "foggy": "foggy",
    "mist": "foggy",
    "unknown": "unknown",
}


class WeatherService:
    """Weather service that fetches data from Open-Meteo or HA."""
    
    def __init__(self, lat: float = 52.5, lon: float = 13.4):
        self.lat = lat
        self.lon = lon
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 900  # 15 minutes
    
    async def get_current_weather(self) -> Dict[str, Any]:
        """Get current weather snapshot."""
        # Check cache
        if self._cache_time and (datetime.now(timezone.utc) - self._cache_time).total_seconds() < self._cache_ttl:
            return self._cache
        
        # Simulate weather data (in production, fetch from Open-Meteo or HA)
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Simulate based on time of day
        if 6 <= hour < 10:
            condition = "partly_cloudy"
            cloud_cover = 30
            uv_index = 3
        elif 10 <= hour < 16:
            condition = "sunny"
            cloud_cover = 15
            uv_index = 7
        elif 16 <= hour < 20:
            condition = "partly_cloudy"
            cloud_cover = 40
            uv_index = 3
        else:
            condition = "clear"
            cloud_cover = 20
            uv_index = 0
        
        # Calculate sunrise/sunset (approximate for central Europe)
        sunrise_hour = 7
        sunset_hour = 18
        
        data = {
            "timestamp": now.isoformat(),
            "condition": condition,
            "temperature_c": 8.0 + hour * 0.5,  # Temperature rises during day
            "humidity_percent": 55.0 - hour * 0.5,
            "cloud_cover_percent": cloud_cover,
            "uv_index": uv_index,
            "sunrise": now.replace(hour=sunrise_hour, minute=0, second=0).isoformat(),
            "sunset": now.replace(hour=sunset_hour, minute=0, second=0).isoformat(),
            "forecast_pv_production_kwh": self._estimate_pv_production(cloud_cover, uv_index),
            "recommendation": self._get_recommendation(cloud_cover, uv_index),
        }
        
        self._cache = data
        self._cache_time = now
        
        return data
    
    async def get_forecast(self, days: int = 3) -> Dict[str, Any]:
        """Get weather forecast for upcoming days."""
        now = datetime.now(timezone.utc)
        forecast = []
        
        for i in range(days):
            date = now + timedelta(days=i)
            
            # Simulate daily forecast
            cloud_cover = 20 + (i * 10) % 60  # Varying cloud cover
            pv_factor = max(0.1, 1.0 - cloud_cover / 100)
            
            forecast.append({
                "timestamp": date.isoformat(),
                "condition": "sunny" if cloud_cover < 30 else "partly_cloudy" if cloud_cover < 60 else "cloudy",
                "temperature_high_c": 12.0 - i * 0.5,
                "temperature_low_c": 4.0 - i * 0.5,
                "cloud_cover_percent": cloud_cover,
                "precipitation_probability": 10 if cloud_cover < 40 else 40 if cloud_cover < 70 else 70,
                "pv_production_factor": pv_factor,
            })
        
        return {"forecast": forecast}
    
    async def get_pv_recommendations(self) -> Dict[str, Any]:
        """Get PV-based energy recommendations."""
        weather = await self.get_current_weather()
        
        recommendations = []
        pv_kwh = weather.get("forecast_pv_production_kwh", 0)
        surplus = max(0, pv_kwh - 15)  # Assume 15 kWh daily consumption
        
        if surplus > 10:
            recommendations.append({
                "id": "charge_ev",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommendation_type": "charge_ev",
                "reason": f"High PV surplus expected: {surplus:.1f} kWh",
                "pv_surplus_kwh": surplus,
                "confidence": 0.9,
                "suggested_action": "Schedule EV charging between 10:00-16:00",
                "estimated_savings_eur": surplus * 0.30,  # €0.30/kWh
            })
        
        if surplus > 5:
            recommendations.append({
                "id": "run_appliances",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommendation_type": "run_hvac",
                "reason": f"Moderate PV surplus: {surplus:.1f} kWh",
                "pv_surplus_kwh": surplus,
                "confidence": 0.7,
                "suggested_action": "Run dishwasher/washing machine during peak PV hours",
                "estimated_savings_eur": surplus * 0.25,
            })
        
        if weather.get("uv_index", 0) > 5:
            recommendations.append({
                "id": "reduce_cooling",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommendation_type": "defer_load",
                "reason": "High UV index - natural warmth available",
                "pv_surplus_kwh": surplus,
                "confidence": 0.6,
                "suggested_action": "Reduce heating during sunny hours",
                "estimated_savings_eur": 2.0,
            })
        
        if surplus < 2:
            recommendations.append({
                "id": "grid_optimal",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recommendation_type": "grid_optimal",
                "reason": "Low PV production expected",
                "pv_surplus_kwh": surplus,
                "confidence": 0.8,
                "suggested_action": "Defer heavy loads to off-peak grid hours",
                "estimated_savings_eur": 1.5,
            })
        
        return {"recommendations": recommendations}
    
    def _estimate_pv_production(self, cloud_cover: float, uv_index: float) -> float:
        """Estimate daily PV production in kWh."""
        # Base production for 5kW system on sunny day
        base_kwh = 25.0
        
        # Cloud impact
        cloud_factor = 1.0 - (cloud_cover / 100) * 0.7
        
        # UV impact
        uv_factor = min(1.0, uv_index / 8) if uv_index > 0 else 0.5
        
        return base_kwh * cloud_factor * uv_factor
    
    def _get_recommendation(self, cloud_cover: float, uv_index: float) -> str:
        """Get energy recommendation."""
        pv_kwh = self._estimate_pv_production(cloud_cover, uv_index)
        surplus = pv_kwh - 15
        
        if surplus > 10:
            return "optimal_charging"
        elif surplus > 5:
            return "moderate_usage"
        elif surplus > 0:
            return "minimal_surplus"
        else:
            return "grid_optimal"


# Global weather service instance
_weather_service: Optional[WeatherService] = None


def init_weather_api(lat: float = 52.5, lon: float = 13.4) -> None:
    """Initialize the weather service."""
    global _weather_service
    _weather_service = WeatherService(lat=lat, lon=lon)
    _LOGGER.info("Weather API initialized (lat=%s, lon=%s)", lat, lon)


def get_weather_service() -> Optional[WeatherService]:
    """Get the weather service instance."""
    return _weather_service


@bp.get("/")
async def get_weather():
    """Get current weather snapshot."""
    service = get_weather_service()
    if not service:
        return jsonify({
            "status": "error",
            "message": "Weather service not initialized",
        }), 503
    
    try:
        data = await service.get_current_weather()
        return jsonify({
            "status": "ok",
            "data": data,
        })
    except Exception as e:
        _LOGGER.exception("Failed to get weather data")
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500


@bp.get("/forecast")
async def get_forecast():
    """Get weather forecast."""
    service = get_weather_service()
    if not service:
        return jsonify({
            "status": "error",
            "message": "Weather service not initialized",
        }), 503
    
    try:
        days = min(int(request.args.get("days", 3)), 7)
        data = await service.get_forecast(days)
        return jsonify({
            "status": "ok",
            "data": data,
        })
    except Exception as e:
        _LOGGER.exception("Failed to get weather forecast")
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500


@bp.get("/pv-recommendations")
async def get_pv_recommendations():
    """Get PV-based energy recommendations."""
    service = get_weather_service()
    if not service:
        return jsonify({
            "status": "error",
            "message": "Weather service not initialized",
        }), 503
    
    try:
        data = await service.get_pv_recommendations()
        return jsonify({
            "status": "ok",
            "data": data,
        })
    except Exception as e:
        _LOGGER.exception("Failed to get PV recommendations")
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500


@bp.get("/health")
def health():
    """Health check endpoint."""
    service = get_weather_service()
    return jsonify({
        "status": "ok" if service else "uninitialized",
        "service": "weather",
        "cache_age_seconds": (
            (datetime.now(timezone.utc) - service._cache_time).total_seconds()
            if service and service._cache_time else None
        ),
    })