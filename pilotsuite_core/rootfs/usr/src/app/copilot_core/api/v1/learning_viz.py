"""Learning Visualization API — Zeigt dem Nutzer was das System lernt.

Diese API ist KRITISCH für Vertrauen und Transparenz:
- Nutzer sieht GELERNTES (Patterns, Preferences, Routines)
- Nutzer sieht FEEDBACK-History
- Nutzer sieht LERN-FORTSCHRITT (Confidence, Acceptances)
- Nutzer kann KORRIGIEREN (manuelles Feedback)

Endpoints:
- GET /api/v1/learning/overview — Lern-Übersicht
- GET /api/v1/learning/patterns — Gelernte Patterns (visualisiert)
- GET /api/v1/learning/progress — Lern-Fortschritt pro Modul/Zone
- GET /api/v1/learning/feedback — Feedback-History (visualisiert)
- POST /api/v1/learning/correct — Manuelle Korrektur
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify
from typing import Any, Dict, List
from datetime import datetime, timezone

from copilot_core.habitus.habitus_storage import get_habitus_storage, PatternState

_LOGGER = logging.getLogger(__name__)

learning_viz_bp = Blueprint("learning_viz", __name__, url_prefix="/api/v1/learning")


@learning_viz_bp.route("/overview", methods=["GET"])
def get_learning_overview():
    """Lern-Übersicht — Was hat das System gelernt?"""
    storage = get_habitus_storage()
    stats = storage.get_stats()
    
    # Lern-Fortschritt berechnen
    total_patterns = stats.get("patterns_total", 0)
    active_patterns = stats.get("patterns_by_state", {}).get("active", 0)
    stable_patterns = stats.get("patterns_by_state", {}).get("stable", 0)
    
    total_feedback = sum(stats.get("feedback_by_type", {}).values())
    acceptances = stats.get("feedback_by_type", {}).get("accepted", 0)
    rejections = stats.get("feedback_by_type", {}).get("rejected", 0)
    
    acceptance_rate = (acceptances / total_feedback * 100) if total_feedback > 0 else 0
    
    return jsonify({
        "status": "healthy",
        "learning_summary": {
            "patterns": {
                "total": total_patterns,
                "active": active_patterns,
                "stable": stable_patterns,
                "observing": stats.get("patterns_by_state", {}).get("observing", 0),
                "learning": stats.get("patterns_by_state", {}).get("learning", 0),
            },
            "preferences": stats.get("preferences_total", 0),
            "routines": stats.get("routines_total", 0),
            "feedback": {
                "total": total_feedback,
                "acceptances": acceptances,
                "rejections": rejections,
                "acceptance_rate": round(acceptance_rate, 1),
            },
            "context_history": stats.get("context_history_total", 0),
        },
        "intelligence_score": _calculate_intelligence_score(stats),
    })


@learning_viz_bp.route("/patterns", methods=["GET"])
def get_patterns_visualized():
    """Gelernte Patterns — visualisiert für Nutzer."""
    storage = get_habitus_storage()
    
    zone = request.args.get("zone")
    state = request.args.get("state")
    
    patterns = storage.get_patterns(
        zone=zone,
        state=PatternState(state) if state else None,
        min_confidence=0.5,  # Nur relevante Patterns zeigen
    )
    
    # Für UI aufbereiten
    visualized = []
    for p in patterns:
        visualized.append({
            "id": p.id,
            "description": p.description,
            "trigger": _format_trigger(p.trigger),
            "action": _format_action(p.action),
            "confidence": round(p.confidence * 100, 1),
            "state": p.state.value,
            "acceptances": p.acceptances,
            "rejections": p.rejections,
            "zones": p.zones,
            "modules": p.modules,
            "last_triggered": p.last_triggered,
            "human_readable": _make_human_readable(p),
        })
    
    return jsonify({
        "total": len(visualized),
        "patterns": visualized,
    })


@learning_viz_bp.route("/progress", methods=["GET"])
def get_learning_progress():
    """Lern-Fortschritt pro Modul/Zone."""
    storage = get_habitus_storage()
    
    # Progress pro Zone
    zones_progress = {}
    for zone in ["living", "bath", "kitchen", "office", "bedroom", "hallway"]:
        patterns = storage.get_patterns(zone=zone)
        active = sum(1 for p in patterns if p.state == PatternState.ACTIVE)
        zones_progress[zone] = {
            "total_patterns": len(patterns),
            "active_patterns": active,
            "learning_progress": round(active / max(len(patterns), 1) * 100, 1),
        }
    
    # Progress pro Modul
    modules_progress = {}
    for module in ["light", "climate", "motion", "music", "energy"]:
        patterns = storage.get_patterns()
        module_patterns = [p for p in patterns if module in p.modules]
        active = sum(1 for p in module_patterns if p.state == PatternState.ACTIVE)
        modules_progress[module] = {
            "total_patterns": len(module_patterns),
            "active_patterns": active,
            "learning_progress": round(active / max(len(module_patterns), 1) * 100, 1),
        }
    
    return jsonify({
        "by_zone": zones_progress,
        "by_module": modules_progress,
    })


@learning_viz_bp.route("/feedback", methods=["GET"])
def get_feedback_visualized():
    """Feedback-History — visualisiert für Nutzer."""
    storage = get_habitus_storage()
    
    limit = request.args.get("limit", "50", type=int)
    feedbacks = storage.get_feedback(limit=limit)
    
    visualized = []
    for fb in feedbacks:
        visualized.append({
            "id": fb.id,
            "type": fb.feedback_type.value,
            "timestamp": fb.timestamp,
            "zone": fb.zone,
            "module": fb.module,
            "comment": fb.comment,
            "icon": _get_feedback_icon(fb.feedback_type.value),
            "color": _get_feedback_color(fb.feedback_type.value),
        })
    
    return jsonify({
        "total": len(visualized),
        "feedbacks": visualized,
    })


@learning_viz_bp.route("/correct", methods=["POST"])
def submit_correction():
    """Manuelle Korrektur vom Nutzer."""
    data = request.get_json()
    
    pattern_id = data.get("pattern_id")
    correction = data.get("correction")  # Was soll anders sein?
    comment = data.get("comment")
    
    storage = get_habitus_storage()
    
    # Feedback als "corrected" speichern
    from copilot_core.habitus.habitus_storage import UserFeedback, FeedbackType
    import uuid
    
    feedback = UserFeedback(
        id=f"fb_{uuid.uuid4().hex[:8]}",
        pattern_id=pattern_id,
        feedback_type=FeedbackType.CORRECTED,
        correction=correction,
        comment=comment,
    )
    
    storage.add_feedback(feedback)
    
    # Pattern-Confidence anpassen
    if pattern_id:
        pattern = storage.get_pattern(pattern_id)
        if pattern:
            pattern.confidence *= 0.8  # Confidence reduzieren bei Korrektur
            storage.save_pattern(pattern)
    
    return jsonify({
        "success": True,
        "message": "Korrektur gespeichert. System lernt daraus!",
    })


# =============================================================================
# Helpers
# =============================================================================

def _calculate_intelligence_score(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Intelligence Score berechnen (für UI)."""
    total_patterns = stats.get("patterns_total", 0)
    active_patterns = stats.get("patterns_by_state", {}).get("active", 0)
    
    total_feedback = sum(stats.get("feedback_by_type", {}).values())
    acceptances = stats.get("feedback_by_type", {}).get("accepted", 0)
    
    # Score: 0-100
    pattern_score = min(total_patterns * 2, 40)  # Max 40 Punkte
    active_score = min(active_patterns * 5, 30)  # Max 30 Punkte
    acceptance_score = min((acceptances / max(total_feedback, 1)) * 30, 30)  # Max 30 Punkte
    
    total_score = pattern_score + active_score + acceptance_score
    
    return {
        "total": round(total_score, 1),
        "max": 100,
        "breakdown": {
            "patterns_learned": round(pattern_score, 1),
            "active_automations": round(active_score, 1),
            "user_acceptance": round(acceptance_score, 1),
        },
        "level": _score_to_level(total_score),
    }


