"""Vacation & Rental API — Slice 259 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("vacation_rental", __name__, url_prefix="/api/v1")
@bp.get("/vacation/mode")
def get_vacation_mode():
    return jsonify({"ok": True, "active": False})
@bp.post("/vacation/on")
def vacation_mode_on():
    return jsonify({"ok": True, "active": True})
@bp.post("/vacation/off")
def vacation_mode_off():
    return jsonify({"ok": True, "active": False})
@bp.get("/rental/guest")
def get_guest_info():
    return jsonify({"ok": True, "guest": "none"})
