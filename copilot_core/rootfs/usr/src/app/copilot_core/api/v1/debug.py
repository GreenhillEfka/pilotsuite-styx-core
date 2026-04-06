"""Debug API — Slice 463 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("debug", __name__, url_prefix="/api/v1")
@bp.get("/debug/info")
def debug_info():
    return jsonify({"ok": True, "info": {}})
@bp.post("/debug/enable")
def enable_debug():
    return jsonify({"ok": True, "enabled": True})
@bp.delete("/debug/disable")
def disable_debug():
    return jsonify({"ok": True, "enabled": False})
