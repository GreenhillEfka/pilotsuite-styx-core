"""Presence V3 API — Slice 500 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("presence_v3", __name__, url_prefix="/api/v1")
@bp.get("/presence/v3/users")
def get_presence_v3_users():
    return jsonify({"ok": True, "users": []})
@bp.get("/presence/v3/status")
def get_presence_v3_status():
    return jsonify({"ok": True, "online": 0})
@bp.post("/presence/v3/update")
def update_presence_v3():
    data = request.get_json() or {}
    return jsonify({"ok": True, "updated": data.get("user")})
