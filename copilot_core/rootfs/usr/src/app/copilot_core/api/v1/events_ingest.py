"""API v1 – Event Ingest endpoint.

Receives batched events from the HA Events Forwarder and stores them
in the Core event store for downstream consumers (Brain Graph, Mood Engine, etc.).

Endpoints:
    POST /api/v1/events          – Ingest a batch of event envelopes
    GET  /api/v1/events          – Query stored events (with filters)
    GET  /api/v1/events/stats    – Store statistics / health
"""
from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify

from copilot_core.api.security import require_token
from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import BatchEventPayload
from copilot_core.ingest.event_store import EventStore

logger = logging.getLogger(__name__)

bp = Blueprint("events_ingest", __name__)


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _parse_positive_int_limit(raw, *, default: int, maximum: int):
    if raw is None:
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, _error("limit must be a positive integer", 400)
    if value <= 0:
        return None, _error("limit must be a positive integer", 400)
    if value > maximum:
        return None, _error(f"limit must be <= {maximum}", 400)
    return value, None

# Singleton store – initialized on first request or by main.py
_store: EventStore | None = None

# Post-ingest callback – called with list of accepted events after each batch
_post_ingest_callback = None


def set_post_ingest_callback(callback) -> None:
    """Register a callback invoked after each successful ingest batch.

    The callback receives a list of accepted (normalized) event dicts.
    Exceptions in the callback are logged but do not fail the HTTP response.
    """
    global _post_ingest_callback
    _post_ingest_callback = callback


def get_store() -> EventStore:
    """Return (and lazily create) the global EventStore singleton."""
    global _store
    if _store is None:
        _store = EventStore()
    return _store


def set_store(store: EventStore) -> None:
    """Allow main.py to inject a pre-configured store."""
    global _store
    _store = store


# ── POST /api/v1/events ─────────────────────────────────────────────

@bp.route("/api/v1/events", methods=["POST"])
@require_token
@validate_json(BatchEventPayload)
def ingest_events(body: BatchEventPayload):
    """Accept a batch of forwarded HA events.

    Expected body:
        { "items": [ { ... event envelope ... }, ... ] }
    """
    if len(body.items) == 0:
        return jsonify({"accepted": 0, "rejected": 0, "deduped": 0}), 200

    store = get_store()
    items = [item.model_dump(exclude_none=True) for item in body.items]
    try:
        result = store.ingest_batch(items)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        logger.exception("Failed to ingest forwarded events")
        return _error(str(exc), 500)

    # Fire post-ingest callback (e.g. EventProcessor → Brain Graph)
    accepted_events = result.pop("accepted_events", [])
    if accepted_events and _post_ingest_callback:
        try:
            _post_ingest_callback(accepted_events)
        except Exception as exc:
            logger.error("Post-ingest callback error: %s", exc, exc_info=True)

    status = 200 if result["rejected"] == 0 else 207  # Multi-Status if partial
    return jsonify(result), status


# ── GET /api/v1/events ──────────────────────────────────────────────

@bp.route("/api/v1/events", methods=["GET"])
@require_token
def query_events():
    """Query stored events with optional filters.

    Query params:
        domain    – filter by HA domain (e.g. "light")
        entity_id – filter by entity_id
        kind      – filter by event kind ("state_changed", "call_service")
        zone_id   – filter by zone_id
        since     – ISO timestamp lower bound
        limit     – max results (default 100, max 1000)
    """
    store = get_store()
    limit, error_response = _parse_positive_int_limit(
        request.args.get("limit"), default=100, maximum=1000
    )
    if error_response:
        return error_response

    try:
        events = store.query(
            domain=request.args.get("domain"),
            entity_id=request.args.get("entity_id"),
            kind=request.args.get("kind"),
            zone_id=request.args.get("zone_id"),
            since=request.args.get("since"),
            limit=limit,
        )
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        logger.exception("Failed to query ingested events")
        return _error(str(exc), 500)

    return jsonify({"events": events, "count": len(events)}), 200


# ── GET /api/v1/events/stats ────────────────────────────────────────

@bp.route("/api/v1/events/stats", methods=["GET"])
@require_token
def events_stats():
    """Return event store statistics for operator diagnostics."""
    store = get_store()
    try:
        payload = store.stats()
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        logger.exception("Failed to build events ingest stats")
        return _error(str(exc), 500)
    return jsonify(payload), 200
