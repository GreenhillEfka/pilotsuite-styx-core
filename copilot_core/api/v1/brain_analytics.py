"""Brain/Neuron Analytics API — Slice 61."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from copilot_core.analytics.brain_analytics import BrainAnalyticsStore

blueprint = Blueprint("brain_analytics", __name__, url_prefix="/api/v1/brain/analytics")

_analytics_store: BrainAnalyticsStore | None = None


def init_blueprint(analytics_store: BrainAnalyticsStore) -> None:
    """Initialize blueprint with store."""
    global _analytics_store
    _analytics_store = analytics_store


@blueprint.route("/events", methods=["GET"])
def get_neuron_events() -> tuple:
    """Get neuron event history."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    neuron_id = request.args.get("neuron_id")
    zone_id = request.args.get("zone_id")
    layer = request.args.get("layer")
    event_type = request.args.get("event_type")
    from_ts = request.args.get("from_timestamp", type=float)
    to_ts = request.args.get("to_timestamp", type=float)
    limit = request.args.get("limit", 100, type=int)
    since_revision = request.args.get("since_revision", type=int)

    history = _analytics_store.build_neuron_history(
        neuron_id=neuron_id or None,
        zone_id=zone_id or None,
        layer=None,
        event_type=None,
        from_timestamp=from_ts,
        to_timestamp=to_ts,
        limit=limit,
        since_revision=since_revision,
    )

    return jsonify(history.to_dict()), 200


@blueprint.route("/patterns", methods=["GET"])
def get_patterns() -> tuple:
    """Get neuron-specific patterns."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    patterns = _analytics_store.build_neuron_patterns(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(patterns.to_dict()), 200


@blueprint.route("/effectiveness", methods=["GET"])
def get_effectiveness() -> tuple:
    """Get brain effectiveness metrics."""
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
    """Get complete brain analytics summary."""
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
def record_neuron_event() -> tuple:
    """Record a neuron event (for testing/integration)."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    data = request.get_json() or {}

    event_id = data.get("event_id") or str(uuid.uuid4())
    neuron_id = data.get("neuron_id")
    zone_id = data.get("zone_id")
    layer = data.get("layer")
    event_type = data.get("event_type", "activated")
    metadata = data.get("metadata", {})

    from copilot_core.analytics.brain_analytics import (
        NeuronEventType,
        NeuronLayer,
    )

    try:
        entry = _analytics_store.add_neuron_event(
            event_id=event_id,
            neuron_id=neuron_id,
            zone_id=zone_id,
            layer=NeuronLayer(layer) if layer else None,
            event_type=NeuronEventType(event_type),
            metadata=metadata,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(entry.to_dict()), 201
