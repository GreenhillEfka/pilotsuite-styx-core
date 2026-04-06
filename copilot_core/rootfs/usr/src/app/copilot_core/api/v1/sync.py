"""Sync API — Slice 364 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("sync", __name__, url_prefix="/api/v1")
@bp.get("/sync/status")
def get_sync_status():
    return jsonify({"ok": True, "status": "idle", "last_sync": None})
@bp.post("/sync/start")
def start_sync():
    return jsonify({"ok": True, "started": True})
@bp.post("/sync/stop")
def stop_sync():
    return jsonify({"ok": True, "stopped": True})
@bp.get("/sync/history")
def get_sync_history():
    return jsonify({"ok": True, "history": []})
