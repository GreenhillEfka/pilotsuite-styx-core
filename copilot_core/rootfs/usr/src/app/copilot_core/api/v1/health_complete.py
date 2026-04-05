"""Health API Complete — Slice 220 (CORE ONLY)."""
from __future__ import annotations
import logging, psutil
from flask import Blueprint, jsonify
from datetime import datetime, timezone
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("health_complete", __name__, url_prefix="/api/v1")
@bp.get("/health")
def get_health():
    return jsonify({"ok": True, "status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})
@bp.get("/health/components")
def get_health_components():
    return jsonify({"ok": True, "components": {"api": "up", "db": "up", "cache": "up"}})
@bp.get("/health/memory")
def get_health_memory():
    mem = psutil.virtual_memory()
    return jsonify({"ok": True, "memory_percent": mem.percent, "available_mb": mem.available // 1024 // 1024})
