"""Experiment API — Slice 468 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("experiment", __name__, url_prefix="/api/v1")
@bp.get("/experiments/list")
def get_experiments_list():
    return jsonify({"ok": True, "experiments": []})
@bp.post("/experiments/create")
def create_experiment():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/experiments/stop")
def stop_experiment():
    data = request.get_json() or {}
    return jsonify({"ok": True, "stopped": data.get("id")})
