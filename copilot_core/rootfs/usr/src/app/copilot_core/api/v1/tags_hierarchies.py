"""Tags & Hierarchies API — Slice 236 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("tags_hierarchies", __name__, url_prefix="/api/v1")
@bp.get("/tags/hierarchies")
def get_tags_hierarchies():
    return jsonify({"ok": True, "hierarchies": []})
@bp.post("/tags/create")
def create_tag():
    data = request.get_json() or {}
    return jsonify({"ok": True, "tag_id": data.get("name")})
@bp.delete("/tags/<tag_id>")
def delete_tag(tag_id: str):
    return jsonify({"ok": True, "deleted": tag_id})
