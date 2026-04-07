"""Fan & Light API — Slice 246 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("fan_light", __name__, url_prefix="/api/v1")
@bp.get("/fan/state")
def get_fan_state():
    return jsonify({"ok": True, "state": "off", "speed": 0})
@bp.post("/fan/set")
def set_fan():
    data = request.get_json() or {}
    return jsonify({"ok": True, "set": data})
@bp.get("/light/state")
def get_light_state():
    return jsonify({"ok": True, "state": "off", "brightness": 0})
@bp.post("/light/set")
def set_light():
    data = request.get_json() or {}
    return jsonify({"ok": True, "set": data})
