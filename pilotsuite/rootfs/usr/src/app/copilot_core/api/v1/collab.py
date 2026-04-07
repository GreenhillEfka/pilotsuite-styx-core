"""Collaboration API — Slice 499 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("collab", __name__, url_prefix="/api/v1")
@bp.get("/collab/sessions")
def get_collab_sessions():
    return jsonify({"ok": True, "sessions": []})
@bp.post("/collab/start")
def start_collab():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("doc")})
@bp.get("/collab/participants")
def get_collab_participants():
    return jsonify({"ok": True, "participants": []})
