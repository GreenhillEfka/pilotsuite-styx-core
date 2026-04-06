"""Tag API — Slice 346 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("tag", __name__, url_prefix="/api/v1")
@bp.get("/tags/list")
def get_tags_list():
    return jsonify({"ok": True, "tags": []})
@bp.post("/tags/create")
def create_tag():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/tags/delete")
def delete_tag():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/tags/hierarchy")
def get_tags_hierarchy():
    return jsonify({"ok": True, "tree": []})
