"""Habitus API — Endpoints für Life-Long-Learning System.

Endpoints:
- GET  /api/v1/habitus — Overview + Stats
- GET  /api/v1/habitus/patterns — Alle Patterns (filterbar)
- POST /api/v1/habitus/patterns — Neues Pattern speichern
- PUT  /api/v1/habitus/patterns/<id> — Pattern updaten
- DELETE /api/v1/habitus/patterns/<id> — Pattern löschen
- POST /api/v1/habitus/feedback — Feedback geben
- GET  /api/v1/habitus/feedback — Feedback-History
- GET  /api/v1/habitus/preferences — Nutzer-Präferenzen
- PUT  /api/v1/habitus/preferences — Präferenz speichern
- GET  /api/v1/habitus/routines — Nutzer-Routinen
- PUT  /api/v1/habitus/routines — Routine speichern
- GET  /api/v1/habitus/context — Context-History
- POST /api/v1/habitus/context — Context speichern
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
from datetime import datetime, timezone
import uuid

from copilot_core.habitus.habitus_storage import (
    get_habitus_storage,
    Pattern,
    PatternState,
    UserPreference,
    UserRoutine,
    UserFeedback,
    FeedbackType,
    ContextHistory,
)

_LOGGER = logging.getLogger(__name__)

habitus_bp = Blueprint("habitus", __name__, url_prefix="/api/v1/habitus")


# =============================================================================
# Overview
# =============================================================================

@habitus_bp.route("", methods=["GET"])
def get_habitus_overview():
    """Habitus Overview — Stats + Summary."""
    storage = get_habitus_storage()
    stats = storage.get_stats()
    
    return jsonify({
        "status": "healthy",
        "stats": stats,
        "learning_summary": {
            "patterns_learned": stats.get("patterns_total", 0),
            "active_patterns": stats.get("patterns_by_state", {}).get("active", 0),
            "preferences_learned": stats.get("preferences_total", 0),
            "routines_learned": stats.get("routines_total", 0),
            "feedback_received": sum(stats.get("feedback_by_type", {}).values()),
        },
    })


# =============================================================================
# Patterns
# =============================================================================

@habitus_bp.route("/patterns", methods=["GET"])
def get_patterns():
    """Patterns laden (filterbar)."""
    storage = get_habitus_storage()
    
    zone = request.args.get("zone")
    state = request.args.get("state")
    min_confidence = request.args.get("min_confidence", "0.0", type=float)
    
    patterns = storage.get_patterns(
        zone=zone,
        state=PatternState(state) if state else None,
        min_confidence=min_confidence,
    )
    
    return jsonify({
        "total": len(patterns),
        "patterns": [p.to_dict() for p in patterns],
    })


@habitus_bp.route("/patterns/<pattern_id>", methods=["GET"])
def get_pattern(pattern_id: str):
    """Einzelnes Pattern laden."""
    storage = get_habitus_storage()
    pattern = storage.get_pattern(pattern_id)
    
    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404
    
    return jsonify(pattern.to_dict())


@habitus_bp.route("/patterns", methods=["POST"])
def save_pattern():
    """Neues Pattern speichern."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Pattern aus Request-Daten erstellen
    pattern = Pattern(
        id=data.get("id", f"p_{uuid.uuid4().hex[:8]}"),
        description=data.get("description", ""),
        trigger=data.get("trigger", {}),
        action=data.get("action", {}),
        confidence=data.get("confidence", 0.0),
        support=data.get("support", 0),
        acceptances=data.get("acceptances", 0),
        rejections=data.get("rejections", 0),
        ignores=data.get("ignores", 0),
        state=PatternState(data.get("state", "observing")),
        zones=data.get("zones", []),
        modules=data.get("modules", []),
        contexts=data.get("contexts", []),
    )
    
    storage = get_habitus_storage()
    storage.save_pattern(pattern)
    
    _LOGGER.info(f"Pattern saved: {pattern.id}")
    
    return jsonify({
        "success": True,
        "pattern_id": pattern.id,
    })


@habitus_bp.route("/patterns/<pattern_id>", methods=["PUT"])
def update_pattern(pattern_id: str):
    """Pattern updaten."""
    storage = get_habitus_storage()
    pattern = storage.get_pattern(pattern_id)
    
    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404
    
    data = request.get_json()
    
    # Update Felder
    if "description" in data:
        pattern.description = data["description"]
    if "trigger" in data:
        pattern.trigger = data["trigger"]
    if "action" in data:
        pattern.action = data["action"]
    if "confidence" in data:
        pattern.confidence = data["confidence"]
    if "state" in data:
        pattern.state = PatternState(data["state"])
    if "zones" in data:
        pattern.zones = data["zones"]
    if "modules" in data:
        pattern.modules = data["modules"]
    
    pattern.last_learned = datetime.now(timezone.utc).isoformat()
    
    storage.save_pattern(pattern)
    
    return jsonify({
        "success": True,
        "pattern_id": pattern_id,
    })


