"""
Suggestions API — Accept, reject, or snooze automation suggestions.

Blueprint prefix: /api/v1/suggestions

Endpoints:
    GET  /api/v1/suggestions           — List pending suggestions
    GET  /api/v1/suggestions/repairs   — List repair/improvement suggestions
    POST /api/v1/suggestions/accept   — Accept a suggestion
    POST /api/v1/suggestions/reject   — Reject a suggestion
    POST /api/v1/suggestions/snooze   — Snooze a suggestion
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

suggestions_bp = Blueprint(
    "suggestions", __name__, url_prefix="/api/v1/suggestions"
)

# Module-level service reference, set by init_suggestions_api()
_suggestion_engine: Optional[Any] = None

# In-memory store for suggestion states (fallback when no engine is available)
_suggestion_states: Dict[str, str] = {}
_states_lock = threading.Lock()


def init_suggestions_api(suggestion_engine=None) -> None:
    """Wire the suggestion engine into the blueprint."""
    global _suggestion_engine
    _suggestion_engine = suggestion_engine
    _LOGGER.info("Suggestions API initialized")


@suggestions_bp.route("", methods=["GET"])
def list_suggestions():
    """List pending suggestions."""
    if _suggestion_engine:
        try:
            pending = _suggestion_engine.get_pending(limit=20)
            return jsonify({"ok": True, "suggestions": pending})
        except Exception as exc:
            _LOGGER.exception("Failed to get pending suggestions")
            return jsonify({"ok": False, "error": str(exc)}), 500

    # Fallback: return example suggestions excluding rejected/accepted
    try:
        from copilot_core.example_config import EXAMPLE_SUGGESTIONS
        with _states_lock:
            filtered = [
                s for s in EXAMPLE_SUGGESTIONS
                if _suggestion_states.get(s["id"]) not in ("accepted", "rejected")
            ]
        return jsonify({"ok": True, "suggestions": filtered})
    except (ImportError, AttributeError):
        return jsonify({"ok": True, "suggestions": []})
    except Exception as exc:
        _LOGGER.warning("Unexpected error listing fallback suggestions: %s", exc)
        return jsonify({"ok": True, "suggestions": []})


@suggestions_bp.route("/accept", methods=["POST"])
@require_token
def accept_suggestion():
    """Accept a suggestion and create the corresponding automation."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.accept(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "accepted"})
        except Exception as exc:
            _LOGGER.exception("Failed to accept suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    with _states_lock:
        _suggestion_states[suggestion_id] = "accepted"
    return jsonify({"ok": True, "id": suggestion_id, "status": "accepted"})


@suggestions_bp.route("/reject", methods=["POST"])
@require_token
def reject_suggestion():
    """Reject a suggestion permanently."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.reject(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "rejected"})
        except Exception as exc:
            _LOGGER.exception("Failed to reject suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    with _states_lock:
        _suggestion_states[suggestion_id] = "rejected"
    return jsonify({"ok": True, "id": suggestion_id, "status": "rejected"})


@suggestions_bp.route("/snooze", methods=["POST"])
@require_token
def snooze_suggestion():
    """Snooze a suggestion (show again later)."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.snooze(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "snoozed"})
        except Exception as exc:
            _LOGGER.exception("Failed to snooze suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    with _states_lock:
        _suggestion_states[suggestion_id] = "snoozed"
    return jsonify({"ok": True, "id": suggestion_id, "status": "snoozed"})


# --- Automation Repair & Improvement Suggestions ---

# Built-in repair/improvement suggestions for common automation issues
_BUILTIN_REPAIR_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "repair_missing_mode",
        "title": "Fehlender Automation-Modus",
        "category": "repair",
        "confidence": 0.95,
        "description": "Automationen ohne 'mode' (single/restart/queued/parallel) koennen "
                       "unerwartete Mehrfach-Ausfuehrungen verursachen. "
                       "Empfehlung: mode: single oder mode: restart hinzufuegen.",
        "severity": "medium",
        "estimated_savings_eur": 0,
        "fix_type": "add_mode_field",
    },
    {
        "id": "repair_missing_from_state",
        "title": "Fehlender from-State bei Trigger",
        "category": "repair",
        "confidence": 0.9,
        "description": "State-Trigger ohne 'from' koennen bei HA-Restart oder Entity-Reload "
                       "faelschlicherweise ausloesen. Empfehlung: from-State angeben.",
        "severity": "medium",
        "estimated_savings_eur": 0,
        "fix_type": "add_from_state",
    },
    {
        "id": "repair_missing_condition",
        "title": "Automation ohne Condition",
        "category": "repair",
        "confidence": 0.85,
        "description": "Automationen ohne Bedingungen fuehren bei jedem Trigger aus. "
                       "Empfehlung: Zustandspruefung (z.B. is_state) vor Aktionen hinzufuegen.",
        "severity": "low",
        "estimated_savings_eur": 0,
        "fix_type": "add_condition",
    },
    {
        "id": "improvement_auto_off_timer",
        "title": "Auto-Aus Timer fuer Geraete",
        "category": "energy",
        "confidence": 0.88,
        "description": "Geraete wie Kaffeemaschinen, Heizluefter und Buegeleisen sollten "
                       "einen Auto-Aus Timer haben (z.B. 30 Min). Spart Energie und erhoeht Sicherheit.",
        "severity": "low",
        "estimated_savings_eur": 15.0,
        "fix_type": "add_auto_off_timer",
    },
    {
        "id": "improvement_presence_light_off",
        "title": "Licht bei Abwesenheit ausschalten",
        "category": "energy",
        "confidence": 0.92,
        "description": "Licht-Automationen sollten einen Abwesenheits-Trigger haben, "
                       "der nach 5-10 Minuten ohne Praesenz das Licht ausschaltet.",
        "severity": "medium",
        "estimated_savings_eur": 25.0,
        "fix_type": "add_presence_off",
    },
    {
        "id": "improvement_cross_dependency_sync",
        "title": "Cross-Dependency Synchronisation",
        "category": "optimization",
        "confidence": 0.8,
        "description": "Gekoppelte Geraete (z.B. Kaffeemaschine + Muehle) sollten "
                       "bidirektional synchronisiert werden, um Inkonsistenzen zu vermeiden.",
        "severity": "low",
        "estimated_savings_eur": 0,
        "fix_type": "add_bidirectional_sync",
    },
]


