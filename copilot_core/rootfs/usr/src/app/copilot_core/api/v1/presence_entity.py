"""Presence Entity API — Slice 510 (CORE ONLY).
Unified presence detection entity.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("presence_entity", __name__, url_prefix="/api/v1")

@bp.get("/entities/presence")
def list_presence_entities():
    return jsonify({"ok": True, "entities": []})

@bp.get("/entities/presence/<entity_id>/state")
def get_presence_state(entity_id):
    return jsonify({"ok": True, "entity_id": entity_id, "present": False})

@bp.post("/entities/presence/<entity_id>/report")
def report_presence(entity_id):
    data = request.get_json() or {}
    return jsonify({"ok": True, "reported": data.get("source")})
