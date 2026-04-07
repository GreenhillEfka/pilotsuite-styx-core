"""Journey API — Slice 406 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("journey", __name__, url_prefix="/api/v1")
@bp.get("/journeys/active")
def get_active_journeys():
    return jsonify({"ok": True, "active": 0})
@bp.post("/journeys/start")
def start_journey():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("user")})
@bp.delete("/journeys/end")
def end_journey():
    data = request.get_json() or {}
    return jsonify({"ok": True, "ended": data.get("id")})
@bp.get("/journeys/stats")
def get_journey_stats():
    return jsonify({"ok": True, "stats": {}})
