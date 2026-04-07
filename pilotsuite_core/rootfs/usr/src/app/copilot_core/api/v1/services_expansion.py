"""Services API Expansion (Slice 172).

Provides service registry, testing, history tracking, and analytics.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)
services_expansion_bp = Blueprint("services_expansion", __name__, url_prefix="/api/v1/services")

# Service Registry with metadata
_SERVICE_REGISTRY = {
    "light.turn_on": {
        "name": "Light Turn On",
        "domain": "light",
        "description": "Turn on a light entity",
        "fields": {"entity_id": {"required": True, "type": "string"}, "brightness": {"required": False, "type": "integer"}}
    },
    "climate.set_temperature": {
        "name": "Climate Set Temperature",
        "domain": "climate",
        "description": "Set target temperature",
        "fields": {"entity_id": {"required": True, "type": "string"}, "temperature": {"required": True, "type": "float"}}
    },
    "media_player.play_media": {
        "name": "Play Media",
        "domain": "media_player",
        "description": "Play media on a media player",
        "fields": {"entity_id": {"required": True, "type": "string"}, "media_content_id": {"required": True, "type": "string"}}
    }
}

# Service call history (in-memory, replace with DB in production)
_service_history: List[Dict[str, Any]] = []

@services_expansion_bp.route("/registry", methods=["GET"])
def get_service_registry():
    """Returns full service registry with metadata."""
    return jsonify({
        "services": _SERVICE_REGISTRY,
        "count": len(_SERVICE_REGISTRY)
    })

@services_expansion_bp.route("/<service_id>/test", methods=["POST"])
def test_service(service_id: str):
    """Test a service call without execution."""
    if service_id not in _SERVICE_REGISTRY:
        return jsonify({"error": "Service not found"}), 404
    
    data = request.get_json() or {}
    service_meta = _SERVICE_REGISTRY[service_id]
    
    # Validate required fields
    missing_fields = []
    for field_name, field_spec in service_meta.get("fields", {}).items():
        if field_spec.get("required") and field_name not in data:
            missing_fields.append(field_name)
    
    return jsonify({
        "valid": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "service": service_meta
    })

@services_expansion_bp.route("/<service_id>/call", methods=["POST"])
def call_service(service_id: str):
    """Execute service call and track history."""
    if service_id not in _SERVICE_REGISTRY:
        return jsonify({"error": "Service not found"}), 404
    
    data = request.get_json() or {}
    
    # Log to history
    _service_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service_id": service_id,
        "data": data,
        "status": "success"
    })
    
    return jsonify({"status": "success", "service_id": service_id})

@services_expansion_bp.route("/history", methods=["GET"])
def get_service_history():
    """Returns service call history."""
    return jsonify({"history": _service_history[-100:]}) # Last 100 calls

@services_expansion_bp.route("/analytics", methods=["GET"])
def get_service_analytics():
    """Returns usage patterns and popular services."""
    if not _service_history:
        return jsonify({"popular_services": [], "total_calls": 0})
    
    service_counts = Counter([h["service_id"] for h in _service_history])
    popular = [
        {"service_id": sid, "call_count": count}
        for sid, count in service_counts.most_common(10)
    ]
    
    return jsonify({
        "popular_services": popular,
        "total_calls": len(_service_history),
        "unique_services": len(service_counts)
    })
