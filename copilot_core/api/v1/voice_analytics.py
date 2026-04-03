"""Voice Analytics API — Slice 57."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

from copilot_core.analytics.voice_analytics import get_voice_analytics_store

_LOGGER = logging.getLogger(__name__)

voice_analytics_bp = Blueprint("voice_analytics", __name__, url_prefix="/api/v1/voice/analytics")


# =============================================================================
# API Endpoints
# =============================================================================

@voice_analytics_bp.route("/commands", methods=["GET"])
def get_voice_command_history():
    """Voice Command History — mit optionalen Filtern."""
    store = get_voice_analytics_store()

    intent_type = request.args.get("intent_type")
    zone_id = request.args.get("zone_id")
    status = request.args.get("status")
    from_time = request.args.get("from_time")
    to_time = request.args.get("to_time")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    history = store.build_history(
        intent_type=intent_type,
        zone_id=zone_id,
        status=status,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "entries": [
            {
                "command_id": e.command_id,
                "intent_type": e.intent_type,
                "raw_command": e.raw_command,
                "zone_id": e.zone_id,
                "zone_name": e.zone_name,
                "module_id": e.module_id,
                "module_name": e.module_name,
                "status": e.status,
                "confidence_score": e.confidence_score,
                "processing_time_ms": e.processing_time_ms,
                "execution_time": e.execution_time,
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


@voice_analytics_bp.route("/intents", methods=["GET"])
def get_voice_intent_patterns():
    """Voice Intent Patterns — intent-spezifische Patterns."""
    store = get_voice_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    patterns = store.build_intent_patterns(time_range_days=time_range_days)

    return jsonify({
        "patterns": [
            {
                "intent_type": p.intent_type,
                "total_commands": p.total_commands,
                "success_count": p.success_count,
                "partial_count": p.partial_count,
                "failed_count": p.failed_count,
                "rejected_count": p.rejected_count,
                "success_rate": p.success_rate,
                "avg_confidence_score": p.avg_confidence_score,
                "avg_processing_time_ms": p.avg_processing_time_ms,
                "min_processing_time_ms": p.min_processing_time_ms,
                "max_processing_time_ms": p.max_processing_time_ms,
                "p95_processing_time_ms": p.p95_processing_time_ms,
                "last_command_time": p.last_command_time,
                "last_status": p.last_status,
                "trend": p.trend,
                "zone_coverage": p.zone_coverage,
            }
            for p in patterns.patterns
        ],
        "total_intents": patterns.total_intents,
        "active_intents": patterns.active_intents,
        "revision": patterns.revision,
    })


@voice_analytics_bp.route("/effectiveness", methods=["GET"])
def get_voice_effectiveness_metrics():
    """Voice Effectiveness Metrics — Success-Rates, Confidence, Processing-Time."""
    store = get_voice_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    metrics = store.get_effectiveness_metrics(time_range_days=time_range_days)

    return jsonify({
        "overall_success_rate": metrics.overall_success_rate,
        "total_commands_24h": metrics.total_commands_24h,
        "total_commands_7d": metrics.total_commands_7d,
        "avg_confidence_score": metrics.avg_confidence_score,
        "avg_processing_time_ms": metrics.avg_processing_time_ms,
        "intent_distribution": metrics.intent_distribution,
        "zone_coverage_total": metrics.zone_coverage_total,
        "rejection_rate": metrics.rejection_rate,
        "timeout_rate": metrics.timeout_rate,
        "revision": metrics.revision,
    })


@voice_analytics_bp.route("/summary", methods=["GET"])
def get_voice_analytics_summary():
    """Voice Analytics Summary — alle Analytics in einer Surface."""
    store = get_voice_analytics_store()

    time_range_days = int(request.args.get("time_range_days", 7))
    summary = store.build_summary(time_range_days=time_range_days)

    return jsonify({
        "history_summary": summary.history_summary,
        "patterns_summary": summary.patterns_summary,
        "effectiveness_summary": summary.effectiveness_summary,
        "revision": summary.revision,
        "generated_at": summary.generated_at,
    })
