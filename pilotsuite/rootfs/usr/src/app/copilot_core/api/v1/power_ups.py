"""Power & UPS API — Slice 251 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("power_ups", __name__, url_prefix="/api/v1")
@bp.get("/power/state")
def get_power_state():
    return jsonify({"ok": True, "voltage": 230.0, "frequency": 50.0})
@bp.get("/ups/state")
def get_ups_state():
    return jsonify({"ok": True, "battery": 100, "on_battery": False})
@bp.get("/power/consumption")
def get_power_consumption():
    return jsonify({"ok": True, "watts": 150.0, "kwh_today": 3.6})
