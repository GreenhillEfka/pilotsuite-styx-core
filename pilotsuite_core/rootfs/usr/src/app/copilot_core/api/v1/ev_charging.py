"""EV Charging API — Slice 255 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("ev_charging", __name__, url_prefix="/api/v1")
@bp.get("/ev/charger")
def get_charger_state():
    return jsonify({"ok": True, "charging": False, "power": 0, "soc": 0})
@bp.post("/ev/start")
def start_charging():
    return jsonify({"ok": True, "started": True})
@bp.post("/ev/stop")
def stop_charging():
    return jsonify({"ok": True, "stopped": True})
@bp.get("/ev/session")
def get_charging_session():
    return jsonify({"ok": True, "kwh": 0, "cost": 0.0})
