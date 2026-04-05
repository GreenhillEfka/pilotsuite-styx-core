"""API v1 – Event Ingest endpoint (DEPRECATED).

This module is DEPRECATED. Use the WebSocket-based HA Events API instead:
- GET /api/v1/ha-events/subscribe — WebSocket endpoint for real-time events
- POST /api/v1/ha-events/subscribe — Subscribe to event types

Legacy endpoints are maintained for backward compatibility but redirect
or return deprecation warnings.
"""
from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

bp = Blueprint("events_ingest", __name__)

DEPRECATION_NOTICE = {
    "deprecated": True,
    "message": "This endpoint is deprecated. Use /api/v1/ha-events/subscribe WebSocket API instead.",
    "migration_guide": "See https://docs.pilotsuite.dev/migration/events-ingest-to-websocket",
    "sunset_date": "2026-06-01",
}

# Runtime callback wiring (used by core_setup.init_services → EventProcessor pipeline)
_ingest_callback: callable = None


def set_post_ingest_callback(callback: callable) -> None:
    global _ingest_callback
    _ingest_callback = callback


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message, **DEPRECATION_NOTICE}), status_code


# ── POST /api/v1/events ─────────────────────────────────────────────

@bp.route("/api/v1/events", methods=["POST"])
def ingest_events():
    """DEPRECATED: Accept a batch of forwarded HA events.
    
    This endpoint is deprecated. Please migrate to the WebSocket-based
    HA Events API at /api/v1/ha-events/subscribe.
    """
    logger.warning(
        "DEPRECATED: POST /api/v1/events called. "
        "Migrate to WebSocket API at /api/v1/ha-events/subscribe"
    )
    
    # Return deprecation notice with 410 Gone
    return jsonify({
        "ok": False,
        "error": "Endpoint deprecated. Use WebSocket API instead.",
        **DEPRECATION_NOTICE,
    }), 410


# ── GET /api/v1/events ──────────────────────────────────────────────

@bp.route("/api/v1/events", methods=["GET"])
def query_events():
    """DEPRECATED: Query stored events with optional filters.
    
    This endpoint is deprecated. Event history is now available via
    the WebSocket connection or /api/v1/ha-events/history.
    """
    logger.warning(
        "DEPRECATED: GET /api/v1/events called. "
        "Use WebSocket API or /api/v1/ha-events/history instead"
    )
    
    return jsonify({
        "ok": False,
        "error": "Endpoint deprecated. Use WebSocket API instead.",
        **DEPRECATION_NOTICE,
    }), 410


# ── GET /api/v1/events/stats ────────────────────────────────────────

@bp.route("/api/v1/events/stats", methods=["GET"])
def events_stats():
    """DEPRECATED: Return event store statistics.
    
    Statistics are now available via the WebSocket connection or
    health endpoints at /api/v1/health/events.
    """
    logger.warning(
        "DEPRECATED: GET /api/v1/events/stats called. "
        "Use WebSocket API or /api/v1/health/events instead"
    )
    
    return jsonify({
        "ok": False,
        "error": "Endpoint deprecated. Use WebSocket API instead.",
        **DEPRECATION_NOTICE,
    }), 410
