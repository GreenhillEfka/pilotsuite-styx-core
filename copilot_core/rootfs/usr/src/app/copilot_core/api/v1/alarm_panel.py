"""Alarm Control Panel API — Slice 248 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("alarm_panel", __name__, url_prefix="/api/v1")
@bp.get("/alarm/state")
def get_alarm_state():
    return jsonify({"ok": True, "state": "disarmed"})
@bp.post("/alarm/arm")
def arm_alarm():
    data = request.get_json() or {}
    return jsonify({"ok": True, "armed": data.get("mode", "away")})
@bp.post("/alarm/disarm")
def disarm_alarm():
    return jsonify({"ok": True, "disarmed": True})
