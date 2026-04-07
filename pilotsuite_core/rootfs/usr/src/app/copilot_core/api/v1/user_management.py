"""User Management API — Slice 308 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("user_management", __name__, url_prefix="/api/v1")
@bp.get("/users/list")
def get_users_list():
    return jsonify({"ok": True, "users": []})
@bp.post("/users/create")
def create_user():
    data = request.get_json() or {}
    return jsonify({"ok": True, "user_id": data.get("username")})
@bp.delete("/users/delete")
def delete_user():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("user_id")})
@bp.get("/users/info")
def get_user_info():
    data = request.get_json() or {}
    return jsonify({"ok": True, "info": {}})
# Backwards compatibility alias
user_management_bp = bp
