"""Permission API — Slice 436 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("permission", __name__, url_prefix="/api/v1")
@bp.get("/permissions/list")
def get_permissions_list():
    return jsonify({"ok": True, "permissions": []})
@bp.post("/permissions/create")
def create_permission():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/permissions/delete")
def delete_permission():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
