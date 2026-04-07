"""Persona API — Slice 404 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("persona", __name__, url_prefix="/api/v1")
@bp.get("/personas/list")
def get_personas_list():
    return jsonify({"ok": True, "personas": []})
@bp.post("/personas/create")
def create_persona():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/personas/delete")
def delete_persona():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/personas/attributes")
def get_persona_attributes():
    return jsonify({"ok": True, "attributes": []})
