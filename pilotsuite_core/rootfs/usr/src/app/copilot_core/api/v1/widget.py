"""Widget API — Slice 355 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("widget", __name__, url_prefix="/api/v1")
@bp.get("/widgets/list")
def get_widgets_list():
    return jsonify({"ok": True, "widgets": []})
@bp.post("/widgets/add")
def add_widget():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("type")})
@bp.delete("/widgets/remove")
def remove_widget():
    data = request.get_json() or {}
    return jsonify({"ok": True, "removed": data.get("id")})
@bp.get("/widgets/positions")
def get_widget_positions():
    return jsonify({"ok": True, "positions": {}})
