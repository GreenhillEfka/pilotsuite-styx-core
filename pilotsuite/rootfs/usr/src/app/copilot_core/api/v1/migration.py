"""Migration API — Slice 372 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("migration", __name__, url_prefix="/api/v1")
@bp.get("/migrations/status")
def get_migrations_status():
    return jsonify({"ok": True, "pending": 0, "applied": 0})
@bp.post("/migrations/run")
def run_migrations():
    return jsonify({"ok": True, "applied": 0})
@bp.get("/migrations/list")
def get_migrations_list():
    return jsonify({"ok": True, "migrations": []})
@bp.delete("/migrations/reset")
def reset_migrations():
    return jsonify({"ok": True, "reset": True})
