"""Sync API — Slice 480 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("sync", __name__, url_prefix="/api/v1")
@bp.get("/sync/status")
def get_sync_status():
    return jsonify({"ok": True, "synced": True})
@bp.post("/sync/trigger")
def trigger_sync():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("source")})
@bp.get("/sync/conflicts")
def get_sync_conflicts():
    return jsonify({"ok": True, "conflicts": []})
