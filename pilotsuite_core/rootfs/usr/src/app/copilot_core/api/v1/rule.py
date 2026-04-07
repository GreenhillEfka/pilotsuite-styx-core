"""Rule API — Slice 424 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("rule", __name__, url_prefix="/api/v1")
@bp.get("/rules/list")
def get_rules_list():
    return jsonify({"ok": True, "rules": []})
@bp.post("/rules/create")
def create_rule():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/rules/delete")
def delete_rule():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
