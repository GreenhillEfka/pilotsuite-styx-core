"""EventBus API - Monitor and query inter-module events.

Endpoints:
  GET /api/v1/events/bus/history    Recent event history
  GET /api/v1/events/bus/metrics    EventBus metrics
"""
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.event_bus import get_event_bus

event_bus_api_bp = Blueprint("event_bus_api", __name__, url_prefix="/api/v1/events/bus")


@event_bus_api_bp.route("/history", methods=["GET"])
@require_token
def event_history():
    """Get recent event bus history."""
    bus = get_event_bus()
    topic = request.args.get("topic")
    limit = min(int(request.args.get("limit", 50)), 200)
    events = bus.get_history(topic=topic, limit=limit)
    return jsonify({"ok": True, "events": events, "count": len(events)})


@event_bus_api_bp.route("/metrics", methods=["GET"])
@require_token
def event_metrics():
    """Get event bus metrics."""
    bus = get_event_bus()
    return jsonify({"ok": True, "metrics": bus.get_metrics()})
