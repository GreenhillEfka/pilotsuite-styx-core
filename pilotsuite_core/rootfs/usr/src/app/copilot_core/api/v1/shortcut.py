"""Shortcut API — Slice 351 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("shortcut", __name__, url_prefix="/api/v1")
@bp.get("/shortcuts/list")
def get_shortcuts_list():
    return jsonify({"ok": True, "shortcuts": []})
@bp.post("/shortcuts/create")
def create_shortcut():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("key")})
@bp.delete("/shortcuts/delete")
def delete_shortcut():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/shortcuts/macros")
def get_macros():
    return jsonify({"ok": True, "macros": []})
