"""Proposal Lifecycle Analytics API — Slice 59."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from copilot_core.analytics.proposal_lifecycle_analytics import ProposalAnalyticsStore

blueprint = Blueprint("proposal_lifecycle_analytics", __name__, url_prefix="/api/v1/proposal-lifecycle/analytics")

_analytics_store: ProposalAnalyticsStore | None = None


def init_blueprint(analytics_store: ProposalAnalyticsStore) -> None:
    """Initialize blueprint with store."""
    global _analytics_store
    _analytics_store = analytics_store


@blueprint.route("/events", methods=["GET"])
def get_lifecycle_events() -> tuple:
    """Get proposal lifecycle event history."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    proposal_id = request.args.get("proposal_id")
    zone_id = request.args.get("zone_id")
    event_type = request.args.get("event_type")
    source = request.args.get("source")
    from_ts = request.args.get("from_timestamp", type=float)
    to_ts = request.args.get("to_timestamp", type=float)
    limit = request.args.get("limit", 100, type=int)
    since_revision = request.args.get("since_revision", type=int)

    history = _analytics_store.build_lifecycle_history(
        proposal_id=proposal_id or None,
        zone_id=zone_id or None,
        event_type=None,  # Would need enum parsing
        source=None,  # Would need enum parsing
        from_timestamp=from_ts,
        to_timestamp=to_ts,
        limit=limit,
        since_revision=since_revision,
    )

    return jsonify(history.to_dict()), 200


@blueprint.route("/patterns", methods=["GET"])
def get_patterns() -> tuple:
    """Get proposal-specific patterns."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    patterns = _analytics_store.build_proposal_patterns(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(patterns.to_dict()), 200


@blueprint.route("/effectiveness", methods=["GET"])
def get_effectiveness() -> tuple:
    """Get proposal lifecycle effectiveness metrics."""
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
    """Get complete proposal analytics summary."""
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
def record_lifecycle_event() -> tuple:
    """Record a proposal lifecycle event (for testing/integration)."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    data = request.get_json() or {}

    event_id = data.get("event_id") or str(uuid.uuid4())
    proposal_id = data.get("proposal_id")
    zone_id = data.get("zone_id")
    module_id = data.get("module_id")
    event_type = data.get("event_type", "proposed")
    source = data.get("source", "predictive")
    metadata = data.get("metadata", {})

    from copilot_core.analytics.proposal_lifecycle_analytics import (
        ProposalEventType,
        ProposalSource,
    )

    try:
        entry = _analytics_store.add_lifecycle_event(
            event_id=event_id,
            proposal_id=proposal_id,
            zone_id=zone_id,
            module_id=module_id,
            event_type=ProposalEventType(event_type),
            source=ProposalSource(source),
            metadata=metadata,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(entry.to_dict()), 201
