"""Blueprints API Expansion (Slice 173).

Provides blueprint categories, YAML validation, import/export, and analytics.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)
blueprints_expansion_bp = Blueprint("blueprints_expansion", __name__, url_prefix="/api/v1/blueprints")

# Blueprint store (in-memory, replace with DB in production)
_blueprints: Dict[str, Dict[str, Any]] = {}

BLUEPRINT_CATEGORIES = [
    "automation",
    "script", 
    "scene",
    "sensor",
    "alert"
]

def _validate_blueprint_yaml(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validates blueprint structure."""
    errors = []
    if "name" not in data:
        errors.append("Missing 'name' field")
    if "blueprint" not in data:
        errors.append("Missing 'blueprint' section")
    elif not isinstance(data.get("blueprint"), dict):
        errors.append("'blueprint' must be a dict")
    return len(errors) == 0, errors

@blueprints_expansion_bp.route("/categories", methods=["GET"])
def get_blueprint_categories():
    """Returns available blueprint categories."""
    return jsonify({
        "categories": BLUEPRINT_CATEGORIES,
        "count": len(BLUEPRINT_CATEGORIES)
    })

@blueprints_expansion_bp.route("/validate", methods=["POST"])
def validate_blueprint():
    """Validates blueprint YAML without importing."""
    data = request.get_json() or {}
    is_valid, errors = _validate_blueprint_yaml(data)
    return jsonify({
        "valid": is_valid,
        "errors": errors
    })

@blueprints_expansion_bp.route("/import", methods=["POST"])
def import_blueprint():
    """Imports a new blueprint."""
    data = request.get_json() or {}
    
    is_valid, errors = _validate_blueprint_yaml(data)
    if not is_valid:
        return jsonify({"error": "Invalid blueprint", "errors": errors}), 400
    
    blueprint_id = data.get("name", "unnamed").lower().replace(" ", "_")
    _blueprints[blueprint_id] = {
        **data,
        "id": blueprint_id,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "category": data.get("blueprint", {}).get("domain", "automation")
    }
    
    return jsonify({"status": "imported", "blueprint_id": blueprint_id})

@blueprints_expansion_bp.route("/<blueprint_id>/export", methods=["GET"])
def export_blueprint(blueprint_id: str):
    """Exports a blueprint as YAML-compatible JSON."""
    if blueprint_id not in _blueprints:
        return jsonify({"error": "Blueprint not found"}), 404
    
    bp = _blueprints[blueprint_id]
    # Remove internal fields
    export_data = {k: v for k, v in bp.items() if k not in ["id", "imported_at"]}
    
    return jsonify({"blueprint": export_data})

@blueprints_expansion_bp.route("/analytics", methods=["GET"])
def get_blueprint_analytics():
    """Returns blueprint usage analytics."""
    if not _blueprints:
        return jsonify({"total": 0, "by_category": {}})
    
    by_category = Counter([bp.get("category", "unknown") for bp in _blueprints.values()])
    
    return jsonify({
        "total": len(_blueprints),
        "by_category": dict(by_category)
    })

# Initialize with sample blueprints
_sample_blueprints = [
    {"name": "Motion Light", "blueprint": {"domain": "automation", "description": "Turn on light on motion"}},
    {"name": "Climate Eco", "blueprint": {"domain": "automation", "description": "Eco mode when away"}},
    {"name": "Battery Alert", "blueprint": {"domain": "sensor", "description": "Alert on low battery"}}
]

for bp in _sample_blueprints:
    bp_id = bp["name"].lower().replace(" ", "_")
    _blueprints[bp_id] = {**bp, "id": bp_id, "imported_at": datetime.now(timezone.utc).isoformat(), "category": bp["blueprint"]["domain"]}
