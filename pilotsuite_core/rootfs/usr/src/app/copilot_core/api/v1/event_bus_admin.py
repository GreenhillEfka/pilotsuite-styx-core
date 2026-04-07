"""Event Bus Admin API — Vertical Slice Phase 2.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("event_bus_admin", __name__, url_prefix="/api/v1/events")

_event_history = []

@bp.route("/publish", methods=["POST"])
def publish_event():
    data = request.get_json() or {}
    event = {
        "event_id": f"evt_{len(_event_history)}",
        "event_type": data.get("event_type"),
        "payload": data.get("payload"),
        "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
        "source": data.get("source", "core")
    }
    _event_history.append(event)
    if len(_event_history) > 1000: _event_history.pop(0)
    return jsonify({"ok": True, "event_id": event["event_id"]})

@bp.route("/recent", methods=["GET"])
def get_recent_events():
    limit = int(request.args.get("limit", 50))
    return jsonify({"ok": True, "events": _event_history[-limit:], "count": len(_event_history)})
