"""Predictive Analytics API — Slice 48."""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.predictive.analytics_store import PredictiveAnalyticsStore

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("predictive_analytics", __name__, url_prefix="/api/v1/predictive/analytics")

_store: PredictiveAnalyticsStore | None = None


def get_store() -> PredictiveAnalyticsStore:
    """Get or create analytics store singleton."""
    global _store
    if _store is None:
        _store = PredictiveAnalyticsStore()
    return _store


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@analytics_bp.route("/usage", methods=["GET"])
@require_token
def get_usage_history():
    """Get predictive usage history."""
    try:
        store = get_store()

        # Parse query params
        time_range_start = request.args.get("start")
        time_range_end = request.args.get("end")
        zone_id = request.args.get("zone_id")
        prediction_type = request.args.get("type")
        since_revision = request.args.get("since_revision", type=int)

        history = store.build_usage_history(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            zone_id=zone_id,
            prediction_type=prediction_type,
            since_revision=since_revision,
        )

        return jsonify({
            "period": "custom",
            "start_at": history.time_range_start,
            "end_at": history.time_range_end,
            "total_proposals": history.total_proposals,
            "total_accepted": history.total_accepted,
            "total_rejected": history.total_rejected,
            "total_expired": history.total_expired,
            "total_pending": history.total_pending,
            "acceptance_rate": history.acceptance_rate,
            "avg_confidence_score": history.avg_confidence_score,
            "revision": history.revision,
            "latest_change_at": history.latest_change_at,
            "has_changes": since_revision is None or history.revision > since_revision,
            "entries": [
                {
                    "proposal_id": e.proposal_id,
                    "pattern_id": e.pattern_id,
                    "zone_id": e.zone_id,
                    "module_id": e.module_id,
                    "prediction_type": e.prediction_type,
                    "confidence_score": e.confidence_score,
                    "outcome": e.outcome,
                    "accepted_at": e.accepted_at,
                    "rejected_at": e.rejected_at,
                    "expired_at": e.expired_at,
                    "feedback": e.feedback,
                    "created_at": e.created_at,
                }
                for e in history.entries
            ],
        })
    except Exception as exc:
        logger.error("Error getting predictive usage history: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/patterns", methods=["GET"])
@require_token
def get_zone_patterns():
    """Get zone predictive patterns."""
    try:
        store = get_store()

        zone_id = request.args.get("zone_id")
        since_revision = request.args.get("since_revision", type=int)

        patterns = store.build_zone_patterns(zone_id=zone_id, since_revision=since_revision)

        return jsonify({
            "revision": patterns.revision,
            "latest_change_at": patterns.latest_change_at,
            "has_changes": since_revision is None or patterns.revision > since_revision,
            "total_zones": patterns.total_zones,
            "zones_with_proposals": patterns.zones_with_proposals,
            "patterns": [
                {
                    "zone_id": p.zone_id,
                    "zone_name": p.zone_name,
                    "total_proposals": p.total_proposals,
                    "accepted_count": p.accepted_count,
                    "rejected_count": p.rejected_count,
                    "expired_count": p.expired_count,
                    "acceptance_rate": p.acceptance_rate,
                    "avg_confidence_score": p.avg_confidence_score,
                    "most_common_prediction_type": p.most_common_prediction_type,
                    "last_proposal_at": p.last_proposal_at,
                    "proposals_last_7_days": p.proposals_last_7_days,
                    "proposals_last_30_days": p.proposals_last_30_days,
                    "dominant_pattern_ids": p.dominant_pattern_ids,
                }
                for p in patterns.patterns
            ],
        })
    except Exception as exc:
        logger.error("Error getting predictive zone patterns: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/effectiveness", methods=["GET"])
