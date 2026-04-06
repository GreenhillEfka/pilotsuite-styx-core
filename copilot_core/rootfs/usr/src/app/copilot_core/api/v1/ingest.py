"""Ingest API — Slice 415 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("ingest", __name__, url_prefix="/api/v1")
@bp.get("/ingest/jobs")
def get_ingest_jobs():
    return jsonify({"ok": True, "jobs": []})
@bp.post("/ingest/run")
def run_ingest():
    data = request.get_json() or {}
    return jsonify({"ok": True, "job_id": data.get("source")})
@bp.get("/ingest/status")
def get_ingest_status():
    return jsonify({"ok": True, "status": {}})
@bp.delete("/ingest/stop")
def stop_ingest():
    data = request.get_json() or {}
    return jsonify({"ok": True, "stopped": data.get("job_id")})
