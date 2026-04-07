"""
REST API for Waste Collection + Birthday Reminders (v3.2.0).

Endpoints:
  POST /api/v1/waste/event        -- Receive waste event from HACS integration
  POST /api/v1/waste/collections  -- Update full waste collection schedule
  GET  /api/v1/waste/status       -- Get current waste status
  POST /api/v1/waste/remind       -- Trigger immediate waste reminder (TTS + notification)
  POST /api/v1/birthday/update    -- Update birthday list from HACS integration
  GET  /api/v1/birthday/status    -- Get current birthday status
  POST /api/v1/birthday/remind    -- Trigger immediate birthday reminder
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

reminders_bp = Blueprint("reminders", __name__, url_prefix="/api/v1")

# Module-level references (set via init_reminders_api)
_waste_service = None
_birthday_service = None


def init_reminders_api(waste_service=None, birthday_service=None):
    """Set service instances for the reminders API."""
    global _waste_service, _birthday_service
    _waste_service = waste_service
    _birthday_service = birthday_service
    _LOGGER.info(
        "Reminders API initialized (waste=%s, birthday=%s)",
        waste_service is not None,
        birthday_service is not None,
    )


def _service_unavailable(service_name: str):
    return jsonify({"ok": False, "error": f"{service_name} not available"}), 503


def _bad_request(message: str):
    return jsonify({"ok": False, "error": message}), 400


def _json_error(message: str, status_code: int = 500):
    return jsonify({"ok": False, "error": message}), status_code


def _read_json_object(*, allow_empty: bool) -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
    data = request.get_json(silent=True)
    if data is None:
        if allow_empty:
            return {}, None
        return None, _bad_request("No JSON body provided")
    if not isinstance(data, dict):
        return None, _bad_request("JSON body must be an object")
    return data, None


def _run_service_call(label: str, fn: Callable[[], Any]):
    try:
        return jsonify(fn())
    except Exception as exc:  # pragma: no cover - exercised via contract tests
        _LOGGER.exception("%s failed", label)
        return _json_error(str(exc))


# ------------------------------------------------------------------
# Waste Collection Endpoints
# ------------------------------------------------------------------

@reminders_bp.route("/waste/event", methods=["POST"])
@require_token
def waste_event():
    """Receive a waste event from the HACS integration."""
    if not _waste_service:
        return _service_unavailable("WasteCollectionService")
    data, error = _read_json_object(allow_empty=False)
    if error:
        return error
    return _run_service_call("waste_event", lambda: _waste_service.update_from_ha(data))


@reminders_bp.route("/waste/collections", methods=["POST"])
@require_token
def waste_collections_update():
    """Update full waste collection schedule."""
    if not _waste_service:
        return _service_unavailable("WasteCollectionService")
    data, error = _read_json_object(allow_empty=False)
    if error:
        return error
    collections = data.get("collections", [])
    if not isinstance(collections, list):
        return _bad_request("collections must be a list")
    return _run_service_call("waste_collections_update", lambda: _waste_service.update_collections(collections))


@reminders_bp.route("/waste/status", methods=["GET"])
@require_token
def waste_status():
    """Get current waste collection status."""
    if not _waste_service:
        return _service_unavailable("WasteCollectionService")
    return _run_service_call("waste_status", _waste_service.get_status)


@reminders_bp.route("/waste/remind", methods=["POST"])
@require_token
def waste_remind():
    """Trigger an immediate waste reminder."""
    if not _waste_service:
        return _service_unavailable("WasteCollectionService")
    data, error = _read_json_object(allow_empty=True)
    if error:
        return error
    message = data.get("message", "")
    tts_entity = data.get("tts_entity", "")
    if not isinstance(message, str):
        return _bad_request("message must be a string")
    if not isinstance(tts_entity, str):
        return _bad_request("tts_entity must be a string")
    if not message:
        try:
            status = _waste_service.get_status()
        except Exception as exc:  # pragma: no cover - exercised via contract tests
            _LOGGER.exception("waste_remind status lookup failed")
            return _json_error(str(exc))
        today = status.get("today", [])
        tomorrow = status.get("tomorrow", [])
        if today:
            message = f"Heute wird abgeholt: {', '.join(today)}."
        elif tomorrow:
            message = f"Morgen wird abgeholt: {', '.join(tomorrow)}. Bitte Tonnen rausstellen!"
        else:
            return jsonify({"ok": True, "message": "Keine Abfuhr in Sicht."})
    return _run_service_call("waste_remind", lambda: _waste_service.deliver_reminder(message, tts_entity))


# ------------------------------------------------------------------
# Birthday Endpoints
# ------------------------------------------------------------------

@reminders_bp.route("/birthday/update", methods=["POST"])
@require_token
def birthday_update():
    """Update birthday list from HACS integration."""
    if not _birthday_service:
        return _service_unavailable("BirthdayService")
    data, error = _read_json_object(allow_empty=False)
    if error:
        return error
    birthdays = data.get("birthdays", [])
    if not isinstance(birthdays, list):
        return _bad_request("birthdays must be a list")
    return _run_service_call("birthday_update", lambda: _birthday_service.update_birthdays(birthdays))


@reminders_bp.route("/birthday/status", methods=["GET"])
@require_token
def birthday_status():
    """Get current birthday status."""
    if not _birthday_service:
        return _service_unavailable("BirthdayService")
    return _run_service_call("birthday_status", _birthday_service.get_status)


@reminders_bp.route("/birthday/remind", methods=["POST"])
@require_token
def birthday_remind():
    """Trigger an immediate birthday reminder."""
    if not _birthday_service:
        return _service_unavailable("BirthdayService")
    data, error = _read_json_object(allow_empty=True)
    if error:
        return error
    message = data.get("message", "")
    tts_entity = data.get("tts_entity", "")
    if not isinstance(message, str):
        return _bad_request("message must be a string")
    if not isinstance(tts_entity, str):
        return _bad_request("tts_entity must be a string")
    if not message:
        try:
            status = _birthday_service.get_status()
        except Exception as exc:  # pragma: no cover - exercised via contract tests
            _LOGGER.exception("birthday_remind status lookup failed")
            return _json_error(str(exc))
        today = status.get("today", [])
        if today:
            names = [b.get("name", "?") for b in today]
            message = f"Heute hat Geburtstag: {', '.join(names)}. Herzlichen Glückwunsch!"
        else:
            return jsonify({"ok": True, "message": "Keine Geburtstage heute."})
    return _run_service_call("birthday_remind", lambda: _birthday_service.deliver_reminder(message, tts_entity))


# ── SLICE 141: Reminders Expansion ─────────────────────────────────

@reminders_bp.get("/suggestions")
def reminder_suggestions():
    """Get smart reminder suggestions based on patterns.
    
    Returns reminders the system suggests based on:
    - Historical patterns
    - Calendar events
    - Location context
    - Time-based habits
    
    Query params:
    - limit: Max suggestions (default 5)
    """
    from copilot_core.reminders.engine import get_reminders_engine
    
    try:
        limit = int(request.args.get("limit", "5"))
    except (ValueError, TypeError):
        limit = 5
    
    limit = max(1, min(limit, 20))
    
    try:
        engine = get_reminders_engine()
        suggestions = engine.get_smart_suggestions(limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get reminder suggestions: %s", e)
        suggestions = []
    
    return jsonify({
        "ok": True,
        "suggestions": suggestions,
        "count": len(suggestions),
        "limit": limit
    })


@reminders_bp.get("/recurring")
def recurring_reminders():
    """Get all recurring reminders.
    
    Query params:
    - pattern: daily|weekly|monthly|yearly (optional, all if omitted)
    - active_only: true|false (default: true)
    """
    from copilot_core.reminders.engine import get_reminders_engine
    
    pattern = request.args.get("pattern")
    
    active_only = request.args.get("active_only", "true").lower() == "true"
    
    try:
        engine = get_reminders_engine()
        recurring = engine.get_recurring_reminders(pattern=pattern, active_only=active_only)
    except Exception as e:
        _LOGGER.warning("Failed to get recurring reminders: %s", e)
        recurring = []
    
    return jsonify({
        "ok": True,
        "recurring": recurring,
        "count": len(recurring),
        "pattern": pattern,
        "active_only": active_only
    })


@reminders_bp.get("/completion/analytics")
def reminder_completion_analytics():
    """Get reminder completion analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.reminders.engine import get_reminders_engine
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        engine = get_reminders_engine()
        analytics = engine.get_completion_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get completion analytics: %s", e)
        analytics = {
            "total_reminders": 0,
            "completed": 0,
            "missed": 0,
            "completion_rate": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
