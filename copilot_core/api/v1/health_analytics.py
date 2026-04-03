"""Health Analytics API Endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from flask import Blueprint, Response, jsonify, request
from typing import Any

from ...analytics.health_analytics import (
    HealthAnalyticsStore,
    HealthCheckEntryV1,
    HealthCheckHistoryV1,
    HealthComponentPatternsV1,
    HealthEffectivenessMetricsV1,
    HealthAnalyticsSummaryV1,
)


_store_instance: HealthAnalyticsStore | None = None


def get_health_analytics_store() -> HealthAnalyticsStore:
    """Health Analytics Store holen (Singleton für API)."""
    global _store_instance
    if _store_instance is None:
        _store_instance = HealthAnalyticsStore()
    return _store_instance


def set_health_analytics_store(store: HealthAnalyticsStore) -> None:
    """Store für Tests setzen."""
    global _store_instance
    _store_instance = store


def create_blueprint() -> Blueprint:
    """Health Analytics Blueprint erstellen."""
    bp = Blueprint("health_analytics", __name__, url_prefix="/api/v1/health/analytics")

    @bp.route("/checks", methods=["GET"])
    def list_checks() -> Response:
        """List health check entries with filtering."""
        component = request.args.get("component")
        status = request.args.get("status")
        from_time = request.args.get("from_time")
        to_time = request.args.get("to_time")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        since_revision = request.args.get("since_revision")

        health_store = get_health_analytics_store()
        history = health_store.build_history(
            component=component,
            status=status,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )

        result: dict[str, Any] = {
            "entries": [asdict(e) for e in history.entries],
            "total_count": history.total_count,
            "revision": history.revision,
        }

        if since_revision:
            since_rev = int(since_revision)
            result["has_changes"] = history.revision > since_rev
            result["delta_revision"] = history.revision - since_rev if history.revision > since_rev else 0

        return jsonify(result)

    @bp.route("/patterns", methods=["GET"])
    def list_patterns() -> Response:
        """List component health patterns."""
        time_range_days = int(request.args.get("time_range_days", 7))
        since_revision = request.args.get("since_revision")

        health_store = get_health_analytics_store()
        patterns = health_store.build_component_patterns(time_range_days=time_range_days)

        result: dict[str, Any] = {
            "patterns": [asdict(p) for p in patterns.patterns],
            "total_components": patterns.total_components,
            "healthy_components": patterns.healthy_components,
            "degraded_components": patterns.degraded_components,
            "unhealthy_components": patterns.unhealthy_components,
            "revision": patterns.revision,
        }

        if since_revision:
            since_rev = int(since_revision)
            result["has_changes"] = patterns.revision > since_rev
            result["delta_revision"] = patterns.revision - since_rev if patterns.revision > since_rev else 0

        return jsonify(result)

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness() -> Response:
        """Get health effectiveness metrics."""
        time_range_days = int(request.args.get("time_range_days", 7))
        since_revision = request.args.get("since_revision")

        health_store = get_health_analytics_store()
        metrics = health_store.get_effectiveness_metrics(time_range_days=time_range_days)

        result: dict[str, Any] = asdict(metrics)

        if since_revision:
            since_rev = int(since_revision)
            result["has_changes"] = metrics.revision > since_rev
            result["delta_revision"] = metrics.revision - since_rev if metrics.revision > since_rev else 0

        return jsonify(result)

    @bp.route("/summary", methods=["GET"])
    def get_summary() -> Response:
        """Get health analytics summary."""
        time_range_days = int(request.args.get("time_range_days", 7))
        since_revision = request.args.get("since_revision")

        health_store = get_health_analytics_store()
        summary = health_store.build_summary(time_range_days=time_range_days)

        result: dict[str, Any] = {
            "history_summary": summary.history_summary,
            "patterns_summary": summary.patterns_summary,
            "effectiveness_summary": summary.effectiveness_summary,
            "revision": summary.revision,
            "generated_at": summary.generated_at,
        }

        if since_revision:
            since_rev = int(since_revision)
            result["has_changes"] = summary.revision > since_rev
            result["delta_revision"] = summary.revision - since_rev if summary.revision > since_rev else 0

        return jsonify(result)

    return bp