@require_token
def get_effectiveness():
    """Get predictive effectiveness metrics."""
    try:
        store = get_store()
        metrics = store.get_effectiveness_metrics()

        return jsonify({
            "total_proposals_analyzed": metrics.total_proposals_analyzed,
            "high_confidence_proposals": metrics.high_confidence_proposals,
            "high_confidence_acceptance_rate": metrics.high_confidence_acceptance_rate,
            "low_confidence_proposals": metrics.low_confidence_proposals,
            "low_confidence_acceptance_rate": metrics.low_confidence_acceptance_rate,
            "avg_time_to_accept_minutes": metrics.avg_time_to_accept_minutes,
            "avg_time_to_reject_minutes": metrics.avg_time_to_reject_minutes,
            "pattern_reinforcement_count": metrics.pattern_reinforcement_count,
            "pattern_degradation_count": metrics.pattern_degradation_count,
            "seasonal_adaptation_events": metrics.seasonal_adaptation_events,
            "effectiveness_score": metrics.effectiveness_score,
            "revision": metrics.revision,
            "latest_change_at": metrics.latest_change_at,
        })
    except Exception as exc:
        logger.error("Error getting predictive effectiveness metrics: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/trends", methods=["GET"])
@require_token
def get_trends():
    """Get predictive trends over time."""
    try:
        store = get_store()

        period = request.args.get("period", "daily")
        limit = request.args.get("limit", 30, type=int)

        trends = store.build_trends(period=period, limit=limit)

        return jsonify({
            "period": trends.period,
            "total_periods": trends.total_periods,
            "trend_direction": trends.trend_direction,
            "trend_slope": trends.trend_slope,
            "revision": trends.revision,
            "latest_change_at": trends.latest_change_at,
            "trends": [
                {
                    "period": t.period,
                    "timestamp": t.timestamp,
                    "proposals_count": t.proposals_count,
                    "accepted_count": t.accepted_count,
                    "rejected_count": t.rejected_count,
                    "avg_confidence": t.avg_confidence,
                    "acceptance_rate": t.acceptance_rate,
                }
                for t in trends.trends
            ],
        })
    except Exception as exc:
        logger.error("Error getting predictive trends: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/summary", methods=["GET"])
@require_token
def get_summary():
    """Get predictive analytics summary."""
    try:
        store = get_store()
        summary = store.get_summary()

        return jsonify({
            "summary_revision": summary.summary_revision,
            "latest_change_at": summary.latest_change_at,
            "usage": {
                "total_proposals": summary.usage.total_proposals,
                "acceptance_rate": summary.usage.acceptance_rate,
                "avg_confidence_score": summary.usage.avg_confidence_score,
            },
            "patterns": {
                "total_zones": summary.patterns.total_zones,
                "zones_with_proposals": summary.patterns.zones_with_proposals,
            },
            "effectiveness": {
                "effectiveness_score": summary.effectiveness.effectiveness_score,
                "high_confidence_acceptance_rate": summary.effectiveness.high_confidence_acceptance_rate,
                "pattern_reinforcement_count": summary.effectiveness.pattern_reinforcement_count,
                "pattern_degradation_count": summary.effectiveness.pattern_degradation_count,
            },
        })
    except Exception as exc:
        logger.error("Error getting predictive analytics summary: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/usage", methods=["POST"])
