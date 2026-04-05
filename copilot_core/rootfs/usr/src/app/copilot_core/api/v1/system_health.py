"""System & Health API — Slice 211."""
from __future__ import annotations
import logging, os, psutil
from flask import Blueprint, jsonify
from datetime import datetime, timezone
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("system_health", __name__, url_prefix="/api/v1")
@bp.get("/system/resources")
def get_system_resources():
    return jsonify({"ok": True, "cpu": psutil.cpu_percent(), "memory": psutil.virtual_memory().percent, "disk": psutil.disk_usage("/").percent})
@bp.get("/ping/latency")
def get_ping_latency():
    import time
    start = time.perf_counter()
    return jsonify({"ok": True, "latency_ms": (time.perf_counter() - start) * 1000, "timestamp": datetime.now(timezone.utc).isoformat()})
@bp.get("/services/registry")
def get_services_registry():
    return jsonify({"ok": True, "services": []})
@bp.get("/blueprints/categories")
def get_blueprints_categories():
    return jsonify({"ok": True, "categories": []})
