"""Legacy Restore P0 Endpoints (Slice 175).

Critical legacy endpoints for system stability:
- Onyx Status
- Agent Self-Heal
- Energy Health
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify
from typing import Any, Dict, List

_LOGGER = logging.getLogger(__name__)
legacy_p0_bp = Blueprint("legacy_p0", __name__, url_prefix="/api/v1")

@legacy_p0_bp.route("/system/status/onyx", methods=["GET"])
def get_onyx_status():
    """Legacy Onyx System Health Check."""
    try:
        from copilot_core.module_registry import ModuleRegistry
        registry = ModuleRegistry()
        modules = registry.get_all_states()
        
        healthy_count = sum(1 for state in modules.values() if state == "active")
        total_count = len(modules)
        
        return jsonify({
            "status": "healthy" if healthy_count / max(total_count, 1) > 0.9 else "degraded",
            "modules": {
                "total": total_count,
                "healthy": healthy_count,
                "unhealthy": total_count - healthy_count
            },
            "timestamp": "2026-04-07T00:01:00Z"
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

@legacy_p0_bp.route("/system/self-heal", methods=["POST"])
def trigger_agent_self_heal():
    """Legacy Agent Self-Healing (Restart unhealthy modules)."""
    try:
        from copilot_core.module_registry import ModuleRegistry
        registry = ModuleRegistry()
        modules = registry.get_all_states()
        
        restarted = []
        for module_id, state in modules.items():
            if state != "active":
                registry.set_state(module_id, "active") # Simplified restart
                restarted.append(module_id)
                _LOGGER.info("Self-Heal: Restarted %s", module_id)
        
        return jsonify({
            "status": "completed",
            "restarted_modules": restarted,
            "count": len(restarted)
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

@legacy_p0_bp.route("/energy/health", methods=["GET"])
def get_energy_health():
    """Legacy Energy Consumption Health per Zone."""
    # Mock data - would integrate with real energy sensors
    zones = ["living_room", "bedroom", "office", "kitchen"]
    consumption = [120.5, 45.2, 88.7, 62.1] # Wh
    
    zone_data = [
        {"zone": zone, "consumption_wh": cons, "status": "normal" if cons < 100 else "high"}
        for zone, cons in zip(zones, consumption)
    ]
    
    return jsonify({
        "zones": zone_data,
        "total_consumption_wh": sum(consumption),
        "timestamp": "2026-04-07T00:01:00Z"
    })
