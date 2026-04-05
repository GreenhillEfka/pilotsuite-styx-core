"""Entities & States API — Slice 209."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("entities_states", __name__, url_prefix="/api/v1/entities")
@bp.get("/<entity_id>/state")
def get_entity_state(entity_id: str):
    return jsonify({"ok": True, "entity_id": entity_id, "state": "unknown"})
@bp.post("/<entity_id>/state")
def set_entity_state(entity_id: str):
    data = request.get_json() or {}
    return jsonify({"ok": True, "entity_id": entity_id, "new_state": data.get("state")})
@bp.get("/statistics/summary")
def get_entities_statistics():
    return jsonify({"ok": True, "total": 0, "by_domain": {}})
