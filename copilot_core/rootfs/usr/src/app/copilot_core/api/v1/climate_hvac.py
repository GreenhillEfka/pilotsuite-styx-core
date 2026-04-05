"""Climate & HVAC API — Slice 245 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("climate_hvac", __name__, url_prefix="/api/v1")
@bp.get("/climate/state")
def get_climate_state():
    return jsonify({"ok": True, "temperature": 21.5, "hvac_mode": "heat"})
@bp.post("/climate/set")
def set_climate():
    data = request.get_json() or {}
    return jsonify({"ok": True, "set": data})
@bp.get("/climate/schedules")
def get_climate_schedules():
    return jsonify({"ok": True, "schedules": []})
