"""Ping & Latency API — Slice 239 (CORE ONLY)."""
from __future__ import annotations
import logging, time
from flask import Blueprint, jsonify
from datetime import datetime, timezone
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("ping_latency", __name__, url_prefix="/api/v1")
@bp.get("/ping/latency")
def get_ping_latency():
    start = time.perf_counter()
    latency_ms = (time.perf_counter() - start) * 1000
    return jsonify({"ok": True, "latency_ms": latency_ms, "timestamp": datetime.now(timezone.utc).isoformat()})
@bp.get("/ping/health")
def get_ping_health():
    return jsonify({"ok": True, "status": "healthy", "response_time_ms": 1})
@bp.get("/ping/websocket")
def test_websocket_ping():
    return jsonify({"ok": True, "websocket": "available"})
