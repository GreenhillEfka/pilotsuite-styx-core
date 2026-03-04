"""
Integration Bus REST API.

Endpoints:
    POST /api/v1/integration/feedback     — Submit suggestion feedback
    GET  /api/v1/integration/bus/stats    — Bus throughput metrics
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from .bus import IntegrationBus

_LOGGER = logging.getLogger(__name__)

integration_bp = Blueprint("integration", __name__, url_prefix="/api/v1/integration")

# Wired by init_integration_api()
_bus: IntegrationBus | None = None
_feedback_loop = None


def init_integration_api(bus: IntegrationBus, feedback_loop=None) -> None:
    """Wire the integration API with bus and feedback loop instances."""
    global _bus, _feedback_loop
    _bus = bus
    _feedback_loop = feedback_loop


@integration_bp.route("/feedback", methods=["POST"])
def post_feedback():
    """Submit feedback for a suggestion.

    Body:
        {
            "suggestion_id": "abc123",
            "accepted": true,
            "related_entities": ["light.kitchen", "switch.coffee"],
            "pattern_key": "light.kitchen:on → switch.coffee:on"  // optional
        }
    """
    if _bus is None:
        return jsonify({"error": "Integration bus not initialized"}), 503

    body = request.get_json(silent=True) or {}
    suggestion_id = body.get("suggestion_id", "")
    accepted = body.get("accepted")

    if accepted is None:
        return jsonify({"error": "Missing 'accepted' field (true/false)"}), 400

    event_type = "suggestion.accepted" if accepted else "suggestion.rejected"
    event = _bus.publish(event_type, {
        "suggestion_id": suggestion_id,
        "related_entities": body.get("related_entities", []),
        "pattern_key": body.get("pattern_key"),
    }, source="user_feedback")

    return jsonify({
        "status": "ok",
        "event_id": event.event_id,
        "event_type": event_type,
    })


@integration_bp.route("/bus/stats", methods=["GET"])
def get_bus_stats():
    """Return integration bus throughput metrics."""
    if _bus is None:
        return jsonify({"error": "Integration bus not initialized"}), 503

    stats = _bus.get_stats()
    if _feedback_loop:
        stats["feedback"] = _feedback_loop.get_stats()
    return jsonify(stats)
