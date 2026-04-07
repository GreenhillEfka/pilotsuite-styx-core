"""Anomaly Detection API (Slice 147).

Anomaly history, acknowledgment, and snooze endpoints.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

anomaly_bp = Blueprint("anomaly", __name__, url_prefix="/api/v1/anomaly")

# In-memory storage (replace with DB in production)
_anomalies: Dict[str, Dict[str, Any]] = {}


def _create_anomaly(
    kind: str,
    severity: str,
    message: str,
    linked_kpi_ids: List[str] = None
) -> Dict[str, Any]:
    """Create a new anomaly record."""
    anomaly_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc)
    
    anomaly = {
        "anomaly_id": anomaly_id,
        "kind": kind,
        "severity": severity,
        "status": "new",
        "message": message,
        "detected_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
        "ttl_min": 60,
        "linked_kpi_ids": linked_kpi_ids or [],
    }
    
    _anomalies[anomaly_id] = anomaly
    return anomaly


@anomaly_bp.route("/history", methods=["GET"])
def get_anomaly_history():
    """Get anomaly history with filtering and pagination."""
    limit = request.args.get("limit", 200, type=int)
    sort = request.args.get("sort", "desc")
    status_filter = request.args.get("status")
    
    anomalies = list(_anomalies.values())
    
    # Filter by status
    if status_filter:
        anomalies = [a for a in anomalies if a["status"] == status_filter]
    
    # Sort by detected_at
    anomalies.sort(
        key=lambda x: x["detected_at"],
        reverse=(sort == "desc")
    )
    
    return jsonify({
        "anomalies": anomalies[:limit],
        "total": len(anomalies),
        "limit": limit,
    })


@anomaly_bp.route("/<anomaly_id>/ack", methods=["POST"])
def acknowledge_anomaly(anomaly_id: str):
    """Acknowledge an anomaly."""
    if anomaly_id not in _anomalies:
        return jsonify({"error": "Anomaly not found"}), 404
    
    anomaly = _anomalies[anomaly_id]
    
    if anomaly["status"] != "new":
        return jsonify({"error": "Anomaly already processed"}), 400
    
    anomaly["status"] = "acknowledged"
    anomaly["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    
    execution_id = str(uuid.uuid4())[:8]
    
    return jsonify({
        "success": True,
        "anomaly_id": anomaly_id,
        "status": "acknowledged",
        "execution_id": execution_id,
    })


@anomaly_bp.route("/<anomaly_id>/snooze", methods=["POST"])
def snooze_anomaly(anomaly_id: str):
    """Snooze an anomaly for a duration."""
    data = request.get_json() or {}
    duration = data.get("duration", "15m")
    
    if anomaly_id not in _anomalies:
        return jsonify({"error": "Anomaly not found"}), 404
    
    anomaly = _anomalies[anomaly_id]
    
    # Parse duration
    duration_map = {
        "15m": 15,
        "1h": 60,
        "4h": 240,
    }
    
    if duration not in duration_map:
        return jsonify({"error": "Invalid duration. Must be one of: 15m, 1h, 4h"}), 400
    
    anomaly["status"] = "snoozed"
    anomaly["snoozed_until"] = (
        datetime.now(timezone.utc) + timedelta(minutes=duration_map[duration])
    ).isoformat()
    anomaly["snooze_duration"] = duration
    
    execution_id = str(uuid.uuid4())[:8]
    
    return jsonify({
        "success": True,
        "anomaly_id": anomaly_id,
        "status": "snoozed",
        "snoozed_until": anomaly["snoozed_until"],
        "execution_id": execution_id,
    })


@anomaly_bp.route("/<anomaly_id>", methods=["DELETE"])
def delete_anomaly(anomaly_id: str):
    """Delete an anomaly (GDPR compliance)."""
    if anomaly_id not in _anomalies:
        return jsonify({"error": "Anomaly not found"}), 404
    
    del _anomalies[anomaly_id]
    
    return jsonify({"success": True, "anomaly_id": anomaly_id})


# Helper for creating test anomalies
def create_test_anomaly(kind: str, severity: str, message: str) -> Dict[str, Any]:
    """Create a test anomaly (for development)."""
    return _create_anomaly(kind, severity, message)
