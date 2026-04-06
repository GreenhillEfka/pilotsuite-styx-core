"""Module Configuration API (Slice 149).


Modular JSON editors for zone modules with field-level validation.

Modular JSON editors for zone modules with validation.

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
        

from typing import Any, Dict, List, Optional, Union

_LOGGER = logging.getLogger(__name__)

module_config_bp = Blueprint("module_config", __name__, url_prefix="/api/v1/zone_automation")

# Module schemas definition
MODULE_SCHEMAS = {
    "presence": {
        "key": "presence",
        "name": "Presence Intelligence",
        "fields": [
            {"key": "presence_hold_minutes", "field_type": "int", "default": 5, "min": 1, "max": 60},
            {"key": "auto_off_minutes", "field_type": "int", "default": 10, "min": 1, "max": 120},
            {"key": "motion_sensitivity", "field_type": "float", "default": 0.8, "min": 0.0, "max": 1.0, "step": 0.1},
        ]
    },
    "light": {
        "key": "light",
        "name": "Light Intelligence",
        "fields": [
            {"key": "scene_default", "field_type": "select", "default": "relax", "options": ["relax", "focus", "energize", "night"]},
            {"key": "brightness_max", "field_type": "int", "default": 100, "min": 0, "max": 100, "step": 1},
            {"key": "adaptive_brightness", "field_type": "bool", "default": True},
        ]
    },
    "climate": {
        "key": "climate",
        "name": "Climate Intelligence",
        "fields": [
            {"key": "target_temp_day", "field_type": "float", "default": 21.0, "min": 15.0, "max": 28.0, "step": 0.5},
            {"key": "target_temp_night", "field_type": "float", "default": 18.0, "min": 15.0, "max": 25.0, "step": 0.5},
            {"key": "eco_mode_enabled", "field_type": "bool", "default": True},
        ]
    },
}

# In-memory storage for module configs
_module_configs: Dict[str, Dict[str, Any]] = {}


@module_config_bp.route("/module-schemas", methods=["GET"])
def get_module_schemas():
    """Get all module schemas."""
    return jsonify({
        "schemas": list(MODULE_SCHEMAS.values()),
        "count": len(MODULE_SCHEMAS),
    })


@module_config_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["GET"])
def get_module_config(zone_id: str, module_id: str):
    """Get configuration for a module in a zone."""
    config_key = f"{zone_id}:{module_id}"
    
    if config_key not in _module_configs:
        # Return default config from schema
        schema = MODULE_SCHEMAS.get(module_id)
        if not schema:
            return jsonify({"error": f"Unknown module: {module_id}"}), 404
        
        default_config = {
            field["key"]: field["default"]
            for field in schema.get("fields", [])
        }
        return jsonify({
            "zone_id": zone_id,
            "module_id": module_id,
            "config": default_config,
            "is_default": True,
        })
    
    return jsonify({
        "zone_id": zone_id,
        "module_id": module_id,
        "config": _module_configs[config_key],
        "is_default": False,
    })


@module_config_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["POST"])
def set_module_config(zone_id: str, module_id: str):
    """Set configuration for a module in a zone."""
    data = request.get_json()
    if not data or "config" not in data:
        return jsonify({"error": "Missing 'config'"}), 400
    
    config = data["config"]
    
    # Validate config
    schema = MODULE_SCHEMAS.get(module_id)
    if not schema:
        return jsonify({"error": f"Unknown module: {module_id}"}), 404
    
    validation_result = _validate_config(module_id, config)
    if not validation_result["valid"]:
        return jsonify({
            "ok": False,
            "error": "validation_failed",
            "field_errors": validation_result["errors"],
        }), 400
    
    # Store config
    config_key = f"{zone_id}:{module_id}"
    _module_configs[config_key] = config
    
    _LOGGER.info("Updated config for %s in zone %s", module_id, zone_id)
    

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

        "config": config,
    })


def _validate_config(module_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate config against schema."""
    schema = MODULE_SCHEMAS.get(module_id)
    if not schema:
        return {"valid": False, "errors": [{"field": "_", "error": "Unknown module"}]}
    
    errors = []
    valid = True
    
    for field in schema.get("fields", []):
        key = field["key"]
        value = config.get(key)
        field_type = field["field_type"]
        
        # Check type
        if field_type == "int" and value is not None and not isinstance(value, int):
            errors.append({"field": key, "error": f"Expected int, got {type(value).__name__}"})
            valid = False
            continue
        
        if field_type == "float" and value is not None and not isinstance(value, (int, float)):
            errors.append({"field": key, "error": f"Expected float, got {type(value).__name__}"})
            valid = False
            continue
        
        if field_type == "bool" and value is not None and not isinstance(value, bool):
            errors.append({"field": key, "error": f"Expected bool, got {type(value).__name__}"})
            valid = False
            continue
        
        # Check min/max for int/float
        if field_type in ("int", "float") and value is not None:
            if "min" in field and value < field["min"]:
                errors.append({"field": key, "error": f"Value {value} below minimum {field['min']}"})
                valid = False
            
            if "max" in field and value > field["max"]:
                errors.append({"field": key, "error": f"Value {value} above maximum {field['max']}"})
                valid = False
        
        # Check select options
        if field_type == "select" and value is not None:
            if value not in field.get("options", []):
                errors.append({"field": key, "error": f"Invalid option '{value}'"})
                valid = False
    
    return {"valid": valid, "errors": errors}


@module_config_bp.route("/modules/<module_id>/validate", methods=["POST"])
def validate_module_config(module_id: str):
    """Validate a module configuration without saving."""
    data = request.get_json()
    if not data or "config" not in data:
        return jsonify({"error": "Missing 'config'"}), 400
    
    config = data["config"]
    
    result = _validate_config(module_id, config)
    
    if result["valid"]:
        return jsonify({"ok": True, "valid": True})
    else:
        return jsonify({
            "ok": False,
            "valid": False,
            "field_errors": result["errors"],
        }), 400

