"""Loadtest API — Slice 466 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("loadtest", __name__, url_prefix="/api/v1")
@bp.get("/loadtests/list")
def get_loadtests_list():
    return jsonify({"ok": True, "loadtests": []})
@bp.post("/loadtests/start")
def start_loadtest():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("scenario")})
@bp.get("/loadtests/status")
def loadtest_status():
    return jsonify({"ok": True, "status": "idle"})
