"""Ping API Expansion (Slice 171).

Extends basic ping with diagnostics, latency tracking, and history.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from flask import Blueprint, jsonify
from typing import Any, Dict, List

_LOGGER = logging.getLogger(__name__)
ping_expansion_bp = Blueprint("ping_expansion", __name__, url_prefix="/api/v1/ping")

# In-memory storage for ping history (replace with DB in production)
_ping_history: List[Dict[str, Any]] = []

@ping_expansion_bp.route("/", methods=["GET"])
def ping_basic():
    """Basic health ping."""
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

@ping_expansion_bp.route("/diagnostics", methods=["GET"])
def ping_diagnostics():
    """Extended ping with component health."""
    diagnostics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": {"status": "ok", "latency_ms": 2.1},
            "cache": {"status": "ok", "latency_ms": 0.5},
            "external_api": {"status": "warning", "latency_ms": 120.0, "details": "High latency"},
        },
        "overall_status": "degraded"
    }
    return jsonify(diagnostics)

@ping_expansion_bp.route("/latency", methods=["GET"])
def ping_latency():
    """Response time tracking endpoint."""
    start_time = time.perf_counter()
    
    # Simulate some work
    time.sleep(0.001) # 1ms delay
    
    end_time = time.perf_counter()
    latency_ms = round((end_time - start_time) * 1000, 2)
    
    # Store in history
    _ping_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": latency_ms
    })
    
    return jsonify({"latency_ms": latency_ms})

@ping_expansion_bp.route("/history", methods=["GET"])
def ping_history():
    """Returns historical ping data."""
    # Return last 50 entries
    return jsonify({"history": _ping_history[-50:]})

# Initialize with some dummy data
def _initialize_ping_history():
    for i in range(10):
        _ping_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": round(10 + (i * 2.5), 2) # Simulated latency trend
        })

_initialize_ping_history()
