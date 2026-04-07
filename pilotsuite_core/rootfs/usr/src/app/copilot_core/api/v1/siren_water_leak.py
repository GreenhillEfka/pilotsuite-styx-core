"""Siren & Water Leak API — Slice 249 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("siren_water_leak", __name__, url_prefix="/api/v1")
@bp.get("/siren/state")
def get_siren_state():
    return jsonify({"ok": True, "state": "off"})
@bp.post("/siren/activate")
def activate_siren():
    data = request.get_json() or {}
    return jsonify({"ok": True, "activated": data.get("tone", "alarm")})
@bp.get("/water_leak/state")
def get_water_leak_state():
    return jsonify({"ok": True, "leak_detected": False})
@bp.post("/water_leak/test")
def test_water_leak():
    return jsonify({"ok": True, "test": "passed"})
