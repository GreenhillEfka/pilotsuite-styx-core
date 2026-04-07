"""Guardrail API — Slice 426 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("guardrail", __name__, url_prefix="/api/v1")
@bp.get("/guardrails/list")
def get_guardrails_list():
    return jsonify({"ok": True, "guardrails": []})
@bp.post("/guardrails/create")
def create_guardrail():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("name")})
@bp.delete("/guardrails/delete")
def delete_guardrail():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
