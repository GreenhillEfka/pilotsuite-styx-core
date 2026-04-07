"""Rollout API — Slice 471 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("rollout", __name__, url_prefix="/api/v1")
@bp.get("/rollouts/list")
def get_rollouts_list():
    return jsonify({"ok": True, "rollouts": []})
@bp.post("/rollouts/start")
def start_rollout():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("feature")})
@bp.get("/rollouts/progress")
def rollout_progress():
    return jsonify({"ok": True, "percentage": 0})
