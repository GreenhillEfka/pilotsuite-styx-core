"""Sensor Data API Endpoints with Caching.

Provides cached access to sensor data for performance optimization.
Cache TTL: 5 minutes (300 seconds)

Endpoints:
- GET /api/v1/sensors - List all sensors with cached data
- GET /api/v1/sensors/<entity_id> - Get specific sensor data
- GET /api/v1/sensors/types - Get sensors grouped by type
- GET /api/v1/sensors/cache/stats - Get cache statistics
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("sensors", __name__, url_prefix="/api/v1/sensors")

from copilot_core.api.security import validate_token as _validate_token
from copilot_core.cache import get_sensor_cache


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


class SensorService:
    """Service for fetching and caching sensor data.
    
    In production, this would connect to Home Assistant or other data sources.
    For now, provides simulated sensor data with realistic patterns.
    """
    
    def __init__(self):
        self._cache = get_sensor_cache()
        self._lock = asyncio.Lock()
    
    def _generate_sensor_id(self, sensor_type: str, room: str, index: int = 1) -> str:
        """Generate Home Assistant style entity ID."""
        return f"sensor.{room}_{sensor_type}_{index}"
    
    def _get_simulated_sensors(self) -> List[Dict[str, Any]]:
        """Generate simulated sensor data for demonstration."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Simulate various sensor types across rooms
        sensors = [
            # Temperature sensors
            {
                "entity_id": "sensor.wohnzimmer_temperature_1",
                "name": "Wohnzimmer Temperatur",
                "state": str(21.5 + (hour - 12) * 0.3),  # Varies with time
                "attributes": {
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "room": "wohnzimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.kueche_temperature_1",
                "name": "Küche Temperatur",
                "state": str(22.0 + (hour - 12) * 0.4),
                "attributes": {
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "room": "kueche",
                    "floor": "eg",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.schlafzimmer_temperature_1",
                "name": "Schlafzimmer Temperatur",
                "state": str(19.0 + (hour - 12) * 0.2),
                "attributes": {
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "room": "schlafzimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            # Humidity sensors
            {
                "entity_id": "sensor.badezimmer_humidity_1",
                "name": "Badezimmer Luftfeuchtigkeit",
                "state": str(55.0 + (hour % 6) * 2),
                "attributes": {
                    "unit_of_measurement": "%",
                    "device_class": "humidity",
                    "room": "badezimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.keller_humidity_1",
                "name": "Keller Luftfeuchtigkeit",
                "state": str(65.0 + (hour % 4)),
                "attributes": {
                    "unit_of_measurement": "%",
                    "device_class": "humidity",
                    "room": "keller",
                    "floor": "ug",
                },
                "last_updated": now.isoformat(),
            },
            # Energy sensors
            {
                "entity_id": "sensor.stromverbrauch_1",
                "name": "Stromverbrauch",
                "state": str(1250.5 + hour * 50),
                "attributes": {
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "room": "hvr",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.energie_kwh_1",
                "name": "Energieverbrauch",
                "state": str(12.5 + hour * 0.8),
                "attributes": {
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "room": "hvr",
                },
                "last_updated": now.isoformat(),
            },
            # Motion/Presence sensors
            {
                "entity_id": "sensor.wohnzimmer_motion_1",
                "name": "Wohnzimmer Bewegung",
                "state": "on" if 8 <= hour <= 22 else "off",
                "attributes": {
                    "device_class": "motion",
                    "room": "wohnzimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.flur_presence_1",
                "name": "Flur Präsenz",
                "state": "on" if 7 <= hour <= 23 else "off",
                "attributes": {
                    "device_class": "occupancy",
                    "room": "flur",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            # Air quality sensors
            {
                "entity_id": "sensor.wohnzimmer_co2_1",
                "name": "Wohnzimmer CO2",
                "state": str(450 + hour * 20),
                "attributes": {
                    "unit_of_measurement": "ppm",
                    "device_class": "carbon_dioxide",
                    "room": "wohnzimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
            {
                "entity_id": "sensor.wohnzimmer_voc_1",
                "name": "Wohnzimmer VOC",
                "state": str(100 + hour * 5),
                "attributes": {
                    "unit_of_measurement": "µg/m³",
                    "device_class": "volatile_organic_compounds",
                    "room": "wohnzimmer",
                    "floor": "og",
                },
                "last_updated": now.isoformat(),
            },
        ]
        
        return sensors
    
    async def get_all_sensors(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get all sensor data with optional caching."""
        cache_key = "sensors:all"
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                _LOGGER.debug("Sensor cache hit: %s", cache_key)
                return cached
        
        # Fetch fresh data
        async with self._lock:
            sensors = self._get_simulated_sensors()
            await self._cache.set(cache_key, sensors)
            _LOGGER.debug("Sensor cache set: %s (count=%d)", cache_key, len(sensors))
        
        return sensors
    
    async def get_sensor(self, entity_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get specific sensor data."""
        cache_key = f"sensor:{entity_id}"
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                _LOGGER.debug("Sensor cache hit: %s", cache_key)
                return cached
        
        # Fetch fresh data
        all_sensors = await self.get_all_sensors(use_cache=False)
        sensor = next((s for s in all_sensors if s["entity_id"] == entity_id), None)
        
        if sensor and use_cache:
            await self._cache.set(cache_key, sensor)
        
        return sensor
    
    async def get_sensors_by_type(self, sensor_type: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get sensors filtered by type."""
        cache_key = f"sensors:type:{sensor_type}"
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        all_sensors = await self.get_all_sensors(use_cache=False)
        
        # Filter by device class or entity domain
        filtered = [
            s for s in all_sensors
            if s.get("attributes", {}).get("device_class") == sensor_type
            or sensor_type in s.get("entity_id", "")
        ]
        
        if use_cache:
            await self._cache.set(cache_key, filtered)
        
        return filtered
    
    async def get_sensors_by_room(self, room: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get sensors filtered by room."""
        cache_key = f"sensors:room:{room}"
        
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        all_sensors = await self.get_all_sensors(use_cache=False)
        
        # Filter by room attribute
        filtered = [
            s for s in all_sensors
            if s.get("attributes", {}).get("room") == room
        ]
        
        if use_cache:
            await self._cache.set(cache_key, filtered)
        
        return filtered
    
    async def invalidate_sensor_cache(self, entity_id: Optional[str] = None) -> None:
        """Invalidate sensor cache (all or specific)."""
        if entity_id:
            await self._cache.delete(f"sensor:{entity_id}")
            await self._cache.delete("sensors:all")
        else:
            await self._cache.invalidate_all()
        
        _LOGGER.info("Sensor cache invalidated: %s", entity_id or "all")


# Global service instance
_sensor_service: Optional[SensorService] = None


def _get_service() -> SensorService:
    """Get or create sensor service instance."""
    global _sensor_service
    if _sensor_service is None:
        _sensor_service = SensorService()
    return _sensor_service


@bp.route("", methods=["GET"])
def get_sensors():
    """Get all sensors with cached data."""
    try:
        service = _get_service()
        
        use_cache_raw = request.args.get("cache", "true")
        if use_cache_raw.lower() not in ("true", "false"):
            return jsonify({"status": "error", "message": "Query parameter 'cache' must be 'true' or 'false'"}), 400
        use_cache = use_cache_raw.lower() != "false"
        
        sensors = asyncio.run(service.get_all_sensors(use_cache=use_cache))
        
        return jsonify({
            "status": "ok",
            "count": len(sensors),
            "cached": use_cache,
            "sensors": sensors,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get sensors: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/<entity_id>", methods=["GET"])
def get_sensor(entity_id: str):
    """Get specific sensor data."""
    try:
        if not entity_id or not entity_id.strip():
            return jsonify({"status": "error", "message": "Path parameter 'entity_id' must not be blank"}), 400
        service = _get_service()
        
        use_cache_raw = request.args.get("cache", "true")
        if use_cache_raw.lower() not in ("true", "false"):
            return jsonify({"status": "error", "message": "Query parameter 'cache' must be 'true' or 'false'"}), 400
        use_cache = use_cache_raw.lower() != "false"
        
        sensor = asyncio.run(service.get_sensor(entity_id, use_cache=use_cache))
        
        if sensor is None:
            return jsonify({"status": "error", "message": f"Sensor not found: {entity_id}"}), 404
        
        return jsonify({
            "status": "ok",
            "sensor": sensor,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get sensor %s: %s", entity_id, e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/types", methods=["GET"])
def get_sensor_types():
    """Get sensors grouped by type."""
    try:
        service = _get_service()
        all_sensors = asyncio.run(service.get_all_sensors())
        
        # Group by device_class
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for sensor in all_sensors:
            device_class = sensor.get("attributes", {}).get("device_class", "unknown")
            if device_class not in grouped:
                grouped[device_class] = []
            grouped[device_class].append(sensor)
        
        return jsonify({
            "status": "ok",
            "types": {
                type_name: {
                    "count": len(sensors),
                    "sensors": sensors,
                }
                for type_name, sensors in grouped.items()
            },
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get sensor types: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/rooms", methods=["GET"])
def get_sensor_rooms():
    """Get sensors grouped by room."""
    try:
        service = _get_service()
        all_sensors = asyncio.run(service.get_all_sensors())
        
        # Group by room
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for sensor in all_sensors:
            room = sensor.get("attributes", {}).get("room", "unknown")
            if room not in grouped:
                grouped[room] = []
            grouped[room].append(sensor)
        
        return jsonify({
            "status": "ok",
            "rooms": {
                room_name: {
                    "count": len(sensors),
                    "sensors": sensors,
                }
                for room_name, sensors in grouped.items()
            },
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get sensor rooms: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/cache/stats", methods=["GET"])
def get_cache_stats():
    """Get sensor cache statistics."""
    try:
        cache = get_sensor_cache()
        stats = asyncio.run(cache.get_stats())
        
        return jsonify({
            "status": "ok",
            "cache_type": "sensor",
            "ttl_seconds": 300,
            "stats": stats,
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get cache stats: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """Clear sensor cache."""
    try:
        data = request.get_json(silent=True)
        if data is None and request.content_length and request.content_length > 0:
            # Body was sent but is not a valid JSON object (e.g., null, array, string)
            return jsonify({"status": "error", "message": "Request body must be a JSON object"}), 400
        if data is None:
            data = {}
        elif not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Request body must be a JSON object"}), 400
        entity_id = None
        if data:
            entity_id = data.get("entity_id")
            if entity_id is not None and not isinstance(entity_id, str):
                return jsonify({"status": "error", "message": "Request body field 'entity_id' must be a string"}), 400
        cache = get_sensor_cache()
        asyncio.run(cache.invalidate_all())
        return jsonify({
            "status": "ok",
            "message": "Sensor cache cleared",
        })
    
    except Exception as e:
        _LOGGER.error("Failed to clear cache: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
