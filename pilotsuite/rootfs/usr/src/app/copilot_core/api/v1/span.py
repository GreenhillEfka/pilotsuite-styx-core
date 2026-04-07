"""Span API — Slice 455 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("span", __name__, url_prefix="/api/v1")
@bp.get("/spans/list")
def get_spans_list():
    return jsonify({"ok": True, "spans": []})
@bp.post("/spans/create")
def create_span():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("trace")})
@bp.delete("/spans/close")
def close_span():
    data = request.get_json() or {}
    return jsonify({"ok": True, "closed": data.get("id")})