@suggestions_bp.route("/repairs", methods=["GET"])
def list_repair_suggestions():
    """List automation repair and improvement suggestions.

    Returns built-in repair suggestions that can be applied to existing automations.
    These are generated from static analysis of common automation anti-patterns.
    """
    with _states_lock:
        filtered = [
            s for s in _BUILTIN_REPAIR_SUGGESTIONS
            if _suggestion_states.get(s["id"]) not in ("accepted", "rejected")
        ]

    # Combine with engine suggestions if available
    engine_repairs: List[Dict[str, Any]] = []
    if _suggestion_engine and hasattr(_suggestion_engine, "get_repair_suggestions"):
        try:
            engine_repairs = _suggestion_engine.get_repair_suggestions(limit=10)
        except Exception as exc:
            _LOGGER.warning("Failed to get engine repair suggestions: %s", exc)

    all_repairs = engine_repairs + filtered
    count = len(all_repairs)
    total_savings = sum(s.get("estimated_savings_eur", 0) for s in all_repairs)

    return jsonify({
        "ok": True,
        "count": count,
        "suggestions": all_repairs,
        "total_potential_savings_eur": round(total_savings, 2),
        "categories": {
            "repair": sum(1 for s in all_repairs if s.get("category") == "repair"),
            "energy": sum(1 for s in all_repairs if s.get("category") == "energy"),
            "optimization": sum(1 for s in all_repairs if s.get("category") == "optimization"),
        },
    })
