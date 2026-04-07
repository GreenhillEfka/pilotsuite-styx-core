"""Build API — Slice 448 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("build", __name__, url_prefix="/api/v1")
@bp.get("/builds/list")
def get_builds_list():
    return jsonify({"ok": True, "builds": []})
@bp.post("/builds/trigger")
def trigger_build():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("project")})
@bp.get("/builds/status")
def get_build_status():
    return jsonify({"ok": True, "status": "idle"})
