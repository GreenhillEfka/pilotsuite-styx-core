"""Load API — Slice 413 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("load", __name__, url_prefix="/api/v1")
@bp.get("/load/jobs")
def get_load_jobs():
    return jsonify({"ok": True, "jobs": []})
@bp.post("/load/run")
def run_load():
    data = request.get_json() or {}
    return jsonify({"ok": True, "job_id": data.get("target")})
@bp.get("/load/status")
def get_load_status():
    return jsonify({"ok": True, "status": {}})
@bp.delete("/load/stop")
def stop_load():
    data = request.get_json() or {}
    return jsonify({"ok": True, "stopped": data.get("job_id")})
