"""Dashboard API — Slice 357 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("dashboard", __name__, url_prefix="/api/v1")
@bp.get("/dashboards/list")
def get_dashboards_list():
    return jsonify({"ok": True, "dashboards": []})
@bp.post("/dashboards/create")
def create_dashboard():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/dashboards/delete")
def delete_dashboard():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/dashboards/active")
def get_active_dashboard():
    return jsonify({"ok": True, "dashboard": None})
