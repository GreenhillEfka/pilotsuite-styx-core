"""Climate & HVAC API — Slice 263 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("climate_hvac", __name__, url_prefix="/api/v1")
@bp.get("/climate/state")
def get_climate_state():
    return jsonify({"ok": True, "temp": 22.0, "mode": "heat"})
@bp.get("/hvac/zones")
def get_hvac_zones():
    return jsonify({"ok": True, "zones": []})
@bp.post("/climate/set")
def set_climate():
    data = request.get_json() or {}
    return jsonify({"ok": True, "temp": data.get("temp")})
@bp.post("/hvac/mode")
def set_hvac_mode():
    data = request.get_json() or {}
    return jsonify({"ok": True, "mode": data.get("mode")})
