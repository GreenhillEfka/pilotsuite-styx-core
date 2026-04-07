"""Irrigation & Garden API — Slice 256 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("irrigation_garden", __name__, url_prefix="/api/v1")
@bp.get("/irrigation/zones")
def get_irrigation_zones():
    return jsonify({"ok": True, "zones": []})
@bp.post("/irrigation/start")
def start_irrigation():
    data = request.get_json() or {}
    return jsonify({"ok": True, "started": data.get("zone")})
@bp.post("/irrigation/stop")
def stop_irrigation():
    return jsonify({"ok": True, "stopped": True})
@bp.get("/irrigation/schedule")
def get_irrigation_schedule():
    return jsonify({"ok": True, "schedule": []})
