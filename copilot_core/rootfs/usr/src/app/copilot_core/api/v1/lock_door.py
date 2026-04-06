"""Lock & Door API — Slice 266 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("lock_door", __name__, url_prefix="/api/v1")
@bp.get("/locks/list")
def get_locks_list():
    return jsonify({"ok": True, "locks": []})
@bp.post("/locks/lock")
def lock_door():
    return jsonify({"ok": True, "locked": True})
@bp.post("/locks/unlock")
def unlock_door():
    return jsonify({"ok": True, "unlocked": True})
@bp.get("/doors/state")
def get_doors_state():
    return jsonify({"ok": True, "open": False})
