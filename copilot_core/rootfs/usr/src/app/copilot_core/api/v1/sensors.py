"""Sensors & Binary Sensors API — Slice 268 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("sensors", __name__, url_prefix="/api/v1")
@bp.get("/sensors/list")
def get_sensors_list():
    return jsonify({"ok": True, "sensors": []})
@bp.get("/sensors/values")
def get_sensor_values():
    return jsonify({"ok": True, "values": {}})
@bp.get("/binary_sensors/list")
def get_binary_sensors_list():
    return jsonify({"ok": True, "sensors": []})
@bp.get("/binary_sensors/state")
def get_binary_sensors_state():
    return jsonify({"ok": True, "states": {}})
