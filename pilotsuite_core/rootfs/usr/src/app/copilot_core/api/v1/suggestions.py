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

# In-memory state for offline fallback mode (without engine)
_suggestion_states: Dict[str, str] = {}
_states_lock = threading.Lock()


def init_suggestions_api(suggestion_engine=None) -> None:
    """Wire the suggestion engine into the blueprint."""
    global _suggestion_engine
    _suggestion_engine = suggestion_engine
    with _states_lock:
        _suggestion_states.clear()
    _LOGGER.info("Suggestions API initialized")


def _json_error(message: str, status: int) -> tuple[Any, int]:
    return jsonify({"ok": False, "error": message}), status


def _require_json_object() -> dict[str, Any] | tuple[Any, int]:
    data = request.get_json(silent=True)
    if data is None:
        return _json_error("No JSON body provided", 400)
    if not isinstance(data, dict):
        return _json_error("JSON body must be an object", 400)
    return data


def _require_suggestion_id(data: dict[str, Any]) -> str | tuple[Any, int]:
    suggestion_id = data.get("id")
    if not isinstance(suggestion_id, str) or not suggestion_id.strip():
        return _json_error("'id' must be a non-empty string", 400)
    return suggestion_id.strip()


def _parse_snooze_minutes(data: dict[str, Any]) -> int | tuple[Any, int]:
    minutes = data.get("minutes", 15)
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        return _json_error("minutes must be a positive integer", 400)
    return minutes


def _accept_with_engine(suggestion_id: str) -> tuple[dict[str, Any], int] | None:
    engine = _suggestion_engine
    if not engine:
        return None

    # Preferred path: proposal-aware lifecycle
    if hasattr(engine, "propose_suggestion"):
        proposal = engine.propose_suggestion(suggestion_id)
        if proposal is None:
            return {"ok": False, "error": "Suggestion not found"}, 404
        return {
            "ok": True,
            "id": suggestion_id,
            "status": "accepted",
            "proposal_id": proposal["proposal_id"],
            "proposal": proposal,
        }, 200

    # Backward-compatible path
    if hasattr(engine, "accept_suggestion"):
        data = engine.accept_suggestion(suggestion_id)
        if data is None:
            return {"ok": False, "error": "Suggestion not found"}, 404
        return {"ok": True, "id": suggestion_id, "status": "accepted", "suggestion": data}, 200

    return {"ok": False, "error": "Engine has no accept method"}, 500


def _reject_with_engine(suggestion_id: str) -> tuple[dict[str, Any], int] | None:
    engine = _suggestion_engine
    if not engine:
        return None

    if hasattr(engine, "dismiss_suggestion"):
        rejected = engine.dismiss_suggestion(suggestion_id)
    elif hasattr(engine, "reject_suggestion"):
        rejected = engine.reject_suggestion(suggestion_id)
    else:
        rejected = None

    if rejected is None:
        return {"ok": False, "error": "Suggestion not found"}, 404
    return {"ok": True, "id": suggestion_id, "status": "rejected"}, 200


def _snooze_with_engine(suggestion_id: str, minutes: int) -> tuple[dict[str, Any], int] | None:
    engine = _suggestion_engine
    if not engine:
        return None

    if hasattr(engine, "snooze_suggestion"):
        snoozed = engine.snooze_suggestion(suggestion_id, minutes=minutes)
    else:
        snoozed = None

    if snoozed is None:
        return {"ok": False, "error": "Suggestion not found"}, 404
    return {"ok": True, "id": suggestion_id, "status": "snoozed", "minutes": minutes}, 200


def _list_with_engine() -> List[Dict[str, Any]]:
    if _suggestion_engine is None:
        return []

    pending_error: Exception | None = None

    # Primary path: explicit pending helper used by older clients
    if hasattr(_suggestion_engine, "get_pending"):
        try:
            return list(_suggestion_engine.get_pending(limit=20))
        except Exception as exc:
            pending_error = exc

    # Backward compatibility: filter suggestions manually from get_suggestions
    if hasattr(_suggestion_engine, "get_suggestions"):
        try:
            suggestions = _suggestion_engine.get_suggestions(
                include_dismissed=False,
                include_accepted=False,
            )
            return suggestions
        except Exception:
            if pending_error is not None:
                raise pending_error
            raise

    if pending_error is not None:
        raise pending_error

    return []


@suggestions_bp.route("", methods=["GET"])
def list_suggestions():
    """List pending suggestions."""
    if _suggestion_engine:
        try:
            pending = _list_with_engine()
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
    """Accept a suggestion and create the corresponding proposal."""
    data = _require_json_object()
    if not isinstance(data, dict):
        return data

    suggestion_id = _require_suggestion_id(data)
    if not isinstance(suggestion_id, str):
        return suggestion_id

    if _suggestion_engine:
        try:
            result = _accept_with_engine(suggestion_id)
        except Exception as exc:
            _LOGGER.exception("Failed to accept suggestion")
            return _json_error(str(exc), 500)
        if result is None:
            return _json_error("Engine has no accept path", 500)
        payload, status = result
        return jsonify(payload), status

    with _states_lock:
        _suggestion_states[suggestion_id] = "accepted"
    return jsonify({"ok": True, "id": suggestion_id, "status": "accepted"})


@suggestions_bp.route("/reject", methods=["POST"])
@require_token
def reject_suggestion():
    """Reject a suggestion permanently."""
    data = _require_json_object()
    if not isinstance(data, dict):
        return data

    suggestion_id = _require_suggestion_id(data)
    if not isinstance(suggestion_id, str):
        return suggestion_id

    if _suggestion_engine:
        try:
            result = _reject_with_engine(suggestion_id)
        except Exception as exc:
            _LOGGER.exception("Failed to reject suggestion")
            return _json_error(str(exc), 500)
        if result is None:
            return _json_error("Engine has no reject path", 500)
        payload, status = result
        return jsonify(payload), status

    with _states_lock:
        _suggestion_states[suggestion_id] = "rejected"
    return jsonify({"ok": True, "id": suggestion_id, "status": "rejected"})


@suggestions_bp.route("/snooze", methods=["POST"])
@require_token
def snooze_suggestion():
    """Snooze a suggestion (show again later)."""
    data = _require_json_object()
    if not isinstance(data, dict):
        return data

    suggestion_id = _require_suggestion_id(data)
    if not isinstance(suggestion_id, str):
        return suggestion_id

    minutes = _parse_snooze_minutes(data)
    if not isinstance(minutes, int):
        return minutes

    if _suggestion_engine:
        try:
            result = _snooze_with_engine(suggestion_id, minutes)
        except Exception as exc:
            _LOGGER.exception("Failed to snooze suggestion")
            return _json_error(str(exc), 500)
        if result is None:
            return _json_error("Engine has no snooze path", 500)
        payload, status = result
        return jsonify(payload), status

    with _states_lock:
        _suggestion_states[suggestion_id] = "snoozed"
    return jsonify({"ok": True, "id": suggestion_id, "status": "snoozed", "minutes": minutes})


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
