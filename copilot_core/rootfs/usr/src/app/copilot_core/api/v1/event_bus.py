"""Event Bus API — Slice 515 (CORE ONLY).
Symbiotic event bus linking HA and Core events.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("event_bus", __name__, url_prefix="/api/v1")

@bp.get("/events/types")
def list_event_types():
    return jsonify({"ok": True, "types": []})

@bp.get("/events/recent")
def get_recent_events():
    return jsonify({"ok": True, "events": []})

@bp.post("/events/publish")
def publish_event():
    data = request.get_json() or {}
    return jsonify({"ok": True, "published": data.get("type")})