@require_token
def add_usage_entry():
    """Record predictive proposal outcome for analytics."""
    try:
        store = get_store()
        payload = request.get_json(silent=True) or {}

        # Validate required fields
        required = ["proposal_id", "pattern_id", "zone_id", "module_id", "prediction_type", "confidence_score", "outcome"]
        missing = [f for f in required if not payload.get(f)]
        if missing:
            return jsonify({"ok": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

        from copilot_core.predictive.analytics import PredictiveUsageEntryV1

        entry = PredictiveUsageEntryV1(
            proposal_id=str(payload["proposal_id"]),
            pattern_id=str(payload["pattern_id"]),
            zone_id=str(payload["zone_id"]),
            module_id=str(payload["module_id"]),
            prediction_type=str(payload["prediction_type"]),
            confidence_score=float(payload["confidence_score"]),
            outcome=str(payload["outcome"]),
            accepted_at=payload.get("accepted_at"),
            rejected_at=payload.get("rejected_at"),
            expired_at=payload.get("expired_at"),
            feedback=payload.get("feedback"),
        )

        store.add_usage_entry(entry)

        return jsonify({
            "ok": True,
            "message": "Predictive usage entry recorded",
            "proposal_id": entry.proposal_id,
            "outcome": entry.outcome,
            "generated_at": _utcnow(),
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Error adding predictive usage entry: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/effectiveness", methods=["POST"])
@require_token
def update_effectiveness():
    """Update effectiveness metrics."""
    try:
        store = get_store()
        payload = request.get_json(silent=True) or {}

        from copilot_core.predictive.analytics import PredictiveEffectivenessMetricsV1

        # Get current metrics
        metrics = store.get_effectiveness_metrics()

        # Update with provided values
        if "total_proposals_analyzed" in payload:
            metrics.total_proposals_analyzed = int(payload["total_proposals_analyzed"])
        if "high_confidence_proposals" in payload:
            metrics.high_confidence_proposals = int(payload["high_confidence_proposals"])
        if "high_confidence_acceptance_rate" in payload:
            metrics.high_confidence_acceptance_rate = float(payload["high_confidence_acceptance_rate"])
        if "low_confidence_proposals" in payload:
            metrics.low_confidence_proposals = int(payload["low_confidence_proposals"])
        if "low_confidence_acceptance_rate" in payload:
            metrics.low_confidence_acceptance_rate = float(payload["low_confidence_acceptance_rate"])
        if "avg_time_to_accept_minutes" in payload:
            metrics.avg_time_to_accept_minutes = payload["avg_time_to_accept_minutes"]
        if "avg_time_to_reject_minutes" in payload:
            metrics.avg_time_to_reject_minutes = payload["avg_time_to_reject_minutes"]
        if "pattern_reinforcement_count" in payload:
            metrics.pattern_reinforcement_count = int(payload["pattern_reinforcement_count"])
        if "pattern_degradation_count" in payload:
            metrics.pattern_degradation_count = int(payload["pattern_degradation_count"])
        if "seasonal_adaptation_events" in payload:
            metrics.seasonal_adaptation_events = int(payload["seasonal_adaptation_events"])
        if "effectiveness_score" in payload:
            metrics.effectiveness_score = float(payload["effectiveness_score"])

        store.update_effectiveness_metrics(metrics)

        return jsonify({
            "ok": True,
            "message": "Effectiveness metrics updated",
            "revision": metrics.revision,
            "effectiveness_score": metrics.effectiveness_score,
            "generated_at": _utcnow(),
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Error updating effectiveness metrics: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@analytics_bp.route("/trends", methods=["POST"])
@require_token
def add_trend_entry():
    """Add trend entry for periodic aggregation."""
    try:
        store = get_store()
        payload = request.get_json(silent=True) or {}

        # Validate required fields
        required = ["period", "timestamp", "proposals_count", "accepted_count", "rejected_count", "avg_confidence", "acceptance_rate"]
        missing = [f for f in required if not payload.get(f)]
        if missing:
            return jsonify({"ok": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

        from copilot_core.predictive.analytics import PredictiveTrendEntryV1

        entry = PredictiveTrendEntryV1(
            period=str(payload["period"]),
            timestamp=str(payload["timestamp"]),
            proposals_count=int(payload["proposals_count"]),
            accepted_count=int(payload["accepted_count"]),
            rejected_count=int(payload["rejected_count"]),
            avg_confidence=float(payload["avg_confidence"]),
            acceptance_rate=float(payload["acceptance_rate"]),
        )

        store.add_trend_entry(entry)

        return jsonify({
            "ok": True,
            "message": "Trend entry recorded",
            "period": entry.period,
            "timestamp": entry.timestamp,
            "generated_at": _utcnow(),
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.error("Error adding trend entry: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
