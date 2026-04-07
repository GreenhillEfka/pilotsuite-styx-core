"""Funnel API — Slice 401 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("funnel", __name__, url_prefix="/api/v1")
@bp.get("/funnels/list")
def get_funnels_list():
    return jsonify({"ok": True, "funnels": []})
@bp.post("/funnels/create")
def create_funnel():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/funnels/delete")
def delete_funnel():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/funnels/stats")
def get_funnel_stats():
    return jsonify({"ok": True, "stats": {}})
