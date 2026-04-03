"""Calendar REST API — Canonical Core Surface for PilotSuite.

Provides endpoints for calendar events, smart scheduling, mood-aware
recommendations, and proactive suggestions.

Follows the same pattern as other Core API surfaces:
- Revision tracking for delta polling
- Analytics surface (usage, patterns, effectiveness)
- Notification integration for proactive suggestions
"""

from flask import Blueprint, request, jsonify
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests as http_requests

from copilot_core.api.security import require_token
from copilot_core.calendar.smart_scheduler import SmartScheduler, SmartSchedulerConfig
from copilot_core.calendar.mood_aware import MoodAwareScheduler, MoodCalendarConfig
from copilot_core.calendar.suggestions import ScheduleSuggester, SuggestionConfig, Suggestion
from copilot_core.calendar.integration_engine import CalendarIntegration

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")

# Global instances (lazy-initialized)
_scheduler: Optional[SmartScheduler] = None
_mood_scheduler: Optional[MoodAwareScheduler] = None
_suggester: Optional[ScheduleSuggester] = None
_integration: Optional[CalendarIntegration] = None


def _get_scheduler() -> SmartScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = SmartScheduler(SmartSchedulerConfig())
    return _scheduler


def _get_mood_scheduler() -> MoodAwareScheduler:
    global _mood_scheduler
    if _mood_scheduler is None:
        _mood_scheduler = MoodAwareScheduler(MoodCalendarConfig())
    return _mood_scheduler


def _get_suggester() -> ScheduleSuggester:
    global _suggester
    if _suggester is None:
        _suggester = ScheduleSuggester(SuggestionConfig())
    return _suggester


def _get_integration() -> CalendarIntegration:
    global _integration
    if _integration is None:
        _integration = CalendarIntegration()
    return _integration


def _get_ha_headers() -> tuple[str, dict]:
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    return ha_url, headers


# =============================================================================
# Basic Calendar Endpoints
# =============================================================================

@calendar_bp.route("", methods=["GET"])
@require_token
def list_calendars():
    """List all HA calendar entities."""
    integration = _get_integration()
    calendars = integration.list_calendar_entities()
    return jsonify({"calendars": calendars, "count": len(calendars)})


@calendar_bp.route("/events/today", methods=["GET"])
@require_token
def events_today():
    """Get all calendar events for today."""
    integration = _get_integration()
    events = integration.get_events_today()
    return jsonify({"events": events, "count": len(events)})


@calendar_bp.route("/events/upcoming", methods=["GET"])
@require_token
def events_upcoming():
    """Get upcoming events for the next N days (default 7)."""
    days = min(int(request.args.get("days", 7)), 30)
    integration = _get_integration()
    events = integration.get_upcoming_events(days=days)
    return jsonify({"events": events, "count": len(events), "days": days})


@calendar_bp.route("/events/range", methods=["GET"])
@require_token
def events_range():
    """Get events for a specific date range."""
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "start and end parameters required"}), 400
    
    integration = _get_integration()
    events = integration.get_events_in_range(start, end)
    return jsonify({"events": events, "count": len(events)})


# =============================================================================
# Smart Scheduling Endpoints
# =============================================================================

@calendar_bp.route("/smart/recommend", methods=["POST"])
@require_token
def smart_recommend():
    """Get smart time slot recommendation."""
    data = request.get_json() or {}
    duration = data.get("duration_minutes", 60)
    event_type = data.get("event_type", "task")
    priority = data.get("priority", "medium")
    look_ahead = data.get("look_ahead_days", 3)
    
    scheduler = _get_scheduler()
    recommendation = scheduler.recommend_slot(
        duration_minutes=duration,
        event_type=event_type,
        priority=priority,
        look_ahead_days=look_ahead,
    )
    
    return jsonify({
        "recommended_start": recommendation.recommended_start.isoformat() if recommendation.recommended_start else None,
        "recommended_end": recommendation.recommended_end.isoformat() if recommendation.recommended_end else None,
        "confidence": recommendation.confidence,
        "reasons": recommendation.reasons,
        "alternatives": [
            {
                "start": alt.start.isoformat() if alt.start else None,
                "end": alt.end.isoformat() if alt.end else None,
                "confidence": alt.confidence,
            }
            for alt in recommendation.alternatives
        ],
    })


@calendar_bp.route("/smart/day-summary", methods=["GET"])
@require_token
def smart_day_summary():
    """Get day summary with calendar density analysis."""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    scheduler = _get_scheduler()
    summary = scheduler.get_day_summary(date_str)
    
    return jsonify({
        "date": summary.date,
        "total_events": summary.total_events,
        "meeting_hours": summary.meeting_hours,
        "free_hours": summary.free_hours,
        "density_score": summary.density_score,
        "focus_blocks": [
            {"start": b.start.isoformat(), "end": b.end.isoformat(), "duration_minutes": b.duration_minutes}
            for b in summary.focus_blocks
        ],
        "break_recommendations": [
            {"start": b.start.isoformat(), "duration_minutes": b.duration_minutes}
            for b in summary.break_recommendations
        ],
        "warnings": summary.warnings,
    })


