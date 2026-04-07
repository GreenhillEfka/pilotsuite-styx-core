"""Storage Info API — Slice 317 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("storage_info", __name__, url_prefix="/api/v1")
@bp.get("/storage/summary")
def get_storage_summary():
    return jsonify({"ok": True, "total": "1GB", "used": "500MB", "free": "500MB", "used_percent": 50})
@bp.get("/storage/usage")
def get_storage_usage():
    return jsonify({"ok": True, "usage": {"data": "200MB", "logs": "100MB", "backups": "200MB"}})
@bp.get("/storage/health")
def get_storage_health():
    return jsonify({"ok": True, "status": "healthy", "errors": 0})
@bp.get("/storage/backup")
def get_storage_backup():
    return jsonify({"ok": True, "last_backup": "2026-04-06T08:00:00Z"})
