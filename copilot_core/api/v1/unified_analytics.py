"""Unified Analytics Dashboard API — Slice 63."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, jsonify, request

if TYPE_CHECKING:
    from copilot_core.analytics.unified_analytics import UnifiedAnalyticsDashboard

blueprint = Blueprint("unified_analytics", __name__, url_prefix="/api/v1/analytics/dashboard")

_dashboard: UnifiedAnalyticsDashboard | None = None


def init_blueprint(data_dir: Path | str) -> None:
    """Initialize blueprint with data directory."""
    global _dashboard
    from copilot_core.analytics.unified_analytics import UnifiedAnalyticsDashboard
    _dashboard = UnifiedAnalyticsDashboard(data_dir)


@blueprint.route("/", methods=["GET"])
def get_dashboard() -> tuple:
    """Get unified analytics dashboard."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)

    dashboard = _dashboard.build_dashboard(days_lookback=days)

    return jsonify(dashboard.to_dict()), 200


@blueprint.route("/module/<module_name>", methods=["GET"])
def get_module_summary(module_name: str) -> tuple:
    """Get summary for a specific analytics module."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    dashboard = _dashboard.build_dashboard(days_lookback=days)

    module = next(
        (m for m in dashboard.modules if m.module == module_name),
        None,
    )

    if not module:
        return jsonify({"error": f"Module {module_name} not found"}), 404

    return jsonify(module.to_dict()), 200


@blueprint.route("/health", methods=["GET"])
def get_health() -> tuple:
    """Get overall analytics health status."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    dashboard = _dashboard.build_dashboard(days_lookback=days)

    return jsonify({
        "overall_health_score": dashboard.overall_health_score,
        "global_revision": dashboard.global_revision,
        "total_events": dashboard.total_events_all_modules,
        "modules_count": len(dashboard.modules),
        "anomalies_count": len(dashboard.anomalies),
        "recommendations_count": len(dashboard.recommendations),
    }), 200


@blueprint.route("/anomalies", methods=["GET"])
def get_anomalies() -> tuple:
    """Get detected anomalies across all modules."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    dashboard = _dashboard.build_dashboard(days_lookback=days)

    return jsonify({
        "anomalies": dashboard.anomalies,
        "count": len(dashboard.anomalies),
        "generated_at": dashboard.generated_at,
    }), 200


@blueprint.route("/recommendations", methods=["GET"])
def get_recommendations() -> tuple:
    """Get recommendations based on analytics."""
    if not _dashboard:
        return jsonify({"error": "Dashboard not initialized"}), 503

    days = request.args.get("days_lookback", 30, type=int)
    dashboard = _dashboard.build_dashboard(days_lookback=days)

    return jsonify({
        "recommendations": dashboard.recommendations,
        "count": len(dashboard.recommendations),
        "generated_at": dashboard.generated_at,
    }), 200
