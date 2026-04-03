"""Module Analytics API — Slice 56."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

from copilot_core.analytics.module_analytics import get_module_analytics_store

_LOGGER = logging.getLogger(__name__)

module_analytics_bp = Blueprint("module_analytics", __name__, url_prefix="/api/v1/module/analytics")


# =============================================================================
# API Endpoints
# =============================================================================

@module_analytics_bp.route("/executions", methods=["GET"])
def get_module_execution_history():
    """Module Execution History — mit optionalen Filtern."""
    store = get_module_analytics_store()

    module_id = request.args.get("module_id")
    zone_id = request.args.get("zone_id")
    status = request.args.get("status")
    trigger_type = request.args.get("trigger_type")
    from_time = request.args.get("from_time")
    to_time = request.args.get("to_time")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    history = store.build_history(
        module_id=module_id,
        zone_id=zone_id,
        status=status,
        trigger_type=trigger_type,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "entries": [
            {
                "execution_id": e.execution_id,
                "module_id": e.module_id,
                "module_name": e.module_name,
                "module_type": e.module_type,
                "zone_id": e.zone_id,
                "zone_name": e.zone_name,
                "status": e.status,
                "trigger_type": e.trigger_type,
                "execution_time": e.execution_time,
                "duration_ms": e.duration_ms,
                "inputs_count": e.inputs_count,
                "outputs_count": e.outputs_count,
                "error_message": e.error_message,
                "metadata": e.metadata,
                "revision": e.revision,
            }
            for e in history.entries
        ],
        "total_count": history.total_count,
        "from_time": history.from_time,
        "to_time": history.to_time,
        "revision": history.revision,
    })


@module_analytics_bp.route("/patterns", methods=["GET"])
def get_module_patterns():
    """Module Patterns — module-spezifische Patterns."""
    store = get_module_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    patterns = store.build_module_patterns(time_range_days=time_range_days)

    return jsonify({
        "patterns": [
            {
                "module_id": p.module_id,
                "module_name": p.module_name,
                "module_type": p.module_type,
                "total_executions": p.total_executions,
                "success_count": p.success_count,
                "partial_count": p.partial_count,
                "failed_count": p.failed_count,
                "skipped_count": p.skipped_count,
                "success_rate": p.success_rate,
                "avg_duration_ms": p.avg_duration_ms,
                "min_duration_ms": p.min_duration_ms,
                "max_duration_ms": p.max_duration_ms,
                "p95_duration_ms": p.p95_duration_ms,
                "avg_inputs_count": p.avg_inputs_count,
                "avg_outputs_count": p.avg_outputs_count,
                "last_execution_time": p.last_execution_time,
                "last_status": p.last_status,
                "trend": p.trend,
                "primary_trigger_type": p.primary_trigger_type,
                "zone_coverage": p.zone_coverage,
            }
            for p in patterns.patterns
        ],
        "total_modules": patterns.total_modules,
        "active_modules": patterns.active_modules,
        "revision": patterns.revision,
    })


@module_analytics_bp.route("/effectiveness", methods=["GET"])
def get_module_effectiveness_metrics():
    """Module Effectiveness Metrics — Success-Rates, MTBF, Zone-Coverage."""
    store = get_module_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    metrics = store.get_effectiveness_metrics(time_range_days=time_range_days)

    return jsonify({
        "overall_success_rate": metrics.overall_success_rate,
        "total_executions_24h": metrics.total_executions_24h,
        "total_executions_7d": metrics.total_executions_7d,
        "avg_duration_ms": metrics.avg_duration_ms,
        "mtbf_hours": metrics.mtbf_hours,
        "mttr_minutes": metrics.mttr_minutes,
        "modules_by_status": metrics.modules_by_status,
        "trigger_type_distribution": metrics.trigger_type_distribution,
        "zone_coverage_total": metrics.zone_coverage_total,
        "revision": metrics.revision,
    })


@module_analytics_bp.route("/summary", methods=["GET"])
def get_module_analytics_summary():
    """Module Analytics Summary — alle Analytics in einer Surface."""
    store = get_module_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    summary = store.build_summary(time_range_days=time_range_days)

    return jsonify({
        "history_summary": summary.history_summary,
        "patterns_summary": summary.patterns_summary,
        "effectiveness_summary": summary.effectiveness_summary,
        "revision": summary.revision,
        "generated_at": summary.generated_at,
    })
