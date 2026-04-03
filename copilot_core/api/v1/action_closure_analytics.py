"""Action Closure Analytics API — Slice 60."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from copilot_core.analytics.action_closure_analytics import ClosureAnalyticsStore

blueprint = Blueprint("action_closure_analytics", __name__, url_prefix="/api/v1/action-closure/analytics")

_analytics_store: ClosureAnalyticsStore | None = None


def init_blueprint(analytics_store: ClosureAnalyticsStore) -> None:
    """Initialize blueprint with store."""
    global _analytics_store
    _analytics_store = analytics_store


@blueprint.route("/events", methods=["GET"])
def get_closure_events() -> tuple:
    """Get action closure event history."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    closure_id = request.args.get("closure_id")
    zone_id = request.args.get("zone_id")
    event_type = request.args.get("event_type")
    source = request.args.get("source")
    from_ts = request.args.get("from_timestamp", type=float)
    to_ts = request.args.get("to_timestamp", type=float)
    limit = request.args.get("limit", 100, type=int)
    since_revision = request.args.get("since_revision", type=int)

    history = _analytics_store.build_closure_history(
        closure_id=closure_id or None,
        zone_id=zone_id or None,
        event_type=None,
        source=None,
        from_timestamp=from_ts,
        to_timestamp=to_ts,
        limit=limit,
        since_revision=since_revision,
    )

    return jsonify(history.to_dict()), 200


@blueprint.route("/patterns", methods=["GET"])
def get_patterns() -> tuple:
    """Get closure-specific patterns."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    patterns = _analytics_store.build_closure_patterns(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(patterns.to_dict()), 200


@blueprint.route("/effectiveness", methods=["GET"])
def get_effectiveness() -> tuple:
    """Get action closure effectiveness metrics."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    metrics = _analytics_store.get_effectiveness_metrics(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(metrics.to_dict()), 200


@blueprint.route("/summary", methods=["GET"])
def get_summary() -> tuple:
    """Get complete closure analytics summary."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    summary = _analytics_store.build_summary(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(summary.to_dict()), 200


@blueprint.route("/events", methods=["POST"])
def record_closure_event() -> tuple:
    """Record an action closure event (for testing/integration)."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    data = request.get_json() or {}

    event_id = data.get("event_id") or str(uuid.uuid4())
    closure_id = data.get("closure_id")
    zone_id = data.get("zone_id")
    module_id = data.get("module_id")
    event_type = data.get("event_type", "created")
    source = data.get("source", "voice")
    metadata = data.get("metadata", {})

    from copilot_core.analytics.action_closure_analytics import (
        ClosureEventType,
        ClosureSource,
    )

    try:
        entry = _analytics_store.add_closure_event(
            event_id=event_id,
            closure_id=closure_id,
            zone_id=zone_id,
            module_id=module_id,
            event_type=ClosureEventType(event_type),
            source=ClosureSource(source),
            metadata=metadata,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(entry.to_dict()), 201
