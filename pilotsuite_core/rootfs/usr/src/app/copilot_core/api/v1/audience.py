"""Audience API — Slice 403 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("audience", __name__, url_prefix="/api/v1")
@bp.get("/audiences/list")
def get_audiences_list():
    return jsonify({"ok": True, "audiences": []})
@bp.post("/audiences/create")
def create_audience():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/audiences/delete")
def delete_audience():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/audiences/size")
def get_audience_size():
    return jsonify({"ok": True, "total": 0})
