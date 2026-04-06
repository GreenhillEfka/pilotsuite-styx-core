"""Restore API — Slice 477 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("restore", __name__, url_prefix="/api/v1")
@bp.get("/restores/list")
def get_restores_list():
    return jsonify({"ok": True, "restores": []})
@bp.post("/restores/start")
def start_restore():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("backup")})
@bp.get("/restores/status")
def restore_status():
    return jsonify({"ok": True, "status": "idle"})
