"""Calendar Analytics API Endpoints."""

from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta

from copilot_core.api.security import require_token
from copilot_core.analytics.calendar_analytics import CalendarAnalyticsStore, CalendarEventType, SuggestionType

logger = logging.getLogger(__name__)

calendar_analytics_bp = Blueprint("calendar_analytics", __name__, url_prefix="/api/v1/calendar/analytics")

_store = None


def _get_store() -> CalendarAnalyticsStore:
    global _store
    if _store is None:
        _store = CalendarAnalyticsStore()
    return _store


@calendar_analytics_bp.route("/usage", methods=["GET"])
@require_token
def get_usage():
    """Get calendar usage history."""
    start = request.args.get("start")
    end = request.args.get("end")
    limit = int(request.args.get("limit", 100))
    
    store = _get_store()
    history = store.build_usage_history(start_date=start, end_date=end, limit=limit)
    
    return jsonify({
        "entries": [
            {
                "entry_id": e.entry_id,
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "duration_minutes": e.duration_minutes,
                "source": e.source,
                "zone_id": e.zone_id,
                "user_id": e.user_id,
                "metadata": e.metadata,
            }
            for e in history.entries
        ],
        "total_count": history.total_count,
        "date_range": history.date_range,
        "revision": history.revision,
        "has_changes": request.args.get("since_revision") 
                       and int(request.args.get("since_revision", 0)) < history.revision,
    })


@calendar_analytics_bp.route("/patterns", methods=["GET"])
@require_token
def get_patterns():
    """Get calendar pattern analysis."""
    store = _get_store()
    patterns = store.build_patterns()
    
    return jsonify({
        "by_event_type": [
            {
                "dimension": p.dimension,
                "value": p.value,
                "count": p.count,
                "percentage": p.percentage,
                "avg_duration_minutes": p.avg_duration_minutes,
                "peak_hours": p.peak_hours,
            }
            for p in patterns.by_event_type
        ],
        "by_hour": [
            {
                "dimension": p.dimension,
                "value": p.value,
                "count": p.count,
                "percentage": p.percentage,
                "avg_duration_minutes": p.avg_duration_minutes,
                "peak_hours": p.peak_hours,
            }
            for p in patterns.by_hour
        ],
        "by_day_of_week": [
            {
                "dimension": p.dimension,
                "value": p.value,
                "count": p.count,
                "percentage": p.percentage,
                "avg_duration_minutes": p.avg_duration_minutes,
            }
            for p in patterns.by_day_of_week
        ],
        "by_zone": [
            {
                "dimension": p.dimension,
                "value": p.value,
                "count": p.count,
                "percentage": p.percentage,
                "avg_duration_minutes": p.avg_duration_minutes,
            }
            for p in patterns.by_zone
        ],
        "revision": patterns.revision,
        "has_changes": request.args.get("since_revision") 
                       and int(request.args.get("since_revision", 0)) < patterns.revision,
    })


@calendar_analytics_bp.route("/effectiveness", methods=["GET"])
@require_token
def get_effectiveness():
    """Get calendar effectiveness metrics."""
    store = _get_store()
    metrics = store.get_effectiveness_metrics()
    
    return jsonify({
        "total_events": metrics.total_events,
        "smart_recommendations_count": metrics.smart_recommendations_count,
        "mood_recommendations_count": metrics.mood_recommendations_count,
        "suggestions_generated": metrics.suggestions_generated,
        "suggestions_accepted": metrics.suggestions_accepted,
        "suggestions_dismissed": metrics.suggestions_dismissed,
        "acceptance_rate": metrics.acceptance_rate,
        "avg_lead_time_minutes": metrics.avg_lead_time_minutes,
        "focus_block_utilization": metrics.focus_block_utilization,
        "break_compliance_rate": metrics.break_compliance_rate,
        "revision": metrics.revision,
        "has_changes": request.args.get("since_revision") 
                       and int(request.args.get("since_revision", 0)) < metrics.revision,
    })


@calendar_analytics_bp.route("/summary", methods=["GET"])
@require_token
def get_summary():
    """Get complete calendar analytics summary."""
    store = _get_store()
    summary = store.build_summary()
    
    return jsonify({
        "usage": {
            "total_count": summary.usage.total_count,
            "date_range": summary.usage.date_range,
        },
        "patterns": {
            "by_event_type_count": len(summary.patterns.by_event_type),
            "by_hour_count": len(summary.patterns.by_hour),
            "by_day_of_week_count": len(summary.patterns.by_day_of_week),
            "by_zone_count": len(summary.patterns.by_zone),
        },
        "effectiveness": {
            "total_events": summary.effectiveness.total_events,
            "acceptance_rate": summary.effectiveness.acceptance_rate,
            "focus_block_utilization": summary.effectiveness.focus_block_utilization,
            "break_compliance_rate": summary.effectiveness.break_compliance_rate,
        },
        "generated_at": summary.generated_at,
        "revision": summary.revision,
        "has_changes": request.args.get("since_revision") 
                       and int(request.args.get("since_revision", 0)) < summary.revision,
    })
