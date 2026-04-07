"""Oncall API — Slice 459 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("oncall", __name__, url_prefix="/api/v1")
@bp.get("/oncall/list")
def get_oncall_list():
    return jsonify({"ok": True, "schedules": []})
@bp.get("/oncall/current")
def get_current_oncall():
    return jsonify({"ok": True, "responder": "none"})
@bp.post("/oncall/escalate")
def escalate_oncall():
    data = request.get_json() or {}
    return jsonify({"ok": True, "escalated": data.get("incident")})