@habitus_bp.route("/patterns/<pattern_id>", methods=["DELETE"])
def delete_pattern(pattern_id: str):
    """Pattern löschen."""
    storage = get_habitus_storage()
    
    if not storage.delete_pattern(pattern_id):
        return jsonify({"error": "Pattern not found"}), 404
    
    return jsonify({
        "success": True,
        "pattern_id": pattern_id,
    })


# =============================================================================
# Feedback
# =============================================================================

@habitus_bp.route("/feedback", methods=["POST"])
def add_feedback():
    """Feedback vom Nutzer."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    feedback = UserFeedback(
        id=f"fb_{uuid.uuid4().hex[:8]}",
        pattern_id=data.get("pattern_id"),
        feedback_type=FeedbackType(data.get("feedback_type", "accepted")),
        zone=data.get("zone"),
        module=data.get("module"),
        action=data.get("action"),
        comment=data.get("comment"),
        correction=data.get("correction"),
    )
    
    storage = get_habitus_storage()
    storage.add_feedback(feedback)
    
    _LOGGER.info(f"Feedback received: {feedback.feedback_type.value} for {feedback.pattern_id}")
    
    return jsonify({
        "success": True,
        "feedback_id": feedback.id,
    })


@habitus_bp.route("/feedback", methods=["GET"])
def get_feedback():
    """Feedback-History laden."""
    storage = get_habitus_storage()
    
    pattern_id = request.args.get("pattern_id")
    feedback_type = request.args.get("feedback_type")
    limit = request.args.get("limit", "100", type=int)
    
    feedbacks = storage.get_feedback(
        pattern_id=pattern_id,
        feedback_type=FeedbackType(feedback_type) if feedback_type else None,
        limit=limit,
    )
    
    return jsonify({
        "total": len(feedbacks),
        "feedbacks": [f.to_dict() for f in feedbacks],
    })


# =============================================================================
# Preferences
# =============================================================================

@habitus_bp.route("/preferences", methods=["GET"])
def get_preferences():
    """Nutzer-Präferenzen laden."""
    storage = get_habitus_storage()
    
    category = request.args.get("category")
    zone = request.args.get("zone")
    
    preferences = storage.get_preferences(
        category=category,
        zone=zone,
    )
    
    return jsonify({
        "total": len(preferences),
        "preferences": [p.to_dict() for p in preferences],
    })


@habitus_bp.route("/preferences", methods=["PUT"])
def save_preference():
    """Nutzer-Präferenz speichern."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    pref = UserPreference(
        category=data.get("category", ""),
        key=data.get("key", ""),
        value=data.get("value"),
        zone=data.get("zone"),
        context=data.get("context"),
        confidence=data.get("confidence", 0.0),
        observations=data.get("observations", 0),
    )
    
    storage = get_habitus_storage()
    storage.save_preference(pref)
    
    return jsonify({
        "success": True,
        "category": pref.category,
        "key": pref.key,
    })


# =============================================================================
# Routines
# =============================================================================

@habitus_bp.route("/routines", methods=["GET"])
def get_routines():
    """Nutzer-Routinen laden."""
    storage = get_habitus_storage()
    routines = storage.get_routines()
    
    return jsonify({
        "total": len(routines),
        "routines": [r.to_dict() for r in routines],
    })


@habitus_bp.route("/routines", methods=["PUT"])
def save_routine():
    """Nutzer-Routine speichern."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    routine = UserRoutine(
        id=data.get("id", f"r_{uuid.uuid4().hex[:8]}"),
        name=data.get("name", ""),
        description=data.get("description", ""),
        time_pattern=data.get("time_pattern", {}),
        duration_minutes=data.get("duration_minutes", 30),
        actions=data.get("actions", []),
        zones=data.get("zones", []),
        confidence=data.get("confidence", 0.0),
        occurrences=data.get("occurrences", 0),
    )
    
    storage = get_habitus_storage()
    storage.save_routine(routine)
    
    return jsonify({
        "success": True,
        "routine_id": routine.id,
    })


# =============================================================================
# Context History
# =============================================================================

@habitus_bp.route("/context", methods=["POST"])
def add_context():
    """Kontext zur History hinzufügen."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    context = ContextHistory(
        timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        zone=data.get("zone", ""),
        modules=data.get("modules", []),
        entities=data.get("entities", {}),
        neurons=data.get("neurons"),
        mood=data.get("mood"),
        events=data.get("events", []),
    )
    
    storage = get_habitus_storage()
    storage.add_context(context)
    
    return jsonify({
        "success": True,
        "timestamp": context.timestamp,
    })


@habitus_bp.route("/context", methods=["GET"])
def get_context_history():
    """Context-History laden."""
    storage = get_habitus_storage()
    
    zone = request.args.get("zone")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    limit = request.args.get("limit", "1000", type=int)
    
    contexts = storage.get_context_history(
        zone=zone,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    
    return jsonify({
        "total": len(contexts),
        "contexts": [c.to_dict() for c in contexts],
    })
