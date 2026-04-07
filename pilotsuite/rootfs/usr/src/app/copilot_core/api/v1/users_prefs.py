"""Users & Preferences API — Slice 224 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("users_prefs", __name__, url_prefix="/api/v1")
@bp.get("/users/<user_id>/preferences")
def get_user_preferences(user_id: str):
    return jsonify({"ok": True, "user_id": user_id, "preferences": {}})
@bp.put("/users/<user_id>/preferences")
def update_user_preferences(user_id: str):
    data = request.get_json() or {}
    return jsonify({"ok": True, "user_id": user_id, "updated": data})
@bp.get("/users/preferences")
def get_all_preferences():
    return jsonify({"ok": True, "preferences": {}})
