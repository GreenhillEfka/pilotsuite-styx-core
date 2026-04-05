"""System & Resources API — Slice 238 (CORE ONLY)."""
from __future__ import annotations
import logging, psutil
from flask import Blueprint, jsonify
from datetime import datetime, timezone
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("system_resources", __name__, url_prefix="/api/v1")
@bp.get("/system/resources")
def get_system_resources():
    return jsonify({
        "ok": True,
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
@bp.get("/system/info")
def get_system_info():
    return jsonify({"ok": True, "platform": "linux", "arch": "x64"})
@bp.get("/system/uptime")
def get_system_uptime():
    return jsonify({"ok": True, "uptime_seconds": psutil.boot_time()})
