"""Activity API — Slice 501 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("activity", __name__, url_prefix="/api/v1")
@bp.get("/activity/list")
def get_activity_list():
    return jsonify({"ok": True, "activities": []})
@bp.get("/activity/recent")
def get_recent_activity():
    return jsonify({"ok": True, "recent": []})
@bp.delete("/activity/clear")
def clear_activity():
    return jsonify({"ok": True, "cleared": True})
