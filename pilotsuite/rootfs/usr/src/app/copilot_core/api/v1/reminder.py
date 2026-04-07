"""Reminder API — Slice 393 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("reminder", __name__, url_prefix="/api/v1")
@bp.get("/reminders/pending")
def get_pending_reminders():
    return jsonify({"ok": True, "pending": 0})
@bp.post("/reminders/create")
def create_reminder():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("message")})
@bp.delete("/reminders/dismiss")
def dismiss_reminder():
    data = request.get_json() or {}
    return jsonify({"ok": True, "dismissed": data.get("id")})
@bp.get("/reminders/history")
def get_reminders_history():
    return jsonify({"ok": True, "history": []})
