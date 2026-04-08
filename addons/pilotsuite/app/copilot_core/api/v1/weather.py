"""Weather API Endpoints for Core Add-on.

Uses Open-Meteo API (no API key required, local-first compatible).
Falls back to time-based estimation if Open-Meteo is unreachable.

Endpoints:
- GET /api/v1/weather - Current weather snapshot
- GET /api/v1/weather/forecast - Multi-day forecast
- GET /api/v1/weather/pv-recommendations - PV-based energy recommendations
- GET /api/v1/weather/health - Health / cache status
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

import requests as http_requests

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("weather", __name__, url_prefix="/weather")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


# Open-Meteo WMO weather code -> PilotSuite condition
_WMO_TO_CONDITION = {
    0: "sunny",          # Clear sky
    1: "sunny",          # Mainly clear
    2: "partly_cloudy",  # Partly cloudy
    3: "cloudy",         # Overcast
    45: "foggy",         # Fog
    48: "foggy",         # Depositing rime fog
    51: "rainy",         # Light drizzle
    53: "rainy",         # Moderate drizzle
    55: "rainy",         # Dense drizzle
    56: "rainy",         # Light freezing drizzle
    57: "rainy",         # Dense freezing drizzle
    61: "rainy",         # Slight rain
    63: "rainy",         # Moderate rain
    65: "rainy",         # Heavy rain
    66: "rainy",         # Light freezing rain
    67: "rainy",         # Heavy freezing rain
    71: "snowy",         # Slight snowfall
    73: "snowy",         # Moderate snowfall
    75: "snowy",         # Heavy snowfall
    77: "snowy",         # Snow grains
    80: "rainy",         # Slight rain showers
    81: "rainy",         # Moderate rain showers
    82: "rainy",         # Violent rain showers
    85: "snowy",         # Slight snow showers
    86: "snowy",         # Heavy snow showers
    95: "stormy",        # Thunderstorm
    96: "stormy",        # Thunderstorm with slight hail
    99: "stormy",        # Thunderstorm with heavy hail
}

_OPEN_METEO_TIMEOUT = 8  # seconds


class WeatherService:
    """Weather service using Open-Meteo API with fallback to estimation."""

    def __init__(self, lat: float = 52.5, lon: float = 13.4):
        self.lat = lat
        self.lon = lon
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 900  # 15 minutes
        self._forecast_cache: Dict[str, Any] = {}
        self._forecast_cache_time: Optional[datetime] = None
        self._forecast_cache_days: int = 0
        self._lock = threading.Lock()
        self._source: str = "none"  # "open_meteo" or "fallback"

    # ------------------------------------------------------------------
    # Open-Meteo fetch
    # ------------------------------------------------------------------

    def _fetch_open_meteo_current(self) -> Optional[Dict[str, Any]]:
        """Fetch current weather from Open-Meteo API."""
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={self.lat}&longitude={self.lon}"
                "&current=temperature_2m,relative_humidity_2m,weather_code,"
                "cloud_cover,uv_index,wind_speed_10m,apparent_temperature"
                "&daily=sunrise,sunset"
                "&timezone=auto"
            )
            resp = http_requests.get(url, timeout=_OPEN_METEO_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            _LOGGER.warning("Open-Meteo current fetch failed: %s", exc)
            return None

    def _fetch_open_meteo_forecast(self, days: int) -> Optional[Dict[str, Any]]:
        """Fetch forecast from Open-Meteo API."""
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={self.lat}&longitude={self.lon}"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
                "cloud_cover_mean,precipitation_probability_max,uv_index_max,"
                "sunshine_duration"
                f"&forecast_days={min(days, 7)}"
                "&timezone=auto"
            )
            resp = http_requests.get(url, timeout=_OPEN_METEO_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            _LOGGER.warning("Open-Meteo forecast fetch failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Fallback (time-based estimation when API unreachable)
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_current() -> Dict[str, Any]:
        """Time-based weather estimation (offline fallback)."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        if 6 <= hour < 10:
            condition, cloud_cover, uv_index = "partly_cloudy", 30, 3
        elif 10 <= hour < 16:
            condition, cloud_cover, uv_index = "sunny", 15, 7
        elif 16 <= hour < 20:
            condition, cloud_cover, uv_index = "partly_cloudy", 40, 3
        else:
            condition, cloud_cover, uv_index = "clear", 20, 0

        return {
            "timestamp": now.isoformat(),
            "condition": condition,
            "temperature_c": round(8.0 + hour * 0.5, 1),
            "apparent_temperature_c": round(7.0 + hour * 0.5, 1),
            "humidity_percent": round(55.0 - hour * 0.5, 1),
            "cloud_cover_percent": cloud_cover,
            "uv_index": uv_index,
            "wind_speed_kmh": 10.0,
            "sunrise": now.replace(hour=7, minute=0, second=0).isoformat(),
            "sunset": now.replace(hour=18, minute=0, second=0).isoformat(),
            "source": "fallback",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_weather(self) -> Dict[str, Any]:
        """Get current weather snapshot (sync, thread-safe)."""
        with self._lock:
            if (
                self._cache_time
                and (datetime.now(timezone.utc) - self._cache_time).total_seconds() < self._cache_ttl
            ):
                return self._cache

        raw = self._fetch_open_meteo_current()

        if raw and "current" in raw:
            cur = raw["current"]
            daily = raw.get("daily", {})
            sunrise_list = daily.get("sunrise", [])
            sunset_list = daily.get("sunset", [])

            wmo_code = cur.get("weather_code", 0)
            cloud_cover = cur.get("cloud_cover", 0)
            uv_index = cur.get("uv_index", 0)

            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "condition": _WMO_TO_CONDITION.get(wmo_code, "unknown"),
                "weather_code": wmo_code,
                "temperature_c": cur.get("temperature_2m"),
                "apparent_temperature_c": cur.get("apparent_temperature"),
                "humidity_percent": cur.get("relative_humidity_2m"),
                "cloud_cover_percent": cloud_cover,
                "uv_index": uv_index,
                "wind_speed_kmh": cur.get("wind_speed_10m"),
                "sunrise": sunrise_list[0] if sunrise_list else None,
                "sunset": sunset_list[0] if sunset_list else None,
                "forecast_pv_production_kwh": self._estimate_pv_production(cloud_cover, uv_index),
                "recommendation": self._get_recommendation(cloud_cover, uv_index),
                "source": "open_meteo",
            }
            self._source = "open_meteo"
        else:
            data = self._fallback_current()
            data["forecast_pv_production_kwh"] = self._estimate_pv_production(
                data["cloud_cover_percent"], data["uv_index"]
            )
            data["recommendation"] = self._get_recommendation(
                data["cloud_cover_percent"], data["uv_index"]
            )
            self._source = "fallback"

        with self._lock:
            self._cache = data
            self._cache_time = datetime.now(timezone.utc)

        return data

    def get_forecast(self, days: int = 3) -> Dict[str, Any]:
        """Get weather forecast for upcoming days."""
        days = max(1, min(days, 7))

        with self._lock:
            if (
                self._forecast_cache_time
                and (datetime.now(timezone.utc) - self._forecast_cache_time).total_seconds() < self._cache_ttl
                and self._forecast_cache_days >= days
            ):
                # Return cached, trim to requested days
                cached = self._forecast_cache.get("forecast", [])
                return {"forecast": cached[:days]}

        raw = self._fetch_open_meteo_forecast(days)

        if raw and "daily" in raw:
            daily = raw["daily"]
            dates = daily.get("time", [])
            forecast = []
            for i, date_str in enumerate(dates):
                wmo = (daily.get("weather_code") or [])[i] if i < len(daily.get("weather_code", [])) else 0
                cloud = (daily.get("cloud_cover_mean") or [])[i] if i < len(daily.get("cloud_cover_mean", [])) else 0
                uv_max = (daily.get("uv_index_max") or [])[i] if i < len(daily.get("uv_index_max", [])) else 0
                precip_prob = (daily.get("precipitation_probability_max") or [])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0
                sunshine_s = (daily.get("sunshine_duration") or [])[i] if i < len(daily.get("sunshine_duration", [])) else 0
                t_max = (daily.get("temperature_2m_max") or [])[i] if i < len(daily.get("temperature_2m_max", [])) else None
                t_min = (daily.get("temperature_2m_min") or [])[i] if i < len(daily.get("temperature_2m_min", [])) else None

                pv_factor = max(0.05, 1.0 - (cloud or 0) / 100 * 0.7)

                forecast.append({
                    "date": date_str,
                    "timestamp": f"{date_str}T12:00:00Z",
                    "condition": _WMO_TO_CONDITION.get(wmo, "unknown"),
                    "weather_code": wmo,
                    "temperature_high_c": t_max,
                    "temperature_low_c": t_min,
                    "cloud_cover_percent": cloud,
                    "precipitation_probability": precip_prob,
                    "uv_index_max": uv_max,
                    "sunshine_duration_h": round((sunshine_s or 0) / 3600, 1),
                    "pv_production_factor": round(pv_factor, 2),
                    "source": "open_meteo",
                })

            result = {"forecast": forecast}
        else:
            # Fallback: time-based estimation
            now = datetime.now(timezone.utc)
            forecast = []
            for i in range(days):
                date = now + timedelta(days=i)
                cloud_cover = 20 + (i * 10) % 60
                pv_factor = max(0.1, 1.0 - cloud_cover / 100)
                forecast.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "timestamp": date.isoformat(),
                    "condition": "sunny" if cloud_cover < 30 else "partly_cloudy" if cloud_cover < 60 else "cloudy",
                    "temperature_high_c": 12.0 - i * 0.5,
                    "temperature_low_c": 4.0 - i * 0.5,
                    "cloud_cover_percent": cloud_cover,
                    "precipitation_probability": 10 if cloud_cover < 40 else 40 if cloud_cover < 70 else 70,
                    "pv_production_factor": pv_factor,
                    "source": "fallback",
                })
            result = {"forecast": forecast}

        with self._lock:
            self._forecast_cache = result
            self._forecast_cache_time = datetime.now(timezone.utc)
            self._forecast_cache_days = days

        return result

    def get_pv_recommendations(self) -> Dict[str, Any]:
        """Get PV-based energy recommendations."""
        weather = self.get_current_weather()

        recommendations = []
        pv_kwh = weather.get("forecast_pv_production_kwh", 0)
        surplus = max(0, pv_kwh - 15)  # Assume 15 kWh daily consumption

        now_iso = datetime.now(timezone.utc).isoformat()

        if surplus > 10:
            recommendations.append({
                "id": "charge_ev",
                "timestamp": now_iso,
                "recommendation_type": "charge_ev",
                "reason": f"Hoher PV-Ueberschuss erwartet: {surplus:.1f} kWh",
                "pv_surplus_kwh": surplus,
                "confidence": 0.9,
                "suggested_action": "EV-Laden zwischen 10:00-16:00 planen",
                "estimated_savings_eur": round(surplus * 0.30, 2),
            })

        if surplus > 5:
            recommendations.append({
                "id": "run_appliances",
                "timestamp": now_iso,
                "recommendation_type": "run_hvac",
                "reason": f"Moderater PV-Ueberschuss: {surplus:.1f} kWh",
                "pv_surplus_kwh": surplus,
                "confidence": 0.7,
                "suggested_action": "Spuelmaschine/Waschmaschine waehrend PV-Peak starten",
                "estimated_savings_eur": round(surplus * 0.25, 2),
            })

        if weather.get("uv_index", 0) > 5:
            recommendations.append({
                "id": "reduce_cooling",
                "timestamp": now_iso,
                "recommendation_type": "defer_load",
                "reason": "Hoher UV-Index - natuerliche Waerme nutzbar",
                "pv_surplus_kwh": surplus,
                "confidence": 0.6,
                "suggested_action": "Heizung waehrend sonniger Stunden reduzieren",
                "estimated_savings_eur": 2.0,
            })

        if surplus < 2:
            recommendations.append({
                "id": "grid_optimal",
                "timestamp": now_iso,
                "recommendation_type": "grid_optimal",
                "reason": "Niedrige PV-Produktion erwartet",
                "pv_surplus_kwh": surplus,
                "confidence": 0.8,
                "suggested_action": "Schwere Lasten auf Nebenzeiten verschieben",
                "estimated_savings_eur": 1.5,
            })

        return {"recommendations": recommendations}

    def _estimate_pv_production(self, cloud_cover: float, uv_index: float) -> float:
        """Estimate daily PV production in kWh (5 kWp system)."""
        base_kwh = 25.0
        cloud_factor = 1.0 - (cloud_cover or 0) / 100 * 0.7
        uv_factor = min(1.0, (uv_index or 0) / 8) if uv_index and uv_index > 0 else 0.5
        return round(base_kwh * cloud_factor * uv_factor, 1)

    def _get_recommendation(self, cloud_cover: float, uv_index: float) -> str:
        """Get energy recommendation category."""
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
def get_weather():
    """Get current weather snapshot."""
    service = get_weather_service()
    if not service:
        return jsonify({"status": "error", "message": "Weather service not initialized"}), 503
    try:
        data = service.get_current_weather()
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        _LOGGER.exception("Failed to get weather data")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.get("/forecast")
def get_forecast():
    """Get weather forecast."""
    service = get_weather_service()
    if not service:
        return jsonify({"status": "error", "message": "Weather service not initialized"}), 503
    try:
        days = min(int(request.args.get("days", 3)), 7)
        data = service.get_forecast(days)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        _LOGGER.exception("Failed to get weather forecast")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.get("/pv-recommendations")
def get_pv_recommendations():
    """Get PV-based energy recommendations."""
    service = get_weather_service()
    if not service:
        return jsonify({"status": "error", "message": "Weather service not initialized"}), 503
    try:
        data = service.get_pv_recommendations()
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        _LOGGER.exception("Failed to get PV recommendations")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.get("/health")
def health():
    """Health check endpoint."""
    service = get_weather_service()
    return jsonify({
        "status": "ok" if service else "uninitialized",
        "service": "weather",
        "source": service._source if service else None,
        "cache_age_seconds": (
            (datetime.now(timezone.utc) - service._cache_time).total_seconds()
            if service and service._cache_time else None
        ),
    })
