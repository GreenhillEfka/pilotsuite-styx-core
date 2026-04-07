"""Test Data API — Slice 377 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("test_data", __name__, url_prefix="/api/v1")
@bp.get("/testdata/count")
def get_testdata_count():
    return jsonify({"ok": True, "count": 0})
@bp.post("/testdata/generate")
def generate_testdata():
    data = request.get_json() or {}
    return jsonify({"ok": True, "generated": data.get("type")})
@bp.delete("/testdata/clear")
def clear_testdata():
    return jsonify({"ok": True, "cleared": True})
@bp.get("/testdata/list")
def get_testdata_list():
    return jsonify({"ok": True, "datasets": []})
