"""Worker API — Slice 420 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("worker", __name__, url_prefix="/api/v1")
@bp.get("/workers/list")
def get_workers_list():
    return jsonify({"ok": True, "workers": []})
@bp.get("/workers/status")
def get_worker_status():
    return jsonify({"ok": True, "status": "idle"})
