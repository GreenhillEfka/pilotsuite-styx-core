"""Theme API — Slice 353 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("theme", __name__, url_prefix="/api/v1")
@bp.get("/themes/list")
def get_themes_list():
    return jsonify({"ok": True, "themes": []})
@bp.post("/themes/activate")
def activate_theme():
    data = request.get_json() or {}
    return jsonify({"ok": True, "activated": data.get("theme")})
@bp.get("/themes/active")
def get_active_theme():
    return jsonify({"ok": True, "theme": "default"})
@bp.get("/themes/preview")
def preview_theme():
    return jsonify({"ok": True, "preview": {}})
