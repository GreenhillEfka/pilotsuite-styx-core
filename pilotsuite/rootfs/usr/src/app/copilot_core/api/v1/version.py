"""Version API — Slice 302 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("version", __name__, url_prefix="/api/v1")
@bp.get("/version/info")
def get_version_info():
    return jsonify({"ok": True, "version": "15.3.40", "build": "2026-04-06"})
@bp.get("/version/check")
def check_updates():
    return jsonify({"ok": True, "update_available": False})
@bp.post("/version/update")
def trigger_update():
    return jsonify({"ok": True, "status": "started"})
# Backwards compatibility alias
version_bp = bp
