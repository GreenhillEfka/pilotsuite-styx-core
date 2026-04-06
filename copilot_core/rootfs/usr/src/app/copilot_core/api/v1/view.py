"""View API — Slice 358 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("view", __name__, url_prefix="/api/v1")
@bp.get("/views/list")
def get_views_list():
    return jsonify({"ok": True, "views": []})
@bp.post("/views/create")
def create_view():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/views/delete")
def delete_view():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/views/active")
def get_active_view():
    return jsonify({"ok": True, "view": None})
