"""Pagination API — Slice 361 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("pagination", __name__, url_prefix="/api/v1")
@bp.get("/pagination/config")
def get_pagination_config():
    return jsonify({"ok": True, "page_size": 20, "max_page_size": 100})
@bp.post("/pagination/set")
def set_pagination():
    data = request.get_json() or {}
    return jsonify({"ok": True, "page_size": data.get("page_size")})
@bp.get("/pagination/info")
def get_pagination_info():
    return jsonify({"ok": True, "page": 1, "total_pages": 1})
@bp.delete("/pagination/reset")
def reset_pagination():
    return jsonify({"ok": True, "reset": True})
