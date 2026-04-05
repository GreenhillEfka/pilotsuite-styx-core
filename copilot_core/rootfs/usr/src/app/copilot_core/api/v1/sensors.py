"""Sensor API — Flat endpoints for Home Assistant integration.

Slice 135: Provides HA-compatible sensor data from canonical sources.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify
from typing import Any, Dict, List

from copilot_core.module_registry import ModuleRegistry

_LOGGER = logging.getLogger(__name__)

sensors_bp = Blueprint("sensors", __name__, url_prefix="/api/v1/sensors")


def _get_registry() -> ModuleRegistry:
    """Get or create the ModuleRegistry singleton."""
    return ModuleRegistry.get_instance()


@sensors_bp.route("/modules", methods=["GET"])
def get_sensor_modules():
    """Module states as flat sensor data for HA.
    
    Returns:
        List of sensor-compatible module entries with state, icon, attributes.
    """
    registry = _get_registry()
    global_states = registry.get_all_states()
    
    sensors: List[Dict[str, Any]] = []
    
    for module_id, state in global_states.items():
        sensor = {
            "unique_id": f"pilotsuite_module_{module_id}",
            "name": module_id.replace("_", " ").title(),
            "state": state,
            "attributes": {
                "module_id": module_id,
                "friendly_name": module_id.replace("_", " ").title(),
            },
            "icon": _module_icon(module_id),
        }
        sensors.append(sensor)
    
    return jsonify({
        "sensors": sensors,
        "count": len(sensors),
    })


@sensors_bp.route("/zones", methods=["GET"])
def get_sensor_zones():
    """Zone states as flat sensor data for HA.
    
    Returns:
        List of sensor-compatible zone entries with module counts.
    """
    try:
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        engine = HabitusZoneEngine()
        overview = engine.get_overview()
        
        sensors: List[Dict[str, Any]] = []
        
        for zone_id, zone_data in overview.get("zones", {}).items():
            enabled_modules = zone_data.get("enabled_modules", [])
            
            sensor = {
                "unique_id": f"pilotsuite_zone_{zone_id}",
                "name": zone_data.get("name", zone_id.replace("_", " ").title()),
                "state": "active" if enabled_modules else "off",
                "attributes": {
                    "zone_id": zone_id,
                    "enabled_modules": enabled_modules,
                    "module_count": len(enabled_modules),
                    "friendly_name": zone_data.get("name", zone_id.replace("_", " ").title()),
                },
                "icon": "mdi:home",
            }
            sensors.append(sensor)
        
        return jsonify({
            "sensors": sensors,
            "count": len(sensors),
        })
    except Exception as exc:
        _LOGGER.warning("Zone sensors failed: %s", exc)
        return jsonify({"sensors": [], "count": 0, "error": str(exc)}), 503


@sensors_bp.route("/system", methods=["GET"])
def get_sensor_system():
    """System health as flat sensor data for HA.
    
    Returns:
        System health metrics as sensor-compatible entries.
    """
    try:
        from copilot_core.system_health.service import SystemHealthMonitor
        monitor = SystemHealthMonitor()
        health = monitor.get_full_health()
        
        sensors: List[Dict[str, Any]] = [
            {
                "unique_id": "pilotsuite_system_health",
                "name": "PilotSuite System",
                "state": health.get("status", "unknown"),
                "attributes": {
                    "cpu_usage": health.get("cpu_usage", 0),
                    "memory_usage": health.get("memory_usage", 0),
                    "disk_usage": health.get("disk_usage", 0),
                    "uptime_hours": health.get("uptime_hours", 0),
                },
                "icon": "mdi:server",
            }
        ]
        
        return jsonify({
            "sensors": sensors,
            "count": len(sensors),
        })
    except Exception as exc:
        _LOGGER.warning("System sensors failed: %s", exc)
        return jsonify({"sensors": [], "count": 0, "error": str(exc)}), 503


def _module_icon(module_id: str) -> str:
    """Return appropriate icon for module type."""
    icons = {
        "presence": "mdi:motion-sensor",
        "light": "mdi:lightbulb",
        "climate": "mdi:thermostat",
        "media": "mdi:speaker",
        "mood": "mdi:emoticon",
        "automation": "mdi:robot",
        "rag": "mdi:brain",
    }
    return icons.get(module_id, "mdi:puzzle")
