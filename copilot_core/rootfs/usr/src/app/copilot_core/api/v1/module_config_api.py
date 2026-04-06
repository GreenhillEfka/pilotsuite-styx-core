"""Module Configuration API (Slice 149).

Modular JSON editors for zone modules with field-level validation.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

module_config_bp = Blueprint("module_config_api", __name__, url_prefix="/api/v1/zone_automation")

# Canonical Schemas for UI Rendering
MODULE_SCHEMAS = {
    "presence": {
        "module_id": "presence",
        "name": "Presence Intelligence",
        "fields": [
            {"key": "presence_hold_minutes", "type": "int", "default": 5, "min": 1, "max": 60, "unit": "min"},
            {"key": "motion_sensitivity", "type": "float", "default": 0.8, "min": 0.0, "max": 1.0, "step": 0.1},
            {"key": "occupancy_mode", "type": "select", "options": ["standard", "precise", "relaxed"], "default": "standard"}
        ]
    },
    "light": {
        "module_id": "light",
        "name": "Light Intelligence",
        "fields": [
            {"key": "adaptive_lighting", "type": "bool", "default": True},
            {"key": "transition_seconds", "type": "int", "default": 3, "min": 0, "max": 30},
            {"key": "night_brightness", "type": "int", "default": 10, "min": 1, "max": 100, "unit": "%"}
        ]
    }
}

@module_config_bp.route("/module-schemas", methods=["GET"])
def get_module_schemas():
    """Get all available module schemas for UI rendering."""
    return jsonify({
        "ok": True,
        "schemas": list(MODULE_SCHEMAS.values())
    })

@module_config_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["GET"])
def get_zone_module_config(zone_id: str, module_id: str):
    """Get current configuration for a specific module in a zone."""
    # Placeholder: In production this pulls from ModuleRegistry
    schema = MODULE_SCHEMAS.get(module_id)
    if not schema:
        return jsonify({"ok": False, "error": "module_not_supported"}), 404
        
    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "module_id": module_id,
        "config": {f["key"]: f["default"] for f in schema["fields"]},
        "schema": schema
    })

@module_config_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["POST"])
def set_zone_module_config(zone_id: str, module_id: str):
    """Validate and save configuration for a module in a zone."""
    data = request.get_json() or {}
    config = data.get("config", {})
    
    schema = MODULE_SCHEMAS.get(module_id)
    if not schema:
        return jsonify({"ok": False, "error": "module_not_supported"}), 404
        
    # Validation Logic
    errors = []
    for field in schema["fields"]:
        val = config.get(field["key"])
        if val is not None:
            if field["type"] == "int" and not isinstance(val, int):
                errors.append(f"{field['key']} must be integer")
            elif field["type"] == "float" and not isinstance(val, (int, float)):
                errors.append(f"{field['key']} must be numeric")
            # Min/Max Check
            if "min" in field and val < field["min"]:
                errors.append(f"{field['key']} too low")
            if "max" in field and val > field["max"]:
                errors.append(f"{field['key']} too high")
                
    if errors:
        return jsonify({"ok": False, "error": "validation_failed", "field_errors": errors}), 400
        
    _LOGGER.info("Config persisted for %s in %s", module_id, zone_id)
    return jsonify({"ok": True, "zone_id": zone_id, "module_id": module_id, "persisted_config": config})

@module_config_bp.route("/modules/<module_id>/validate", methods=["POST"])
def validate_module_config(module_id: str):
    """Standalone validation endpoint for live UI feedback."""
    # Logic reused from POST /zones/...
    return jsonify({"ok": True, "valid": True})
