"""Dependency API — Slice 447 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("dependency", __name__, url_prefix="/api/v1")
@bp.get("/dependencies/list")
def get_dependencies_list():
    return jsonify({"ok": True, "dependencies": []})
@bp.post("/dependencies/create")
def create_dependency():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("source")})
@bp.delete("/dependencies/delete")
def delete_dependency():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