def _score_to_level(score: float) -> str:
    """Score in Level übersetzen."""
    if score >= 80:
        return "Expert"
    elif score >= 60:
        return "Advanced"
    elif score >= 40:
        return "Intermediate"
    elif score >= 20:
        return "Beginner"
    else:
        return "Novice"


def _format_trigger(trigger: Dict[str, Any]) -> str:
    """Trigger human-lesbar formatieren."""
    parts = []
    if "time" in trigger:
        parts.append(f"um {trigger['time']}")
    if "presence" in trigger and trigger["presence"]:
        parts.append("wenn Präsenz erkannt")
    if "zone" in trigger:
        parts.append(f"in {trigger['zone']}")
    return " ".join(parts) if parts else str(trigger)


def _format_action(action: Dict[str, Any]) -> str:
    """Action human-lesbar formatieren."""
    module = action.get("module", "unknown")
    command = action.get("command", "unknown")
    
    actions = {
        ("light", "turn_on"): "Licht einschalten",
        ("light", "turn_off"): "Licht ausschalten",
        ("climate", "set_temperature"): "Temperatur einstellen",
        ("music", "play"): "Musik starten",
        ("music", "stop"): "Musik stoppen",
    }
    
    return actions.get((module, command), f"{module}: {command}")


def _make_human_readable(pattern) -> str:
    """Pattern als natürlicher Satz."""
    trigger = _format_trigger(pattern.trigger)
    action = _format_action(pattern.action)
    return f"Wenn {trigger}, dann {action}."


def _get_feedback_icon(feedback_type: str) -> str:
    """Icon für Feedback-Typ."""
    icons = {
        "accepted": "✅",
        "rejected": "❌",
        "ignored": "⏭️",
        "corrected": "✏️",
    }
    return icons.get(feedback_type, "📝")


def _get_feedback_color(feedback_type: str) -> str:
    """Farbe für Feedback-Typ."""
    colors = {
        "accepted": "green",
        "rejected": "red",
        "ignored": "gray",
        "corrected": "orange",
    }
    return colors.get(feedback_type, "blue")