@calendar_bp.route("/smart/alarm-suggestion", methods=["GET"])
@require_token
def smart_alarm_suggestion():
    """Get alarm adjustment suggestion based on tomorrow's schedule."""
    scheduler = _get_scheduler()
    suggestion = scheduler.get_alarm_suggestion()
    
    return jsonify({
        "current_alarm": suggestion.current_alarm.isoformat() if suggestion.current_alarm else None,
        "suggested_alarm": suggestion.suggested_alarm.isoformat() if suggestion.suggested_alarm else None,
        "reason": suggestion.reason,
        "confidence": suggestion.confidence,
        "first_meeting": suggestion.first_meeting.isoformat() if suggestion.first_meeting else None,
    })


# =============================================================================
# Mood-Aware Scheduling Endpoints
# =============================================================================

@calendar_bp.route("/mood/recommend", methods=["POST"])
@require_token
def mood_recommend():
    """Get mood-aware time slot recommendation."""
    data = request.get_json() or {}
    duration = data.get("duration_minutes", 60)
    event_type = data.get("event_type", "task")
    
    mood_scheduler = _get_mood_scheduler()
    recommendation = mood_scheduler.recommend_with_mood(
        duration_minutes=duration,
        event_type=event_type,
    )
    
    return jsonify({
        "recommended_start": recommendation.recommended_start.isoformat() if recommendation.recommended_start else None,
        "recommended_end": recommendation.recommended_end.isoformat() if recommendation.recommended_end else None,
        "confidence": recommendation.confidence,
        "mood_factors": recommendation.mood_factors,
        "reasons": recommendation.reasons,
    })


@calendar_bp.route("/mood/summary", methods=["GET"])
@require_token
def mood_summary():
    """Get calendar summary with mood insights."""
    mood_scheduler = _get_mood_scheduler()
    summary = mood_scheduler.get_mood_summary()
    
    return jsonify({
        "current_mood": summary.current_mood,
        "stress_index": summary.stress_index,
        "energy_level": summary.energy_level,
        "calendar_density": summary.calendar_density,
        "recommendations": summary.recommendations,
        "optimal_focus_windows": [
            {"start": w.start.isoformat(), "end": w.end.isoformat()}
            for w in summary.optimal_focus_windows
        ],
        "avoid_windows": [
            {"start": w.start.isoformat(), "end": w.end.isoformat(), "reason": w.reason}
            for w in summary.avoid_windows
        ],
    })


@calendar_bp.route("/mood/adjust-event", methods=["POST"])
@require_token
def mood_adjust_event():
    """Adjust event timing based on current mood state."""
    data = request.get_json() or {}
    event_id = data.get("event_id")
    if not event_id:
        return jsonify({"error": "event_id required"}), 400
    
    mood_scheduler = _get_mood_scheduler()
    adjustment = mood_scheduler.adjust_event_for_mood(event_id)
    
    return jsonify({
        "original_time": adjustment.original_time.isoformat() if adjustment.original_time else None,
        "adjusted_time": adjustment.adjusted_time.isoformat() if adjustment.adjusted_time else None,
        "reason": adjustment.reason,
        "mood_impact": adjustment.mood_impact,
    })


@calendar_bp.route("/mood/lighting-automation", methods=["POST"])
@require_token
def mood_lighting_automation():
    """Create lighting automation based on event mood context."""
    data = request.get_json() or {}
    event_id = data.get("event_id")
    if not event_id:
        return jsonify({"error": "event_id required"}), 400
    
    mood_scheduler = _get_mood_scheduler()
    automation = mood_scheduler.create_lighting_automation(event_id)
    
    return jsonify({
        "automation_id": automation.automation_id,
        "scene": automation.scene,
        "brightness": automation.brightness,
        "color_temp": automation.color_temp,
        "trigger": automation.trigger,
        "entity_id": automation.entity_id,
    })


# =============================================================================
# Suggestions Endpoints
# =============================================================================

@calendar_bp.route("/suggestions", methods=["GET"])
@require_token
def get_suggestions():
    """Get all proactive calendar suggestions."""
    look_ahead = int(request.args.get("look_ahead_hours", 24))
    suggester = _get_suggester()
    suggestions = suggester.get_all_suggestions(look_ahead_hours=look_ahead)
    
    return jsonify({
        "suggestions": [
            {
                "id": s.id,
                "type": s.type,
                "priority": s.priority.value,
                "title": s.title,
                "message": s.message,
                "trigger": s.trigger,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in suggestions
        ],
        "count": len(suggestions),
    })


@calendar_bp.route("/suggestions/<suggestion_id>/accept", methods=["POST"])
@require_token
def accept_suggestion(suggestion_id):
    """Accept a proactive suggestion."""
    suggester = _get_suggester()
    action = suggester.accept_suggestion(suggestion_id)
    
    return jsonify({
        "suggestion_id": suggestion_id,
        "action": action.get("action"),
        "details": action.get("details"),
        "status": "accepted",
    })


@calendar_bp.route("/suggestions/<suggestion_id>/dismiss", methods=["POST"])
@require_token
def dismiss_suggestion(suggestion_id):
    """Dismiss a proactive suggestion."""
    suggester = _get_suggester()
    suggester.dismiss_suggestion(suggestion_id)
    
    return jsonify({
        "suggestion_id": suggestion_id,
        "status": "dismissed",
    })


# =============================================================================
# Context for LLM
# =============================================================================

@calendar_bp.route("/context", methods=["GET"])
@require_token
def get_context():
    """Get calendar context for LLM system prompt injection."""
    integration = _get_integration()
    context = integration.get_calendar_context_for_llm()
    
    return jsonify({
        "context": context,
        "generated_at": datetime.now().isoformat(),
    })
