"""Sort API — Slice 360 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("sort", __name__, url_prefix="/api/v1")
@bp.get("/sort/list")
def get_sort_list():
    return jsonify({"ok": True, "orders": []})
@bp.post("/sort/apply")
def apply_sort():
    data = request.get_json() or {}
    return jsonify({"ok": True, "applied": data.get("order")})
@bp.get("/sort/default")
def get_default_sort():
    return jsonify({"ok": True, "default": "asc"})
@bp.delete("/sort/reset")
def reset_sort():
    return jsonify({"ok": True, "reset": True})
