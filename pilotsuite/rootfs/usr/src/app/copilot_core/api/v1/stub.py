"""Stub API — Slice 376 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("stub", __name__, url_prefix="/api/v1")
@bp.get("/stubs/list")
def get_stubs_list():
    return jsonify({"ok": True, "stubs": []})
@bp.post("/stubs/create")
def create_stub():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/stubs/delete")
def delete_stub():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/stubs/active")
def get_active_stubs():
    return jsonify({"ok": True, "active": []})
