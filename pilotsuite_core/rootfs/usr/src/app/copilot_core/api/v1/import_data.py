"""Import API — Slice 363 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("import_data", __name__, url_prefix="/api/v1")
@bp.get("/import/list")
def get_import_list():
    return jsonify({"ok": True, "imports": []})
@bp.post("/import/create")
def create_import():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("source")})
@bp.get("/import/status")
def get_import_status():
    return jsonify({"ok": True, "status": "pending"})
@bp.delete("/import/delete")
def delete_import():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
