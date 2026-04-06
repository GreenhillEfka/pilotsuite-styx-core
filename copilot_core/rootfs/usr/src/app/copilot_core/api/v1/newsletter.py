"""Newsletter API — Slice 398 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("newsletter", __name__, url_prefix="/api/v1")
@bp.get("/newsletter/list")
def get_newsletter_list():
    return jsonify({"ok": True, "newsletters": []})
@bp.post("/newsletter/create")
def create_newsletter():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("subject")})
@bp.delete("/newsletter/delete")
def delete_newsletter():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/newsletter/subscribers")
def get_newsletter_subscribers():
    return jsonify({"ok": True, "count": 0})
