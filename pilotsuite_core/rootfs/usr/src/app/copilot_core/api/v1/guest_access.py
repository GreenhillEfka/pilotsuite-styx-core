"""Guest & Access API — Slice 260 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("guest_access", __name__, url_prefix="/api/v1")
@bp.get("/guest/list")
def get_guest_list():
    return jsonify({"ok": True, "guests": []})
@bp.post("/guest/add")
def add_guest():
    data = request.get_json() or {}
    return jsonify({"ok": True, "guest_id": data.get("name")})
@bp.get("/access/codes")
def get_access_codes():
    return jsonify({"ok": True, "codes": []})
@bp.post("/access/generate")
def generate_access_code():
    return jsonify({"ok": True, "code": "1234"})
