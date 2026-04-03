"""Zone Truth Analytics API — Slice 58."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from copilot_core.analytics.zone_truth_analytics import ZoneAnalyticsStore
    from copilot_core.zone_truth.store import ZoneTruthStore

blueprint = Blueprint("zone_truth_analytics", __name__, url_prefix="/api/v1/zone-truth/analytics")

_analytics_store: ZoneAnalyticsStore | None = None
_zone_truth_store: ZoneTruthStore | None = None


def init_blueprint(analytics_store: ZoneAnalyticsStore, zone_truth_store: ZoneTruthStore) -> None:
    """Initialize blueprint with stores."""
    global _analytics_store, _zone_truth_store
    _analytics_store = analytics_store
    _zone_truth_store = zone_truth_store


@blueprint.route("/sync/executions", methods=["GET"])
def get_sync_executions() -> tuple:
    """Get zone sync execution history."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    zone_id = request.args.get("zone_id")
    event_type = request.args.get("event_type")
    status = request.args.get("status")
    from_ts = request.args.get("from_timestamp", type=float)
    to_ts = request.args.get("to_timestamp", type=float)
    limit = request.args.get("limit", 100, type=int)
    since_revision = request.args.get("since_revision", type=int)

    history = _analytics_store.build_sync_history(
        zone_id=zone_id or None,
        event_type=None,  # Would need enum parsing
        status=None,  # Would need enum parsing
        from_timestamp=from_ts,
        to_timestamp=to_ts,
        limit=limit,
        since_revision=since_revision,
    )

    return jsonify(history.to_dict()), 200


@blueprint.route("/sync/patterns", methods=["GET"])
def get_sync_patterns() -> tuple:
    """Get zone-specific sync patterns."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    patterns = _analytics_store.build_zone_patterns(
        days_lookback=days,
        since_revision=since_revision,
    )

    # Resolve zone names from ZoneTruthStore if available
    if _zone_truth_store:
        for pattern in patterns.patterns:
            zone = _zone_truth_store.get_zone(pattern.zone_id)
            if zone:
                pattern.zone_name = zone.name or zone.zone_id

    return jsonify(patterns.to_dict()), 200


@blueprint.route("/sync/effectiveness", methods=["GET"])
def get_effectiveness() -> tuple:
    """Get zone truth effectiveness metrics."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    metrics = _analytics_store.get_effectiveness_metrics(
        days_lookback=days,
        since_revision=since_revision,
    )

    return jsonify(metrics.to_dict()), 200


@blueprint.route("/sync/summary", methods=["GET"])
def get_summary() -> tuple:
    """Get complete zone analytics summary."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    since_revision = request.args.get("since_revision", type=int)

    summary = _analytics_store.build_summary(
        days_lookback=days,
        since_revision=since_revision,
    )

    # Resolve zone names if ZoneTruthStore is available
    if _zone_truth_store:
        if summary.patterns:
            for pattern in summary.patterns.patterns:
                zone = _zone_truth_store.get_zone(pattern.zone_id)
                if zone:
                    pattern.zone_name = zone.name or zone.zone_id

    return jsonify(summary.to_dict()), 200


@blueprint.route("/sync/events", methods=["POST"])
def record_sync_event() -> tuple:
    """Record a zone sync event (for testing/integration)."""
    if not _analytics_store:
        return jsonify({"error": "Analytics store not initialized"}), 503

    data = request.get_json() or {}

    event_id = data.get("event_id") or str(uuid.uuid4())
    zone_id = data.get("zone_id")
    event_type = data.get("event_type", "topology_sync")
    status = data.get("status", "success")
    entity_count_before = data.get("entity_count_before", 0)
    entity_count_after = data.get("entity_count_after", 0)
    entities_changed = data.get("entities_changed", 0)
    source = data.get("source", "ha_topology_sync")
    metadata = data.get("metadata", {})

    from copilot_core.analytics.zone_truth_analytics import (
        ZoneSyncEventType,
        ZoneSyncStatus,
    )

    try:
        entry = _analytics_store.add_sync_event(
            event_id=event_id,
            zone_id=zone_id,
            event_type=ZoneSyncEventType(event_type),
            status=ZoneSyncStatus(status),
            entity_count_before=entity_count_before,
            entity_count_after=entity_count_after,
            entities_changed=entities_changed,
            source=source,
            metadata=metadata,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(entry.to_dict()), 201
