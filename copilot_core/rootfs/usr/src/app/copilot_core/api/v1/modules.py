"""Module APIs — Slices 67-82.

API endpoints for all intelligence modules:
- Presence (Slices 67, 70, 75)
- Light (Slices 68, 71, 76)
- TimeOfDay (Slices 69, 72, 77)
- Rules (Slices 73, 78)
- Climate (Slice 80)
- Humidity (Slice 81)
- Energy (Slice 82)
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Blueprint ───────────────────────────────────────────────────────

modules_bp = Blueprint("modules", __name__, url_prefix="/modules")

# Module registry (populated by core_setup.py)
_module_instances: Dict[str, Any] = {}


def register_module(name: str, instance: Any) -> None:
    """Register a module instance."""
    _module_instances[name] = instance
    logger.info(f"Registered module: {name}")


def get_module(name: str) -> Optional[Any]:
    """Get a module instance by name."""
    return _module_instances.get(name)


# ── Endpoints ───────────────────────────────────────────────────────

@modules_bp.get("/list")
def list_modules():
    """List all registered modules."""
    return jsonify({
        "modules": list(_module_instances.keys()),
        "count": len(_module_instances),
    })


@modules_bp.get("/<name>/status")
def module_status(name: str):
    """Get module status."""
    module = get_module(name)
    
    if not module:
        return jsonify({"error": f"Module '{name}' not found"}), 404
    
    if hasattr(module, "get_status"):
        return jsonify(module.get_status())
    
    return jsonify({"name": name, "status": "active"})


@modules_bp.get("/<name>/config")
def module_config(name: str):
    """Get module configuration."""
    module = get_module(name)
    
    if not module:
        return jsonify({"error": f"Module '{name}' not found"}), 404
    
    if hasattr(module, "get_config"):
        return jsonify(module.get_config())
    
    return jsonify({"name": name, "config": {}})


@modules_bp.post("/<name>/action")
def module_action(name: str):
    """Execute module action."""
    module = get_module(name)
    
    if not module:
        return jsonify({"error": f"Module '{name}' not found"}), 404
    
    data = request.get_json() or {}
    action = data.get("action")
    
    if not action:
        return jsonify({"error": "Missing 'action' in request body"}), 400
    
    if hasattr(module, "execute_action"):
        try:
            result = module.execute_action(action, data)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.exception(f"Module action failed: {name}.{action}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": f"Module '{name}' does not support actions"}), 405


# ── Presence Module API ─────────────────────────────────────────────

@modules_bp.get("/presence/zones")
def presence_zones():
    """Get presence status for all zones."""
    module = get_module("presence")
    
    if not module:
        return jsonify({"error": "Presence module not loaded"}), 503
    
    if hasattr(module, "get_all_zones_status"):
        return jsonify(module.get_all_zones_status())
    
    return jsonify({"zones": []})


@modules_bp.get("/presence/zone/<zone_id>")
def presence_zone(zone_id: str):
    """Get presence status for a specific zone."""
    module = get_module("presence")
    
    if not module:
        return jsonify({"error": "Presence module not loaded"}), 503
    
    if hasattr(module, "get_zone_status"):
        return jsonify(module.get_zone_status(zone_id))
    
    return jsonify({"zone_id": zone_id, "state": "unknown"})


# ── Light Module API ────────────────────────────────────────────────

@modules_bp.get("/light/zones")
def light_zones():
    """Get light status for all zones."""
    module = get_module("light")
    
    if not module:
        return jsonify({"error": "Light module not loaded"}), 503
    
    if hasattr(module, "get_all_zones_status"):
        return jsonify(module.get_all_zones_status())
    
    return jsonify({"zones": []})


@modules_bp.post("/light/zone/<zone_id>/scene")
def light_scene(zone_id: str):
    """Activate light scene for a zone."""
    module = get_module("light")
    
    if not module:
        return jsonify({"error": "Light module not loaded"}), 503
    
    data = request.get_json() or {}
    scene = data.get("scene")
    
    if not scene:
        return jsonify({"error": "Missing 'scene' in request body"}), 400
    
    if hasattr(module, "activate_scene"):
        try:
            result = module.activate_scene(zone_id, scene)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.exception(f"Light scene failed: {zone_id}.{scene}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Scene activation not supported"}), 405


# ── Climate Module API ──────────────────────────────────────────────

@modules_bp.get("/climate/zones")
def climate_zones():
    """Get climate status for all zones."""
    module = get_module("climate")
    
    if not module:
        return jsonify({"error": "Climate module not loaded"}), 503
    
    if hasattr(module, "get_all_zones_status"):
        return jsonify(module.get_all_zones_status())
    
    return jsonify({"zones": []})


@modules_bp.post("/climate/zone/<zone_id>/setpoint")
def climate_setpoint(zone_id: str):
    """Set climate setpoint for a zone."""
    module = get_module("climate")
    
    if not module:
        return jsonify({"error": "Climate module not loaded"}), 503
    
    data = request.get_json() or {}
    temperature = data.get("temperature")
    
    if temperature is None:
        return jsonify({"error": "Missing 'temperature' in request body"}), 400
    
    if hasattr(module, "set_setpoint"):
        try:
            result = module.set_setpoint(zone_id, temperature)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.exception(f"Climate setpoint failed: {zone_id}.{temperature}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Setpoint control not supported"}), 405


# ── Humidity Module API ─────────────────────────────────────────────

@modules_bp.get("/humidity/zones")
def humidity_zones():
    """Get humidity status for all zones."""
    module = get_module("humidity")
    
    if not module:
        return jsonify({"error": "Humidity module not loaded"}), 503
    
    if hasattr(module, "get_all_zones_status"):
        return jsonify(module.get_all_zones_status())
    
    return jsonify({"zones": []})


# ── Energy Module API ───────────────────────────────────────────────

@modules_bp.get("/energy/forecast")
def energy_forecast():
    """Get energy forecast."""
    module = get_module("energy")
    
    if not module:
        return jsonify({"error": "Energy module not loaded"}), 503
    
    if hasattr(module, "get_forecast"):
        return jsonify(module.get_forecast())
    
    return jsonify({"forecast": {}})


@modules_bp.get("/energy/optimization")
def energy_optimization():
    """Get energy optimization recommendations."""
    module = get_module("energy")
    
    if not module:
        return jsonify({"error": "Energy module not loaded"}), 503
    
    if hasattr(module, "get_optimization_recommendations"):
        return jsonify(module.get_optimization_recommendations())
    
    return jsonify({"recommendations": []})


# ── TimeOfDay Module API ────────────────────────────────────────────

@modules_bp.get("/timeofday/current")
def timeofday_current():
    """Get current time of day state."""
    module = get_module("timeofday")
    
    if not module:
        return jsonify({"error": "TimeOfDay module not loaded"}), 503
    
    if hasattr(module, "get_current_state"):
        return jsonify(module.get_current_state())
    
    return jsonify({"state": "unknown"})


@modules_bp.get("/timeofday/zones")
def timeofday_zones():
    """Get time of day state for all zones."""
    module = get_module("timeofday")
    
    if not module:
        return jsonify({"error": "TimeOfDay module not loaded"}), 503
    
    if hasattr(module, "get_all_zones_status"):
        return jsonify(module.get_all_zones_status())
    
    return jsonify({"zones": []})


# ── Rules Module API ────────────────────────────────────────────────

@modules_bp.get("/rules/list")
def rules_list():
    """List all rules."""
    module = get_module("rules")
    
    if not module:
        return jsonify({"error": "Rules module not loaded"}), 503
    
    if hasattr(module, "list_rules"):
        return jsonify({"rules": module.list_rules()})
    
    return jsonify({"rules": []})


@modules_bp.post("/rules/<rule_id>/activate")
def rules_activate(rule_id: str):
    """Activate a rule."""
    module = get_module("rules")
    
    if not module:
        return jsonify({"error": "Rules module not loaded"}), 503
    
    if hasattr(module, "activate_rule"):
        try:
            result = module.activate_rule(rule_id)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logger.exception(f"Rule activation failed: {rule_id}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Rule activation not supported"}), 405


# ── SLICE 146: Modules API Expansion ─────────────────────────────────

@bp.get("/health")
def modules_health():
    """Get health status of all modules.
    
    Returns per-module:
    - module_id
    - status: healthy|degraded|unhealthy
    - last_seen: Last activity timestamp
    - error_count: Recent error count
    """
    from copilot_core.modules.registry import get_module_registry
    
    try:
        registry = get_module_registry()
        health = registry.get_all_modules_health()
    except Exception as e:
        _LOGGER.warning("Failed to get modules health: %s", e)
        health = []
    
    return jsonify({
        "ok": True,
        "health": health,
        "count": len(health),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/<module_id>/health")
def module_health(module_id):
    """Get health status of a specific module.
    
    Returns:
    - module_id
    - status: healthy|degraded|unhealthy
    - last_seen: Last activity timestamp
    - error_count: Recent error count
    - details: Additional health details
    """
    from copilot_core.modules.registry import get_module_registry
    
    try:
        registry = get_module_registry()
        health = registry.get_module_health(module_id=module_id)
    except Exception as e:
        _LOGGER.warning("Failed to get module health: %s", e)
        health = {
            "module_id": module_id,
            "status": "unknown",
            "last_seen": None,
            "error_count": 0,
            "details": {}
        }
    
    return jsonify({
        "ok": True,
        "health": health,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/dependencies")
def modules_dependencies():
    """Get module dependency graph.
    
    Query params:
    - module_id: Specific module (optional, all if omitted)
    """
    from copilot_core.modules.registry import get_module_registry
    
    module_id = request.args.get("module_id")
    
    try:
        registry = get_module_registry()
        if module_id:
            deps = registry.get_module_dependencies(module_id=module_id)
        else:
            deps = registry.get_all_dependencies()
    except Exception as e:
        _LOGGER.warning("Failed to get dependencies: %s", e)
        deps = {"nodes": [], "edges": []}
    
    return jsonify({
        "ok": True,
        "dependencies": deps,
        "module_id": module_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/metrics")
def modules_metrics():
    """Get performance metrics for all modules.
    
    Query params:
    - hours: Time range (default 24)
    """
    from copilot_core.modules.registry import get_module_registry
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    hours = max(1, min(hours, 720))
    
    try:
        registry = get_module_registry()
        metrics = registry.get_modules_metrics(hours=hours)
    except Exception as e:
        _LOGGER.warning("Failed to get modules metrics: %s", e)
        metrics = []
    
    return jsonify({
        "ok": True,
        "metrics": metrics,
        "hours": hours,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
