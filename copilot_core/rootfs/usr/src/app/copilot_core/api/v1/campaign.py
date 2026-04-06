"""Campaign API — Slice 400 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("campaign", __name__, url_prefix="/api/v1")
@bp.get("/campaigns/active")
def get_active_campaigns():
    return jsonify({"ok": True, "active": 0})
@bp.post("/campaigns/create")
def create_campaign():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/campaigns/end")
def end_campaign():
    data = request.get_json() or {}
    return jsonify({"ok": True, "ended": data.get("id")})
@bp.get("/campaigns/stats")
def get_campaign_stats():
    return jsonify({"ok": True, "stats": {}})
