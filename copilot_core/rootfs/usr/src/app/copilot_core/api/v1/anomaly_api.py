"""Anomaly Detection API (Slice 147).

Standardized endpoint for system anomalies with Ack/Snooze support.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

anomaly_bp = Blueprint("anomaly_api", __name__, url_prefix="/api/v1/anomaly")

# In-memory store for demonstration (production uses DB)
_anomalies: Dict[str, Dict[str, Any]] = {}

@anomaly_bp.route("/history", methods=["GET"])
def get_anomaly_history():
    """Get recent system anomalies."""
    limit = request.args.get("limit", 200, type=int)
    return jsonify({
        "ok": True,
        "anomalies": list(_anomalies.values())[:limit],
        "total": len(_anomalies),
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat()}
    })

@anomaly_bp.route("/anomalies/<id>/ack", methods=["POST"])
def acknowledge_anomaly(id: str):
    """Acknowledge a detected anomaly."""
    if id not in _anomalies:
        return jsonify({"ok": False, "error": "not_found"}), 404
        
    _anomalies[id]["status"] = "acknowledged"
    _anomalies[id]["ack_at"] = datetime.now(timezone.utc).isoformat()
    
    return jsonify({
        "ok": True, 
        "anomaly_id": id, 
        "execution_id": str(uuid.uuid4())
    })

@anomaly_bp.route("/anomalies/<id>/snooze", methods=["POST"])
def snooze_anomaly(id: str):
    """Snooze an anomaly for a specific duration."""
    data = request.get_json() or {}
    duration = data.get("duration", "1h") # 15m|1h|4h
    
    if id not in _anomalies:
        return jsonify({"ok": False, "error": "not_found"}), 404
        
    _anomalies[id]["status"] = "snoozed"
    _anomalies[id]["snoozed_until"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat() # Simplified
    
    return jsonify({
        "ok": True, 
        "anomaly_id": id, 
        "execution_id": str(uuid.uuid4())
    })

def record_anomaly(kind: str, severity: str, message: str, linked_kpi: Optional[str] = None):
    """Internal helper to record a new anomaly."""
    anomaly_id = str(uuid.uuid4())[:8]
    _anomalies[anomaly_id] = {
        "anomaly_id": anomaly_id,
        "kind": kind,
        "severity": severity, # info|warning|critical
        "status": "new",
        "message": message,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "ttl_min": 60,
        "linked_kpi_ids": [linked_kpi] if linked_kpi else []
    }
    return anomaly_id
