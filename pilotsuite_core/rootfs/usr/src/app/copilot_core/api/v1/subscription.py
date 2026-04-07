"""Subscription API — Slice 504 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("subscription", __name__, url_prefix="/api/v1")
@bp.get("/subscriptions/list")
def get_subscriptions_list():
    return jsonify({"ok": True, "subscriptions": []})
@bp.post("/subscriptions/create")
def create_subscription():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("plan")})
@bp.delete("/subscriptions/cancel")
def cancel_subscription():
    data = request.get_json() or {}
    return jsonify({"ok": True, "cancelled": data.get("id")})
