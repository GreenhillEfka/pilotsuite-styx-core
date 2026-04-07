"""Mock API — Slice 375 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("mock", __name__, url_prefix="/api/v1")
@bp.get("/mock/count")
def get_mock_count():
    return jsonify({"ok": True, "count": 0})
@bp.post("/mock/generate")
def generate_mock():
    data = request.get_json() or {}
    return jsonify({"ok": True, "generated": data.get("type")})
@bp.delete("/mock/clear")
def clear_mock():
    return jsonify({"ok": True, "cleared": True})
@bp.get("/mock/templates")
def get_mock_templates():
    return jsonify({"ok": True, "templates": []})
