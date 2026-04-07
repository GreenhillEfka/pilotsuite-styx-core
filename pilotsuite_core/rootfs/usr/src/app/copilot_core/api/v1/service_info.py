"""Service Info API — Slice 330 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("service_info", __name__, url_prefix="/api/v1")
@bp.get("/services/list")
def get_services_list():
    return jsonify({"ok": True, "services": []})
@bp.get("/services/status")
def get_services_status():
    return jsonify({"ok": True, "running": 0, "stopped": 0})
@bp.post("/services/start")
def start_service():
    data = request.get_json() or {}
    return jsonify({"ok": True, "started": data.get("name")})
@bp.post("/services/stop")
def stop_service():
    data = request.get_json() or {}
    return jsonify({"ok": True, "stopped": data.get("name")})
